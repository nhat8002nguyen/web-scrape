from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import undetected_chromedriver as uc
from seleniumbase import Driver
import requests
from bs4 import BeautifulSoup

import pandas as pd
from time import sleep, perf_counter
import os
import dotenv
from tqdm import tqdm


def main():
    # Using selenium
    print("Started the program!")
    dotenv.load_dotenv()

    driver: WebDriver = Driver(uc=True, no_sandbox=True, headless=False)
    wait = WebDriverWait(driver, 30)

    driver.get("https://allpeople.com/a+a+association_abta-us")

    sleep(1000)

    # Using Requests and BeautifulSoup
    # resp = requests.get("https://allpeople.com/ajah+sneed_belk_7067-us")
    # if resp.status_code != 200:
    #     print(f"Error getting the page: {resp.status_code}")
    #     return

    # soup = BeautifulSoup(resp.content, "html.parser")
    # email = soup.select_one("div.c-email").text
    # print(email)

    print("Done")


if __name__ == "__main__":
    main()
