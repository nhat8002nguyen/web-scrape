from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from PIL import Image

import pandas as pd
import json
import os
import time
import requests
import pytesseract
import cv2


SCREENSHOTS_FOLDER = "screenshots"

def main():
    website = 'https://www.tiktok.com/@handii0412/video/7266473832859389192'

    path = '.\chromedriver.exe'
    is_have_screenshots_folder = False
    for root, dirs, files in os.walk(os.getcwd()):
        for name in files:
            if 'chromedriver' in name:
                path = os.path.join(root, name)
        
        for dir in dirs:
            if SCREENSHOTS_FOLDER in dir:
                is_have_screenshots_folder = True

    if is_have_screenshots_folder is False:
        os.mkdir(os.path.join(os.getcwd(), "screenshots"))

    os_username = os.environ["USERNAME"]
    # user_data_dir = f"C:\\Users\\{os_username}\\AppData\\Local\\Google\\Chrome\\User Data"

    chrome_options = Options()
    # chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--start-maximized')
    # chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    chrome_options.add_argument('--auto-open-devtools-for-tabs')

    service = Service(executable_path=path)
    driver = webdriver.Chrome(options=chrome_options, service=service)
    driver.get(website)
    wait = WebDriverWait(driver, 100)

    wait.until(EC.presence_of_element_located((
        By.XPATH,
        "//div[@id='tiktok-verify-ele']//img"
    )))
    time.sleep(1)

	# Get the captcha image with origin source
    img_src = driver.find_element(
        by=By.XPATH,
        value='//div[@id="tiktok-verify-ele"]//img'
    ).get_attribute("src")
    img_data = requests.get(img_src).content
    with open(f'./{SCREENSHOTS_FOLDER}/tiktok-captcha.jpeg', 'wb') as handler:
        handler.write(img_data) 

	# Get captcha image from screenshot 
    img_path = f"./{SCREENSHOTS_FOLDER}/tiktok-captcha.png"
    saved_img_ok = driver.save_screenshot(img_path)
    if saved_img_ok == False:
        print("Error: can not save image")
    opened_image = Image.open(img_path)

    width, height = opened_image.size
    print(width, height)
    left = width/4 
    top = 1.2 * height/4 
    right = 3 * width/4
    bottom = 2.9 * height/4
    
    cropped_img = opened_image.crop((left, top, right, bottom))
    cropped_img.save(f"./{SCREENSHOTS_FOLDER}/cropped-tiktok-captcha.png")    

    img = cv2.imread(f"./{SCREENSHOTS_FOLDER}/cropped-tiktok-captcha.png")
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) 

    pytesseract.pytesseract.tesseract_cmd = r"E:\Program Files\Tesseract-OCR\tesseract.exe"
    data = pytesseract.image_to_string(img) 

    print(data)

	# click to image
    img_container = driver.find_element(
        by=By.XPATH,
        value="//div[@id='tiktok-verify-ele']//img"
    )
    ac = ActionChains(driver)
    ac.move_to_element(img_container).move_by_offset(
        50, 50).click().perform()

    time.sleep(1000)


if __name__ == "__main__":
    main()
