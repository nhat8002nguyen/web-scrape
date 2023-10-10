from typing import Iterable
import scrapy
from scrapy.http import Request
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule


class TdddCrawlerSpider(CrawlSpider):
    name = "tddd_crawler"
    allowed_domains = ["www.thegioididong.com"]
    # start_urls = ["https://www.thegioididong.com/dtdd"]

    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'

    def start_requests(self):
        yield scrapy.Request(
            url="https://www.thegioididong.com/dtdd", 
            headers={
                'User-Agent': self.user_agent
            }
        )

    def set_request_headers(self, request, spider):
        request.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'

        return request

    rules = (
        Rule(
            LinkExtractor(
                restrict_xpaths="//ul[@class='listproduct']/li/a",
            ), 
            callback="parse_item", 
            process_request="set_request_headers",
        ),
    )

    def parse_item(self, response):
        headers = response.request.headers

        p_name = response.xpath('//section[contains(@class, "detail")]/h1/text()').get()
        p_price = response.xpath('//p[@class="box-price-present"]/text()').get()

        p_warranty_policies_items = response.xpath('//ul[@class="policy__list"]/li')
        p_warranty_policies = []
        for item in p_warranty_policies_items:
            texts = [text.strip(" ").strip("\n").strip(" ") for text in item.xpath('./p/text()').getall()]
            p_warranty_policies.append(" ".join(texts))

        yield {
            "name": p_name,
            "present_price": p_price,
            "warranty_policies": p_warranty_policies,
            "User-Agent": headers['User-Agent'].decode('utf-8')
        }
