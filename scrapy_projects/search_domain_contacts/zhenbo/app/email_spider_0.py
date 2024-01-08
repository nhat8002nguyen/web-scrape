from typing import Any, Optional
import scrapy
from datetime import datetime
import csv
import json
import os
from dotenv import load_dotenv
from json import loads
import re
from urllib.parse import urlparse
from scrapy.crawler import CrawlerProcess
import requests
from time import sleep, perf_counter, time
from pandas import DataFrame
from tqdm import tqdm
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed
from domain_timeout_middleware import DomainTimeoutMiddleware
from item_pipeline import XLSXPipeline


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
            with open(f"{os.environ['OUTPUT_PATH']}/{self.csv_file[:self.csv_file.rfind('.')]}_success_urls_{self.start_index}_{self.end_index}.json") as file:
                data = loads(file.read())
                urls = list(data["success_urls"].values())
        except FileNotFoundError:
            findSuccessfulUrls_v1(
                self.csv_file, self.start_index, self.end_index)
            sleep(3)
            urls = list[str]()
            with open(f"{os.environ['OUTPUT_PATH']}/{self.csv_file[:self.csv_file.rfind('.')]}_success_urls_{self.start_index}_{self.end_index}.json") as file:
                data = loads(file.read())
                urls = list(data["success_urls"].values())

        break_second = 10
        print(f"Break {break_second} seconds before moving to next step.")
        sleep(break_second)

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
            if i == 0:
                id = domain + "-" + email + "-" + ", ".join(phones)
                yield {
                    'id': id,
                    'domain': domain,
                    'email': email,
                    'phones': ", ".join(phones),
                }
            else:
                id = domain + "-" + email
                yield {
                    'id': id,
                    'domain': domain,
                    'email': email,
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
    urls = list[str]()
    start_time = perf_counter()
    with open(f"{os.environ['INPUT_PATH']}/{csv_file}", 'r') as file:
        reader = csv.DictReader(file)
        rows = list(reader)

        length = end_index-start_index+1
        urls = list[str]()
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
    }).to_json(f"{os.environ['OUTPUT_PATH']}/{csv_file[:csv_file.rfind('.')]}_success_urls_{start_index}_{end_index}.json")

    cover_elapsed_time = (perf_counter() - start_time)
    print(f"Takes {cover_elapsed_time} seconds to collect success urls!")
    print(
        f"There are {len(urls)} with 200 response status in total {end_index-start_index+1} domain.")


def makeRequests(rows: list[str], start_index: str, end_index: str) -> list[str]:
    urls = list[str]()
    with requests.Session() as session:
        # session.proxies = proxy
        for i in tqdm(range(start_index, end_index+1)):
            row = rows[i]
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
            urls.append(response.url)

    return urls


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
            'CONCURRENT_REQUESTS_PER_DOMAIN': 16,
            'CONCURRENT_REQUESTS_PER_IP': 16,
            'FEED_EXPORT_ENCODING': "utf-8",
            'FEED_FORMAT': 'json',
            'FEEDS':  {
                f'{os.environ["OUTPUT_PATH"]}/output_{start_index}_{end_index}.json': {
                    'format': 'json',
                    'overwrite': True,  # Optional: Set to True if you want to overwrite the file
                },
            },
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
        }
    )
    spider_classes = {
        "email_spider": EmailSpider,
    }
    process.crawl(spider_classes[spider_name],
                  file_name, start_index, end_index)
    process.start()


def remove_duplicates_of_files():
    folder_path = os.environ["OUTPUT_PATH"]
    output_file_pattern = re.compile(r"output_\d+_\d+\.json")

    # Ensure the path is valid
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        # Iterate over all files in the folder
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)

            # Check if it's a file (not a directory)
            if os.path.isfile(file_path) and output_file_pattern.match(filename):
                remove_duplicates_json(file_path)

    # If the path is not valid, print an error message
    else:
        print("Invalid folder path.")


def remove_duplicates_json(path: str):
    try:
        # Assuming the JSON data is in a file called 'data.json'
        with open(path, 'r') as file:
            data = json.load(file)

        # Use a set to track unique entries
        unique_entries = set()
        cleaned_data = []

        for entry in data:
            # Create a tuple of the dictionary values to track uniqueness
            identifier = tuple(entry.values())

            if identifier not in unique_entries:
                cleaned_data.append(entry)
                unique_entries.add(identifier)

        # Now `cleaned_data` contains unique entries
        # Write the cleaned data back to a file or use it as needed
        with open(f'{path[:path.rfind(".")]}_cleaned.json', 'w') as file:
            json.dump(cleaned_data, file, indent=4)

        # Print the cleaned data for review
        print(json.dumps(cleaned_data, indent=4))
    except FileNotFoundError:
        print(f"File not found: {path}")
    except:
        print("Could not remove duplicates!")


def convert_json_to_xlsx_files():
    folder_path = os.environ["OUTPUT_PATH"]
    output_file_pattern = re.compile(r"output_\d+_\d+_cleaned\.json")

    # Ensure the path is valid
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        # Iterate over all files in the folder
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)

            # Check if it's a file (not a directory)
            if os.path.isfile(file_path) and output_file_pattern.match(filename):
                data = None
                with open(file_path, "r") as file:
                    # Parse JSON
                    data = json.loads(file.read())

                if data == None:
                    continue

                # Create a DataFrame from the JSON data
                df = DataFrame(data)

                # Specify the output XLSX file path
                output_path = f"{os.environ['XLSX_OUTPUT_PATH']}/{filename[:filename.rfind('.')]}.xlsx"

                # Write the DataFrame to an Excel file
                df.to_excel(output_path, index=False)

                print(f"Excel file '{output_path}' created successfully.")


if __name__ == "__main__":
    load_dotenv()

    data = None
    with open(os.environ["BATCH_FILE"], "r") as file:
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
    sleep(3)

    print("INFO: Removing duplicates entries in output json files...")
    remove_duplicates_of_files()
    sleep(2)

    print("INFO: Converting JSON to XLSX...")
    convert_json_to_xlsx_files()

    print("DONE!")
