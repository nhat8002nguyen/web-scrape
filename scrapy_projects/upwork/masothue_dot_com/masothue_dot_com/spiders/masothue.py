from typing import Iterable
import scrapy
from scrapy.http import Request
import time


class MasothueSpider(scrapy.Spider):
    name = "masothue"
    allowed_domains = ["masothue.com"]
    # start_urls = ["http://masothue.com/"]
    domain_url = "https://masothue.com"

    headers = {
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0", 
        "Accept-Encoding":"gzip, deflate", 
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", 
        "DNT":"1",
        "Connection":"close", 
        "Upgrade-Insecure-Requests":"1"
    }

    def start_requests(self):
        yield scrapy.Request(
            url="https://masothue.com/",
            headers=self.headers,
            callback=self.parse
        )

    def parse(self, response):
        provinces_urls = response.xpath("//div[@id='sidebar']//li/a/@href").getall()

        for url in provinces_urls[:10]:
            yield scrapy.Request(
                url=self.domain_url + url,
                callback=self.parse_province_page,
                headers=self.headers
            )

    def parse_province_page(self, response):
        district_items = response.xpath("//div[@id='sidebar']//li/a")

        for item in district_items:
            yield scrapy.Request(
                url= self.domain_url + item.xpath("./@href").get(),
                callback=self.parse_district_page,
                headers=self.headers,
                meta={
                    'district_name': item.xpath("./text()").get()
                }
            )

    def parse_district_page(self, response):
        for page in range(11)[1:]:
            yield {
                'district_name': response.meta.get("district_name"),
                'page_url': f"{response.url}?page={page}"
            }