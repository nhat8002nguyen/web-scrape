import argparse
from tqdm import tqdm
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException

from seleniumbase import Driver

from time import sleep
import os
import dotenv
import pandas as pd


def main():
    dotenv.load_dotenv()

    driver: WebDriver = Driver(
        uc=True,
        no_sandbox=True,
        headless=True,
        proxy="005844proxies:005844proxies@38.154.227.167:5868"
    )
    driver.maximize_window()
    wait = WebDriverWait(driver, 30)

    url = "https://app.dexzcodes.com/app#!searchResultsPage"
    driver.get(url)

    driver.find_element(
        by=By.CSS_SELECTOR,
        value='input[id="home--login-form-username"]'
    ).send_keys("kagaminguyendu123@gmail.com")

    driver.find_element(
        by=By.CSS_SELECTOR,
        value='input[id="home--login-form-password"]'
    ).send_keys("@Rg3!gxMP@iRsks")

    driver.find_element(
        by=By.CSS_SELECTOR,
        value='button[id="home--login-submit"]'
    ).click()

    wait.until(EC.presence_of_element_located((
        By.CSS_SELECTOR,
        ".emphasized"
    ))).click()

    wait.until(EC.presence_of_element_located((
        By.CSS_SELECTOR,
        'div[class="catalog-button"] .v-button-wrap'
    ))).click()

    wait.until(EC.presence_of_element_located((
        By.XPATH,
        '//div[text()="Methodology"]'
    ))).click()

    methodology = "PCR, multiplex, reverse transcriptase (RT)"
    wait.until(EC.presence_of_element_located((
        By.XPATH,
        f'//span[text()="{methodology}"]'
    ))).click()

    sleep(3)

    result = {}
    result["Test Name (Title)"] = []
    result["Lab / Mfr Test ID"] = []
    result["Lab / Manufacturer"] = []
    result["NPI Number"] = []
    result["CLIA Number"] = []
    result["Address"] = []
    result["State"] = []
    result["Methodology"] = []

    page_count = 0
    while True:
        # Already scrape few pages
        if page_count >= 0:
            page_data = scrape_page(driver, wait, methodology)

            result["Test Name (Title)"].extend(page_data["Test Name (Title)"])
            result["Lab / Mfr Test ID"].extend(page_data["Lab / Mfr Test ID"])
            result["Lab / Manufacturer"].extend(
                page_data["Lab / Manufacturer"])
            result["NPI Number"].extend(page_data["NPI Number"])
            result["CLIA Number"].extend(page_data["CLIA Number"])
            result["Address"].extend(page_data["Address"])
            result["State"].extend(page_data["State"])
            result["Methodology"].extend(page_data["Methodology"])

        is_break = False
        while True:
            try:
                next_button = driver.find_element(
                    by=By.CSS_SELECTOR,
                    value=".next"
                )
                if next_button.get_attribute("class").find("v-disabled") > 0:
                    is_break = True
                    break

                next_button.click()
                break
            except Exception:
                continue

        sleep(10)

        page_count += 1

        if is_break:
            break

    df = pd.DataFrame(data=result)
    df.to_csv(f"./{methodology}.csv", index=False)

    driver.close()


def scrape_page(driver: WebDriver, wait: WebDriverWait, methodology: str) -> list:
    result = {}
    result["Test Name (Title)"] = []
    result["Lab / Mfr Test ID"] = []
    result["Lab / Manufacturer"] = []
    result["NPI Number"] = []
    result["CLIA Number"] = []
    result["Address"] = []
    result["State"] = []
    result["Methodology"] = []

    index = 1
    while True:
        try:
            rows = driver.find_elements(
                by=By.CSS_SELECTOR,
                value='table[role=grid] tr'
            )

            if index >= len(rows):
                # if index == 21:
                break

            if index % 10 == 0:
                sleep(5)

            row = rows[index]
            index += 1

            test_name = row.find_element(
                by=By.CSS_SELECTOR,
                value='td:nth-child(1)'
            ).text

            test_id = row.find_element(
                by=By.CSS_SELECTOR,
                value='td:nth-child(2)'
            ).text

            lab = row.find_element(
                by=By.CSS_SELECTOR,
                value='td:nth-child(3)'
            )
            lab_name = lab.text

            try:
                lab_icon = row.find_element(
                    by=By.CSS_SELECTOR,
                    value='.rightIconAfterLabel'
                )
                if lab_icon:
                    lab_icon.click()

                    first_option = wait.until(EC.presence_of_all_elements_located((
                        By.CSS_SELECTOR,
                        'div.v-popupview-popup .v-button-caption'
                    )))[0]
                    first_option.click()
            except NoSuchElementException as ex:
                lab.click()

            npi = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR,
                'div[location="npi-num"]'
            ))).text

            clia = driver.find_element(
                by=By.CSS_SELECTOR,
                value='div[location="clia-num"]'
            ).text

            address = " ".join(driver.find_element(
                by=By.CSS_SELECTOR,
                value='div[location="contact-address"]'
            ).text.split("\n"))

            state = address[address.rfind(",")+2:address.rfind(" ")]

            print(test_name)
            print(test_id)
            print(lab_name)
            print(npi)
            print(clia)
            print(address)
            print(state)
            print("-------------------------------------------------------")

            result["Test Name (Title)"].append(test_name)
            result["Lab / Mfr Test ID"].append(test_id)
            result["Lab / Manufacturer"].append(lab_name)
            result["NPI Number"].append(npi)
            result["CLIA Number"].append(clia)
            result["Address"].append(address)
            result["State"].append(state)
            result["Methodology"].append(methodology)

            driver.back()
            sleep(3)

        except ElementClickInterceptedException as ex:
            index -= 1
        except StaleElementReferenceException as ex:
            index -= 1
        except IndexError:
            index -= 1

    return result


if __name__ == "__main__":
    print("Program started!")

    main()
