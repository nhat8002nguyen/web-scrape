import csv
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
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


def wait_for_element(selector, by=By.CSS_SELECTOR, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, selector)))


def get_detail_data(detail_url) -> list[object, bool]:
    driver.get(detail_url)

    try:
        try:
            wait_for_element('main h1')
        except:
            pass

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        data = {
            "Company Name": soup.select_one('main h1').text.strip(),
            "Company Website": soup.select_one('a[title="Visiter le site"]')['href'] if soup.select_one('a[title="Visiter le site"]') else None,
            "Company Email": soup.select_one('a .icon--link').parent['href'][7:] if soup.select_one('a .icon--link') else None,
            "Company Phone": soup.select_one('a .icon--phone').parent['href'][4:] if soup.select_one('a .icon--phone') else None,
        }

        return [data, True]
    except Exception as e:
        print(f"Error loading detail page {detail_url}: {e}")
        return [{"failed_url": detail_url}, False]


def scrape_list():
    driver.get(
        "https://www.champagne.fr/fr/visiter-la-champagne/annuaire-caves-champagne")

    data_list = []
    failed_list = []

    # wait for all cookie button displaying
    try:
        accept_button = wait_for_element(
            'button[title="Oui"]')
        accept_button.click()
        yes_button = wait_for_element('button[id="axeptio_btn_acceptAll"]')
        yes_button.click()
    except:
        print("failed to wait for cookie button")

    distance_select = wait_for_element(
        '#filter-radius div[role="listbox"] .select__inner')
    distance_select.click()

    distance_50_option = wait_for_element('#choices--radius-item-choice-6')
    sleep(1)
    distance_50_option.click()

    # wait for all cookie button displaying
    try:
        accept_button = wait_for_element(
            'button[title="Oui"]')
        accept_button.click()
        yes_button = wait_for_element('button[id="axeptio_btn_acceptAll"]')
        yes_button.click()
    except:
        print("failed to wait for cookie button")

    try:
        # Handle infinite scroll
        while True:
            try:
                load_more = wait_for_element(
                    '.meta-grid-row button[data-ref="loadmore"]')
                driver.execute_script(
                    "arguments[0].scrollIntoView();", load_more)
                sleep(2)
                load_more = wait_for_element(
                    '.meta-grid-row button[data-ref="loadmore"]')
                load_more.click()
                print("loading more...")
            except TimeoutException:
                break

            time.sleep(2)  # Wait to load the data
        print("loaded all")

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        exhibitor_links = [a['href']
                           for a in soup.select('.meta-grid-row article a')]

        # for link in exhibitor_links:
        for link in exhibitor_links:
            result = get_detail_data(link)
            if result[1] == True and result[0]:
                detail_data = result[0]
                print(detail_data)
                data_list.append(detail_data)
            elif result[1] == False:
                failed_list.append(result[0]["failed_url"])

    except Exception as e:
        print(e)

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
