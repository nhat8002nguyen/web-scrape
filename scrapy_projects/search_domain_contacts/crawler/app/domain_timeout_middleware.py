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


class DomainTimeoutMiddleware(HttpCompressionMiddleware):
    def __init__(self, stats=None):
        super().__init__(stats)
        self.domain_timestamps = {}  # Dictionary to store the last timestamp for each domain
        self.domain_timeout = 30.0

    @classmethod
    def from_crawler(cls, crawler):
        middleware = super(DomainTimeoutMiddleware, cls).from_crawler(crawler)
        crawler.signals.connect(middleware.spider_closed,
                                signal=signals.spider_closed)
        return middleware

    def process_request(self, request, spider):
        # Check if the domain has exceeded the timeout
        domain = self._get_domain(request)
        if domain in self.domain_timestamps:
            last_timestamp = self.domain_timestamps[domain]
            elapsed_time = time() - last_timestamp
            if elapsed_time > self.domain_timeout:
                print(
                    f"WARNING: Domain {domain} exceeded timeout. Skipping request.")
                raise IgnoreRequest  # Skip the request

    def process_response(self, request, response, spider):
        # Update the timestamp for the current domain
        domain = self._get_domain(request)
        self.domain_timestamps[domain] = time()
        return response

    def spider_closed(self, spider):
        # Clean up resources when the spider is closed
        self.domain_timestamps.clear()

    def _get_domain(self, request):
        return request.url.split('/')[2]  # Extract domain from the URL
