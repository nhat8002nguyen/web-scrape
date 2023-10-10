import scrapy

class WorldometersSpider(scrapy.Spider):
    name = "worldometers"
    allowed_domains = ["www.worldometers.info"]
    start_urls = ["https://www.worldometers.info/world-population/population-by-country"]

    def parse(self, response):
        countries = response.xpath('//td/a')

        for country in countries:
            country_name = country.xpath('./text()').get()
            country_link = country.xpath('./@href').get()

            # absolute_link = response.urljoin(country_link)

            yield response.follow(
                url=country_link, 
                callback=self.parse_country, 
                meta={ 'country_name': country_name}
            )

    def parse_country(self, response):
        rows = response.xpath('(//table[contains(@class, "table")])[1]/tbody/tr')

        country_name = response.request.meta["country_name"]

        for row in rows:
            year = row.xpath('./td[1]/text()').get()
            population = row.xpath('./td[2]/strong/text()').get()

            yield {
                "country_name": country_name,
                "year": year,
                "population": population
            }