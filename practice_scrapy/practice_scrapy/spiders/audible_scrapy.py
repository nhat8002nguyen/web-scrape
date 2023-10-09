from typing import Iterable
import scrapy


class AudibleScrapySpider(scrapy.Spider):
    name = "audible_scrapy"
    allowed_domains = ["www.audible.com"]
    # start_urls = ["https://www.audible.com/search"]

    def start_requests(self):
        yield scrapy.Request(
                url="https://www.audible.com/search",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
                },
                callback=self.parse
            )

    def parse(self, response):
        headers = response.request.headers

        product_items = response.xpath(
            "//div[@data-widget='productList']//li[contains(@class, 'productListItem')]"
        )

        for prd in product_items:
            title = prd.xpath(".//h3/a/text()").get()
            authors = prd.xpath(".//li[contains(@class, 'authorLabel')]//a/text()").getall()
            length = prd.xpath(".//li[contains(@class, 'runtimeLabel')]/span/text()").get()

            yield {
                'title': title,
                'authors': authors,
                'length': length,
            }

        pagingContainer = response.xpath("//ul[contains(@class, 'pagingElements')]")
        
        next_page_relative_url = pagingContainer.xpath(".//span[contains(@class, 'nextButton')]/a/@href").get()

        disabled_button = pagingContainer.xpath(".//span[contains(@class, 'nextButton')]/a/@aria-disabled").get()

        if disabled_button is None:
            yield response.follow(
                url=next_page_relative_url, 
                callback=self.parse, 
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'
                })
