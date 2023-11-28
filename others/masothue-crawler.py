from typing import Iterable
import scrapy
from scrapy.http import Request
from scrapy.crawler import CrawlerProcess
import json
from w3lib.http import basic_auth_header


class MasothueSpider(scrapy.Spider):
    name = "masothue"
    allowed_domains = ["masothue.com"]
    domain_url = "https://masothue.com"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0",
        "Accept-Encoding": "gzip, deflate",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "DNT": "1",
        "Connection": "close",
        "Upgrade-Insecure-Requests": "1"
    }

    def start_requests(self):
        all_urls = []
        for path in [
            "./error_urls_13.json", "./error_urls_14.json", "./error_urls_18.json", "./error_urls_20.json",
            "./error_urls_21.json"]:
            with open(path, "r") as file:
                data = json.load(file)

            urls = [data["url"][key] for key in data["url"]]
            all_urls.extend(urls)

        for url in all_urls:
            self.headers["Proxy-Authorization"] = basic_auth_header(
                "uuwboduo-rotate", "i4h001ld3d7q")

            yield scrapy.Request(
                url=url,
                callback=self.parse_item,
                headers=self.headers,
                meta={"proxy": "http://p.webshare.io:80"}
            )

    def parse_item(self, response):
        row_tags = response.xpath('//table[@class="table-taxinfo"]/tbody/tr')

        nation_name = ""
        shortcut_name = ""
        tax_id = ""
        address = ""
        representative = ""
        year_of_birth = ""
        place_of_birth = ""
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
                    td_texts = row.xpath("./td[2]/text()").getall()
                    if td_texts is not None:
                        bio_text = " ".join(td_texts)
                        if "sinh năm" in bio_text:
                            try:
                                year_of_birth_index = bio_text.index("năm")+4
                                if year_of_birth_index > 0:
                                    close_parentheses_i = bio_text.index(")")
                                    year_of_birth = bio_text[year_of_birth_index: year_of_birth_index+4]
                                    place_of_birth = bio_text[year_of_birth_index +
                                                              7: close_parentheses_i]
                            except ValueError:
                                pass

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

        last_updated_code = response.xpath(
            "//table[@class='table-taxinfo']/tbody/tr/td[1]/strong/text()").get()
        last_updated_date = response.xpath(
            '//table[@class="table-taxinfo"]//em/text()').get()

        company_name = response.xpath(
            '//table[@class="table-taxinfo"]/thead/tr/th/span/text()').get()

        if company_name is None:
            return

        industry_rows = response.xpath('//table[@class="table"]//tr/td//a')
        industry_codes = []
        industry_texts = []
        for industry_row in industry_rows:
            industry_text = industry_row.xpath("./text()").get()
            if len(industry_text) == 4:
                industry_codes.append(industry_text)
            else:
                industry_texts.append(industry_text)

        district_name = response.xpath(
            '//aside[contains(@class, "container")]/h3/a[2]/text()').get()
        city = ""
        if "Thành phố" in district_name:
            city = district_name

        ward = ""
        try:
            ward_start = address.index("Phường")
            ward_length = address[ward_start:].index(",")
            ward = address[ward_start:ward_start+ward_length]
        except:
            pass

        conscious = response.xpath(
            '//aside[contains(@class, "container")]/h3/a[1]/text()').get()

        data = {
            "URL": response.url,
            "Company name": company_name,
            "Internation name": nation_name,
            "Short name": shortcut_name,
            "Tax code": tax_id,
            "Address": address,
            "Representative": representative,
            "Year of birth": year_of_birth,
            "Place of birth": place_of_birth,
            "Phone": telephone,
            "Date of operation": active_date,
            "Management by": managed_by,
            "status": status,
            "Update the last tax code": last_updated_code,
            "The last tax code update date": last_updated_date[0:10] if last_updated_date is not None else "",
            "Last tax code update time": last_updated_date[11:] if last_updated_date is not None else "",
            "Code - Business industry": " - ".join(industry_codes),
            "Industry - Business lines": " - ".join(industry_texts),
            "Type of business": type_of_business,
            "Ward": ward,
            "District": district_name,
            "City": city,
            "Conscious": conscious
        }

        yield data


if __name__ == "__main__":
    process = CrawlerProcess({
        'FEED_EXPORT_ENCODING': "utf-8",
        "FEED_EXPORTERS": {
            'xlsx': 'scrapy_xlsx.XlsxItemExporter',
        },
        'FEED_FORMAT': 'xlsx',
        'FEED_URI': 'error_items.xlsx',
    })
    process.crawl(MasothueSpider)
    process.start()

    print("done")
