from typing import Iterable
import scrapy
from scrapy.http import Request
from random import choice
from json import load
from scrapy_selenium import SeleniumRequest


class DaycareownersSpider(scrapy.Spider):
    name = "daycareowners"
    allowed_domains = ["www.facebook.com"]
    # start_urls = ["https://www.facebook.com/groups/daycareowners"]

    base_url = "https://www.facebook.com"

    headers = {
        "Accept-Encoding": "gzip, deflate",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "DNT": "1",
        "Connection": "close",
        "Upgrade-Insecure-Requests": "1"
    }

    def get_headers(self):
        random_user_agent = choice(fake_user_agents)

        self.headers["User-Agent"] = random_user_agent
        return self.headers

    def start_requests(self):
        with open("./postLinks-58.txt", "r") as file:
            links = file.readlines()

        with open("./fb-cookies.json") as file:
            cookies_data = load(file)

        for link in links[0:1]:
            yield scrapy.Request(
                url=self.base_url + link,
                headers=self.get_headers(),
                cookies=cookies_data,
                callback=self.parse
            )

    def parse(self, response):
        print(response.xpath("//h1"))


fake_user_agents = [
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5615.138 Safari/537.36 AVG/112.0.21002.139",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.34 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.53 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5837.210 Safari/537.36 OPR/100.0.4334.120",
    "Mozilla/5.0 (Windows NT 10.0; Win64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.5840.194 Safari/537.36 OPR/98.0.3535.107",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4476.33 UBrowser/6.2.3964.2 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3864.33 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3722.20 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3689.97 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4290.130 Safari/537.36 Core/1.70.3722.400 QQBrowser/10.5.3739.400",
    "Mozilla/5.0 (Windows; U; Windows NT 5.0; en-US; rv:1.4b) Gecko/20030516 Mozilla Firebird/0.6",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3992.125 Safari/537.36 QIHU 360EE",
    "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Internet Explorer/74.0.386.84 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.3526.46 Safari/537.36 QIHU 360EE",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Safari/82.0.1630.75 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.4439.136 Safari/537.36 QIHU 360EE",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.3481.120 Safari/537.36 QIHU 360EE",
]
