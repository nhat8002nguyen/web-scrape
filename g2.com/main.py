from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

# Create an options object for the Chrome browser
options = webdriver.ChromeOptions()

# Add any desired options here, such as:
# options.add_argument("--headless")  # Run Chrome in headless mode (no GUI)
# options.add_argument("--disable-gpu")  # Disable GPU acceleration

# Create an instance of the undetected_chromedriver
driver = uc.Chrome(options=options)

# Specify the website you want to scrape
url = 'https://www.g2.com/products/hihello/reviews'

try:
    # Navigate to the website
    driver.get(url)

    # Wait for a specific element to load (optional, but recommended)
    # Example: wait for an element with the class name 'product-item'
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'product-item'))
    )

    # Extract data from the website using Selenium's methods
    # Examples:
    # title = driver.find_element(By.TAG_NAME, 'h1').text
    # prices = driver.find_elements(By.CLASS_NAME, 'price')
    # for price in prices:
    #     print(price.text)

    # ... your scraping logic here ...

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    # Close the browser window
    driver.quit()
