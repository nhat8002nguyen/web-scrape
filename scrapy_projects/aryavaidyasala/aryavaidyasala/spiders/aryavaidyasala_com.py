from typing import Iterable
import scrapy
from scrapy.http import Request, Response
from random import choice

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from seleniumbase import Driver

import pandas as pd
from time import sleep, perf_counter
import os
import dotenv
from tqdm import tqdm


class Card():
    def __init__(self, img: str, name: str, price: str, p_url: str, cat: str) -> None:
        self.img = img
        self.name = name
        self.price = price
        self.p_url = p_url
        self.cat = cat


class Detail(Card):
    def __init__(self, img: str, name: str, price: str, p_url: str, cat: str, sub_imgs: list[str], pack_size: str, ingredients: str, description: str, dosage: str, caution: str) -> None:
        super().__init__(img, name, price, p_url, cat)
        if sub_imgs == None:
            self.sub_imgs = []
        else:
            self.sub_imgs = sub_imgs

        self.pack_size = pack_size
        self.ingredients = ingredients
        self.description = description
        self.dosage = dosage
        self.caution = caution


class AryavaidyasalaComSpider(scrapy.Spider):
    name = "aryavaidyasala_com"
    allowed_domains = ["shop.aryavaidyasala.com"]
    start_urls = ["https://shop.aryavaidyasala.com"]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0",
        "Accept-Encoding": "gzip, deflate",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "DNT": "1",
        "Connection": "close",
        "Upgrade-Insecure-Requests": "1"
    }

    proxies = []
    with open(f"{os.environ['ROOT_PATH']}/proxies.txt") as file:
        proxies = file.readlines()
        proxies = [p.strip() for p in proxies if p.strip()]

    def parse(self, resp: Response):
        driver = None
        wait = None
        for i in tqdm(range(8, 22)):
            proxy_index = 0
            while True:
                try:
                    if driver != None:
                        driver.close()
                        driver.quit()
                        driver = None
                        sleep(3)

                    proxy = self.proxies[proxy_index]
                    proxy_index += 1
                    if proxy_index == 200:
                        proxy_index = 0

                    driver: WebDriver = Driver(
                        uc=True, no_sandbox=True, headless=True,
                        proxy=proxy
                    )
                    wait = WebDriverWait(driver, 60)

                    driver.get(
                        "https://shop.aryavaidyasala.com/medicines.html")
                    lis = wait.until(EC.presence_of_all_elements_located((
                        By.XPATH,
                        '//div[@role="tabpanel"]/ol/li'
                    )))
                    if len(lis) > 0:
                        self.logger.info("Success to load website!")
                        break
                except:
                    self.logger.error("Failed to get page, retrying...")
                    continue

            li = lis[i]
            cat_url = li.find_element(
                by=By.XPATH,
                value="./a"
            )
            if cat_url != None:
                cat_url = cat_url.get_attribute("href")
            else:
                continue

            cards = self.process_category(driver, cat_url)

            for card in cards:
                yield {
                    "id": card.cat+card.name+card.price,
                    "type": "card",
                    "product_url": card.p_url,
                    "image": card.img,
                    "name": card.name,
                    "price": card.price,
                    "cat": card.cat
                }

            for j in tqdm(range(len(cards))):
                c = cards[j]
                try:
                    detail = self.process_detail_page(
                        driver=driver,
                        wait=wait,
                        url=c.p_url,
                    )
                except:
                    self.logger.error(
                        f"Failed to get detail of product: {c.p_url}")
                    continue

                yield {
                    "id": c.cat+detail.name+detail.price,
                    "type": "detail",
                    "product_url": detail.p_url,
                    "images": "\n".join(detail.sub_imgs),
                    "cat": c.cat,
                    "name": detail.name,
                    "price": detail.price,
                    "pack_size": detail.pack_size,
                    "ingredients": detail.ingredients,
                    "indications": detail.description,
                    "dosage": detail.dosage,
                    "caution": detail.caution
                }

                sleep(2)

            sleep(5)

        driver.close()

    def process_category(self, driver: WebDriver, cat_url: str) -> list[Card]:
        driver.get(cat_url)

        cat = driver.find_element(
            by=By.CSS_SELECTOR,
            value='h1[class="page-title"]>span'
        )
        if cat != None:
            cat = cat.text

        cards = []
        while True:
            p_items = driver.find_elements(
                by=By.CSS_SELECTOR,
                value='ol.product-items>li'
            )
            for item in p_items:
                try:
                    img = item.find_element(
                        by=By.CSS_SELECTOR,
                        value='img.product-image-photo'
                    )
                    if img != None:
                        img = img.get_attribute("src")
                except NoSuchElementException:
                    img = ""

                try:
                    name = item.find_element(
                        by=By.CSS_SELECTOR,
                        value='.product-item-name>a'
                    )
                    p_url = None
                    if name != None:
                        p_url = name.get_attribute("href")
                        name = name.text
                except:
                    name = ""
                    p_url = ""

                try:
                    price = item.find_element(
                        by=By.CSS_SELECTOR,
                        value='span.price-container'
                    )
                    if price != None:
                        price = price.text
                except:
                    price = ""

                card = Card(img, name, price, p_url, cat)
                cards.append(card)

            try:
                next_btn = driver.find_element(
                    by=By.CSS_SELECTOR,
                    value='div.toolbar-products li.pages-item-next>a'
                )
                if next_btn != None:
                    driver.get(next_btn.get_attribute("href"))
                    sleep(3)
                else:
                    break
            except NoSuchElementException:
                break

        return cards

    def process_detail_page(self, driver: WebDriver, wait: WebDriverWait, url: str) -> Detail:
        driver.get(url)
        imgs = wait.until(EC.presence_of_all_elements_located((
            By.CSS_SELECTOR,
            '.fotorama__stage__shaft img[class="fotorama__img"]'
        )))
        if len(imgs) > 0:
            imgs = [img.get_attribute("src") for img in imgs]

        try:
            name = driver.find_element(
                by=By.CSS_SELECTOR,
                value='h1.page-title>span'
            )
            if name != None:
                name = name.text
        except:
            name = ""

        try:
            pack_size = driver.find_element(
                by=By.CSS_SELECTOR,
                value='form > span[class="custom_code"]'
            )
            if pack_size != None:
                pack_size = pack_size.text
        except:
            pack_size = ""

        try:
            price = driver.find_element(
                by=By.CSS_SELECTOR,
                value='.product-info-price span.price'
            )
            if price != None:
                price = price.text
        except:
            price = ""

        try:
            description = driver.find_element(
                by=By.XPATH,
                value='//h5[contains(., "Indication")]/strong[2]'
            )
            if description != None:
                description = description.text
        except:
            description = ""

        try:
            dosage = driver.find_element(
                by=By.XPATH,
                value='//h5[contains(., "Dosage")]/strong[2]'
            )
            if dosage != None:
                dosage = dosage.text
        except:
            dosage = ""

        try:
            usage = driver.find_element(
                by=By.XPATH,
                value='//h5[contains(., "Usage")]/strong[2]'
            )
            if usage != None:
                usage = usage.text
        except:
            usage = ""

        try:
            caution = driver.find_element(
                by=By.XPATH,
                value='//h5[contains(., "Caution")]/strong[2]'
            )
            if caution != None:
                caution = caution.text
        except:
            caution = ""

        try:
            ingredients = driver.find_elements(
                by=By.CSS_SELECTOR,
                value='div[class="product attribute description"] table>tbody>tr>td:nth-child(3)'
            )
            ingredients = ", ".join([ing.text for ing in ingredients])
        except:
            ingredients = ""

        return Detail(
            None, name, price, url, None, imgs, pack_size, ingredients, description, dosage, caution
        )
