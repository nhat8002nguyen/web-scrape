import scrapy
import json
import requests

class QuotesScraperSpider(scrapy.Spider):
    name = "quotes_scraper"
    allowed_domains = ["quotes.toscrape.com"]
    start_urls = ["https://quotes.toscrape.com/api/quotes?page=1"]

    def parse(self, response):
        json_response = json.loads(response.body)

        quotes = json_response.get('quotes')

        for quote in quotes:
            yield {
                'author': quote.get('author').get('name'),
                'tags': quote.get('tags'),
                'quote': quote.get('text')
            }

        has_next = json_response.get('has_next')
        next_page = json_response.get('page')+1
        next_page_url = f"https://quotes.toscrape.com/api/quotes?page={next_page}"

        if has_next:
            yield scrapy.Request(url=next_page_url)    
