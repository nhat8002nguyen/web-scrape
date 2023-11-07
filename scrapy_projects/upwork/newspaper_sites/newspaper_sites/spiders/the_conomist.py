import scrapy


class TheConomistSpider(scrapy.Spider):
    name = "the_conomist"
    allowed_domains = ["www.economist.comm"]
    start_urls = ["https://www.economist.comm"]

    def parse(self, response):
        pass
