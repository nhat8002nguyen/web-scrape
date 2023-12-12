from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.webdriver import WebDriver
import undetected_chromedriver as uc

import pandas as pd
import time
import os
import dotenv

from categories import categories as cats


def main():
    dotenv.load_dotenv()

    amazon_new_releases_url = 'https://www.blinkist.com/en/nc/login/'

    website = amazon_new_releases_url
    path = '/usr/bin/chromedriver'

    chrome_options = Options()
    # chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--start-maximized')
    # chrome_options.add_argument('--auto-open-devtools-for-tabs')

    service = Service(executable_path=path)

    driver = uc.Chrome(options=chrome_options)

    driver.get(website)

    wait = WebDriverWait(driver, 10)

    cookie_button = driver.find_element(
        by=By.XPATH,
        value='//div[@class="cookie-disclaimer__actions"]/button//span'
    )
    cookie_button.click()

    email_input = driver.find_element(
        by=By.XPATH,
        value='//input[@name="login[email]"]'
    )
    email_input.send_keys(os.environ["BLINKIST_EMAIL"])

    pass_input = driver.find_element(
        by=By.XPATH,
        value='//input[@name="login[password]"]'
    )
    pass_input.send_keys(os.environ["BLINKIST_PASS"])

    submit_input = driver.find_element(
        by=By.XPATH,
        value='//input[@name="commit"]'
    )
    submit_input.click()

    time.sleep(5)

    driver.get(cats[0])

    book_items = driver.find_elements(
        by=By.XPATH,
        value='//a[@class="letter-book-list__item"]'
    )
    book_urls = [item.get_attribute("href") for item in book_items]

    for url in book_urls[:10]:
        scrapeDataFromBookUrl(driver, wait, url)
        time.sleep(3)

    print("Successfully scraped 10 books in the first category!")


def scrapeDataFromBookUrl(driver: WebDriver, driver_wait: WebDriverWait, url: str):
    driver.get(url)

    read_btn = driver_wait.until(EC.presence_of_element_located((
        By.XPATH,
        '//div[@data-test-id="book-controls-desktop"]//a[@data-test-id="read-button"]'
    )))

    read_btn.click()
    time.sleep(3)

    chapter_count = 0
    total_chapter_links = -1
    while True:
        try:
            chapter = driver_wait.until(EC.presence_of_element_located((
                By.XPATH,
                '//h5[@data-test-id="currentChapterNumber"]'
            )))
            if chapter != None:
                chapter = chapter.text
        except:
            chapter = "Final summary"
            pass

        title = driver.find_element(
            by=By.XPATH,
            value='//h2[contains(@class,"reader-content__headline")]'
        )
        if title != None:
            title = title.text

        paragraphs = driver.find_elements(
            by=By.XPATH,
            value='//span[contains(@class, "reader-content__text")]/p'
        )
        description = "\n".join([p.text for p in paragraphs])

        lis = driver.find_elements(
            by=By.XPATH,
            value='//span[contains(@class, "reader-content__text")]/ul/li'
        )
        for li in lis:
            description = description + "\n" + "- " + li.text

        # Print values
        print(chapter)
        print(title)
        print(description)
        print("--------------------------------------------------------------")
        print("--------------------------------------------------------------")

        # Navigate to the next chapter
        key_ideas_btn = driver.find_element(
            by=By.XPATH,
            value='//a[@data-test-id="keyIdeas"]'
        )
        key_ideas_btn.click()
        time.sleep(0.5)

        chapter_links = driver.find_elements(
            by=By.XPATH,
            value='//div[@data-test-id="chapterLink"]'
        )
        if total_chapter_links <= 0:
            total_chapter_links = len(chapter_links)

        if chapter_count+1 < len(chapter_links):
            chapter_links[chapter_count+1].click()
            time.sleep(3)
        else:
            break

        chapter_count += 1



if __name__ == "__main__":
    main()
