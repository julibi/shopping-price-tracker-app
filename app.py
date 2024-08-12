import json
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, Response
from functools import wraps

# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.common.by import By
# from selenium.webdriver.chrome.options import Options

app = Flask(__name__)

@app.route('/')
def home():
    print("hello test")
    return "Hello, Flask!"

def validate_url(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        url = request.json.get('url')
        response = requests.get(url)
        
        if not url:
            return jsonify({"error": "No URL provided"}), 400
        
        if response.status_code != 200:
            raise requests.exceptions.RequestException(f"Failed to retrieve the page, status code: {response.status_code}")
        
        # TODOS:
        # check robots.txt
        # check if url is safe?
        
        return f(*args, **kwargs)  # Call the original function with all its arguments
    
    return decorated_function

@app.route('/crawl', methods=['POST'])
@validate_url
def crawl():
    try:
        # TODOs:
        # check if url was already posted
        # sometimes returns EURO, sometimes €
        # currency and price being string, sometimes tho html, makes code ugly
        # unify price format, 165.00 or 165,00 and then what about big numbers?
        # refactoring idea: first check what website this is from, then scrape accordingly - create multiple scrapers

        # Step 1: Fetch the webpage content
        url = request.json.get('url')
        response = requests.get(url)
        
        if response.status_code != 200:
            raise requests.exceptions.RequestException(f"Failed to retrieve the page, status code: {response.status_code}")

        #  # Setup Selenium WebDriver with Chrome
        # chrome_options = Options()
        # chrome_options.add_argument("--headless")  # Run Chrome in headless mode (without GUI)
        # chrome_options.add_argument("--no-sandbox")
        # chrome_options.add_argument("--disable-dev-shm-usage")

        # # Specify the path to ChromeDriver
        # service = Service('/Applications/chromedriver')

        # # Initialize WebDriver
        # driver = webdriver.Chrome(service=service, options=chrome_options)

        # # Navigate to the URL
        # driver.get(url)

        # # Get the page source after JavaScript execution
        # html = driver.page_source

        # # Quit the driver
        # driver.quit()

        # Step 2: Make soup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Step 3: find product name
        product_name = soup.find('meta', property='og:title').get('content') if soup.find('meta', property='og:title') else None

        # Step 4: find price
        print('searching price with property')
        price_tag = soup.find('meta', attrs={'property': re.compile(r'price', re.IGNORECASE)})
        if not price_tag:
            print('searching price with itemprop')
            price_tag = soup.find('meta', attrs={'itemprop': re.compile(r'price', re.IGNORECASE)})
        if not price_tag:
            print('searching price with classname containing price: ')
            price_elements = soup.find_all(class_=re.compile(r'\bprice\b', re.IGNORECASE))
            if len(price_elements) > 0:
                price_tag = price_elements[0]
        if not price_tag:
            print('searching price inside og:description')
            meta_tag = soup.find('meta', {'property': 'og:description'})
            content = meta_tag.get('content', '')
            # Use a regular expression to find the first price (e.g., numbers followed by a comma/period and another number, then a currency symbol)
            price_pattern = r'\d{1,3}(?:[.,]\d{2})?\s?(&nbsp;|\s)?€'
            match = re.search(price_pattern, content)

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
                "url": url,
                "product_name": product_name,
                "price": price,
                "currency": currency
            }
        else:
            response_data = {
                "url": url,
                "response": "No product found"
            }

        # Return the JSON response, ensuring the non-ASCII characters like '€' are preserved
        return Response(json.dumps(response_data, ensure_ascii=False), content_type='application/json')

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400

    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)


