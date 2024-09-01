import csv
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
from time import sleep

# Initialize WebDriver
# or use another WebDriver like Firefox, Edge, etc.
options = webdriver.ChromeOptions()
options.add_argument("--headless")
driver = webdriver.Chrome(options=options)


def load_cookies(driver: WebDriver, cookies_file: str):
    with open(cookies_file, 'r') as file:
        cookies = json.load(file)
        for cookie in cookies:
            # The domain attribute can't have leading dot for some WebDrivers, ensure format
            if 'domain' in cookie and cookie['domain'].startswith('.'):
                cookie['domain'] = cookie['domain'][1:]
            driver.add_cookie(cookie)


def wait_for_element(selector, by=By.CSS_SELECTOR, timeout=15):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, selector)))


def get_detail_data(detail_url):
    driver.get(detail_url)

    try:
        wait_for_element('#exhibitor_details_showobjective p')
        # If needed, insert more waits for other elements

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Extract social network links and assign to specific columns
        social_links = {
            "Facebook": "",
            "Twitter": "",
            "LinkedIn": "",
            "Instagram": ""
        }

        social_networks = soup.select('.section-container a')
        for link in social_networks:
            href = link.get('href', '')
            if 'facebook.com' in href:
                social_links['Facebook'] = href
            elif 'twitter.com' in href:
                social_links['Twitter'] = href
            elif 'linkedin.com' in href:
                social_links['LinkedIn'] = href
            elif 'instagram.com' in href:
                social_links['Instagram'] = href
            elif 'youtube.com' in href:
                social_links['Youtube'] = href

        data = {
            "Company Name": soup.select_one('div.details-header h1').text.strip(),
            "Company Website": soup.select_one('#exhibitor_details_website a')['href'] if soup.select_one('#exhibitor_details_website a') else None,
            "Company Email": soup.select_one('#exhibitor_details_email a')['href'][7:] if soup.select_one('#exhibitor_details_email a') else None,
            "Company Phone": soup.select_one('#exhibitor_details_phone a')['href'][4:] if soup.select_one('#exhibitor_details_phone a') else None,
            "Why Visit Our Stand": soup.select_one('#exhibitor_details_showobjective p').text.strip() if soup.select_one('#exhibitor_details_showobjective p') else None,
            "Brands We Represent": soup.select_one('#exhibitor_details_brands p').text.strip() if soup.select_one('#exhibitor_details_brands p') else None,
            "Description": soup.select_one('#exhibitor_details_description p').text.strip() if soup.select_one('#exhibitor_details_description p') else None,
            "Address": ", ".join([s.text for s in soup.select('#exhibitor_details_address p span')]) if soup.select_one('#exhibitor_details_address p') else None,
            "Product Groups": ', '.join([span.text for span in soup.select('div[data-dtm-category-name="Product Groups"] div span')]),
            **social_links  # Adding social network links to data dictionary
        }

        return data
    except Exception as e:
        print(f"Error loading detail page {detail_url}: {e}")
        return {}


def scrape_list():
    driver.get(
        "https://www.barconvent.com/en-gb/for-visitors/ExhibitorList.html#/")

    data_list = []

    accept_button = wait_for_element(
        'button[id="onetrust-accept-btn-handler"]')
    accept_button.click()
    yes_button = wait_for_element('button[value=yes]')
    yes_button.click()

    # for i in range(6):  # Loop through the first 6 span items
    for i in range(6):  # Loop through the first 6 span items
        time.sleep(5)
        try:
            # Wait for and click span item
            wait_for_element(
                f'.current-listing li:nth-child({i+1}) div[class=" duplicate-checkbox"]')
            span_item = driver.find_element(
                By.CSS_SELECTOR, f'.current-listing li:nth-child({i+1}) div[class=" duplicate-checkbox"]')
            span_item.click()

            filter_group = wait_for_element('.selected-filters label').text

            # Handle infinite scroll
            last_height = driver.execute_script(
                "return document.body.scrollHeight")
            while True:
                driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)  # Wait to load the data
                new_height = driver.execute_script(
                    "return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            soup = BeautifulSoup(driver.page_source, 'html.parser')

            exhibitor_links = [a['href'] for a in soup.select(
                'ul div[class="exh-detail-container"] div[data-testid="name-control"] a')]

            # for link in exhibitor_links:
            for link in exhibitor_links:
                detail_data = get_detail_data(link)
                if detail_data:
                    print(detail_data)
                    detail_data['Filter group'] = filter_group
                    data_list.append(detail_data)

            # Refresh page after each category
            driver.get(
                "https://www.barconvent.com/en-gb/for-visitors/ExhibitorList.html#/")
            time.sleep(3)  # Wait for page to reload

        except Exception as e:
            print(f"Error in list scraping for span item {i+1}: {e}")
            continue  # Skip to the next span item

    return data_list


def export_to_csv(data_list, filename="exhibitors_data.csv"):
    keys = data_list[0].keys()
    with open(filename, 'w', newline='', encoding='utf-8') as output_file:
        dict_writer = csv.DictWriter(output_file, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(data_list)


if __name__ == "__main__":
    data = scrape_list()
    if len(data) > 0:
        export_to_csv(data)
    driver.quit()
