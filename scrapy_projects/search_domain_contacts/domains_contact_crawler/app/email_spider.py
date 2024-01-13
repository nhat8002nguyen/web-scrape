from simplepush import send
from item_pipeline import XLSXPipeline
from domain_timeout_middleware import DomainTimeoutMiddleware
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
from tqdm import tqdm
from pandas import DataFrame
from time import sleep, perf_counter, time
import requests
from scrapy.crawler import CrawlerProcess
from urllib.parse import urlparse
import re
from json import loads
from typing import Any, Optional
import scrapy
from datetime import datetime
import csv
import json
import os
from dotenv import load_dotenv
load_dotenv()

ROOT_PATH = os.environ['PROJECT_ROOT']
INPUT_PATH = ROOT_PATH + os.environ['INPUT_PATH']
OUTPUT_PATH = ROOT_PATH + os.environ['OUTPUT_PATH']
BATCH_FILE_PATH = ROOT_PATH + os.environ['BATCH_FILE']
APP_PATH = ROOT_PATH + "/app"


class EmailSpider(scrapy.Spider):
    name = 'email_spider'
    csv_file = 'first.csv'

    proxy = {
        'http': "http://webshareio005844-rotate:webshareio005844@p.webshare.io:80",
        'https': "http://webshareio005844-rotate:webshareio005844@p.webshare.io:80",
    }

    def __init__(self, file_name: str = "first.csv", start_index: int = 0, end_index: int = 0, **kwargs: Any):
        super().__init__(self.name, **kwargs)
        self.csv_file = file_name
        self.proxy_with_auth = os.environ["PROXY_ROTATING_ENDPOINT"] if "PROXY_ROTATING_ENDPOINT" in os.environ else ""
        self.start_index = start_index
        self.end_index = end_index
        self.phone_pattern = re.compile(r'''
                (?:(?:\+\d{1,3}[\s.-]?)|\(\d{1,3}\)[\s.-]?)  # Either country code or area code wrapped in parentheses with an optional space
                \d{2,4}  # Main part of the phone number
                [\s.-]?  # Optional space, dot, or dash as separators
                \d{2,4}  # Second part of the phone number
                [\s.-]?  # Optional space, dot, or dash as separators
                \d{2,9}  # Third part of the phone number
            ''', re.VERBOSE)

    def start_requests(self):
        try:
            urls = list[str]()
            with open(f"{OUTPUT_PATH}/{self.csv_file[:self.csv_file.rfind('.')]}_success_urls_{self.start_index}_{self.end_index}.json") as file:
                data = loads(file.read())
                urls = list(data["success_urls"].values())
        except FileNotFoundError:
            findSuccessfulUrls_v1(
                self.csv_file, self.start_index, self.end_index)
            sleep(3)
            urls = list[str]()
            with open(f"{OUTPUT_PATH}/{self.csv_file[:self.csv_file.rfind('.')]}_success_urls_{self.start_index}_{self.end_index}.json") as file:
                data = loads(file.read())
                urls = list(data["success_urls"].values())

        break_second = 5
        print(
            f"INFO: Break {break_second} seconds before moving to next step.")
        sleep(break_second)

        # step 2: navigate each urls and find the contact information.
        for i in tqdm(range(len(urls))):
            url = urls[i]["url"]
            yield scrapy.Request(
                url=url, callback=self.parse,
                meta={
                    "proxy": self.proxy_with_auth,
                    "XID": urls[i]["XID"]
                }
            )

    def parse(self, response):
        return self.parse_contact(response, self.parse_sub, 0)

    def parse_sub(self, response):
        return self.parse_contact(response, self.parse_sub, 1)

    def parse_contact(self, response, callback, depth: int):
        try:
            page_text = response.text
        except:
            return

        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'

        emails = list(set(re.findall(email_pattern, page_text)))
        phones = list(set(re.findall(self.phone_pattern, page_text)))
        phones = list(filter(is_invalid_date, phones))
        phones = list(filter(lambda x: False if str(
            x).startswith("+0") else True, phones))

        domain = urlparse(response.url).netloc
        if "www." in domain:
            domain = domain[domain.index("www.")+4:]

        # Filter emails to include only those that match the domain being crawled
        matching_emails = [
            email for email in emails if email.endswith('@' + domain)]

        for i, email in enumerate(matching_emails):
            id = domain + "-" + email
            yield {
                'id': id,
                'XID': response.meta["XID"],
                'domain': domain,
                'email': email,
            }

        for i, phone in enumerate(phones):
            id = domain + "-" + phone
            yield {
                'id': id,
                'XID': response.meta["XID"],
                'domain': domain,
                'phone': phone,
            }

        # stop scanning urls
        if depth == 1:
            return

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
                        "proxy": self.proxy_with_auth,
                        "XID": response.meta["XID"]
                    },
                )

    def valid_url(self, url: str) -> bool:
        if len(url) <= 1:
            return False
        media_formats = (
            ".mp3", ".wav", ".ogg", ".aac", ".flac",
            ".mp4", ".webm", ".avi", ".mkv", ".mov",
            ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
            ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
            ".zip", ".tar", ".gz", ".rar",
            ".obj", ".stl", ".fbx",
            ".ttf", ".otf",
            ".svg", ".ai",
            ".exe", ".dll",
            ".sqlite", ".db"
        )
        if url.lower().endswith(media_formats):
            return False

        return True


