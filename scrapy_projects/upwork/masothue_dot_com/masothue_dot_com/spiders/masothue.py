from typing import Iterable
import scrapy
from scrapy.http import Request
import time


class MasothueSpider(scrapy.Spider):
    name = "masothue"
    allowed_domains = ["masothue.com"]
    # start_urls = ["http://masothue.com/"]
    domain_url = "https://masothue.com"

    headers = {
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0", 
        "Accept-Encoding":"gzip, deflate", 
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", 
        "DNT":"1",
        "Connection":"close", 
        "Upgrade-Insecure-Requests":"1"
    }

    def start_requests(self):
        yield scrapy.Request(
            url="https://masothue.com/",
            headers=self.headers,
            callback=self.parse
        )

    def parse(self, response):
        provinces_urls = response.xpath("//div[@id='sidebar']//li/a/@href").getall()

        for url in provinces_urls[:5]:
            yield scrapy.Request(
                url=self.domain_url + url,
                callback=self.parse_province_page,
                headers=self.headers
            )

    def parse_province_page(self, response):
        district_items = response.xpath("//div[@id='sidebar']//li/a")

        for item in district_items:
            yield scrapy.Request(
                url= self.domain_url + item.xpath("./@href").get(),
                callback=self.parse_district_page,
                headers=self.headers,
                meta={
                    'district_name': item.xpath("./text()").get()
                }
            )

    def parse_district_page(self, response):
        for page in range(11)[1:2]:
            yield scrapy.Request(
                url=f"{response.url}?page={page}",
                callback=self.parse_companies_list_page,
                headers=self.headers,
                meta={
                    'page_num': page
                }
            )

    def parse_companies_list_page(self, response):
        current_page_number = response.xpath('//span[@class="page-numbers current"]/text()').get()
        path_page_num = response.meta['page_num']
        if int(current_page_number) != path_page_num:
            pass

        companies_urls = response.xpath("//div[@class='tax-listing']/div/h3/a/@href").getall()

        for url in companies_urls:
            yield scrapy.Request(
                url=self.domain_url + url,
                callback=self.parse_item,
                headers=self.headers
            )

    def parse_item(self, response):
        row_tags = response.xpath('//table[@class="table-taxinfo"]/tbody/tr')

        nation_name = ""
        shortcut_name = ""
        tax_id = ""
        address = ""
        representative = ""
        telephone = ""
        active_date = ""
        managed_by = ""
        type_of_business = ""
        status = ""

        for row in row_tags[:10]:
            entry = row.xpath("./td[1]/text()").get()
            if entry is not None:
                if "Tên quốc tế" in entry:
                    nation_name = row.xpath("./td[2]/span/text()").get()

                if "Tên viết tắt" in entry:
                    shortcut_name = row.xpath("./td[2]/span/text()").get() 

                if "Mã số thuế" in entry:
                    tax_id = row.xpath("./td[2]/span/text()").get()

                if "Địa chỉ" in entry:
                    address = row.xpath("./td[2]/span/text()").get()

                if "Người đại diện" in entry:
                    representative = row.xpath("./td[2]/span/a/text()").get()

                if "Điện thoại" in entry:
                    telephone = row.xpath("./td[2]/span/text()").get()

                if "Ngày hoạt động" in entry:
                    active_date = row.xpath("./td[2]/span/text()").get()

                if "Quản lý bởi" in entry:
                    managed_by = row.xpath("./td[2]/span/text()").get()

                if "Loại hình DN" in entry:
                    type_of_business = row.xpath("./td[2]/a/text()").get()

                if "Tình trạng" in entry:
                    status = row.xpath("./td[2]/a/text()").get()

        last_updated_date = response.xpath('//table[@class="table-taxinfo"]//em/text()').get()
        company_name = response.xpath('//table[@class="table-taxinfo"]/thead/tr/th/span/text()').get()
        career_tags = response.xpath('//table[@class="table"]//tr/td/strong/a')

        career_code = ""
        career_text = ""
        if career_tags is not None and len(career_tags) > 0:
            career_code = career_tags[0].xpath('./text()').get()
            career_text = career_tags[1].xpath('./text()').get()

        data = {
            "company_name": company_name,
            "nation_name": nation_name,
            "shortcut_name": shortcut_name,
            "tax_id": tax_id,
            "address": address,
            "representative": representative,
            "telephone": telephone,
            "active_date": active_date,
            "managed_by": managed_by,
            "type_of_business": type_of_business,
            "status": status,
            "last_updated_date": last_updated_date,
            "career_code": career_code,
            "career_text": career_text
        }

        yield data