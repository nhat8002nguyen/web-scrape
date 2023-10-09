from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

import pandas as pd
import time
import os
import dotenv

dotenv.load_dotenv()

website = 'https://twitter.com/'

path = '/usr/bin/chromedriver'


chrome_options = Options()
# chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--start-maximized')
# chrome_options.add_argument('--auto-open-devtools-for-tabs')

service = Service(executable_path=path)
driver = webdriver.Chrome(options=chrome_options, service=service)
driver.get(website)
wait = WebDriverWait(driver, 5)

def login_to_twitter():
	# move to the login form
	login_btn = driver.find_element(by=By.XPATH, value='//a[@href="/login"]')
	login_btn.click()

	# fill the username
	username_input = wait.until(EC.presence_of_element_located((By.XPATH, '//input[@autocomplete="username"]')))
	username_input.send_keys(os.environ.get('TWITTER_USER'))

	# move to the passowrd step
	next_step_button = driver.find_element(
		by=By.XPATH, value='//div[@role="dialog"]//div[contains(@style, "background-color: rgb(15, 20, 25)")]')
	next_step_button.click()

	# fill the password
	pass_input = wait.until(EC.presence_of_element_located((By.XPATH, '//input[@autocomplete="current-password"]')))
	pass_input.send_keys(os.environ.get('TWITTER_PASS'))

	# Click login to access twitter home page
	next_step_button = driver.find_element(
		by=By.XPATH, value='//div[@role="dialog"]//div[contains(@style, "background-color: rgb(15, 20, 25)")]')
	next_step_button.click()

	time.sleep(120)

login_to_twitter()
