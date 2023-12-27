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
from custom_web_driver import get_responses, get_custom_driver

import pandas as pd
from time import sleep
import os
import dotenv
from json import loads, dump


def main():
    print("Started the program!")
    dotenv.load_dotenv()

    driver: WebDriver = get_custom_driver(headless=True)
    wait = WebDriverWait(driver, 5)

    loginToFacebookPage(driver=driver, wait=wait)

    total_scroll = 10
    request_ids = set[str]()
    scroll_count = 0
    post_links = set[str]()
    batch_start = 0

    while True:
        posts = wait.until(EC.presence_of_all_elements_located((
            By.XPATH,
            '//div[@role="feed"]/div[contains(@class, "x1yztbdb")]'
        )))

        # for each 1000 scrolls, check if years of posts belong to 2020, then stop
        out_of_target = 0
        for post in posts[-20:]:
            timestamp = post.find_element(
                by=By.XPATH,
                value='.//div[contains(@class, "x1cy8zhl")]//div[contains(@class, "xu06os2")][2]//a'
            ).text
            if "2020" in timestamp:
                out_of_target += 1
            if out_of_target > 15:
                break
        
        if out_of_target > 15:
            break

        response_data = get_responses(driver=driver)

        for response in response_data.responses:
            if "bulk-route-definitions" in response.request_url:
                if response.request_id in request_ids or response.data == {}:
                    continue

                for key in response.data["payload"]["payloads"]:
                    if "/groups/daycareowners/posts/" in key:
                        key: str = key
                        post_link = f"https://web.facebook.com{key[:key.rfind('/')]}"
                        if post_link in post_links:
                            continue

                        print(post_link)
                        post_links.add(post_link)

        driver.execute_script(
            "arguments[0].scrollIntoView(true)", posts[len(posts)-2])

        if scroll_count % 1000 == 0:
            with open(f"fb-post-links-{batch_start}-{scroll_count}.txt", "r") as file:
                file.writelines(post_links)
                post_links = set[str]()

            batch_start = scroll_count + 1
            sleep(120)

        scroll_count += 1
        sleep(3)

    if len(post_links) > 0:
        with open(f"fb-post-links-{batch_start}-{scroll_count}.txt", "r") as file:
            file.writelines(post_links)
            post_links = set[str]()


def loginToFacebookPage(driver: WebDriver, wait: WebDriverWait):
    driver.get("https://web.facebook.com/groups/daycareowners")

    try:
        with open("./fb-selenium-cookies.json", "r") as file:
            cookies = loads(file.read())
            for cookie in cookies:
                driver.add_cookie(cookie_dict=dict(cookie))
        driver.refresh()
    except FileNotFoundError:
        email_input = wait.until(EC.presence_of_element_located((
            By.XPATH,
            '//form[@id="login_popup_cta_form"]//input[@name="email"]'
        )))
        email_input.send_keys(os.environ["FACEBOOK_EMAIL"])

        pass_input = driver.find_element(
            by=By.XPATH,
            value='//form[@id="login_popup_cta_form"]//input[@type="password"]'
        )
        pass_input.send_keys(os.environ["FACEBOOK_PASS"])

        login_btn = driver.find_element(
            by=By.XPATH,
            value='//form[@id="login_popup_cta_form"]//div[@aria-label="Accessible login button"]'
        )
        login_btn.click()

        sleep(5)

        cookies = driver.get_cookies()
        with open("./fb-selenium-cookies.json", "w") as file:
            dump(cookies, file)


if __name__ == "__main__":
    main()
