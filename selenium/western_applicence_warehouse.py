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

website = 'https://www.google.com/search?q=western+appliance+warehouse%2C++7261+garden+grove+blvd&sca_esv=577352139&rlz=1C5CHFA_enUS973US973&sxsrf=AM9HkKnMBwGeaLzEiMEbmfu5LB072N38lQ%3A1698459288912&ei=mG48ZcmZN-nQ2roPqu-HiA0&ved=0ahUKEwjJxdL01ZeCAxVpqFYBHar3AdEQ4dUDCBA&uact=5&oq=western+appliance+warehouse%2C++7261+garden+grove+blvd&gs_lp=Egxnd3Mtd2l6LXNlcnAiNHdlc3Rlcm4gYXBwbGlhbmNlIHdhcmVob3VzZSwgIDcyNjEgZ2FyZGVuIGdyb3ZlIGJsdmQyBRAAGKIEMgUQABiiBDIFEAAYogQyCBAAGIkFGKIESJsOUMEDWMMIcAF4AZABAJgB4AKgAfwEqgEHMC4yLjAuMbgBA8gBAPgBAfgBAsICChAAGEcY1gQYsAPCAgUQABiABMICBhAAGBYYHsICCBAAGIoFGIYD4gMEGAAgQYgGAZAGCA&sclient=gws-wiz-serp#lpc=lpc&scso=_m248ZfOLPP7m2roP_v61yAk_56:1273.3333740234375,_6nA8ZeQR3d3aug--upuIBg_51:353.3333435058594'

path = '/usr/bin/chromedriver'
# path = './chromedriver'


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

driver.switch_to.frame("lpc")

product_container = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@class='V7nvVb']")))

categories = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//div[@class='f8twAd']")))



count = 1
while True:
	category = driver.find_element(
		by=By.XPATH,
		value=f"//div[@class='f8twAd'][{count}]"
	)
	count += 1

	if category is None:
		break

	prd_count = 1
	while True:
		# click all view more button
		while True:
			view_more_button = wait.until(EC.presence_of_element_located((
				By.XPATH, 
				"//c-wiz[@class='SSPGKf']//div[@class='b7K3Ue']"
			)))

			view_more_button.click()

			if "none" in view_more_button.get_attribute(name="style"):
				break

		category = wait.until(EC.presence_of_element_located((
			By.XPATH,
			f"//div[@class='f8twAd'][{count}]"
		)))

		cat_prd = category.find_element(
			by=By.XPATH,
			value=f".//div[@class='J8zyUd'][{prd_count}]"
		)
		prd_count += 1

		if cat_prd is not None:
			cat_prd.click()

			product_container = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@class='hReZbc']")))

			title = product_container.find_element(
				by=By.XPATH,
				value=".//div[@class='NjC1lf']"
			).text
			print(title)
			price = product_container.find_element(
				by=By.XPATH,
				value=".//div[@class='hwaVm']"
			).text
			print(price)
			details = product_container.find_element(
				by=By.XPATH,
				value=".//div[@class='mI4Zw']"
			).text
			print(details)

			back_button = driver.find_element(
				by=By.XPATH,
				value="//span[@class='mmV8jb'][1]"
			)

			back_button.click()

		

driver.close()

