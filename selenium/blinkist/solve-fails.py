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
from models import Book, ExportFrame

from seleniumbase import Driver

import pandas as pd
from time import sleep, perf_counter
import os
import dotenv
from tqdm import tqdm
from json import loads


LIST_FILE_NAMES = ["fail-url-categ-21-0-99", "fail-url-categ-21-100-199"]
BATCH_LENGTH = 100
START_BOOK_INDEX = 0

categories = [
    "https://www.blinkist.com/en/nc/categories/entrepreneurship-and-small-business-en/books",
    "https://www.blinkist.com/en/nc/categories/science-en/books",
    "https://www.blinkist.com/en/nc/categories/economics-en/books",
    "https://www.blinkist.com/en/nc/categories/corporate-culture-en/books",
    "https://www.blinkist.com/en/nc/categories/money-and-investments-en/books",
    "https://www.blinkist.com/en/nc/categories/relationships-and-parenting-en/books",
    "https://www.blinkist.com/en/nc/categories/parenting-en/books",
    "https://www.blinkist.com/en/nc/categories/education-en/books",
    "https://www.blinkist.com/en/nc/categories/society-and-culture-en/books",
    "https://www.blinkist.com/en/nc/categories/politics-and-society-en/books",
    "https://www.blinkist.com/en/nc/categories/health-and-fitness-en/books",
    "https://www.blinkist.com/en/nc/categories/biography-and-history-en/books",
    "https://www.blinkist.com/en/nc/categories/management-and-leadership-en/books",
    "https://www.blinkist.com/en/nc/categories/psychology-en/books",
    "https://www.blinkist.com/en/nc/categories/technology-and-the-future-en/books",
    "https://www.blinkist.com/en/nc/categories/nature-and-environment-en/books",
    "https://www.blinkist.com/en/nc/categories/philosophy-en/books",
    "https://www.blinkist.com/en/nc/categories/career-and-success-en/books",
    "https://www.blinkist.com/en/nc/categories/marketing-and-sales-en/books",
    "https://www.blinkist.com/en/nc/categories/personal-growth-and-self-improvement-en/books",
    "https://www.blinkist.com/en/nc/categories/communication-and-social-skills-en/books",
    "https://www.blinkist.com/en/nc/categories/motivation-and-inspiration-en/books",
    "https://www.blinkist.com/en/nc/categories/productivity-and-time-management-en/books",
    "https://www.blinkist.com/en/nc/categories/mindfulness-and-happiness-en/books",
    "https://www.blinkist.com/en/nc/categories/religion-and-spirituality-en/books",
    "https://www.blinkist.com/en/nc/categories/biography-and-memoir-en/books",
    "https://www.blinkist.com/en/nc/categories/creativity-en/books",
]

