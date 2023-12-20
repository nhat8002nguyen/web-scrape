

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

from models import ProductCategoryMeta, ProductMetaData, Product, ProductVariant, ProductExportData
from contants import default_headers
from utilities import format_currency

default_headers = {
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


def main():
    driver: WebDriver = Driver(uc=True, no_sandbox=True, headless=True)
    driver_wait = WebDriverWait(driver, 15)

    # debug area

    # debug area

    with open('./recovery_files/fashion-footwear-meta-products.json', 'r', encoding="utf8") as openfile:
        # Reading from json file
        meta_products = load(openfile)

    if len(meta_products) <= 0:
        raise "Not found any meta products!"

    product_export_data = get_products_from_meta(
        driver, driver_wait, meta_products)
    products = product_export_data.products
    products_variants = product_export_data.products_variants
    start_index = product_export_data.start_index
    end_index = product_export_data.end_index

    if len(products) <= 0:
        raise "Fail to process fetching products data!"

    # This is in content spider
    df = pd.DataFrame({
        "Category": [p.main_categ for p in products],
        "Sub Category": [p.sub_categ1 for p in products],
        "Sub Sub Category": [p.sub_categ2 for p in products],
        "Sub Sub Sub Category": [p.sub_categ3 for p in products],
        "Name": [p.name for p in products],
        "Brand": [p.brand for p in products],
        "Regular Price": [p.regular_price for p in products],
        "Sale Price": [p.sale_price for p in products],
        "Description": [p.description for p in products],
        "Images": ["\n".join(p.images) for p in products],
        "brand description": [p.brand_description for p in products],
        "URL": [p.url for p in products],
        "order number in the popularity sort": [p.product_number for p in products],
        "first sentence": [p.description_first_sentence for p in products],
        "variants": [p.variants for p in products]
    })

    df.to_excel(
        f"./content_stage_outputs/fashion-footwear-meta-products-{start_index}-{end_index}.xlsx", index=False)

    if len(products_variants) > 0:
        df = pd.DataFrame({
            "Product Code": [v.product_code for v in products_variants],
            "Variant Code": [p.code for p in products_variants],
            "Name": [p.name for p in products_variants],
            "ean": [p.ean for p in products_variants],
            "image 1": [v.images[0] if 0 < len(v.images) else "" for v in products_variants],
            "image 2": [v.images[1] if 1 < len(v.images) else "" for v in products_variants],
            "image 3": [v.images[2] if 2 < len(v.images) else "" for v in products_variants],
            "image 4": [v.images[3] if 3 < len(v.images) else "" for v in products_variants],
            "image 5": [v.images[4] if 4 < len(v.images) else "" for v in products_variants],
            "image 6": [v.images[5] if 5 < len(v.images) else "" for v in products_variants],
            "image 7": [v.images[6] if 6 < len(v.images) else "" for v in products_variants],
            "image 8": [v.images[7] if 7 < len(v.images) else "" for v in products_variants],
            "image 9": [v.images[8] if 8 < len(v.images) else "" for v in products_variants],
            "image 10": [v.images[9] if 9 < len(v.images) else "" for v in products_variants],
            "image 11": [v.images[10] if 10 < len(v.images) else "" for v in products_variants],
            "image 12": [v.images[11] if 11 < len(v.images) else "" for v in products_variants],
            "image 13": [v.images[12] if 12 < len(v.images) else "" for v in products_variants],
            "image 14": [v.images[13] if 13 < len(v.images) else "" for v in products_variants],
            "image 15": [v.images[14] if 14 < len(v.images) else "" for v in products_variants],
        })

    df.to_excel(
        f"./content_stage_outputs/fashion-footwear-meta-products-variants-{start_index}-{end_index}.xlsx", index=False)


def get_products_from_meta(
    driver: WebDriver, driver_wait: WebDriverWait, items: list[dict]
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
    result = list[Product]()
    variants_data = list[ProductVariant]()
    start_index = 10
    end_index = 19
    for i in tqdm(range(len(items[start_index:end_index+1]))):
        # make request to fetch product data for each item
        item = items[i]

        p = Product()
        p.main_categ = [item["main_categ"] if "main_categ" in item else ""]
        p.sub_categ1 = [item["sub_categ1"] if "sub_categ1" in item else ""]
        p.sub_categ2 = [item["sub_categ2"] if "sub_categ2" in item else ""]
        p.sub_categ3 = [item["sub_categ3"] if "sub_categ3" in item else ""]
        p.product_number = [item["product_number"]
                            if "product_number" in item else ""]

        response = requests.get(
            url=f"https://api.ecom.azrieli.com/shop-api/products/by-code/{item['product_code']}?locale=he_IL",
            headers=default_headers,
            params={
                "locale": "he_IL",
            }
        )

        resp_json = response.json()

        p.name = resp_json["name"]

        if resp_json["brand"] != None:
            p.brand = resp_json["brand"]["name"]
        else:
            p.brand = ""

        if resp_json["priceData"]["strikethroughPrice"] and resp_json["priceData"]["strikethroughPrice"]["current"] > 0:
            p.regular_price = format_currency(
                resp_json["priceData"]["strikethroughPrice"]["current"])
        else:
            p.regular_price = 0

        p.sale_price = format_currency(
            resp_json["priceData"]["finalPrice"]["current"])

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
        p.images = images_dict.values()

        # get variants information
        p.variants = ""
        if "variants" in resp_json and len(resp_json["variants"]) > 0:
            names = list[str]()
            for v in resp_json["variants"]:
                variant = ProductVariant()
                variant.product_code = item["product_code"]
                variant.code = v["code"]
                if v["name"] != None:
                    variant.name = v["name"]
                    names.append(v["name"])
                else:
                    variant.name = ""
                    names.append("")

                variant.images = list[str]()
                savable_imgs = list[str]()
                for img in v["images"]:
                    if images_dict.get(img["path"]):
                        variant.images.append(images_dict[img["path"]])
                    else:
                        savable_imgs.append(img["path"])

                if len(savable_imgs) > 0:
                    saved_imgs_name = saveImagesToFiles(
                        savable_imgs, resp_json["code"], v["code"]).values()
                    variant.images.extend(saved_imgs_name)

                variant.ean = v["ean"]
                variants_data.append(variant)

            p.variants = ", ".join(names)

        p.url = f"https://www.azrieli.com/p/{resp_json['code']}"

        driver.get(url=p.url)

        try:
            popup_close_btn = driver.find_element(
                by=By.XPATH,
                value='//ui-icon[@uidialogclose]'
            )
            popup_close_btn.click()
        except NoSuchElementException:
            pass

        try:
            first_sentence_tag = driver_wait.until(EC.presence_of_element_located((
                By.XPATH,
                '//app-provided-by/a'
            )))
            if first_sentence_tag != None:
                p.description_first_sentence = first_sentence_tag.text
        except:
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
            print(err)
            p.brand_description = ""
            pass

        result.append(p)

    result_data = ProductExportData()
    result_data.products = result
    result_data.products_variants = variants_data
    result_data.start_index = start_index
    result_data.end_index = end_index

    return result_data


def saveImagesToFiles(urls: list[str], p_code: str, v_code: str = "default") -> dict[str, str]:
    images_name = dict[str, str]()
    for i in range(len(urls)):
        resp = requests.get(urls[i])
        saved_name = f"{p_code}-{v_code}-{i+1}.jpg"
        with open(f"./content_stage_outputs/images/{saved_name}", "wb") as f:
            f.write(resp.content)

        images_name[urls[i]] = saved_name

    return images_name


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
