import scrapy
import pandas


class Crawl500CompaniesLinkSpider(scrapy.Spider):

    name = "crawl_500_companies_sites"

    # get domains list from the domains file
    with open('company_domains.csv', 'r') as file:
        urls = [line.strip(" ") for line in file.read().split('\n')]
        domains = []
        for url in urls:
            if 'http://' in url:
                domains.append(url[7:-1])
            elif 'https://' in url:
                domains.append(url[8:-1])
            else:
                domains.append(url[:-1])
    allowed_domains =['www.zyxware.com']
    allowed_domains.extend(domains)

    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'

    def start_requests(self):
        yield scrapy.Request(
            url="https://www.zyxware.com/articles/4344/list-of-fortune-500-companies-and-their-websites",
            headers={
                'User-Agent': self.user_agent
            },
            callback=self.parse
        ) 

    def parse(self, response):
        company_urls = response.xpath('//table[@class="table"]/tbody/tr/td[3]/text()').getall()

        for url in company_urls:
            # domains.append(url)

            yield scrapy.Request(
                url=url,
                callback=self.parse_item,
                headers={
                    'User-Agent': self.user_agent
                },
            )

        # pandas.DataFrame({
        #     'domain': domains
        # }).to_csv('company_domains_output.csv', index=False, header=False)
        

    def parse_item(self, response):
        yield {
            'url': response.request.url,
            'home_text': response.xpath('//p/text()').getall()
        }