def findSuccessfulUrls_v1(csv_file: str, start_index: str, end_index: str):
    urls = list[dict]()
    start_time = perf_counter()
    with open(f"{INPUT_PATH}/{csv_file}", 'r') as file:
        reader = csv.DictReader(file)
        rows = list(reader)

        length = end_index-start_index+1
        num_workers = os.cpu_count()
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(
                makeRequests, rows, start_index + i *
                (length//num_workers), start_index +
                (i+1)*(length//num_workers)-1
            ) for i in range(num_workers)]

            for future in as_completed(futures):
                try:
                    result = future.result()
                    urls.extend(result)
                except Exception as e:
                    # Handle exceptions raised in makeRequests function
                    print(f"An error occurred: {e}")

    DataFrame({
        "success_urls": urls
    }).to_json(f"{OUTPUT_PATH}/{csv_file[:csv_file.rfind('.')]}_success_urls_{start_index}_{end_index}.json")

    cover_elapsed_time = (perf_counter() - start_time)
    print(f"Takes {cover_elapsed_time} seconds to collect success urls!")
    print(
        f"There are {len(urls)} with 200 response status in total {end_index-start_index+1} domain.")


def makeRequests(rows: list[str], start_index: str, end_index: str) -> list[dict]:
    domains = list[dict]()
    with requests.Session() as session:
        # session.proxies = proxy
        for i in tqdm(range(start_index, end_index+1)):
            row = rows[i]
            xID = str(row['XID']).lower()
            lower_domain = str(row['DOMAIN']).lower()
            url = 'https://' + lower_domain
            try:
                response = session.get(url, timeout=3)
            except:
                print(
                    f"INFO: Connection FAIL: https://{lower_domain} not found.")
                continue

            if response.status_code != 200:
                continue

            print(f"INFO: Connection SUCCESS: {response.url}")
            domains.append({
                'XID': xID,
                'url': response.url,
            })

    return domains


def is_invalid_date(date_str, date_format='+%Y-%m-%d'):
    try:
        datetime.strptime(date_str, date_format)
        return False
    except ValueError:
        return True


def run_spider(args):
    spider_name = args[0]
    file_name = args[1]
    start_index = args[2]
    end_index = args[3]
    process = CrawlerProcess(
        settings={
            'REQUEST_FINGERPRINTER_IMPLEMENTATION': '2.7',
            'ROBOTSTXT_OBEY': False,
            'DEPTH_LIMIT': 1,
            'CONCURRENT_REQUESTS_PER_DOMAIN': 32,
            'CONCURRENT_REQUESTS_PER_IP': 32,
            'FEED_EXPORT_ENCODING': "utf-8",
            'ITEM_PIPELINES': {
                XLSXPipeline: 300,
                # Add other pipelines if needed, with their respective priority values
            },
            'DOWNLOADER_MIDDLEWARES': {
                # Adjust priority accordingly
                DomainTimeoutMiddleware: 543,
            },
            'START_INDEX': start_index,
            'END_INDEX': end_index,
            'LOG_LEVEL': 'INFO' if os.environ["ENV"] == "prod" else "DEBUG",
            'REACTOR_THREADPOOL_MAXSIZE': 20,
            'RETRY_ENABLED': False,
            'DOWNLOAD_TIMEOUT': 30,
            'CSV_INPUT_NAME': file_name
        }
    )
    spider_classes = {
        "email_spider": EmailSpider,
    }
    process.crawl(spider_classes[spider_name],
                  file_name, start_index, end_index)
    process.start()


if __name__ == "__main__":
    data = None
    with open(BATCH_FILE_PATH, "r") as file:
        data = json.loads(file.read())

    if data == None:
        print("ERROR: error when reading batches.json, please check again!")

    input_name = data["input"]
    batches = data["batches"]
    spider_args = [("email_spider", input_name, batch["start"], batch["end"])
                   for batch in batches]

    # Create a multiprocessing pool
    num_workers = multiprocessing.cpu_count()
    print(f"INFO: There are {num_workers} CPUs")
    with multiprocessing.Pool(processes=num_workers) as pool:
        # Run each spider in a separate process
        pool.map(run_spider, spider_args)

    print("Notifying the program is done...")
    send(os.environ["SIMPLEPUSH_KEY"], "message",
         title=f"Crawler for {input_name} is DONE!", event=f"Crawler for {input_name} is DONE!")
    print(f"Crawler for {input_name} is DONE!")
