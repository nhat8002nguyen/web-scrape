import csv
from tqdm import tqdm
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
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

import pandas as pd
from time import sleep, perf_counter
import os
import dotenv
dotenv.load_dotenv()


class QualityImagesSpider(scrapy.Spider):
    name = "quality_images"
    allowed_domains = ["shop.aryavaidyasala.com"]
    start_urls = ["https://shop.aryavaidyasala.com/medicines.html"]

    proxies = []
    with open(f"{os.environ['ROOT_PATH']}/proxies.txt") as file:
        proxies = file.readlines()
        proxies = [p.strip() for p in proxies if p.strip()]

    def parse(self, response):
        p_urls = []
        with open(f"{os.environ['BACK_UP']}/detail_medicines_items_all.csv") as csvfile:
            # Requires header row in the CSV
            reader = csv.reader(csvfile, delimiter=";")
            for row in reader:
                p_urls.append(row[1])

            p_urls = p_urls[1:]

        driver: WebDriver = Driver(
            uc=True, no_sandbox=True, headless=True,
            proxy=self.proxies[0]
        )

        for j in tqdm(range(0, len(p_urls))):
            try:
                img_data = self.process_detail_page(
                    driver,
                    url=p_urls[j],
                )
            except:
                self.logger.error(
                    f"Failed to get detail of product: {p_urls[j]}")
                continue

            yield {
                "id": j,
                "type": "images",
                "product_url": img_data["url"],
                "images": "\n".join(img_data["imgs"]),
                "indication": img_data["indication"],
                "usage": img_data["usage"],
                "dosage": img_data["dosage"],
                "caution": img_data["caution"],
            }

            sleep(2)

    def process_detail_page(self, driver: WebDriver, url: str) -> dict[str, str]:
        proxy_index = 0
        while True:
            try:
                wait = WebDriverWait(driver, 60)
                actions = ActionChains(driver)

                driver.get(url)
                imgs = wait.until(EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR,
                    '.fotorama__stage__shaft img[class="fotorama__img"]'
                )))

                try:
                    indication = driver.find_element(
                        by=By.XPATH,
                        value='//h5[contains(., "Indication")]/strong[2]'
                    )
                    if indication != None:
                        indication = indication.text
                except:
                    indication = ""

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

                if len(imgs) > 0:
                    while True:
                        try:
                            img_frame = driver.find_element(
                                by=By.CSS_SELECTOR,
                                value='.fotorama__active.fotorama__loaded'
                            )
                            img_frame.click()
                            sleep(0.5)
                            break
                        except:
                            pass

                    quality_imgs = []
                    try:
                        img_thumbs = wait.until(EC.presence_of_all_elements_located((
                            By.CSS_SELECTOR,
                            '.fotorama__nav__frame--thumb'
                        )))
                        for thumb in img_thumbs:
                            active_img = wait.until(EC.presence_of_element_located((
                                By.CSS_SELECTOR,
                                '.fotorama__loaded--full.fotorama__active > img[class="fotorama__img--full"]'
                            )))
                            quality_imgs.append(
                                active_img.get_attribute("src"))
                            actions.key_down(Keys.RIGHT)
                            actions.key_up(Keys.RIGHT)
                            actions.perform()
                            sleep(1)
                    except TimeoutException:
                        active_img = wait.until(EC.presence_of_element_located((
                            By.CSS_SELECTOR,
                            '.fotorama__loaded--full.fotorama__active > img[class="fotorama__img--full"]'
                        )))
                        quality_imgs.append(active_img.get_attribute("src"))

                    return {
                        "url": url,
                        "imgs": quality_imgs,
                        "indication": indication,
                        "usage": usage,
                        "dosage": dosage,
                        "caution": caution,
                    }
            except Exception as ex:
                proxy_index += 1
                if proxy_index == 200:
                    proxy_index = 0

                if driver != None:
                    driver.close()
                    driver.quit()
                    driver = None
                    sleep(1)

                proxy = self.proxies[proxy_index]

                driver: WebDriver = Driver(
                    uc=True, no_sandbox=True, headless=True,
                    proxy=proxy
                )

                self.logger.error("Failed to get page, retrying...")
                self.logger.error(ex)
