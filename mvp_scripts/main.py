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
from json import load
from random import random

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


class ProductCategoryMeta():
    main_categ: str
    sub_categ1: str
    sub_categ2: str
    sub_categ3: str
    product_slug: str


class Product(ProductCategoryMeta):
    # Category, Sub Category, Sub Sub Category, Sub Sub Sub Category, Name, Brand, Regular Price, Sale Price, Description, EAN(if Available), Images, brand description, URL, order number in the popularity sort, first sentence in the description (it says supplier information - blue color),

    name: str
    brand: str
    regular_price: int
    sale_price: str
    description: str
    EAN: str
    images: list[str]
    brand_description: str
    url: str
    order_number: int
    description_first_sentence: str


def main():
    print("Started the program!")
    dotenv.load_dotenv()

    driver: WebDriver = Driver(uc=True, no_sandbox=True, headless=True)
    default_wait = WebDriverWait(driver, 30)

    base_url = "https://www.azrieli.com"
    driver.get(base_url)

    categories = default_wait.until(EC.presence_of_all_elements_located((
        By.XPATH,
        '//app-bottom-bar//app-bottom-bar-category//a'
    )))
    categories_urls = [categ.get_attribute("href") for categ in categories]

    categ1_slugs = [url[url.rfind("/")+1:] for url in categories_urls]

    all_product_categ_meta = list[ProductCategoryMeta]()
    for categ1_slug in categ1_slugs[:1]:
        response = requests.get(
            url=f"https://api.ecom.azrieli.com/shop-api/taxons/by-slug/{categ1_slug}",
            headers=default_headers,
            params={
                "locale": "he_IL"
            }
        )

        json = response.json()
        children = json["self"]["children"]
        if len(children) <= 0:
            product_categ_metas = getProductsCategMetas(
                json["self"]["name"], "", "", "", json["self"]["slug"])
            all_product_categ_meta.append(product_categ_metas)
            continue

        for child in children:
            children_1 = child["children"]
            if len(children_1) <= 0:
                product_categ_metas = getProductsCategMetas(
                    json["self"]["name"], child["name"], "", "", child["slug"], )
                all_product_categ_meta.append(product_categ_metas)
                continue

            for child_1 in children_1:
                children_2 = child_1["children"]

                if len(children_2) <= 0:
                    product_categ_metas = getProductsCategMetas(
                        json["self"]["name"], child["name"], child_1["name"], "", child_1["slug"])
                    all_product_categ_meta.append(product_categ_metas)
                    continue

                for child_2 in children_2:
                    children_3 = child_2["children"]

                    if len(children_3) <= 0:
                        product_categ_metas = getProductsCategMetas(
                            json["self"]["name"], child["name"], child_1["name"], child_2["name"], child_2["slug"])
                        all_product_categ_meta.append(product_categ_metas)
                        continue

    # loop for each deapest slug
    for meta in all_product_categ_meta[:1]:
        products = getProductsFromMeta(meta)

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
            "EAN": [p.EAN for p in products],
            "Images": [", ".join(p.images) for p in products],
            "brand description": [p.brand_description for p in products],
            "URL": [p.url for p in products],
            "order number in the popularity sort": [p.order_number for p in products],
            "first sentence": [p.description_first_sentence for p in products],
        })

        df.to_excel(f"./output-{random() * 100}.xlsx", index=False)

    driver.close()


def getProductsFromMeta(meta: ProductCategoryMeta) -> list[Product]:
    # fetch products' url from deapest slug
    response = requests.get(
        url=f"https://api.ecom.azrieli.com/shop-api/search/products",
        headers=default_headers,
        params={
            "locale": "he_IL",
            "taxons%5B%5D": meta.product_slug,
            "page": 1,
            "limit": 40,
            "order_by": "popularity",
            "sort": "desc",
            "relevancyPercentage": 50,
            "baseTaxon": meta.product_slug
        }
    )
    if response.status_code != 200:
        return []

    json = response.json()
    items = json["items"]
    if len(items) <= 0:
        return []

    result = list[Product]()
    for i in range(len(items)):
        p = Product()

        p.main_categ = meta.main_categ
        p.sub_categ1 = meta.sub_categ1
        p.sub_categ2 = meta.sub_categ2
        p.sub_categ3 = meta.sub_categ3

        item = items[i]

        p.name = item["name"]

        if item["brand"] != None:
            p.brand = item["brand"]["name"]
        else:
            p.brand = ""

        if item["priceData"]["strikethroughPrice"] and item["priceData"]["strikethroughPrice"]["current"] > 0:
            p.regular_price = item["priceData"]["strikethroughPrice"]["current"]
        else:
            p.regular_price = 0

        p.sale_price = item["priceData"]["finalPrice"]["current"]

        p.description = item["description"]

        p.EAN = ""

        p.images = [img["path"] for img in item["images"]]

        if "short_description" in item:
            p.brand_description = item["short_description"]
        else:
            p.brand_description = ""

        p.url = f"https://www.azrieli.com/p/{item['code']}"

        p.order_number = (json["page"]-1)*json["limit"]+i+1

        p.description_first_sentence = item["description"]

        result.append(p)

    return result


def getProductsCategMetas(
    categ: str, categ1: str, categ2: str, categ3: str, deapest_slug: str
) -> ProductCategoryMeta:
    print(f"categ: {categ}")
    print(f"categ1: {categ1}")
    print(f"categ2: {categ2}")
    print(f"categ3: {categ3}")
    print(f"deapest_slug: {deapest_slug}")
    print(f"-------------------------------------------------")

    p = ProductCategoryMeta()
    p.main_categ = categ
    p.sub_categ1 = categ1
    p.sub_categ2 = categ2
    p.sub_categ3 = categ3
    p.product_slug = deapest_slug

    return p


if __name__ == "__main__":
    main()
