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

from models import ProductCategoryMeta, ProductMetaData
from contants import default_headers
from utilities import replace_dash_with_underscore


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

    categ_slugs = [url[url.rfind("/")+1:] for url in categories_urls]

    for categ_slug in categ_slugs[5:6]:
        all_product_categ_meta = list[ProductCategoryMeta]()
        response = requests.get(
            url=f"https://api.ecom.azrieli.com/shop-api/taxons/by-slug/{categ_slug}",
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
        all_meta_products = list[ProductMetaData]()
        for j in tqdm(range(len(all_product_categ_meta))):
            # get all product
            meta_products = get_meta_products(all_product_categ_meta[j])
            all_meta_products.extend(meta_products)

        save_meta_products(categ_slug, all_meta_products)

    driver.close()


def save_meta_products(categ_slug: str, meta_products: list[ProductMetaData]) -> None:
    products_dicts = []
    for p in meta_products:
        product_dict = {
            "main_categ": p.main_categ,
            "sub_categ1": p.sub_categ1,
            "sub_categ2": p.sub_categ2,
            "sub_categ3": p.sub_categ3,
            "product_code": p.product_code,
            "product_number": p.product_number
        }
        products_dicts.append(product_dict)

    with open(f'./recovery_files/{categ_slug}-meta-products.json', 'w', encoding='utf8') as f:
        dump(products_dicts, f, ensure_ascii=False)


def get_meta_products(categ_meta: ProductCategoryMeta) -> list[ProductMetaData]:
    # fetch products' url from deapest slug
    page = 1
    limit = 40
    response = requests.get(
        url=f"https://api.ecom.azrieli.com/shop-api/search/products",
        headers=default_headers,
        params={
            "locale": "he_IL",
            "taxons[]": replace_dash_with_underscore(categ_meta.deapest_slug),
            "page": page,
            "limit": limit,
            "order_by": "popularity",
            "sort": "desc",
            "relevancyPercentage": 50,
            "baseTaxon": replace_dash_with_underscore(categ_meta.deapest_slug)
        }
    )
    if response.status_code != 200:
        return []
    try:
        json = response.json()
    except:
        print(f"Could not fetch json response from slug {categ_meta.deapest_slug}!")
        return []
    items = json["items"]
    if len(items) <= 0:
        return []

    result = list[ProductMetaData]()
    for i in range(len(items)):
        item = items[i]
        p = ProductMetaData()
        p.main_categ = categ_meta.main_categ
        p.sub_categ1 = categ_meta.sub_categ1
        p.sub_categ2 = categ_meta.sub_categ2
        p.sub_categ3 = categ_meta.sub_categ3
        p.product_code = item["code"]
        p.product_number = (page-1)*limit + (i + 1)

        result.append(p)

    return result


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
