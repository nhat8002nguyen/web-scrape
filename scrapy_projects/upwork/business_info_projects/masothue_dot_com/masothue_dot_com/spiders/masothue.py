from typing import Iterable
import scrapy
from scrapy.http import Request


class MasothueSpider(scrapy.Spider):
    name = "masothue"
    allowed_domains = ["masothue.com"]
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
        provinces_items = response.xpath("//div[@id='sidebar']//li/a")

        for a_tag in provinces_items[8:10]:
            yield scrapy.Request(
                url=self.domain_url + a_tag.xpath("./@href").get(),
                callback=self.parse_province_page,
                headers=self.headers,
                meta={
                    "province_name": a_tag.xpath("./text()").get()
                },
            )

    def parse_province_page(self, response):
        district_items = response.xpath("//div[@id='sidebar']//li/a")

        for item in district_items:
            yield scrapy.Request(
                url= self.domain_url + item.xpath("./@href").get(),
                callback=self.parse_district_page,
                headers=self.headers,
                meta={
                    "province_name": response.meta["province_name"],
                    'district_name': item.xpath("./text()").get()
                }
            )

    def parse_district_page(self, response):
        ward_a_tags = response.xpath("//div[@id='sidebar']//li/a")

        for tag in ward_a_tags:
            yield scrapy.Request(
                url=self.domain_url + tag.xpath("./@href").get(),
                callback=self.parse_ward_page,
                headers=self.headers,
                meta={
                    "province_name": response.meta["province_name"],
                    "district_name": response.meta["district_name"],
                    "ward_name": tag.xpath("./text()").get() 
                }
            )
    
    def parse_ward_page(self, response):
        for page in range(11)[1:]:
            yield scrapy.Request(
                url=f"{response.url}?page={page}",
                callback=self.parse_companies_list_page,
                headers=self.headers,
                meta={
                    "province_name": response.meta["province_name"],
                    "district_name": response.meta["district_name"],
                    "ward_name": response.meta["ward_name"],
                    "page_num": page,
                }
            )

    def parse_companies_list_page(self, response):
        current_page_number = response.xpath('//span[@class="page-numbers current"]/text()').get()
        path_page_num = response.meta['page_num']
        if int(current_page_number) != path_page_num:
            pass

        companies_a_tags = response.xpath("//div[@class='tax-listing']/div/h3/a")

        for tag in companies_a_tags:
            company_name = tag.xpath("./text()").get()

            company_signs = [
                "CÔNG TY", "CHI NHÁNH", "VĂN PHÒNG", "DOANH NGHIỆP", "DNTN", "CTY", "TNHH", 
                "CỔ PHẦN", "HÃNG", "KINH DOANH", "TẬP ĐOÀN", "HỘ", "ỦY BAN", "UBND", "TRƯỜNG", "VIỆN", 
                "NGÂN HÀNG", "CƠ SỞ", "TRUNG TÂM", "TT", "SIÊU THỊ", "HỢP", "XÃ", "BAN"]
            not_a_company = True
            for sign in company_signs:
                if sign in company_name:
                    not_a_company = False
                    break

            if not_a_company:
                continue

            yield scrapy.Request(
                url=self.domain_url + tag.xpath("./@href").get(),
                callback=self.parse_item,
                headers=self.headers,
                meta={
                    "province_name": response.meta["province_name"],
                    "district_name": response.meta["district_name"],
                    "ward_name": response.meta["ward_name"],
                }
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
                                    place_of_birth = bio_text[year_of_birth_index+7: close_parentheses_i]
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

        
        last_updated_code = response.xpath("//table[@class='table-taxinfo']/tbody/tr/td[1]/strong/text()").get()
        last_updated_date = response.xpath('//table[@class="table-taxinfo"]//em/text()').get()

        company_name = response.xpath('//table[@class="table-taxinfo"]/thead/tr/th/span/text()').get()

        industry_rows = response.xpath('//table[@class="table"]//tr/td//a')
        industry_codes = []
        industry_texts = []
        for industry_row in industry_rows:
            industry_text = industry_row.xpath("./text()").get()
            if len(industry_text) == 4:
                industry_codes.append(industry_text)
            else:
                industry_texts.append(industry_text)
        
        city = ""
        if "Thành phố" in response.meta["district_name"]: 
            city = response.meta["district_name"]

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
            "The last tax code update date": last_updated_date[0:10],
            "Last tax code update time": last_updated_date[11:],
            "Code - Business industry": " - ".join(industry_codes),
            "Industry - Business lines": " - ".join(industry_texts),
            "Type of business": type_of_business,
            "Ward": response.meta["ward_name"],
            "District": response.meta["district_name"],
            "City": city,
            "Conscious": response.meta["province_name"]
        }

        yield data
