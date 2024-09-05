from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import os
import httpx
import asyncio
import re 
from decimal import Decimal, InvalidOperation
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from items import models, schemas
from items.database import Base, SessionLocal, engine

load_dotenv()

    # TODOs:
        # call /items endpoint from /crawl endpoint DONE
        # protect endpoint DONE
        # migrations -> Alembic DONE
        # cronjob DONE
        # check for discounts DOING
            # find older that 24h DONE
            # migration for price DOING
            # check for discount
            # add a discrount price
            # remove a discount price
        # response = await client.post("http://localhost:8000/items" -> make it dynamic
        # docker
        # FE integration, how to notify people
        # check if url was already posted
        # sometimes returns EURO, sometimes €
        # currency and price being string, sometimes tho html, makes code ugly
        # unify price format, 165.00 or 165,00 and then what about big numbers?
        # refactoring idea: first check what website this is from, then scrape accordingly - create multiple scrapers   

app = FastAPI()

# DB Session Dependency

async def get_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        db = SessionLocal()
        try:
            yield db
        finally:
            await db.close()

# scheduler setup

scheduler = BackgroundScheduler()

def run_check_for_price_changes():
    asyncio.run(check_for_price_changes())

@app.on_event("startup")
async def start_scheduler():
    scheduler.add_job(run_check_for_price_changes, IntervalTrigger(seconds=2))
    scheduler.start()

@app.on_event("shutdown")
def shutdown_scheduler():
    scheduler.shutdown()

# classes

class UrlRequest(BaseModel):
    url: str

# constants

INTERNAL_TOKEN = os.getenv("SECRET_TOKEN_PROTECTED_ROUTE")

# helper functions

async def validate_url(url: str):  
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail=f"URL returned status code {response.status_code}")
            else:
                return response
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"URL validation failed: {e}")

def verify_internal_request(internal_authorization: str = Header(None)):
    if internal_authorization != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="Not authorized")

# we want no thousand separators and we want a dot as a decimal separator
def sanitize_price_string(price_str: str) -> float:
    #  Find the last occurrence of comma or dot, followed by exactly two digits
    match = re.search(r'[,.](\d{2})$', price_str)
    
    if match:
        # If a match is found, it means we have a decimal separator
        decimal_part = match.group(1)  # The two digits following the separator
        
        # Clean the integer part by removing all non-digit characters
        integer_part = re.sub(r'[^\d]', '', price_str[:match.start()])
        
        # decimal separator is always a dot
        sanitized_price = f"{integer_part}.{decimal_part}"
    else:
        # If no match is found, it means there is no valid decimal part, so remove all commas and dots
        sanitized_price = re.sub(r'[^\d]', '', price_str) + ".00"  # Append .00 for whole numbers

    # Convert to float
    try:
        return float(sanitized_price)
    except ValueError:
        raise ValueError(f"Cannot convert {price_str} to a valid float number")



# routes

@app.post("/crawl")
async def crawl(url_request: UrlRequest):
    try:
        # Step 1: Fetch the webpage content (and validate the URL)
        response = await validate_url(url_request.url)

        # Step 2: Make soup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Step 3: find product name
        product_name = soup.find('meta', property='og:title').get('content') if soup.find('meta', property='og:title') else None

        # Step 4: find price
        print('searching price with meta attribute property')
        price_tag = soup.find('meta', attrs={'property': re.compile(r'price', re.IGNORECASE)})
        if not price_tag:
            print('searching price with meta attribute itemprop')
            price_tag = soup.find('meta', attrs={'itemprop': re.compile(r'price', re.IGNORECASE)})
        if not price_tag:
            print('searching price with classname containing price: ')
            price_elements = soup.find_all(class_=re.compile(r'\bprice\b', re.IGNORECASE))
            if len(price_elements) > 0:
                price_tag = price_elements[0]
        if not price_tag:
            print('searching price inside meta og:description')
            meta_tag = soup.find('meta', {'property': 'og:description'})
            content = meta_tag.get('content', '')
            # Use a regular expression to find the first price (e.g., numbers followed by a comma/period and another number, then a currency symbol)
            price_pattern = r'\d{1,3}(?:[.,]\d{2})?\s?(&nbsp;|\s)?€'
            match = re.search(price_pattern, content)
        if not price_tag:
            print('searching price inside og:description')

            # Print the first price found
            if match:
                price_tag = match.group()
                
        # make price a string
        if isinstance(price_tag, str):
            # If price_tag is a string, it is already the price
            price = price_tag
        else:
            # If price_tag is an HTML element, extract the content
            price = price_tag.get('content', '') if price_tag else ''
        
        # cleanse price string
        price = re.sub(r'[^\d,\.]', '', price)

        # Step 5: find currency
        currency_tag = soup.find('meta', attrs={'property': re.compile(r'currency', re.IGNORECASE)})

        if not currency_tag:
            currency_tag = soup.find('meta', attrs={'itemprop': re.compile(r'priceCurrency', re.IGNORECASE)})
        if not currency_tag:
            meta_tag = soup.find('meta', {'property': 'og:description'})
            content = meta_tag.get('content', '')

            # Use a regular expression to find the first currency symbol
            currency_symbol_pattern = r'€|\$|£|¥|₹'  # Extend this to include other symbols if needed
            match = re.search(currency_symbol_pattern, content)

            # Extract the first currency symbol found
            if match:
                currency_tag = match.group()
            else:
                currency_tag = None

        # make price a string
        if isinstance(currency_tag, str):
            # If price_tag is a string, it is already the price
            currency = currency_tag
        else:
            # If price_tag is an HTML element, extract the content
            currency = currency_tag.get('content', '') if currency_tag else ''
            print('content: ',currency)

        # Define the response data based on the condition
        if product_name:
            async with httpx.AsyncClient() as client:
                post_data = {
                    "url": url_request.url,
                    "product_name": product_name,
                    "price": price,
                    "currency": currency,
                }
                headers = {"Internal-Authorization": INTERNAL_TOKEN}
                response = await client.post("http://localhost:8000/items", json=post_data, headers=headers)
                return response.json()
        else:
            response_data = {
                "url": url_request.url,
                "response": "No product found"
            }
            return response_data
    
    except ValueError as ve:
        # Handle ValueError and return a 400 response
        raise HTTPException(status_code=400, detail=str(ve))
    except httpx.RequestError as e:
        # Handle requests exceptions and return a 500 response
        raise HTTPException(status_code=500, detail=str(e))

