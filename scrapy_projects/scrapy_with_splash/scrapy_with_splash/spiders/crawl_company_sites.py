from typing import Iterable
import scrapy
from scrapy.http import Request
from scrapy_splash import SplashRequest


class CrawlCompanySitesSpider(scrapy.Spider):
    name = "crawl_company_sites"

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

    lua_scripts = '''
        function main(splash, args)
            assert(splash:go{
                url=args.url,
                headers={
                    ['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36'
                }
            })

            assert(splash:wait(0.5))
            local scroll_to = splash:jsfunc('window.scrollTo')
            local get_scroll_height = splash:jsfunc('function(){ return document.body.scrollHeight; }')
            scroll_to(0, get_scroll_height())
            assert(splash:wait(2))
            
            last_height = get_scroll_height()
            while true do
                scroll_to(0, get_scroll_height())
                splash:wait(3)
                current_height = get_scroll_height()
                
                if current_height == last_height then
                    break
                else
                    last_height = current_height
                end
            end
                
            return {
                html = splash:html(),
                png = splash:png(),
                har = splash:har(),
            }
        end
    '''

    def parse(self, response):
        company_urls = response.xpath('//table[@class="table"]/tbody/tr/td[3]/text()').getall()

        for url in company_urls:
            # domains.append(url)

            yield SplashRequest(
                url=url,
                endpoint='execute',
                args={ 'lua_script': self.lua_scripts },
                callback=self.parse_item
            )


    def parse_item(self, response):
        texts = []
        texts.extend([text.strip('\n\r\t ') for text in response.xpath("//p/text()").getall()])
        texts.extend([text.strip('\n\r\t ') for text in response.xpath("//h1/text()").getall()])
        texts.extend([text.strip('\n\r\t ') for text in response.xpath("//h2/text()").getall()])
        texts.extend([text.strip("\n\r\t ") for text in response.xpath("//h3/text()").getall()])
        texts.extend([text.strip("\n\r\t ") for text in response.xpath("//h4/text()").getall()])
        texts.extend([text.strip("\n\r\t ") for text in response.xpath("//h5/text()").getall()])
        texts.extend([text.strip("\n\r\t ") for text in response.xpath("//a/text()").getall()])
        texts.extend([text.strip("\n\r\t ") for text in response.xpath("//span/text()").getall()])
        texts.extend([text.strip("\n\r\t ") for text in response.xpath("//strong/text()").getall()])
        texts.extend([text.strip("\n\r\t ") for text in response.xpath("//em/text()").getall()])
        texts.extend([text.strip("\n\r\t ") for text in response.xpath("//u/text()").getall()])
        texts.extend([text.strip("\n\r\t ") for text in response.xpath("//s/text()").getall()])

        texts = [text for text in texts if text != ""]
        

        yield {
            'url': response.request.url,
            'text': texts
        }

