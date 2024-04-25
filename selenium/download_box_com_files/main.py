import argparse
import simplepush
import requests
from tqdm import tqdm
import csv
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
from selenium.webdriver.common.action_chains import ActionChains

from seleniumbase import Driver

import pandas as pd
from time import sleep, perf_counter
import os
import dotenv


def main(url: str):
    dotenv.load_dotenv()

    driver: WebDriver = Driver(uc=True, no_sandbox=True, headless=True)
    driver.maximize_window()
    wait = WebDriverWait(driver, 30)

    driver.get(url)
    page_context = wait.until(EC.presence_of_element_located((
        By.CSS_SELECTOR,
        ".pagination .btn-content"
    )))
    total_pages = int(page_context.text[page_context.text.index("of")+3:])
    print(f"There are total {total_pages} in this URL.")

    env_num_pages = os.environ["NUM_PAGES"]
    if env_num_pages != "ALL":
        total_pages = int(env_num_pages) if int(
            env_num_pages) < total_pages else total_pages

    for page in tqdm(range(1, total_pages+1)):
        driver.get(
            f"{url}?page={page}")

        actions = ActionChains(driver)

        rows = wait.until(EC.presence_of_all_elements_located((
            By.CSS_SELECTOR,
            "div.table-row"
        )))

        for i in range(len(rows)):
            folder_name = rows[i].find_element(
                by=By.CSS_SELECTOR,
                value=".item-name"
            ).text

            if any(fname.find(folder_name) > 0 for fname in os.listdir(f"{os.environ['ROOT']}/downloaded_files")):
                continue

            actions.context_click(rows[i]).perform()

            download_button = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "li.DownloadMenuItem"
            )))
            download_button.click()

            popup_close_button = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "button.modal-close-button"
            )))
            sleep(1)
            popup_close_button.click()

            sleep(4)

            if i == 9:
                check_download_progress(
                    f"{os.environ['ROOT']}/downloaded_files", page, i+1)

                rows = wait.until(EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR,
                    "div.table-row"
                )))

        check_download_progress(
            f"{os.environ['ROOT']}/downloaded_files", page, len(rows))

        print(f"Download page {page} completed!")


def check_download_progress(directory: str, page: int, num_folders: int):
    # While there's a .crdownload file in the directory, the download is still in progress
    print(f"Downloading {num_folders} folders in page {page}...")
    while any(fname.endswith('.crdownload') for fname in os.listdir(directory)):
        sleep(10)  # Sleep for a short interval to wait before rechecking


if __name__ == "__main__":
    print("Program started!")

    # Create the parser
    parser = argparse.ArgumentParser(description='Description of your script.')

    # Define the optional `--url` argument
    parser.add_argument('--url', type=str, help='The URL to process')

    # Parse the arguments
    args = parser.parse_args()

    # Use the `url` argument in your script (if provided)
    if args.url:
        print(f"Received URL: {args.url}")
        main(args.url)
    else:
        print("No URL provided.")
