from tqdm import tqdm
import csv
from docx import Document
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
import re
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
from time import sleep, perf_counter
import os
import dotenv
dotenv.load_dotenv()

doc_path = f"{os.environ['ROOT']}/linkedin_posts.docx"
csv_path = f"{os.environ['ROOT']}/linkedin_posts.csv"


def main():
    print("Started the program!")

    driver: WebDriver = Driver(uc=True, no_sandbox=True, headless=True)
    wait = WebDriverWait(driver, 30)
    driver.get("https://www.linkedin.com/login")

    email_input = driver.find_element(
        by=By.CSS_SELECTOR,
        value='input[id="username"]'
    )
    email_input.send_keys(os.environ["EMAIL"])

    pass_input = driver.find_element(
        by=By.CSS_SELECTOR,
        value='input[id="password"]'
    )
    pass_input.send_keys(os.environ["PASS"])

    button = driver.find_element(
        by=By.CSS_SELECTOR,
        value='button[type="submit"]'
    )
    button.click()

    sleep(3)

    driver.get("https://www.linkedin.com/in/kent-choi/recent-activity/all/")

    last_height = get_scroll_height(driver=driver)

    if not os.path.exists(doc_path):
        doc = Document()
    else:
        doc = Document(doc_path)

    added_count = 0
    post_ids = set()

    while True:
        current_posts = wait.until(EC.presence_of_all_elements_located((
            By.CSS_SELECTOR,
            '.scaffold-finite-scroll__content .break-words'
        )))

        len_posts = len(current_posts)
        start_index = 0 if len_posts < 20 else len_posts-20
        is_end = True

        # Open the file in append mode ('a') and write the new data
        with open(csv_path, mode='a', newline='', encoding="utf-8") as file:
            writer = csv.writer(file)

            for post in current_posts[start_index:]:
                post_text = post.text

                post_id = post_text[0:100]
                if post_id in post_ids:
                    continue

                is_end = False
                post_ids.add(post_id)

                writer.writerow(
                    [f'Post number {added_count+1}', post_text])

                doc.add_heading(f'Post number {added_count+1}:', level=2)
                added_count += 1
                doc.add_paragraph(post_text)

                print(post_text)
                print("-----------")

        if is_end:
            break

        driver.execute_script(
            'arguments[0].scrollIntoView();', current_posts[len(current_posts)-1])

        # Save the document with the new content added
        doc.save(doc_path)

        sleep(3)

        new_height = get_scroll_height(driver=driver)

        if new_height == last_height:
            break

        last_height = new_height

    doc.save(doc_path)

    print("Done! Program closes after 1 min")
    sleep(60)


def get_scroll_height(driver: WebDriver):
    return driver.execute_script("return document.body.scrollHeight")


def scroll_to_bottom(driver: WebDriver):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")


if __name__ == "__main__":
    main()
