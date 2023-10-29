from typing import Iterable
import scrapy
from scrapy.http import Request
from scrapy_splash import SplashRequest


USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:48.0) Gecko/20100101 Firefox/48.0'

class EventhunterSpider(scrapy.Spider):
    name = "eventhunter"
    allowed_domains = ["eventhunter.notion.site"]
    # start_urls = ["https://eventhunter.notion.site/eventhunter/9c233ae8a2544cb79631cc714ebe002d?v=5be9e321daa744a6801f3cab9008f0fd"]

    lua_script = '''
        function main(splash)
            assert(splash:go(splash.args.url))
            splash:wait(splash.args.wait)
            return splash:html()
        end
    '''

    def start_requests(self):
        yield SplashRequest(
            url="https://eventhunter.notion.site/eventhunter/9c233ae8a2544cb79631cc714ebe002d?v=5be9e321daa744a6801f3cab9008f0fd", 
            callback=self.parse, 
            endpoint='execute',
            args={'wait': 5, 'lua_source': self.lua_script},
            headers={'User-Agent': USER_AGENT,'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
        )

    def parse(self, response):
        yield {
            'response': response.text
        }
        table_rows = response.xpath("//div[@class='notion-table-view-row']")

        for row in table_rows:
            cells = row.xpath(".//div[@class='notion-table-view-cell']")

            event_name = cells[0].xpath(".//a/span/text()").get()
            
            organizer_type = cells[1].xpath(".//span/text()").get()

            attendees = cells[2].xpath(".//span/text()").getall()

            oppotunities = cells[3].xpath(".//span/text()").getall()

            attendances = cells[4].xpath(".//span/text()").getall()

            start_time = cells[5].xpath("./div/div/div/div/text()").get()

            end_time = cells[6].xpath("./div/div/div/div/text()").get()

            websites = cells[7].xpath("./div/div/div/a/@href").get()

            sponsorship_site = cells[8].xpath("./div/div/div/a/@href").get()

            sponsor_download = cells[9].xpath("./div/div/div/div/span").get()

            linkedin = cells[10].xpath(".//span/a/@href").get()

            attendee_list = cells[11].xpath(".//span/text()").get()

            venue = cells[12].xpath(".//span/text()").get()

            city = cells[13].xpath(".//span/text()").get()

            state_of_province = cells[14].xpath(".//span/text()").get()

            country = cells[15].xpath(".//span/text()").get()

            low_price = cells[16].xpath(".//div[contains(text(), '$')]/text()").get()

            high_price = cells[17].xpath(".//div[contains(text(), '$')]/text()").get()

            early_bird_dealine = cells[18].xpath(".//div[contains(text(), '/')]/text()").get()

            sponsorship_contact_email = cells[19].xpath(".//a[contains(text(), '@')]/text()").get()

            sponsorship_contact_name = cells[20].xpath(".//span/text()").get()

            files_media = cells[21].xpath("").get()

            latest_sponsor_list = cells[22].xpath(".//a/@href").get()

            sponsors_exhibitors = cells[23].xpath(".//span/text()").get()

            peek_url = cells[24].xpath(".//a/@href").get()

            notes = cells[25].xpath(".//span/text()").get()

            yield {
                'event name': event_name
            }