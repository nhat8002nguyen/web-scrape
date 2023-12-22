

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import undetected_chromedriver as uc

from seleniumbase import Driver

import pandas as pd
import time
import os
import dotenv
import requests
from json import load, dump
from random import random
from tqdm import tqdm
from html2text import HTML2Text

from models import ProductCategoryMeta, ProductVariant, ProductExportData
from contants import default_headers
from utilities import format_currency
from openpyxl.utils.exceptions import IllegalCharacterError 


BATCH_SIZE=1000
START_INDEX=0
END_INDEX=4999

session = requests.Session()
session.headers = {
    "Cache-Control": "no-cache",
    "Accept-Encoding": "gzip, deflate, br",
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "origin": "https://www.azrieli.com",
    "pragma": "no-cache",
    "referer": "https://www.azrieli.com/",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
session.verify = False
session.proxies = {
    "http": "http://webshareio005844-rotate:webshareio005844@p.webshare.io:80",
    "https": "http://webshareio005844-rotate:webshareio005844@p.webshare.io:80",
}


def main():
    dotenv.load_dotenv()
    print("Program was started!")
    # using seleniumbase
    driver: WebDriver = Driver(
        uc=True, no_sandbox=True, headless=False,
        # proxy="webshareio005844-rotate:webshareio005844@p.webshare.io:80",
    )

    # use regular selenium webdriver
    # chrome_options = Options()
    # chrome_options.add_argument('--disable-gpu')
    # chrome_options.add_argument("--headless")
    # chrome_options.add_argument("--no-sandbox")
    # chrome_options.add_argument("--disable-dev-shm-usage")
    # chrome_options.add_argument("--verbose")
    # chrome_options.add_argument("--log-path=chrome_log.txt")
    # driver = webdriver.Chrome(
    #     options=chrome_options
    # )

    print("Web driver connected!")
    driver_wait = WebDriverWait(driver, 15)

    name_category = "home-garden-meta-products"
    with open(f'{os.environ["RECOVERY_PATH"]}/{name_category}.json', 'r', encoding="utf8") as openfile:
        # Reading from json file
        meta_products = load(openfile)

    if len(meta_products) <= 0:
        raise "Not found any meta products!"

    scrape_products_from_meta(
        driver, driver_wait, meta_products,
        name_category
    )

    print("DONE!")
    driver.close()
    session.close()


def scrape_products_from_meta(
    driver: WebDriver, driver_wait: WebDriverWait, items: list[dict],
    name_category: str
) -> ProductExportData:
    '''
        a dict example:
        {
            "main_categ": "לבית ולגן",
            "sub_categ1": "רהיטים",
            "sub_categ2": "מיטות ומזרנים",
            "sub_categ3": "מזרנים",
            "product_code": "AZR03CH44"
        },
    '''
    result = list[ProductVariant]()
    start_index = START_INDEX
    end_index = END_INDEX
    batch_start = start_index
    for i in tqdm(range(len(items[start_index:end_index+1]))):
        # make request to fetch product data for each item
        item = items[i]

        p = ProductVariant()
        p.main_categ = item["main_categ"] if "main_categ" in item else ""
        p.sub_categ1 = item["sub_categ1"] if "sub_categ1" in item else ""
        p.sub_categ2 = item["sub_categ2"] if "sub_categ2" in item else ""
        p.sub_categ3 = item["sub_categ3"] if "sub_categ3" in item else ""
        p.product_code = item["product_code"]
        p.product_number = (item["product_number"]
                            if "product_number" in item else "")
        p.attributes_values = list()

        response = session.get(
            url=f"https://api.ecom.azrieli.com/shop-api/products/by-code/{item['product_code']}?locale=he_IL",
            params={
                "locale": "he_IL",
            },
        )

        resp_json = response.json()

        p.name = resp_json["name"]

        if resp_json["brand"] != None:
            p.brand = resp_json["brand"]["name"]
        else:
            p.brand = ""

        p.sale_price = format_currency(
            resp_json["priceData"]["finalPrice"]["current"])

        if resp_json["priceData"]["strikethroughPrice"] and resp_json["priceData"]["strikethroughPrice"]["current"] > 0:
            p.regular_price = format_currency(
                resp_json["priceData"]["strikethroughPrice"]["current"])
        else:
            p.regular_price = p.sale_price

        p.description = ""
        if "attributes" in resp_json:
            attrs: list = resp_json["attributes"]
            for attr in attrs:
                if "code" in attr and attr["code"] == "description":
                    if "type" in attr and attr["type"] == "textarea":
                        h = HTML2Text()
                        h.ignore_links = True
                        p.description = h.handle(attr["value"])
                    else:
                        p.description = attr["description"]
                    break

        images_dict = saveImagesToFiles(
            [img["path"] for img in resp_json["images"]], resp_json["code"])
        p.images = list(images_dict.values())

        # get variants information
        children = list[ProductVariant]()
        if "variants" in resp_json and len(resp_json["variants"]) > 0:
            p.type = "variable"
            for v in resp_json["variants"]:
                child = ProductVariant()
                child.type = "variation"
                child.sku = f"{p.product_code}-{v['code']}"
                child.name = p.name
                child.parent_code = p.product_code
                if resp_json["priceData"]["strikethroughPrice"] and resp_json["priceData"]["strikethroughPrice"]["current"] > 0:
                    child.regular_price = format_currency(
                        resp_json["priceData"]["strikethroughPrice"]["current"])
                else:
                    child.regular_price = p.regular_price

                sale_price = format_currency(
                    v["priceData"]["finalPrice"]["current"])
                try:
                    if float(sale_price) > 0:
                        child.sale_price = sale_price
                    else:
                        child.sale_price = p.sale_price
                except:
                    child.sale_price = p.sale_price

                count = 0
                for nameAxis in v["nameAxis"].values():
                    option_name = nameAxis["option_name"]
                    option_value = nameAxis["option_value"]
                    if count == 0:
                        child.attr_name1 = option_name
                        child.attr_value1 = option_value
                    if count == 1:
                        child.attr_name2 = option_name
                        child.attr_value2 = option_value
                    if count == 2:
                        child.attr_name3 = option_name
                        child.attr_value3 = option_value
                    if count < len(p.attributes_values):
                        p.attributes_values[count][1].add(option_value)
                    else:
                        p.attributes_values.append(
                            (option_name, set([option_value])))

                    count += 1

                if len(v["images"]):
                    if v["images"][0]["path"] in images_dict:
                        child.image = images_dict[v["images"][0]["path"]]
                    else:
                        values = saveImagesToFiles(
                            [v["images"][0]["path"]], p.product_code, v["code"]).values()
                        if len(values) > 0:
                            child.image = list(values)[0]
                else:
                    child.image = list(p.images)[0]

                children.append(child)

        # get the main product url
        p.url = f"https://www.azrieli.com/p/{resp_json['code']}"

        driver.get(url=p.url)

        try:
            popup_close_btn = driver.find_element(
                by=By.XPATH,
                value='//ui-icon[@uidialogclose]'
            )
            popup_close_btn.click()
        except NoSuchElementException:
            print(f"Fail to close popup of {p.product_code}!")
            pass

        try:
            first_sentence_tag = driver_wait.until(EC.presence_of_element_located((
                By.XPATH,
                '//app-provided-by/a'
            )))
            if first_sentence_tag != None:
                p.description_first_sentence = first_sentence_tag.text
        except:
            print(f"Fail to fetch first sentence of {p.product_code}!")
            p.description_first_sentence = ""
            pass

        try:
            about_tab_tag = driver_wait.until(EC.presence_of_element_located((
                By.XPATH,
                '//app-tabs//div[@class="swiper-wrapper"]//div[@data-swiper-slide-index]//h3[contains(text(), "אודות המותג")]'
            )))
            if about_tab_tag == None:
                raise "Not found about tag"
            about_tab_tag.click()

            about_text_container = driver.find_element(
                by=By.XPATH,
                value='//app-product-tab-item'
            )
            p.brand_description = about_text_container.text
        except Exception as err:
            print(f"Fail to fetch brand description {p.product_code}!")
            p.brand_description = ""
            pass

        result.append(p)
        result.extend(children)

        if (i+1) % BATCH_SIZE == 0: 
            try:
                saveBatchToFile(result, name_category, batch_start, i)
                batch_start = i+1
                result = list[ProductVariant]()
            except Exception:
                print(f"Fail to save batch to file {p.product_code}!")
                continue

    if len(result) > 0:
        saveBatchToFile(result, name_category, batch_start, end_index)

def saveBatchToFile(result: list[ProductVariant], name_category: str, start: int, end: int):
    if len(result) <= 0:
        raise "Fail to process fetching products data!"

    products = result
    start_index = start
    end_index = end

    try:
        df = pd.DataFrame({
            "Type": [p.type for p in products],
            "SKU": [p.sku if p.sku else p.product_code for p in products],
            "Name": [p.name for p in products],
            "First Sentence": [p.description_first_sentence if p.product_code else "" for p in products],
            "Description": [p.description if p.product_code else "" for p in products],
            "Brand": [p.brand if p.product_code else "" for p in products],
            "Brand description": [p.brand_description if p.product_code else "" for p in products],
            "URL": [p.url if p.product_code else "" for p in products],
            "Order number in the popularity sort": [p.product_number if p.product_code else "" for p in products],
            "Sale Price": [p.sale_price for p in products],
            "Regular Price": [p.regular_price for p in products],
            "Category": [p.main_categ if p.product_code else "" for p in products],
            "Sub Category": [p.sub_categ1 if p.product_code else "" for p in products],
            "Sub Sub Category": [p.sub_categ2 if p.product_code else "" for p in products],
            "Sub Sub Sub Category": [p.sub_categ3 if p.product_code else "" for p in products],
            "Images": [p.image if p.image else ", ".join(p.images) for p in products],
            "Parent": [p.parent_code for p in products],
            "Attribute name 1": [p.attr_name1 if p.sku else (
                p.attributes_values[0][0] if len(p.attributes_values) > 0 else ""
            ) for p in products],
            "Attribute value 1": [p.attr_value1 if p.sku else (
                ", ".join(p.attributes_values[0][1]) if len(
                    p.attributes_values) > 0 else ""
            ) for p in products],
            "Attribute name 2": [p.attr_name2 if p.sku else (
                p.attributes_values[1][0] if len(p.attributes_values) > 1 else ""
            )for p in products],
            "Attribute value 2": [p.attr_value2 if p.sku else (
                ", ".join(p.attributes_values[1][1]) if len(
                    p.attributes_values) > 1 else ""
            ) for p in products],
            "Attribute name 3": [p.attr_name3 if p.sku else (
                p.attributes_values[2][0] if len(p.attributes_values) > 2 else ""
            ) for p in products],
            "Attribute value 3": [p.attr_value3 if p.sku else (
                ", ".join(p.attributes_values[2][1]) if len(
                    p.attributes_values) > 2 else ""
            ) for p in products],
        })

        df.to_excel(
            f"{os.environ['CONTENT_PATH']}/{name_category}-{start_index}-{end_index}.xlsx", index=False)
    except IllegalCharacterError:
        print(f"IllegalCharacterError: in {name_category} from {start} to {end}")
        pass


def saveImagesToFiles(urls: list[str], p_code: str, v_code: str = "default") -> dict[str, str]:
    try:
        images_name = dict[str, str]()
        for i in range(len(urls)):
            resp = session.get(
                url=urls[i],
            )
            saved_name = f"{p_code}-{v_code}-{i+1}.jpg"
            with open(f"{os.environ['CONTENT_PATH']}/images/{saved_name}", "wb") as f:
                f.write(resp.content)
                images_name[urls[i]] = saved_name

        return images_name
    except:
        print(f"Fail to save image {p_code}-{v_code} to file!")
        return dict()


def getProductsCategMetas(
    categ: str, categ1: str, categ2: str, categ3: str, deapest_slug: str
) -> ProductCategoryMeta:
    p = ProductCategoryMeta()
    p.main_categ = categ
    p.sub_categ1 = categ1
    p.sub_categ2 = categ2
    p.sub_categ3 = categ3
    p.deapest_slug = deapest_slug

    return p


if __name__ == "__main__":
    main()