def main():
    print("Started the program!")
    dotenv.load_dotenv()

    driver: WebDriver = Driver(uc=True, no_sandbox=True, headless=True)
    wait = WebDriverWait(driver, 60)

    login(driver=driver, wait=wait)

    for i in tqdm(range(len(LIST_FILE_NAMES))):
        start_time = perf_counter()
        exportFrame = ExportFrame()
        exportFrame.file_name = LIST_FILE_NAMES[i]

        book_urls = list[str]()
        with open(f"{os.environ['ABSOLUTE_PATH']}/{LIST_FILE_NAMES[i]}.json") as file:
            json = loads(file.read())
            urls_dict: dict = json["urls"]
            book_urls = list(urls_dict.values())

        fail_urls = []
        batch_start_index = START_BOOK_INDEX
        num_book_urls = len(book_urls[START_BOOK_INDEX:])
        for j in tqdm(range(START_BOOK_INDEX, START_BOOK_INDEX + num_book_urls)):
            if j % BATCH_LENGTH == 0 and j > 0:
                # logout and initialize a new web driver, avoid session timeout.
                logout(driver, wait)
                driver: WebDriver = Driver(
                    uc=True, no_sandbox=True, headless=True)
                wait = WebDriverWait(driver, 60)
                login(driver=driver, wait=wait)

            try:
                bookData = scrapeDataFromBookUrl(driver, wait, book_urls[j])
            except Exception as err:
                print(err)
                fail_urls.append(book_urls[j])
                continue

            # add to data export
            exportFrame.author_list.append(bookData.author)
            exportFrame.book_name_list.append(bookData.book_name)
            exportFrame.introduction_list.append(bookData.introduction)

            # additional infomation
            exportFrame.author_about_list.append(bookData.author_about)
            exportFrame.intro_title_list.append(bookData.intro_title)
            exportFrame.short_summary_list.append(bookData.short_summary)
            exportFrame.time_list.append(bookData.time)
            exportFrame.num_key_ideas_list.append(bookData.num_key_ideas)
            exportFrame.cat0_list.append(bookData.cat0)
            exportFrame.cat1_list.append(bookData.cat1)
            exportFrame.cat2_list.append(bookData.cat2)
            exportFrame.cat3_list.append(bookData.cat3)
            exportFrame.cat4_list.append(bookData.cat4)

            key_ideas = bookData.key_ideas
            exportFrame.section0s.append(
                (key_ideas[0] if 0 < len(key_ideas) else ""))
            exportFrame.section1s.append(
                (key_ideas[1] if 1 < len(key_ideas) else ""))
            exportFrame.section2s.append(
                (key_ideas[2] if 2 < len(key_ideas) else ""))
            exportFrame.section3s.append(
                (key_ideas[3] if 3 < len(key_ideas) else ""))
            exportFrame.section4s.append(
                key_ideas[4] if 4 < len(key_ideas) else "")
            exportFrame.section5s.append(
                key_ideas[5] if 5 < len(key_ideas) else "")
            exportFrame.section6s.append(
                key_ideas[6] if 6 < len(key_ideas) else "")
            exportFrame.section7s.append(
                key_ideas[7] if 7 < len(key_ideas) else "")
            exportFrame.section8s.append(
                key_ideas[8] if 8 < len(key_ideas) else "")
            exportFrame.section9s.append(
                key_ideas[9] if 9 < len(key_ideas) else "")
            exportFrame.section10s.append(
                key_ideas[10] if 10 < len(key_ideas) else "")
            exportFrame.section11s.append(
                key_ideas[11] if 11 < len(key_ideas) else "")
            exportFrame.section12s.append(
                key_ideas[12] if 12 < len(key_ideas) else "")
            exportFrame.section13s.append(
                key_ideas[13] if 13 < len(key_ideas) else "")
            exportFrame.section14s.append(
                key_ideas[14] if 14 < len(key_ideas) else "")
            exportFrame.section15s.append(
                key_ideas[15] if 15 < len(key_ideas) else "")
            exportFrame.section16s.append(
                key_ideas[16] if 16 < len(key_ideas) else "")
            exportFrame.section17s.append(
                key_ideas[17] if 17 < len(key_ideas) else "")
            exportFrame.section18s.append(
                key_ideas[18] if 18 < len(key_ideas) else "")
            exportFrame.section19s.append(
                key_ideas[19] if 19 < len(key_ideas) else "")

            sleep(3)

            if (j+1) % BATCH_LENGTH == 0 or j == (START_BOOK_INDEX + num_book_urls) - 1:
                fail_df = pd.DataFrame({
                    "urls": fail_urls
                })
                fail_df.to_json(
                    f"{os.environ['ABSOLUTE_PATH']}/fail-url-file-num-{i}-{batch_start_index}-{j}.json", index=False)
                fail_urls = []

                try:
                    exportFrame.exportXLSX(i, batch_start_index, j)
                    print(
                        f"Successfully saved xlsx data from {batch_start_index} to {j}!")
                    print(
                        "------------------------------------------------------------------------")
                except:
                    exportFrame.exportJson(i, batch_start_index, j)

                batch_start_index = j+1

        if len(exportFrame.author_list) > 0:
            try:
                exportFrame.exportXLSX(
                    i, batch_start_index, (START_BOOK_INDEX + num_book_urls) - 1)
                print(
                    f"Successfully saved xlsx data from {batch_start_index} to {j}!")
            except:
                exportFrame.exportJson(
                    i, batch_start_index, (START_BOOK_INDEX + num_book_urls) - 1)

        print(
            f"Successfully scraped {num_book_urls} books in the fail file number {i}!")
        print(f"Elapsed time: {perf_counter()-start_time}")

        cate_delay = 60
        print(f"Delay {cate_delay} seconds after moving to next category")
        print("------------------------------------------------------------------------")
        sleep(cate_delay)


def login(driver: WebDriver, wait: WebDriverWait, isStart=True):
    driver.get('https://www.blinkist.com/en/nc/login/')

    if isStart:
        try:
            cookie_button = wait.until(EC.presence_of_element_located((
                By.XPATH,
                '//div[@class="cookie-disclaimer__actions"]/button//span'
            )))
            cookie_button.click()
            sleep(1)
        except Exception as err:
            print("Cookie button not found!")
            pass

    try:
        email_input = wait.until(EC.presence_of_element_located((
            By.XPATH,
            '//input[@name="login[email]"]'
        )))
        email_input.send_keys(os.environ["BLINKIST_EMAIL_0"])

        pass_input = wait.until(EC.presence_of_element_located((
            By.XPATH,
            '//input[@name="login[password]"]'
        )))
        pass_input.send_keys(os.environ["BLINKIST_PASS_0"])

        submit_input = wait.until(EC.presence_of_element_located((
            By.XPATH,
            '//input[@name="commit"]'
        )))
        submit_input.click()
        sleep(3)
    except Exception:
        exit()


def logout(driver: WebDriver, wait: WebDriverWait):
    driver.get("https://www.blinkist.com/en/app/library")

    logout_button = wait.until(EC.presence_of_element_located((
        By.XPATH,
        '//a[@href="/nc/logout"]'
    )))
    logout_button.click()
    sleep(10)


def logAndExit(driver, start_cate, end_cate, err):
    with open(f"log-{start_cate}-{end_cate}.txt", "x") as file:
        file.write(f"Error: {err}")
    driver.close()
    exit()


