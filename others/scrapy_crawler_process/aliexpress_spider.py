from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from seleniumbase import Driver

import pandas as pd
import time
from tqdm import tqdm

headers = {
    "Cache-Control": "no-cache",
    "Accept-Encoding": "gzip, deflate, br",
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "origin": "https://www.azrieli.com",
    "pragma": "no-cache",
    "referer": "https://www.azrieli.com/",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def main():

    try:
        cur_excel_file = pd.read_excel("./aliexpress-top-ranking.xlsx")
    except FileNotFoundError:
        pd.DataFrame().to_excel("./aliexpress-top-ranking.xlsx")

    new_df = pd.DataFrame()

    with Driver(uc=True, headless=True) as driver:
        driver: WebDriver = driver
        wait = WebDriverWait(driver, 30)
        nav_index = 1
        driver.get("https://sale.aliexpress.com/__pc/rankings_list.htm")

        nav_items = driver.find_elements(
            by=By.XPATH,
            value='//div[contains(@class, "nav-item")]'
        )

        for i in tqdm(range(1, len(nav_items))):
            if i > 1:
                driver.get(
                    "https://sale.aliexpress.com/__pc/rankings_list.htm")
                nav_items = driver.find_elements(
                    by=By.XPATH,
                    value='//div[contains(@class, "nav-item")]'
                )
            category_name = nav_items[i].find_element(
                by=By.XPATH, value='./span').text

            nav_items[i].click()

            try:
                product_groups = wait.until(EC.presence_of_all_elements_located((
                    By.XPATH,
                    '//div[contains(@style, "display: block;")]//div[@class="product-container"]//a[@class="product-cell"]'
                )))
            except TimeoutException:
                nav_items = driver.find_elements(
                    by=By.XPATH,
                    value='//div[contains(@class, "nav-item")]'
                )
                nav_items[i].click()

            group_urls = [g.get_attribute("href") for g in product_groups]

            g_p_urls = []
            for g_url in group_urls:
                driver.get(
                    url=g_url,
                )
                product_items = []
                try:
                    product_items = wait.until(EC.presence_of_all_elements_located((
                        By.XPATH,
                        '//div[@class="top-ranking"]//ul[@class="rankings-list"]//a'
                    )))
                except TimeoutException:
                    # retry if timeout
                    driver.get(url=g_url)
                    product_items = wait.until(EC.presence_of_all_elements_located((
                        By.XPATH,
                        '//div[@class="top-ranking"]//ul[@class="rankings-list"]//a'
                    )))

                urls = [item.get_attribute("href") for item in product_items]
                g_p_urls.extend(urls)

                time.sleep(6)

            new_df = pd.concat([
                pd.DataFrame({
                    "Category": [category_name for _ in g_p_urls],
                    "URL": g_p_urls
                }),
                new_df
            ])

            time.sleep(30)

    merged_excel = pd.concat([new_df, cur_excel_file], ignore_index=True)

    merged_excel.to_excel("./aliexpress-top-ranking.xlsx", index=False)


if __name__ == "__main__":
    main()
