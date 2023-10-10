from typing import Iterable
import scrapy
from scrapy.http import Request
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule


class TikiMobileProductSpider(CrawlSpider):
    name = "tiki_mobile_product"
    allowed_domains = ["tiki.vn"]

    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'

    def start_requests(self):
        yield scrapy.Request(
                url="https://tiki.vn/dien-thoai-may-tinh-bang/c1789",
                headers={
                    'User-Agent': self.user_agent
                }
            )

    def set_request_headers(self, request, spider):
        request.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'
        return request

    rules = (
        Rule(
            LinkExtractor(restrict_xpaths='//a[contains(@class, "product-item")]'), 
            callback="parse_item", 
            process_request="set_request_headers",
        ),
        Rule(
            LinkExtractor(
                restrict_xpaths='//a[contains(@data-view-id, "product_list_pagination_item") and ./img[@alt="arrow-right"]]'
            ), 
        )
    )

    def parse_item(self, response):
        yield {
            'title': response.xpath('//h1[contains(@class, "Title__TitledStyled")]/text()').get(),
            'current_price': (
                response.xpath('//div[contains(@class, "product-price__current-price")]/text()').get() + 
                response.xpath('//div[contains(@class, "product-price__current-price")]/sup/text()').get() 
            ),
            'seller': response.xpath('//span[contains(@class, "seller-name")]/a/span/text()').get()
        }
