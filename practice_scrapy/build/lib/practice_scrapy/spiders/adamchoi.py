from typing import Iterable
import scrapy
from scrapy.http import Request
from scrapy_splash import SplashRequest


class AdamchoiSpider(scrapy.Spider):
    name = "adamchoi"
    allowed_domains = ["www.adamchoi.co.uk"]
    # start_urls = ["https://www.adamchoi.co.uk/overs/detailed"]

    script = '''
        function main(splash, args)
            splash:private_model_enabled = false
            splash:on_request(function(request)
                request:set_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36')
            end)

            assert(splash:go(args.url))
            assert(splash:wait(3))
            
            match_btns = assert(splash:select_all('label.btn.btn-sm.btn-primary'))
            match_btns[2].mouse_click()
            assert(splash:wait(3))
            
            assert(splash:set_viewport_full())
            
            return {splash:png(), splash:html()}
        end
    '''

    def start_requests(self): 
        yield SplashRequest(
            url="https://www.adamchoi.co.uk/overs/detailed",
            callback=self.parse, 
            endpoint='execute',
            args={
                'lua_source': self.script
            }
        )

    def parse(self, response):
        rows = response.xpath("//tr")

        for row in rows:
            date = row.xpath("./td[1]/text()").get()
            first_team = row.xpath("./td[2]/text()").get()
            scores = row.xpath("./td[3]/text()").get()
            second_team = row.xpath("./td[4]/text()").get()

            yield {
                'date': date,
                'first_team': first_team,
                'scores': scores,
                'second_team': second_team,
            }
