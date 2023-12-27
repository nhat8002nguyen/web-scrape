from typing import Any, Iterable, Optional
import scrapy
from scrapy.http import Request
import openpyxl
import re
from json import loads
from typing import Callable
import logging
from dotenv import load_dotenv
import os
from tqdm import tqdm

from scrapy.crawler import CrawlerProcess
from w3lib.http import basic_auth_header

from seleniumbase import Driver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException


class BookInfo():
    author: str
    category: str

    def __init__(self, author: str, category: str) -> None:
        self.author = author
        self.category = category


class BlinkistScraperSpider(scrapy.Spider):
    name = "blinkist_scraper"
    allowed_domains = ["www.blinkist.com"]
    # start_urls = ["https://www.blinkist.com/en/books"]

    headers = {
        "Authority": "www.blinkist.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.blinkist.com/",
        "Origin": "https://www.blinkist.com",
        "DNT": "1",
        "Connection": "close",
        "Upgrade-Insecure-Requests": "1"
    }

    def __init__(self, name: str | None = None, **kwargs: Any):
        super().__init__(name, **kwargs)
        load_dotenv()

        with open(os.environ["COOKIES_PATH"], "r") as file:
            cookies = loads(file.read())

        web_driver: WebDriver = Driver(
            uc=True,
            # proxy="webshareio005844-rotate:webshareio005844@p.webshare.io:80",
            headless=True,
        )
        web_driver.get("https://www.blinkist.com")
        for cookie in cookies:
            web_driver.add_cookie(cookie_dict=cookie)

        self.web_driver = web_driver

        # Configure logging
        logging.basicConfig(
            filename="fail-urls.log",
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def start_requests(self):
        for i in tqdm(range(0, 27)):
            file_name = f"blinkist-output-categ-{i+1}"

            is_scrape_all = False
            if (i+1) in [3, 10, 11, 12, 13, 14, 15, 18, 24, 25, 26, 27]:
                is_scrape_all = True

            book_slugs = self.get_book_slugs(
                file_path=f'{os.environ["COOKIES_PATH"]}/blinkist-consolidated/{file_name}.xlsx',
                is_scrape_all=is_scrape_all,
            )

            count = 0
            self.headers["Proxy-Authorization"] = basic_auth_header(
                "webshareio005844-rotate", "webshareio005844"
            )
            for slug in book_slugs:
                yield scrapy.Request(
                    url=f"https://jsonplaceholder.typicode.com/posts/{count}",
                    headers=self.headers,
                    meta={
                        "url": f"https://www.blinkist.com/en/books/{slug}",
                        "proxy": "http://p.webshare.io:80",
                        "file_name": file_name,
                        "slug": slug
                    },
                    callback=self.selenium_request,
                    dont_filter=True,
                )
                count += 1

    def selenium_request(
        self,
        response
    ):
        self.web_driver.get(url=response.meta["url"])

        try:
            author_tag = self.web_driver.find_element(
                by=By.XPATH,
                value='//div[@data-test-id="book-hero-section"]//div[contains(@class, "text-h5")]'
            )
            author_text = ''
            if author_tag != None:
                author_text = author_tag.text

            categ_tag = self.web_driver.find_element(
                by=By.XPATH,
                value='//div[@data-test-id="book-hero-section"]/section/div[contains(@class, "justify-between")]//div[contains(@class, "text-blue")]/div[contains(@class, "items-center")][2]'
            )
            if categ_tag != None:
                categ_text = categ_tag.text

            return {
                "Category": categ_text,
                "Author": author_text,
                "Slug": response.meta["slug"]
            }

        except:
            print(f"Fail to get author name of {response.meta['url']}")
            logging.error(
                f"File name {response.meta['file_name']}: fail url - {response.meta['url']}")
            return {
                "Author": "",
                "Category": ""
            }

    def get_book_slugs(self, file_path: str, is_scrape_all: bool = False) -> None:
        # Load the workbook and select the active worksheet
        wb = openpyxl.load_workbook(
            file_path, read_only=True)

        sheet = wb.active  # or use wb['Sheet1'] if you know the sheet name

        slugs = list[str]()
        # Iterate through each row in the worksheet
        for row in sheet.iter_rows(values_only=True):
            if is_scrape_all != True and "Brief summary" not in row[0]:
                continue

            name: str = row[1]
            name = name.split("\n")[0]
            slug = self.title_to_slug(name)
            slugs.append(slug)

        wb.close()

        return slugs

    def title_to_slug(self, title: str):
        """Convert title to slug."""
        if title[0] == "$":
            title = title[1:]

        title = re.sub(r'\$(\d+)', r'\1-dollars', title)

        # Convert to lowercase
        slug = title.lower()

        # Remove punctuation
        slug = re.sub(r'[^\w\s-]', '', slug)

        # Replace whitespace and repeats with a single hyphen
        slug = re.sub(r'[\s]+', '-', slug)

        # Add '-en' at the end of the slug
        slug += '-en'

        return slug

    def closed(self, reason):
        self.logger.info("Closing web driver service...")
        self.web_driver.close()

if __name__ == "__main__":
    process = CrawlerProcess({
        'FEED_EXPORT_ENCODING': "utf-8",
        # "FEED_EXPORTERS": {
        #     'xlsx': 'scrapy_xlsx.XlsxItemExporter',
        # },
        'FEED_FORMAT': 'json',
        'FEED_URI': 'blinkist-additional-info.json',
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1
    })
    process.crawl(BlinkistScraperSpider)
    process.start()