from typing import Iterable
import scrapy
from scrapy.http import Request


class CaravanqldSpider(scrapy.Spider):
    name = "caravanqld"
    allowed_domains = ["www.caravanqld.com.au"]

    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'

    def start_requests(self):
        yield scrapy.Request(
            url="https://www.caravanqld.com.au/park",
            callback=self.parse,
            headers={
                'User-Agent': self.user_agent
            }
        )


    def parse(self, response):
        items = response.xpath("//div[contains(@class, 'project item')]")
        for item in items:
            url = item.xpath('./div/a/@href').get()
            yield scrapy.Request(
                url=url,
                callback=self.parse_item,
                headers={
                    'User-Agent': self.user_agent
                }
            )

        next_page_url = response.xpath("//a[@class='next page-numbers']/@href").get()

        if next_page_url is not None:
            yield scrapy.Request(
                url=next_page_url,
                callback=self.parse,
                headers={
                    'User-Agent': self.user_agent
                }
            )
            

    def parse_item(self, response):
        yield {
            'title': response.xpath("//div[@class='showdesktop']/h1/text()").get(),
            'postal_address': response.xpath("//div[@class='showdesktop']/text()").getall()[1].strip('\n '),
            'email': response.xpath("//section/div[contains(@class, 'container')]/div[@class='row']/div[contains(@class, 'col-md-4')]/a[3]/@href").get()[7:]
        }