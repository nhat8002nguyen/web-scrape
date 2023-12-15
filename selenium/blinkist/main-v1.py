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
import time
import os
import dotenv


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


class Book():
    author: str
    book_name: str
    introduction: str
    key_ideas: list[str]
    final_summary: str

    def __init__(self, author="", book_name="", introduction="", key_ideas=list()) -> None:
        self.author = author
        self.book_name = book_name
        self.introduction = introduction
        self.key_ideas = key_ideas


def main():
    print("Started the program!")
    dotenv.load_dotenv()

    driver = Driver(uc=True, no_sandbox=True, headless=True,
                    proxy="webshareio005844-rotate:webshareio005844@p.webshare.io:80")
    driver.get('https://www.blinkist.com/en/nc/login/')
    wait = WebDriverWait(driver, 60)

    try:
        cookie_button = wait.until(EC.presence_of_element_located((
            By.XPATH,
            '//div[@class="cookie-disclaimer__actions"]/button//span'
        )))
        cookie_button.click()
        time.sleep(1)
    except Exception as err:
        print(err)
        pass

    try:
        email_input = wait.until(EC.presence_of_element_located((
            By.XPATH,
            '//input[@name="login[email]"]'
        )))
        email_input.send_keys(os.environ["BLINKIST_EMAIL_3"])

        pass_input = wait.until(EC.presence_of_element_located((
            By.XPATH,
            '//input[@name="login[password]"]'
        )))
        pass_input.send_keys(os.environ["BLINKIST_PASS_3"])

        submit_input = wait.until(EC.presence_of_element_located((
            By.XPATH,
            '//input[@name="commit"]'
        )))
        submit_input.click()
    except Exception as err:
        logAndExit(driver, start_cate, end_cate, err)

    time.sleep(5)

    start_cate = 17
    end_cate = 22 
    for i in range(start_cate, end_cate):
        start_time = time.perf_counter()
        driver.get(categories[i])

        try:
            book_items = wait.until(EC.presence_of_all_elements_located((
                By.XPATH,
                '//a[@class="letter-book-list__item"]'
            )))
        except Exception as err:
            logAndExit(driver, start_cate, end_cate, err)
            
        book_urls = [item.get_attribute("href") for item in book_items]

        author_list = []
        book_name_list = []
        introduction_list = []
        section0s = []
        section1s = []
        section2s = []
        section3s = []
        section4s = []
        section5s = []
        section6s = []
        section7s = []
        section8s = []
        section9s = []
        section10s = []
        section11s = []
        section12s = []
        section13s = []
        section14s = []
        section15s = []
        section16s = []
        section17s = []
        section18s = []
        section19s = []

        fail_urls = []
        num_book_urls = len(book_urls)
        for url in book_urls:
            try:
                bookData = scrapeDataFromBookUrl(driver, wait, url)
            except:
                fail_urls.append(url)
                continue

            # add to data export
            author_list.append(bookData.author)
            book_name_list.append(bookData.book_name)
            introduction_list.append(bookData.introduction)

            key_ideas = bookData.key_ideas
            section0s.append((key_ideas[0] if 0 < len(key_ideas) else ""))
            section1s.append((key_ideas[1] if 1 < len(key_ideas) else ""))
            section2s.append((key_ideas[2] if 2 < len(key_ideas) else ""))
            section3s.append((key_ideas[3] if 3 < len(key_ideas) else ""))
            section4s.append(key_ideas[4] if 4 < len(key_ideas) else "")
            section5s.append(key_ideas[5] if 5 < len(key_ideas) else "")
            section6s.append(key_ideas[6] if 6 < len(key_ideas) else "")
            section7s.append(key_ideas[7] if 7 < len(key_ideas) else "")
            section8s.append(key_ideas[8] if 8 < len(key_ideas) else "")
            section9s.append(key_ideas[9] if 9 < len(key_ideas) else "")
            section10s.append(key_ideas[10] if 10 < len(key_ideas) else "")
            section11s.append(key_ideas[11] if 11 < len(key_ideas) else "")
            section12s.append(key_ideas[12] if 12 < len(key_ideas) else "")
            section13s.append(key_ideas[13] if 13 < len(key_ideas) else "")
            section14s.append(key_ideas[14] if 14 < len(key_ideas) else "")
            section15s.append(key_ideas[15] if 15 < len(key_ideas) else "")
            section16s.append(key_ideas[16] if 16 < len(key_ideas) else "")
            section17s.append(key_ideas[17] if 17 < len(key_ideas) else "")
            section18s.append(key_ideas[18] if 18 < len(key_ideas) else "")
            section19s.append(key_ideas[19] if 19 < len(key_ideas) else "")

            time.sleep(3)

        fail_df = pd.DataFrame({
            "urls": fail_urls
        })
        fail_df.to_json(
            f"{os.environ['ABSOLUTE_PATH']}fail-url-categ-{i+1}.json", index=False)

        df = pd.DataFrame({
            "Author": author_list,
            "Book Name": book_name_list,
            "Introduction": introduction_list,
            "Section 1": section0s,
            "Section 2": section1s,
            "Section 3": section2s,
            "Section 4": section3s,
            "Section 5": section4s,
            "Section 6": section5s,
            "Section 7": section6s,
            "Section 8": section7s,
            "Section 9": section8s,
            "Section 10": section9s,
            "Section 11": section10s,
            "Section 12": section11s,
            "Section 13": section12s,
            "Section 14": section13s,
            "Section 15": section14s,
            "Section 16": section15s,
            "Section 17": section16s,
            "Section 18": section17s,
            "Section 19": section18s,
            "Section 20": section19s,
        })

        try:
            df.to_excel(
                f"{os.environ['ABSOLUTE_PATH']}/blinkist-output-categ-{i+1}-all.xlsx", index=False)
        except:
            df.to_json(
                f"{os.environ['ABSOLUTE_PATH']}/blinkist-output-categ-{i+1}-all.json", index=False)
            logAndExit(driver, start_cate, end_cate, err)

        print(
            f"Successfully scraped {num_book_urls} books in the category number {i+1}!")
        print(f"Elapsed time: {time.perf_counter()-start_time}")

        cate_delay = 300
        print(f"Delay {cate_delay} seconds after moving to next category")
        time.sleep(cate_delay)

def logAndExit(driver, start_cate, end_cate, err):
    with open(f"log-{start_cate}-{end_cate}.txt", "x") as file:
        file.write(f"Error: {err}") 
    driver.close()
    exit()

def scrapeDataFromBookUrl(driver: WebDriver, driver_wait: WebDriverWait, url: str) -> Book:
    book = Book("", "", "", list())
    driver.get(url)

    book_name = driver_wait.until(EC.presence_of_element_located((
        By.XPATH,
        '//h1'
    )))
    if book_name != None:
        book.book_name = book_name.text
        print(f"Book name is: {book_name.text}")

    author = driver_wait.until(EC.presence_of_element_located((
        By.XPATH,
        '//h2'
    )))
    if author != None:
        book.author = author.text
        print(f"Author: {author.text}")

    read_btn = driver_wait.until(EC.presence_of_element_located((
        By.XPATH,
        '//div[@data-test-id="book-controls-desktop"]//a[@data-test-id="read-button"]'
    )))

    read_btn.click()
    time.sleep(3)

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
            time.sleep(3)
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

        # print(chapter)
        # print(title)
        # print(description)
        # print("--------------------------------------------------------------")

    return book


if __name__ == "__main__":
    main()
