import csv
from tqdm import tqdm
from typing import Iterable
import scrapy
from scrapy.http import Request, Response
from random import choice

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from seleniumbase import Driver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

import pandas as pd
from time import sleep, perf_counter
import os
import dotenv
dotenv.load_dotenv()


class DebankSyveAiSpider(scrapy.Spider):
    name = "debank_syve_ai"
    allowed_domains = ["debank.com"]

    def start_requests(self):
        yield scrapy.Request(
            url="https://debank.com/profile",
            callback=self.parse
        )

    def parse(self, response: Response):
        driver: WebDriver = Driver(uc=True, no_sandbox=True, headless=True)
        driver.get("https://api.syve.ai/dashboards/pnl_checker/")
        driver.maximize_window()
        wait = WebDriverWait(driver, 30)
        actions = ActionChains(driver)

        df = pd.read_excel(
            '/Users/nhatnguyen/Workspaces/web-scrape/scrapy_projects/debank_com/Block_1.xlsx')
        name_column = df['Wallet']
        size = name_column.size
        size = 10
        start_time = perf_counter()

        for i in tqdm(range(size)):
            wallet_id = name_column.iloc[i]
            while True:
                try:
                    input_tag = wait.until(EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        'input[aria-label="**Wallet Address**"]'
                    )))
                    actions.double_click(input_tag)
                    actions.send_keys(wallet_id)
                    actions.perform()

                    button = driver.find_element(
                        by=By.CSS_SELECTOR,
                        value='button[kind="secondary"]'
                    )
                    button.click()

                    sleep(1)

                    metrics = wait.until(EC.presence_of_all_elements_located((
                        By.CSS_SELECTOR,
                        'div[data-testid="stMetricValue"]'
                    )))

                    total_return = metrics[8].text
                    win_rate = metrics[7].text
                    total_investment = metrics[6].text
                    unrealized_profit = metrics[5].text
                    realized_profit = metrics[4].text
                    total_profit = metrics[3].text
                    tokens_traded = metrics[2].text

                    actions.reset_actions()
                    actions.double_click(input_tag)
                    actions.send_keys(Keys.BACK_SPACE)
                    actions.perform()
                    button.click()

                    wait.until(EC.presence_of_all_elements_located((
                        By.XPATH,
                        '//strong[contains(text(), "Invalid input")]'
                    )))

                    break
                except Exception as err:
                    print(err)
                    print("Retrying...")
                    driver.get("https://api.syve.ai/dashboards/pnl_checker/")
                    pass

            yield {
                "wallet": wallet_id,
                "type": "syve",
                "total_return": total_return,
                "win_rate": win_rate,
                "total_investment": total_investment,
                "unrealized_profit": unrealized_profit,
                "realized_profit": realized_profit,
                "total_profit": total_profit,
                "tokens_traded": tokens_traded,
            }

        for i in tqdm(range(10)):
            driver.get(f"https://debank.com/profile")
            wallet_id = name_column.iloc[i]
            while True:
                try:
                    input = driver.find_element(
                        by=By.CSS_SELECTOR,
                        value='.db-input>input'
                    )
                    input.send_keys(wallet_id)

                    option = wait.until(EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        '.db-user'
                    )))

                    option.click()

                    debank_value = wait.until(EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        'div[class="projectTitle-number"]'
                    ))).text

                    break
                except:
                    debank_value = ""
                    driver.get(f"https://debank.com/profile")

            yield {
                "wallet": wallet_id,
                "type": "debank",
                "debank": debank_value,
            }

        elapsed_time = perf_counter() - start_time
        print(f"Time to scrape {size} items is {elapsed_time:.4f}")

        driver.close()
