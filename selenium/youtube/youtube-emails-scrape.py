from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

import undetected_chromedriver as uc
import pandas as pd
import json
import os
from time import sleep


def main():
    website = 'https://www.youtube.com/'

    os_username = os.environ["USERNAME"]
    user_data_dir = f"C:\\Users\\{os_username}\\AppData\\Local\\Google\\Chrome\\User Data"

    chrome_options = Options()
    # chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--start-maximized')
    # chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    # chrome_options.add_argument('--auto-open-devtools-for-tabs')

    # driver = webdriver.Chrome(options=chrome_options)
    # driver.get(website)
    # wait = WebDriverWait(driver, 100)

    driver = uc.Chrome(use_subprocess=False, options=chrome_options)
    driver.get(website)

    signin_btn = driver.find_element(
        by=By.XPATH,
        value='//div[@id="end"]//div[@id="buttons"]//ytd-button-renderer'
    )
    signin_btn.click()

    email_input = driver.find_element(
        by=By.XPATH,
        value="//input[@type='email']"
    )
    email_input.send_keys("kagaminguyendu123@gmail.com")

    next_btn = driver.find_element(
        by=By.XPATH,
        value='//div[@id="identifierNext"]'
    )
    next_btn.click()

    sleep(10)


if __name__ == "__main__":
    main()
