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

    # This variable is used for testing with a small number of pages.
    env_num_pages = os.environ["NUM_PAGES"]
    if env_num_pages != "ALL":
        total_pages = int(env_num_pages) if int(
            env_num_pages) < total_pages else total_pages

    for page in tqdm(range(1, total_pages+1)):
        driver.get(
            f"{url}?page={page}")

        actions = ActionChains(driver)

        # Get all the rows of a page.
        rows = wait.until(EC.presence_of_all_elements_located((
            By.CSS_SELECTOR,
            "div.table-row"
        )))

        for i in range(len(rows)):
            folder_name = rows[i].find_element(
                by=By.CSS_SELECTOR,
                value=".item-name"
            ).text

            # Check that if the current row folder name is already downloaded or being processed to avoid duplicates.
            if any(fname.find(folder_name) > 0 for fname in os.listdir(f"{os.environ['ROOT']}/downloaded_files")):
                continue

            # Right click to a row to display download option using context_click.
            actions.context_click(rows[i]).perform()

            download_button = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "li.DownloadMenuItem"
            )))
            download_button.click()

            # After hitting the download option of a row, a popup will be displayed.
            popup_close_button = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "button.modal-close-button"
            )))

            # Add sleep a bit to avoid interacting too fast, and fail to close the popup because the popup is open slowly.
            sleep(1)
            popup_close_button.click()

            # Add a long sleep at least 3 seconds to avoid unable to click when the page show many success toasts in
            # the top middle of the page.
            sleep(4)

            # To avoid network overload, limit to 10 concurrent download processes a page since a page has 20 rows.
            if i == 9:
                check_download_progress(
                    f"{os.environ['ROOT']}/downloaded_files", page, i+1)

                # Avoid elements are stale due to the long wait time.
                rows = wait.until(EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR,
                    "div.table-row"
                )))

        # Wait for all rows to be done before moving to the next page.
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
