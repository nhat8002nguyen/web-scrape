from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.webdriver import WebDriver

import pandas as pd
import time
import os
import dotenv

def main():
	dotenv.load_dotenv()
	website = 'https://twitter.com/'

	path = '.\chromedriver.exe'
	for root, dirs, files in os.walk(os.getcwd()):
		for name in files:
			if 'chromedriver' in name:
				path = os.path.join(root, name)			

	os_username = os.environ["USERNAME"]
	user_data_dir = f"C:\\Users\\{os_username}\\AppData\\Local\\Google\\Chrome\\User Data"

	chrome_options = Options()
	# chrome_options.add_argument('--headless')
	chrome_options.add_argument('--no-sandbox')
	chrome_options.add_argument('--disable-dev-shm-usage')
	chrome_options.add_argument('--start-maximized')
	# chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

	service = Service(executable_path=path)
	driver = webdriver.Chrome(options=chrome_options, service=service)
	driver.get(website)
	wait = WebDriverWait(driver, 100)

	login_to_twitter(driver, wait)

def login_to_twitter(driver: WebDriver, wait: WebDriverWait):
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

if __name__ == "__main__":
	main()
