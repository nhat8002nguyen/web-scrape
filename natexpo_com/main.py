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


def get_detail_data(id: str) -> list[object, bool]:
    driver.get(f"https://liste-exposants.hubj2c.com/natexpo24/main?id={id}")

    try:
        try:
            wait_for_element('.modal-title')
            wait_for_element('.fe-drapeau')
        except:
            pass

        sleep(1)
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        data = {
            "Company Name": soup.select_one('.modal-title').text.strip(),
            "Description": " ".join([div.text.strip() for div in soup.select('.container .card-block')]) if soup.select('.container .card-block') else None,
            "Country": soup.select_one('.fe-drapeau')['title'] if soup.select_one('.fe-drapeau') else None,
            "Address": "\n".join([div.text.strip() if "http" not in div.text.strip() else "" for div in soup.select('.card-block .col-10 div')]) if soup.select('.card-block .col-10 div') else None,
            "Website": soup.select_one('.fe-lien a')['href'] if soup.select_one('.fe-lien a') else None,
            "Social Media": "\n".join([a['href'] for a in soup.select('a[class=fe-social]')]) if soup.select('a[class=fe-social]') else None,
        }

        return [data, True]
    except Exception as e:
        print(f"Error loading detail page {id}: {e}")
        return [{"failed_url": id}, False]


def scrape_list():
    driver.get(
        "https://natexpo.com/visiter/liste-exposants/")

    data_list = []
    failed_list = []

    iframe = driver.find_element(by=By.XPATH, value="//iframe[@name='demo']")
    driver.switch_to.frame(iframe)

    try:
        wait_for_element('tbody tr')
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        trs = soup.select('tbody tr')
        company_ids = [tr['id'] if tr.has_key('id') else None for tr in trs]

        # for link in exhibitor_links:
        for id in company_ids:
            result = get_detail_data(id)
            if result[1] == True and result[0]:
                detail_data = result[0]
                print(detail_data)
                data_list.append(detail_data)
            elif result[1] == False:
                failed_list.append(result[0]["failed_url"])

    except Exception as e:
        print(e)

    return data_list


def export_to_csv(data_list, filename="data.csv"):
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
