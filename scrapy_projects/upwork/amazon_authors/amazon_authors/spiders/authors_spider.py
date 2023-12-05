import scrapy
from scrapy_selenium import SeleniumRequest
from random import choice
from logging import ERROR

fake_user_agents = [
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5615.138 Safari/537.36 AVG/112.0.21002.139",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.34 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.53 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5837.210 Safari/537.36 OPR/100.0.4334.120",
    "Mozilla/5.0 (Windows NT 10.0; Win64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.5840.194 Safari/537.36 OPR/98.0.3535.107",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4476.33 UBrowser/6.2.3964.2 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3864.33 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3722.20 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3689.97 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4290.130 Safari/537.36 Core/1.70.3722.400 QQBrowser/10.5.3739.400",
    "Mozilla/5.0 (Windows; U; Windows NT 5.0; en-US; rv:1.4b) Gecko/20030516 Mozilla Firebird/0.6",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3992.125 Safari/537.36 QIHU 360EE",
    "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Internet Explorer/74.0.386.84 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.3526.46 Safari/537.36 QIHU 360EE",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Safari/82.0.1630.75 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.4439.136 Safari/537.36 QIHU 360EE",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.3481.120 Safari/537.36 QIHU 360EE",
]


class AuthorsSpider(scrapy.Spider):
    name = 'authors_spider'
    headers = {
        "Accept-Encoding": "gzip, deflate",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "DNT": "1",
        "Connection": "close",
        "Upgrade-Insecure-Requests": "1"
    }

    def get_headers(self):
        random_user_agent = choice(fake_user_agents)

        self.headers["User-Agent"] = random_user_agent
        return self.headers

    def start_requests(self):
        yield scrapy.Request(
            url="https://www.amazon.com/s?k=self+published+books+on+amazon&crid=1U0JOKQUVIARF&sprefix=self-published+books%2Caps%2C352&ref=nb_sb_ss_ts-doa-p_2_20",
            headers=self.get_headers(),
            callback=self.parse,
        )

    def parse(self, response):
        # Loop through each author's info section
        book_items = response.xpath(
            '//div[@data-component-type="s-search-result"]')
        for book in book_items:
            # Extract the details needed and yield the item
            book_title = book.xpath(
                './/div[@data-cy="title-recipe"]/h2/a/span/text()').get(),

            name_tags = book.xpath(
                './/div[@data-cy="title-recipe"]//div[contains(@class, "a-color-secondary")]/*[contains(@class, "a-size-base")]')
            names = "".join([tag.xpath("./text()").get() for tag in name_tags])
            try:
                names = names[names.index("by")+3:]
            except:
                self.log(f"Fail getting authors of {book_title}", ERROR)
                pass

            details_url = book.xpath(
                './/span[@data-component-type="s-product-image"]/a[contains(@class, "a-link-normal")]/@href').get()

            if names != "":
                yield scrapy.Request(
                    url="https://www.amazon.com" + details_url,
                    callback=self.parse_details,
                    meta={
                        "names": names,
                        "book_title": book_title
                    },
                    headers=self.get_headers()
                )

            # Possibly follow to the next page if there is one
            next_page = response.xpath(
                '//a[contains(@class, "s-pagination-next")]').attrib['href']
            if next_page is not None:
                yield response.follow(
                    url=next_page, 
                    callback=self.parse, 
                    headers=self.get_headers()
                )

    def parse_details(self, response):
        book_genres = response.xpath(
            '//div[@data-feature-name="detailBullets"]/ul/li//ul/li//a/text()').getall()

        if len(book_genres) > 0:
            yield {
                "Book title": response.meta["book_title"],
                "Authors": response.meta["names"],
                "Book genres": " - ".join(book_genres),
                "Book link": response.url,
            }
