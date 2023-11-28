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
from dotenv import load_dotenv


def main():
    load_dotenv()
    website = 'https://www.facebook.com/groups/daycareowners'

    os_username = os.environ["USERNAME"]
    user_data_dir = f"C:\\Users\\{os_username}\\AppData\\Local\\Google\\Chrome\\User Data"

    chrome_options = Options()
    # chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--start-maximized')
    # chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    # chrome_options.add_argument('--auto-open-devtools-for-tabs')

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(website)
    wait = WebDriverWait(driver, 100)

    # driver = uc.Chrome(use_subprocess=False, options=chrome_options)
    # driver.get(website)
    # wait = WebDriverWait(driver, 100)

    email_input = wait.until(EC.presence_of_element_located((
        By.XPATH,
        '//form[@id="login_popup_cta_form"]//input[@name="email"]'
    )))

    email_input.send_keys(os.environ["FACEBOOK_EMAIL"])

    email_input = driver.find_element(
        by=By.XPATH,
        value='//form[@id="login_popup_cta_form"]//input[@type="password"]'
    )
    email_input.send_keys(os.environ["FACEBOOK_PASS"])

    login_btn = driver.find_element(
        by=By.XPATH,
        value='//form[@id="login_popup_cta_form"]//div[@aria-label="Accessible login button"]'
    )
    login_btn.click()

    # //div[@role="feed"]//div[@data-ad-preview="message"]
    wait.until(EC.presence_of_all_elements_located((
        By.XPATH,
        '//div[contains(@class, "x1yztbdb")]'
    )))

    post_contents = []
    post_comments = []
    keys = set()

    i = 0
    while i < 20:
        i += 1
        try:
            posts = driver.find_elements(
                by=By.XPATH,
                value='//div[contains(@class, "x1yztbdb")]'
            )
            for post in posts[-40:]:
                post_text_tags = post.find_elements(
                    by=By.XPATH,
                    value='.//div[@data-ad-preview="message"]//div[contains(@style, "text-align")]'
                )
                post_content = "\n".join([tag.text for tag in post_text_tags])

                if post_content in keys or post_content == "":
                    continue
                keys.add(post_content)

                comment_tags = post.find_elements(
                    by=By.XPATH,
                    value='.//div[@role="article"]//div[contains(@class, "x1r8uery")]//span[@lang="en"]'
                )
                comments = []
                for tag in comment_tags:
                    comments.append(tag.text)

                print(post_content)
                print(comments)

                post_contents.append(post_content) 
                post_comments.append(comments) 

            driver.execute_script("arguments[0].scrollIntoView(true)", posts[len(posts)-1])
            sleep(6)
        except:
            pass 
        
    dataFrame = pd.DataFrame({
        'Post Content': post_contents,
        'Comments': post_comments
    })

    dataFrame.to_excel("./daycare-owners-posts.xlsx")



if __name__ == "__main__":
    main()
