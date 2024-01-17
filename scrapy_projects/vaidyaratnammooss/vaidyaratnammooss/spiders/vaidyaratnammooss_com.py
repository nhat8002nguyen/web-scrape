from typing import Iterable
import scrapy
from scrapy.http import Request


class VaidyaratnammoossComSpider(scrapy.Spider):
    name = "vaidyaratnammooss_com"
    allowed_domains = ["shop.vaidyaratnammooss.com"]

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Cookie': 'PHPSESSID=e39oll26gkhd91c3ums6t1odb5; _ga=GA1.1.1463472639.1705486062; _fbp=fb.1.1705486062504.2056812132; _ga_C70JBW73WG=GS1.1.1705499940.3.1.1705499945.0.0.0',
        'Referer': 'https://shop.vaidyaratnammooss.com/',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"'
    }

    def start_requests(self) -> Iterable[Request]:
        return [scrapy.Request(
            url="https://shop.vaidyaratnammooss.com",
            headers=self.headers,
            callback=self.parse
        )]

    def parse(self, response):
        nav_a_items = response.xpath('//div[@class="navcontainer"]//li/a')
        for a in nav_a_items:
            cat = a.xpath("./text()").get()
            yield response.follow(
                url=a.xpath("./@href").get(),
                callback=self.parse_category,
                meta={
                    "cat": cat
                }
            )

    def parse_category(self, response):
        lis = response.xpath(
            '//div[@id="main-wrapper"]//ul[@class="productbox"]/li')
        for li in lis:
            name = li.xpath('./h4/a/text()').get()
            name = name.strip() if name is not None else ""

            price = li.xpath('.//span[@class="productpricewrap"]/text()').get()
            out_of_stock = li.xpath(
                './div[@class="carted" and contains(text(), "Out of stock")]/text()').get()

            pack_size_items = li.xpath(
                './div[@class="productavailablewrap"]//option/text()').getall()

            price_value = price.strip() if price is not None and price.strip() else (
                out_of_stock if out_of_stock else ""
            )

            yield {
                "id": f"card-{response.meta['cat']}-{name}-{price_value}-{','.join(pack_size_items)}",
                "cat": response.meta["cat"],
                "type": "card",
                "name": name,
                "price": price_value,
                "pack_size": " ,".join(pack_size_items)
            }

            detail_url = li.xpath('./h4/a/@href').get()

            yield response.follow(
                url=detail_url,
                callback=self.parse_detail_page,
                meta={
                    "id": f"detail-{response.meta['cat']}-{name}-{price_value}-{','.join(pack_size_items)}",
                    "cat": response.meta["cat"],
                    "name": name,
                    "price": price_value,
                    "pack_size": ", ".join(pack_size_items)
                }
            )

    def parse_detail_page(self, response):
        # XPath expressions to extract the information that follows the headers
        ingredients = response.xpath(
            '//strong[contains(text(), "Ingredients")]/following::text()[2]').extract_first()
        indications = response.xpath(
            '//strong[contains(text(), "Indications")]/following::text()[2]').extract_first()
        dosage = response.xpath(
            '//strong[contains(text(), "Dosage")]/following::text()[2]').extract_first()

        # Process and clean the extracted text if necessary
        ingredients = ingredients.strip() if ingredients else None
        indications = indications.strip() if indications else None
        dosage = dosage.strip() if dosage else None

        # Your code for further processing or saving the data
        yield {
            "id": response.meta["id"],
            "type": "detail",
            "cat": response.meta["cat"],
            "name": response.meta["name"],
            "price": response.meta["price"],
            "pack_size": response.meta["pack_size"],
            'ingredients': ingredients,
            'indications': indications,
            'dosage': dosage
        }