def scrapeDataFromBookUrl(driver: WebDriver, driver_wait: WebDriverWait, url: str) -> Book:
    book = Book("", "", "", list())
    driver.get(url)

    driver_wait.until(EC.presence_of_element_located((
        By.XPATH,
        '//div[@data-test-id="book-controls-desktop"]//a[@data-test-id="read-button"]'
    )))

    book_name = driver_wait.until(EC.presence_of_element_located((
        By.XPATH,
        "//div[contains(@class, 'm:order-1')]/div[@class='mx-4']/h1"
    )))
    if book_name != None:
        book.book_name = book_name.text
        print(f"Book name is: {book_name.text}")

    author = driver_wait.until(EC.presence_of_element_located((
        By.XPATH,
        "//div[contains(@class, 'm:order-1')]/div[@class='mx-4']/h2"
    )))
    if author != None:
        book.author = author.text
        print(f"Author: {author.text}")

    author_abouts = driver_wait.until(EC.presence_of_all_elements_located((
        By.XPATH,
        "//h4[contains(., 'About the author')]/following-sibling::div[1]//p"
    )))
    if author_abouts != None and len(author_abouts) > 0:
        book.author_about = "\n".join([about.text for about in author_abouts])
        print(f"Author abouts: {book.author_about}")

    intro_title = driver.find_element(
        by=By.XPATH,
        value="//div[contains(@class, 'm:order-1')]/div[@class='mx-4']/p"
    )
    if intro_title != None:
        book.intro_title = intro_title.text
        print(f"Intro title: {book.intro_title}")

    time = driver.find_element(
        by=By.XPATH,
        value="//div[contains(@class, 'm:order-1')]//div[contains(@class, 'grid-cols-2')]/div[2]/span"
    )
    if time != None:
        book.time = time.text
        print(f"Time: {book.time}")

    num_key_ideas = driver.find_element(
        by=By.XPATH,
        value="//div[contains(@class, 'm:order-1')]//div[contains(@class, 'grid-cols-2')]/div[3]/span"
    )
    if num_key_ideas != None:
        book.num_key_ideas = num_key_ideas.text
        print(f"Num key ideas: {book.num_key_ideas}")

    short_summary = driver.find_element(
        by=By.XPATH,
        value='//h4[contains(text(),"What\'s it about?")]/following-sibling::div/p'
    )
    if short_summary != None:
        book.short_summary = short_summary.text
        print(f"Short summary: {book.short_summary}")

    categories = driver.find_elements(
        by=By.XPATH,
        value="//a[@data-test-id='b-chip']//span"
    )
    if categories != None and len(categories) > 0:
        if 0 < len(categories):
            book.cat0 = categories[0].text
            print(f"Category 0: {book.cat0}")
        if 1 < len(categories):
            book.cat1 = categories[1].text
            print(f"Category 1: {book.cat1}")
        if 2 < len(categories):
            book.cat2 = categories[2].text
            print(f"Category 2: {book.cat2}")
        if 3 < len(categories):
            book.cat3 = categories[3].text
            print(f"Category 3: {book.cat3}")
        if 4 < len(categories):
            book.cat4 = categories[4].text
            print(f"Category 4: {book.cat4}")

    print("------------Content-------------")

    read_btn = driver_wait.until(EC.presence_of_element_located((
        By.XPATH,
        '//div[@data-test-id="book-controls-desktop"]//a[@data-test-id="read-button"]'
    )))
    content_url = read_btn.get_attribute("href")
    print(f"Going to {content_url}...\n-------------")
    driver.get(url=content_url)
    sleep(3)

    chapter_count = 0
    total_chapter_links = -1
    while True:
        # Navigate to the next chapter
        key_ideas_btn = driver_wait.until(EC.presence_of_element_located((
            By.XPATH,
            '//a[@data-test-id="keyIdeas"]'
        )))
        key_ideas_btn.click()

        chapter_links = driver_wait.until(EC.presence_of_all_elements_located((
            By.XPATH,
            '//div[@data-test-id="chapterLink"]'
        )))
        if total_chapter_links <= 0:
            total_chapter_links = len(chapter_links)

        if chapter_count < len(chapter_links):
            chapter_links[chapter_count].click()
            sleep(3)
        else:
            break
        chapter_count += 1

        if chapter_count == total_chapter_links:
            chapter = "Final summary"
        else:
            try:
                chapter = driver_wait.until(EC.presence_of_element_located((
                    By.XPATH,
                    '//h5[@data-test-id="currentChapterNumber"]'
                )))
                if chapter != None:
                    chapter = chapter.text
            except NoSuchElementException:
                chapter = "Final summary"

        title = driver_wait.until(EC.presence_of_element_located((
            By.XPATH,
            '//h2[contains(@class,"reader-content__headline")]'
        )))
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

        content = f'''Chapter: {chapter}\nHeadline: {title}\nContent: {description}'''
        # if this is the introduction
        if chapter_count == 1:
            book.introduction = content
        else:
            book.key_ideas.append(content)

        print(chapter)
        print(title)
        print(description)
        print("--------------------------------------------------------------------")

    return book


if __name__ == "__main__":
    main()
