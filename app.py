import httpx
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from bs4 import BeautifulSoup
import re
from sqlalchemy.orm import Session

from items import models, schemas
from items.database import SessionLocal, engine

    # TODOs:
        # check if url was already posted
        # sometimes returns EURO, sometimes €
        # currency and price being string, sometimes tho html, makes code ugly
        # unify price format, 165.00 or 165,00 and then what about big numbers?
        # refactoring idea: first check what website this is from, then scrape accordingly - create multiple scrapers   

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

models.Base.metadata.create_all(engine)

class UrlRequest(BaseModel):
    url: str

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
            response_data = {
                "url": url_request.url,
                "product_name": product_name,
                "price": price,
                "currency": currency,
            }
        else:
            response_data = {
                "url": url_request.url,
                "response": "No product found"
            }

        # Return the JSON response, ensuring the non-ASCII characters like '€' are preserved
        return response_data
    
    except ValueError as ve:
        # Handle ValueError and return a 400 response
        raise HTTPException(status_code=400, detail=str(ve))
    except httpx.RequestError as e:
        # Handle requests exceptions and return a 500 response
        raise HTTPException(status_code=500, detail=str(e))
    
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

@app.post("/shopping-items")
def create_shopping_item(request: schemas.ItemCreate, db: Session = Depends(get_db)):
    # Check if the item already exists
    # existing_item = db.query(models.Item).filter(Item.url == ItemCreate.url).first()
    # if existing_item:
    #     raise HTTPException(status_code=400, detail="Item already exists")
    
    # Create new item
    new_item = models.Item(url=request.url, product_name=request.product_name, price=request.price, currency=request.currency)
    print(new_item, db)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    # Log all items for debugging
    all_items = db.query(models.Item).all()
    print(f"All items in the database: {all_items}")

    return new_item

    


