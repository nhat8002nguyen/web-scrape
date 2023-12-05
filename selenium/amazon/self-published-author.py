from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
import time

# Start up Selenium with a headless Chrome
options = Options()
# options.add_argument("--headless")
options.add_argument(
    "User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

driver = webdriver.Chrome(options=options)

# This is a placeholder URL for the book page
book_page_url = "https://www.amazon.com/s?k=self+published&crid=1VZ82RHUX6BPI&sprefix=self+published+authors%2Caps%2C307&ref=nb_sb_ss_ts-doa-p_1_22"
driver.get(book_page_url)

# Ensure the page is loaded completely before scraping
time.sleep(5)  # Wait 5 seconds for the page to load

# Now, extract the needed details

items = driver.find_elements(
    By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]')
for item in items:
    try:
        name_row = driver.find_element(
            By.CSS_SELECTOR, 'div[data-cy="title-recipe"]>div.a-color-secondary>div.a-row')
        names = name_row.find_elements(
            By.CSS_SELECTOR, '.a-size-base')
        names = " ".join(names)
        names = names[names.index("by")+3:names.rfind("|")-1]

        # author_name = driver.find_element(By.CSS_SELECTOR, '').text
        # # Amazon doesn't display email addresses; you'd have to find this elsewhere.
        # email_address = ""
        # book_title = driver.find_element(
        #     By.CSS_SELECTOR, 'SELECTOR_FOR_BOOK_TITLE').text
        # genre_elements = driver.find_elements(
        #     By.CSS_SELECTOR, 'SELECTOR_FOR_GENRE')
        # book_genre = [e.text for e in genre_elements]
    except Exception as e:
        print(f'An error occurred: {e}')

# Close the driver
driver.quit()

# Print or process the extracted information
# print(f"Author Name: {author_name}")
# print(f"Email Address: {email_address}") - Note: We don't scrape emails as they are typically not public
# print(f"Book Title: {book_title}")
# print(f"Book Genres: {book_genre}")
