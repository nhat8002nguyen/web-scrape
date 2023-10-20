import scrapy


class BehanceHiresSpider(scrapy.Spider):
    name = "behance_hires"
    allowed_domains = ["www.behance.net"]
    start_urls = ["https://www.behance.net/v3/graphql"]

    def parse(self, response):

        pass
