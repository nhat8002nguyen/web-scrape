import scrapy
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import undetected_chromedriver as uc

from seleniumbase import Driver

import pandas as pd
import time
import os
import dotenv


class AliexpressScrapeSpider(scrapy.Spider):
    name = "aliexpress_scrape"
    allowed_domains = ["sale.aliexpress.com"]
    # start_urls = ["https://sale.aliexpress.com/__pc/rankings_list.htm"]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0",
        "Accept-Encoding": "gzip, deflate",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "DNT": "1",
        "Connection": "close",
        "Upgrade-Insecure-Requests": "1"
    }

    def start_requests(self):
        yield scrapy.Request(
            url="https://sale.aliexpress.com/__pc/rankings_list.htm",
            headers=self.headers,
            callback=self.parse,
        )

    def parse(self, response):
        with Driver(uc=True, headless=True) as driver:
            driver: WebDriver = driver
            wait = WebDriverWait(driver, 10)
            driver.get("https://sale.aliexpress.com/__pc/rankings_list.htm")
            nav_index = 1

            while True:
                nav_items = driver.find_elements(
                    by=By.XPATH,
                    value='//div[contains(@class, "nav-item")]'
                )
                nav_items[nav_index].click()
                product_groups = wait.until(EC.presence_of_all_elements_located((
                    By.XPATH,
                    '//div[@style="display: block;"]//div[@class="product-container"]//a[@class="product-cell"]'
                )))
                group_urls = [g.get_attribute("href") for g in product_groups]

                for g_url in group_urls:
                    yield scrapy.Request(
                        url=g_url,
                        headers=self.headers,
                        callback=self.parse_group,
                        meta={
                            "category": nav_items[nav_index].find_element(
                                by=By.XPATH,
                                value='./span'
                            ).text
                        }
                    )

    def parse_group(self, response):
        product_items = response.xpath(
            '//div[@class="top-ranking"]//ul[@class="rankings-list"]//a/@href').get()
        
        yield {
            "Category": response.request.meta["category"],
            "URL": response.url
        }
