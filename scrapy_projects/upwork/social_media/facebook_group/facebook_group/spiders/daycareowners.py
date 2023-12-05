import scrapy


class DaycareownersSpider(scrapy.Spider):
    name = "daycareowners"
    allowed_domains = ["www.facebook.com"]
    start_urls = ["https://www.facebook.com/groups/daycareowners"]

    def parse(self, response):
        pass
