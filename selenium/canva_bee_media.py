from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

import pandas as pd
import json
import os
import time

def create_key(row):
	try:
		image_url_tag = row.find_element(
			by=By.XPATH,
			value=".//img"
		)
		if image_url_tag is not None: 
			image_url = image_url_tag.get_attribute("src") 
	except:
		image_url = ""	

	try:
		title = row.find_element(
			by=By.XPATH,
			value=".//div[2]/p"
		).text
	except:
		title = ""

	return image_url + title

def main():
	website = 'https://www.canva.com/creators/template/dashboard'

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
	chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
	chrome_options.add_argument("--no-sandbox")

	service = Service(executable_path=path)
	driver = webdriver.Chrome(options=chrome_options, service=service)
	driver.get(website)
	wait = WebDriverWait(driver, 100)

	wait.until(EC.presence_of_all_elements_located((
		By.XPATH,
		"//div[@role='tabpanel']//table[contains(@class, 'h74dDw')]//tbody/tr//td[1]//div/p[1]"
	)))

	# pause for setup filter
	time.sleep(30)

	# key_set to avoid duplication
	key_set = set()

	image_url_list = []
	title_list = []
	design_type_list = []
	published_list = []
	published_date_list = []
	total_applies_list = []
	total_usages_list = []

	init = True
	while True:
		rows = wait.until(EC.presence_of_all_elements_located((
			By.XPATH,
			"//div[@role='tabpanel']//table[contains(@class, 'h74dDw')]//tbody/tr"
		)))

		if init == True: 
			init = False	
			target_rows = rows[:-1]
		else:
			# take last 40 items despite of duplication
			target_rows = rows[-40:-1]

		if gen_key(target_rows[-1]) in key_set:
			break

		for row in target_rows:
			try:
				image_url_tag = row.find_element(
					by=By.XPATH,
					value=".//img"
				)
				if image_url_tag is not None: 
					image_url = image_url_tag.get_attribute("src") 
			except:
				image_url = ""	

			try:
				title = row.find_element(
					by=By.XPATH,
					value=".//td[1]//div/p[1]"
				).text
			except:
				title = ""

			key = gen_key(row)
			if key in key_set:
				continue
			key_set.add(key)

			image_url_list.append(image_url)
			title_list.append(title)

			try:
				design_type = row.find_element(
					by=By.XPATH,
					value=".//td[1]//div/p[2]"
				).text
			except:
				design_type = ""
			design_type_list.append(design_type)

			try:
				published = row.find_element(
					by=By.XPATH,
					value=".//td[2]//p[2]"
				).text
			except:
				published = "Approved"
			published_list.append(published)

			try: 
				published_date = row.find_element(
					by=By.XPATH,
					value=".//td[2]//p[1]"
				).text
			except:
				published_date = ""
			published_date_list.append(published_date)

			try:
				total_applies = row.find_element(
					by=By.XPATH,
					value=".//td[3]//p"
				).text
			except:
				total_applies = 0
			total_applies_list.append(total_applies)

			try:
				total_usages = row.find_element(
					by=By.XPATH,
					value=".//td[4]//p"
				).text
			except:
				total_usages = 0
			total_usages_list.append(total_usages)

		driver.execute_script("arguments[0].scrollIntoView(true)", rows[len(rows)-1])
		

	driver.close()

	dataframe = pd.DataFrame({
		'Image url': image_url_list,
		'Title': title_list,
		'Design Type': design_type_list,
		'Published': published_list,
		'Published date': published_date_list,
		'Total Applies': total_applies_list,
		'Total Usages': total_usages_list
	})

	dataframe.to_csv("./canva_bee_creativa_media.csv", index=False)

def gen_key(row):
	try:
		image_url_tag = row.find_element(
			by=By.XPATH,
			value=".//img"
		)
		if image_url_tag is not None: 
			image_url = image_url_tag.get_attribute("src") 
	except:
		image_url = ""	

	try:
		title = row.find_element(
			by=By.XPATH,
			value=".//div[2]/p"
		).text
	except:
		title = ""

	return f"{image_url} - {title}"	

if __name__ == "__main__":
	main()