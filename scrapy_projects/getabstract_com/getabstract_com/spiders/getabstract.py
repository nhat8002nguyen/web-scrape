import scrapy
from json import loads
import requests
from bs4 import BeautifulSoup


class GetabstractSpider(scrapy.Spider):
    name = "getabstract"
    allowed_domains = ["www.getabstract.com"]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0",
        "Accept-Encoding": "gzip, deflate",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "DNT": "1",
        "Connection": "close",
        "Upgrade-Insecure-Requests": "1"
    }

    def start_requests(self):
        self.cookies = None
        with open("./cookies.json", "r") as file:
            self.cookies = list(loads(file.read()))

            self.session = requests.Session()
            for cookie in self.cookies:
                self.session.cookies.set(
                    name=cookie['name'],
                    value=cookie['value'],
                    domain=cookie.get('domain'),
                    path=cookie.get('path'),
                    secure=cookie.get('secure'),
                    # Add additional attrs as necessary
                    rest={'HttpOnly': cookie.get('httpOnly')}
                )

        yield scrapy.Request(
            url="https://www.getabstract.com/en/explore",
            headers=self.headers,
            callback=self.parse,
            cookies=self.cookies
        )

    def parse(self, response):
        category_list = response.xpath(
            "//div[@role='main']//div[contains(@class, 'row')]/div[@class='col']/a/@href").getall()

        for category in category_list[0:2]:
            yield response.follow(
                url=category,
                callback=self.parse_category
            )

    def parse_category(self, response):
        book_urls = response.xpath(
            "//div[@role='main']//div[contains(@class, 'row')]/div[@class='col']//a/@href").getall()

        category = response.xpath(
            "//div[@class='channel-header__title']/h1/text()").get()

        for book in book_urls:
            yield response.follow(
                url=book,
                callback=self.activate_content,
                meta={
                    'category': category
                }
            )

    def activate_content(self, response):
        url: str = response.url

        activate_relative_url = response.xpath(
            '//div[contains(@class, "abstractUpgrade")]/form/@action').get()
        if activate_relative_url != None:
            try:
                activate_url = f"https://www.getabstract.com{activate_relative_url}"
                activate_resp = self.session.post(
                    url=activate_url,
                )

                if activate_resp.ok == False:
                    self.logger.error(f"Fail to activate the url: {url}")
                    return

                result = self.parse_activated_content(
                    response, activate_resp.text)
                yield result

                self.logger.info(f"Success to activate the url: {url}")
                return
            except Exception as ex:
                self.logger.error(ex)

        yield response.follow(
            url=url,
            callback=self.parse_content,
            dont_filter=True,
            meta={
                'category': response.meta['category']
            }
        )

    def parse_activated_content(self, response, content: str):
        soup = BeautifulSoup(content, 'html.parser')

        try:
            book_name = soup.select_one(
                'div.sumpage-header h1').get_text(strip=True)
        except:
            book_name = ""
            self.logger.error(f"Fail to get book name")

        try:
            short_title = soup.select_one(
                'div.sumpage-header h2').get_text(strip=True)
        except:
            short_title = ""
            self.logger.error(f"Fail to get short title")

        try:
            authors = [author.get_text(strip=True) for author in soup.select(
                'div.sumpage-header__authors a')]
            authors = ", ".join(authors)
        except:
            authors = ""
            self.logger.error(f"Fail to get authors")

        try:
            about_authors = " ".join([p.get_text(strip=True)
                                     for p in soup.select('p#aboutAuthor')])
        except:
            about_authors = ""
            self.logger.error(f"Fail to get about authors")

        try:
            recommendation = " ".join([p.get_text(strip=True) for p in soup.select(
                "div[role='main'] .recommendation p")])
            self.logger.debug(f"Recommendation: {recommendation[:100]}")
        except:
            recommendation = ""
            self.logger.error(f"Fail to get recommendation")

        try:
            takeaways = " ".join([li.get_text(strip=True) for li in soup.select(
                "div[role='main'] ul.takeaways li")])
            self.logger.debug(f"Takeaways: {takeaways[:100]}")
        except:
            takeaways = ""
            self.logger.error(f"Fail to get takeaways")

        try:
            summary = " ".join([div.get_text(strip=True) for div in soup.select(
                "div[role='main'] .summary-typography div")])
            self.logger.debug(f"Summary: {summary[:100]}")
        except:
            summary = ""
            self.logger.error(f"Fail to get summary")

        return {
            "Category": response.meta["category"],
            "Book name": book_name,
            "Short title": short_title,
            "Authors": authors,
            "About the authors": about_authors,
            "Recommendation": recommendation,
            "Takeaways": takeaways,
            "summary": summary
        }

    def parse_content(self, response):
        try:
            book_name = response.xpath(
                '//div[@class="sumpage-header"]//h1/text()').get().strip()
        except:
            book_name = ""
            self.logger.error(f"Fail to get book name of {response.url}")

        try:
            short_title = response.xpath(
                '//div[@class="sumpage-header"]//h2/text()').get().strip()
        except:
            short_title = ""
            self.logger.error(f"Fail to get short title of {response.url}")

        try:
            authors = response.xpath(
                '//div[@class="sumpage-header__authors"]/a/text()').getall()
            authors = ", ".join(authors).strip()
        except:
            authors = ""
            self.logger.error(f"Fail to get author of {response.url}")

        try:
            about_authors = response.xpath(
                '//p[@id="aboutAuthor"]//text()').getall()
            about_authors = "".join(about_authors).strip()
        except:
            about_authors = ""
            self.logger.error(f"Fail to get about authors of {response.url}")

        try:
            recommendation = response.xpath(
                "//div[@role='main']//div[contains(@class, 'recommendation')]/p/text()").getall()
            recommendation = "".join(recommendation).strip()
            self.logger.debug(f"Recommendation: {recommendation[:100]}")
        except:
            self.logger.error(f"Fail to get recommendation of {response.url}")
            recommendation = ""

        try:
            takeaways = response.xpath(
                "//div[@role='main']//ul[contains(@class, 'takeaways')]//text()").getall()
            takeaways = "".join(takeaways).strip()
            self.logger.debug(f"Takeaways: {takeaways[:100]}")
        except:
            self.logger.error(f"Fail to get takeaways of {response.url}")
            takeaways = ""

        try:
            summary = response.xpath(
                "//div[@role='main']//div[@class='summary-typography']//text()"
            ).getall()
            summary = "".join(summary).strip()
            self.logger.debug(f"Summary: {summary[:100]}")
        except:
            self.logger.error(f"Fail to get summary of {response.url}")
            summary = ""

        yield {
            "Category": response.meta["category"],
            "Book name": book_name,
            "Short title": short_title,
            "Authors": authors,
            "About the authors": about_authors,
            "Recommendation": recommendation,
            "Takeaways": takeaways,
            "summary": summary
        }
