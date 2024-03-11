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
import simplepush
from scrapy import signals
from scrapy.signalmanager import dispatcher

import pandas as pd
from time import sleep, perf_counter
import os
import dotenv
dotenv.load_dotenv()


class DebankSyveAiSpider1(scrapy.Spider):
    name = "debank_syve_ai_1"
    allowed_domains = ["debank.com"]

    def __init__(self, start_index=None, end_index=None, *args, **kwargs):
        super(DebankSyveAiSpider1, self).__init__(*args, **kwargs)
        # Convert parameters to integers and handle defaults if necessary
        self.start_index = int(start_index) if start_index is not None else 0
        self.end_index = int(end_index) if end_index is not None else 0

        self.item_count = 0
        dispatcher.connect(self.spider_closed, signal=signals.spider_closed)

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
            f'{os.environ["ROOT"]}/Block_1.xlsx')
        name_column = df['Wallet']
        size = self.end_index - self.start_index + 1
        start_time = perf_counter()

        wallet_data = {}
        for i in tqdm(range(self.start_index, self.end_index+1)):
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

                    sleep(3)

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

            wallet_data[wallet_id] = {
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

        simplepush.send(key=os.environ["SIMPLEPUSH_KEY"], title=f'{self.name} is 50%',
                        message=f'scraped the first part of {size} items')

        for i in tqdm(range(self.start_index, self.end_index+1)):
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

            wallet_item = wallet_data.get(wallet_id, {})
            wallet_item["debank"] = debank_value

            self.item_count += 1
            yield wallet_item

        elapsed_time = perf_counter() - start_time
        print(f"Time to scrape {size} items is {elapsed_time:.4f}")

        driver.close()

    def spider_closed(self, spider, reason):
        self.log('Spider is closing: %s' % self.name)
        simplepush.send(key=os.environ["SIMPLEPUSH_KEY"], title=f'{spider.name} is done',
                        message=f'spider closed, scraped {self.item_count} items')
