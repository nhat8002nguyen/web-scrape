import scrapy


class MasothueSpider(scrapy.Spider):
    name = "masothue"
    allowed_domains = ["masothue.com"]
    start_urls = ["http://masothue.com/"]

    def parse(self, response):
        pass