async def check_for_price_changes(db: AsyncSession = Depends(get_db)):
    print("Running price change check...")

    async with SessionLocal() as db:  
    
        # Get the current time and calculate the time 24 hours ago
        now = datetime.now(timezone.utc)
        twenty_four_hours_ago = now - timedelta(hours=24)

        # Query the database for items where last_updated is older than 24 hours
        query = select(models.Item).where(models.Item.last_updated < twenty_four_hours_ago)
        result = await db.execute(query)
        items = result.scalars().all()

        for item in items:
            print(f"Checking item: {item.product_name}")

            current_price = item.price

            # If the price has changed, update the discount_price
            if current_price != item.price:
                print(f"Price change detected for {item.product_name}: Old Price = {item.price}, New Price = {current_price}")
                item.discount_price = current_price
                item.last_updated = now

                # Add the updated item back to the session
                db.add(item)

        # Commit changes to the database
        await db.commit()

@app.get("/check-for-discount")
async def check_for_discount(item: schemas.Item):

    try:
        # Step 1: Fetch the webpage content (and validate the URL)
        response = await validate_url(item.url)

        # Step 2: Make soup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Step 3: Check for possible discounts on page
        # Search for crossed-out prices
        crossed_out_prices = soup.find_all(style=re.compile(r'text-decoration:\s*line-through', re.IGNORECASE))
        if not crossed_out_prices:
            crossed_out_prices = soup.find_all(class_=re.compile(r'\bstrikethrough\b', re.IGNORECASE))

        # Search for discount percentages
        discount_pattern = re.compile(r'-\d+%')
        discount_texts = soup.find_all(text=discount_pattern)
        for text in discount_texts:
            print(f"Discount found: {text}")

        # Return the JSON response, ensuring the non-ASCII characters like '€' are preserved
        return {'hello': 'world'}
    
    except ValueError as ve:
        # Handle ValueError and return a 400 response
        raise HTTPException(status_code=400, detail=str(ve))
    except httpx.RequestError as e:
        # Handle requests exceptions and return a 500 response
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/items")
async def create_item(request: schemas.ItemCreate, db: AsyncSession = Depends(get_db), authorized: str = Depends(verify_internal_request)):
    try:
        async with db.begin():  # Manage transactions
            # Step 0: Check if the item already exists
            query = select(models.Item).filter(models.Item.url == request.url)
            result = await db.execute(query)
            existing_item = result.scalars().first()

            if existing_item:
                raise HTTPException(status_code=400, detail="Item already exists")

            # Step 1: Create new item
            new_item = models.Item(
                url=request.url,
                product_name=request.product_name,
                price=request.price,
                currency=request.currency,
                last_updated=datetime.now(timezone.utc) 
            )
            db.add(new_item)
            await db.commit()  # Commit the transaction

            # Refreshing the item after commit is usually not necessary
            # await db.refresh(new_item)

            return new_item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# just for development
@app.delete("/items", status_code=204)
async def delete_all_items(db: AsyncSession = Depends(get_db)):
    try:
        async with db.begin():
            # Step 1: Delete all items from the table
            await db.execute(models.Item.__table__.delete())
            await db.commit()  # Commit the transaction to apply the changes
        return {"detail": "All items deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
