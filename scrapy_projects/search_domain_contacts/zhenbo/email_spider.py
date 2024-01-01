from typing import Any, Optional
import scrapy
import csv
import os
from dotenv import load_dotenv
from json import loads
import re
from urllib.parse import urlparse
from scrapy.crawler import CrawlerProcess
import requests
from requests.exceptions import ConnectionError, ReadTimeout
from time import sleep, perf_counter
from pandas import DataFrame
import argparse
from tqdm import tqdm
import multiprocessing
from scrapy.utils.project import get_project_settings


class EmailSpider(scrapy.Spider):
    name = 'email_spider'
    csv_file = 'first.csv'

    proxy = {
        'http': "http://webshareio005844-rotate:webshareio005844@p.webshare.io:80",
        'https': "http://webshareio005844-rotate:webshareio005844@p.webshare.io:80",
    }

    def __init__(self, file_name: str = "first.csv", start_index: int = 0, end_index: int = 0, **kwargs: Any):
        super().__init__(self.name, **kwargs)
        load_dotenv()
        self.csv_file = file_name
        self.proxy_with_auth = "http://webshareio005844-rotate:webshareio005844@p.webshare.io:80"
        self.start_index = start_index
        self.end_index = end_index
        self.phone_pattern = re.compile(r'''
                (?:\+\d{1,3}[\s.-]?|\(\d{1,3}\)[\s.-]?)  # Either country code or area code wrapped in parentheses with an optional space
                \d{2,4}  # Main part of the phone number
                [\s.-]?  # Optional space, dot, or dash as separators
                \d{2,4}  # Second part of the phone number
                [\s.-]?  # Optional space, dot, or dash as separators
                \d{2,9}  # Third part of the phone number
            ''', re.VERBOSE)

    def start_requests(self):
        try:
            urls = list[str]()
            with open(f"{os.environ['OUTPUT_PATH']}/{self.csv_file[:self.csv_file.rfind('.')]}_success_urls_{self.start_index}_{self.end_index}.json") as file:
                data = loads(file.read())
                urls = list(data["success_urls"].values())
        except FileNotFoundError:
            findSuccessfulUrls(self.csv_file, self.start_index, self.end_index)
            urls = list[str]()
            with open(f"{os.environ['OUTPUT_PATH']}/{self.csv_file[:self.csv_file.rfind('.')]}_success_urls_{self.start_index}_{self.end_index}.json") as file:
                data = loads(file.read())
                urls = list(data["success_urls"].values())

        # step 2: navigate each urls and find the contact information.
        for i in tqdm(range(len(urls))):
            url = urls[i]
            yield scrapy.Request(
                url=url, callback=self.parse,
                meta={
                    "proxy": self.proxy_with_auth
                }
            )

    def parse(self, response):
        return self.parse_contact(response, self.parse_sub)

    def parse_sub(self, response):
        return self.parse_contact(response, self.parse_sub)

    def parse_contact(self, response, callback):
        try:
            page_text = response.text
        except:
            return

        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'

        emails = list(set(re.findall(email_pattern, page_text)))
        phones = list(set(re.findall(self.phone_pattern, page_text)))

        domain = urlparse(response.url).netloc
        if "www." in domain:
            domain = domain[domain.index("www.")+4:]

        # Filter emails to include only those that match the domain being crawled
        matching_emails = [
            email for email in emails if email.endswith('@' + domain)]

        yield {
            'domain': domain,
            'emails': ", ".join(matching_emails),
            'phones': ", ".join(phones),
        }

        # Follow links within the same domain
        for next_url in response.css('a::attr(href)').getall():
            if not next_url or not self.valid_url(next_url):
                continue

            next_url = response.urljoin(next_url)
            parsed_url = urlparse(next_url)
            if parsed_url.netloc == domain:
                yield scrapy.Request(
                    next_url, callback=callback,
                    meta={
                        "proxy": self.proxy_with_auth
                    },
                )

    def valid_url(self, url: str) -> bool:
        if len(url) <= 1:
            return False
        if url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            return False

        return True

    def closed(self, reason):
        #TODO: remove all duplicates on the outputs.
        try:
            pass
        except:
            pass

def findSuccessfulUrls(csv_file: str, start_index: str, end_index: str):
    urls = list[str]()
    session = requests.Session()
    # session.proxies = proxy
    start_time = perf_counter()
    with open(f"{os.environ['INPUT_PATH']}/{csv_file}", 'r') as file:
        reader = csv.DictReader(file)
        rows = list(reader)

        target_rows = rows[start_index:end_index+1]
        for i in tqdm(range(start_index, end_index+1)):
            row = rows[i]
            lower_domain = str(row['DOMAIN']).lower()
            url = 'https://' + lower_domain
            try:
                response = session.get(url, timeout=5)
            except:
                print(
                    f"INFO: Connection FAIL: https://{lower_domain} not found.")
                continue

            if response.status_code != 200:
                continue

            print(f"INFO: Connection SUCCESS: {response.url}")
            urls.append(response.url)

    DataFrame({
        "success_urls": urls
    }).to_json(f"{os.environ['OUTPUT_PATH']}/{csv_file[:csv_file.rfind('.')]}_success_urls_{start_index}_{end_index}.json")

    cover_elapsed_time = (perf_counter() - start_time) / 60
    print(f"Takes {cover_elapsed_time} minutes to collect success urls!")
    print(
        f"There are {len(urls)} with 200 response status in total {len(target_rows)} domain.")
    break_second = 60
    print(f"Break {break_second} seconds before moving to next step.")
    sleep(break_second)

def run_spider(args):
    spider_name = args[0]
    file_name = args[1]
    start_index = args[2]
    end_index = args[3]
    process = CrawlerProcess(
        settings={
            'ROBOTSTXT_OBEY': False,
            'DEPTH_LIMIT': 3,
            'CONCURRENT_REQUESTS_PER_DOMAIN': 16,
            'CONCURRENT_REQUESTS_PER_IP': 16,
            'FEED_EXPORT_ENCODING': "utf-8",
            # "FEED_EXPORTERS": {
            #     'xlsx': 'scrapy_xlsx.XlsxItemExporter',
            # },
            'FEED_FORMAT': 'json',
            'FEED_URI': f'output_{start_index}_{end_index}.json',
        }
    )
    spider_classes = {
        "email_spider": EmailSpider,
    }
    process.crawl(spider_classes[spider_name], file_name, start_index, end_index)
    process.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Find emails and phones from domains in csv file')
    parser.add_argument('--csv', metavar='path', required=True,
                        help='the path to input csv file')
    args = parser.parse_args()

    spider_args = [
        ("email_spider", args.csv, 0, 9999),
        # ("email_spider", args.csv, 10000, 19999),
        # ("email_spider", args.csv, 20000, 29999),
    ]

    # Create a multiprocessing pool
    with multiprocessing.Pool() as pool:
        # Run each spider in a separate process
        pool.map(run_spider, spider_args)
