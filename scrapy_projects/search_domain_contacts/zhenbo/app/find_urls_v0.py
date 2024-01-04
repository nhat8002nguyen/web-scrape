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
from requests.exceptions import ConnectionError, ReadTimeout
from time import sleep, perf_counter, time
from pandas import DataFrame
import argparse
from tqdm import tqdm
import multiprocessing
from scrapy.utils.project import get_project_settings
from concurrent.futures import ThreadPoolExecutor, as_completed
from scrapy.exceptions import IgnoreRequest
from scrapy import signals
from scrapy.downloadermiddlewares.httpcompression import HttpCompressionMiddleware

def findSuccessfulUrls(csv_file: str, start_index: str, end_index: str):
    urls = list[str]()
    session = requests.Session()
    # session.proxies = proxy
    start_time = perf_counter()
    with open(f"{os.environ['INPUT_PATH']}/{csv_file}", 'r') as file:
        reader = csv.DictReader(file)
        rows = list(reader)

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

    cover_elapsed_time = (perf_counter() - start_time)
    print(f"Takes {cover_elapsed_time} seconds to collect success urls!")
    print(
        f"There are {len(urls)} with 200 response status in total {end_index-start_index+1} domain.")