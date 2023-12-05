from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains


import undetected_chromedriver as uc
import pandas as pd
import json
import os
from time import sleep
from dotenv import load_dotenv
from chrome_web_driver import get_custom_driver


def main():
    load_dotenv()
    website = 'https://www.facebook.com/groups/daycareowners'

    os_username = os.environ["USERNAME"]
    user_data_dir = f"C:\\Users\\{os_username}\\AppData\\Local\\Google\\Chrome\\User Data"

    driver = get_custom_driver(headless=True)
    driver.get(website)
    wait = WebDriverWait(driver, 100)

    driver.get_log

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

    post_urls = []
    post_contents = []
    post_comments = []
    keys = set()

    i = 0

    driver.execute_script("window.scrollTo(0, 300)")

    while i < 10:
        i += 1
        posts = driver.find_elements(
            by=By.XPATH,
            value='//div[contains(@class, "x1yztbdb")]'
        )
        start_index = -10 if len(posts) > 10 else 0
        for post in posts[start_index:]:
            post_text_tags = post.find_elements(
                by=By.XPATH,
                value='.//div[@data-ad-preview="message"]//div[contains(@style, "text-align")]'
            )

            post_content = "\n".join([tag.text for tag in post_text_tags])
            if post_content in keys or post_content == "":
                continue
            keys.add(post_content)
            print(post_content)

            # get the url
            post_url = None
            datetime_tag = post.find_element(
                by=By.XPATH,
                value='.//div[contains(@class, "x1cy8zhl")]//span[contains(@class, "x4k7w5x")]//a[@role="link"]'
            )
            if datetime_tag is not None:
                hover = ActionChains(driver).move_to_element(datetime_tag)
                hover.perform()
                sleep(1)
                post_url = post.find_element(
                    by=By.XPATH,
                    value='.//div[contains(@class, "x1cy8zhl")]//span[contains(@class, "x4k7w5x")]//a[@role="link"]'
                ).get_attribute("@href")
            post_urls.append(post_url if post_url is not None else "")

            if post.find_element(
                by=By.XPATH,
                value='.//span[contains(text(), "comment")]'
            ) is not None:
                try:
                    sleep(1)
                    comment_tag = post.find_element(
                        by=By.XPATH,
                        value='.//div[@role="article"]//div[contains(@class, "x1r8uery")]//span[@lang="en"]'
                    )
                    comments = [
                        {
                            "main_comment": comment_tag.text if comment_tag is not None else "",
                        }
                    ]
                except:
                    pass

            try:
                popup_button = post.find_element(
                    by=By.XPATH,
                    value='.//span[contains(text(), " comments")]'
                )
                sleep(1)
                popup_button.click()
            except:
                continue

            # wait for content loaded in popup
            try:
                wait.until(EC.presence_of_all_elements_located((
                    By.XPATH,
                    '//div[@role="dialog"]//div[@role="article"]//div[contains(@class, "x1r8uery")]//span[@lang="en"]'
                )))
            except TimeoutError:
                pass
            except:
                pass

            dialog = driver.find_element(
                by=By.XPATH,
                value='.//div[@role="dialog"]'
            )

            main_comment_tags = dialog.find_elements(
                by=By.XPATH,
                value='.//div[@class="x1gslohp"]/div'
            )

            comments = []

            for main_comment_tag in main_comment_tags:
                sleep(0.5)
                try:
                    main_comment_div = main_comment_tag.find_element(
                        by=By.XPATH,
                        value='./div/div[1]//div[@role="article"]//div[contains(@class, "x1r8uery")]//span[@lang="en"]'
                    )
                except:
                    continue
                main_comment_text = ""
                if main_comment_div is not None:
                    main_comment_text = main_comment_div.text
                else:
                    continue

                # expand all replies
                while True:
                    try:
                        view_all_expand_tag = main_comment_tag.find_element(
                            by=By.XPATH,
                            value='.//span[contains(text(), "View all")]'
                        )
                        view_1_reply_tag = main_comment_tag.find_element(
                            by=By.XPATH,
                            value='.//span[contains(text(), "View")]'
                        )
                        if view_all_expand_tag is None and view_1_reply_tag is None:
                            break
                    except:
                        break

                    try:
                        sleep(1)
                        if view_all_expand_tag is not None:
                            view_all_expand_tag.click()
                        if view_1_reply_tag is not None:
                            view_1_reply_tag.click()
                    except:
                        pass

                    sleep(3)

                replies_spans = main_comment_tag.find_elements(
                    by=By.XPATH,
                    value='./div/div[2]//div[@role="article"]//div[contains(@class, "x1r8uery")]//span[@lang="en"]'
                )
                replies_texts = [
                    replies_span.text for replies_span in replies_spans]

                comment = {
                    "main_comment": main_comment_text,
                    "replies": replies_texts
                }

                comments.append(comment)

            post_contents.append(post_content)
            post_comments.append(comments)

            close_dialog_btn = dialog.find_element(
                by=By.XPATH,
                value='.//div[@aria-label="Close"]'
            )
            close_dialog_btn.click()

        driver.execute_script(
            "arguments[0].scrollIntoView(true)", posts[len(posts)-1])
        sleep(3)

    col1 = []
    col2 = []
    col3 = []
    for i in range(len(post_contents)):
        if len(post_comments[i]) == 0:
            col1.append(post_contents[i])
            col2.append("")
            col3.append("")
            continue

        for j in range(len(post_comments[i])):
            replies = post_comments[i][j]["replies"]
            if len(replies) == 0:
                col1.append(post_contents[i] if j == 0 else "")
                col2.append(post_comments[i][j]["main_comment"])
                col3.append("")
                continue

            for k in range(len(replies)):
                if k == 0:
                    col1.append(post_contents[i] if j == 0 else "")
                    col2.append(post_comments[i][j]["main_comment"])
                    col3.append(replies[k])
                else:
                    col1.append("")
                    col2.append("")
                    col3.append(replies[k])

    dataFrame = pd.DataFrame({
        'col 1': col1,
        'col 2': col2,
        'col 3': col3
    })

    dataFrame.to_excel("./daycare-owners-posts_1.xlsx")


if __name__ == "__main__":
    main()
