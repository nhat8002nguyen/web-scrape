import argparse
from tqdm import tqdm
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains

from seleniumbase import Driver

from time import sleep
import os
import dotenv


def main():
    dotenv.load_dotenv()

    driver: WebDriver = Driver(uc=True, no_sandbox=True, headless=True)
    driver.maximize_window()
    wait = WebDriverWait(driver, 30)

    driver.get(
        "https://www.upwork.com/jobs/span-class-highlight-span-Powered-commerce-Site-Developer_~011dc0f0498449fb54")

    el = wait.until(
        lambda d: d.find_element(By.CSS_SELECTOR, "#challenge-stage"))

    iframe = driver.find_element(By.CSS_SELECTOR, "#turnstile-wrapper iframe")

    driver.switch_to.frame(iframe)

    # Solve the challenge
    # For example, if the challenge is a CAPTCHA, you could use the following code to solve it:
    captcha = wait.until(
        lambda d: d.find_element(By.CSS_SELECTOR, "input[type=checkbox]"))
    captcha.click()
    # ... code to solve the CAPTCHA ...
    # submit_button = driver.find_element_by_xpath("//button[@class='submit-button']")
    # submit_button.click()
    sleep(20)
    # Get the content of the website

    driver.save_screenshot("Upwork_bypass.png")

    body = wait.until(EC.presence_of_element_located((
        By.CSS_SELECTOR,
        "section div .text-body-sm"
    )))

    print(body.text)

    sleep(1000)


if __name__ == "__main__":
    main()
