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
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager

dotenv.load_dotenv()

path = '/usr/bin/chromedriver'

chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--start-maximized')
# chrome_options.add_argument('--auto-open-devtools-for-tabs')

class TikiMobileProduct:
	def __init__(self, title, cur_price, seller) -> None:
		self.title = title
		self.cur_price = cur_price
		self.seller = seller

class SeleniumScraper:
	def __init__(self, url, wait_timeout = 5) -> None:
		self.service = Service(executable_path=path)
		self.url = url
		self.wait_timeout = wait_timeout

	@contextmanager
	def get_driver(self):
		try:
			self.driver = webdriver.Chrome(options=chrome_options, service=self.service)
			self.driver.get(self.url)
			self.driver_wait = WebDriverWait(self.driver, self.wait_timeout)
			yield (self.driver, self.driver_wait)
		finally:
			self.driver.close()

def get_all_links_of_page(page):
	product_urls = []

	scraper = SeleniumScraper(url=f"https://tiki.vn/dien-thoai-may-tinh-bang/c1789?page={page}")	
	with scraper.get_driver() as (driver, _):
		product_a_tags = driver.find_elements(
			by=By.XPATH, 
			value='//div[@data-view-id="product_list_container"]//a[@data-view-id="product_list_item"]'
		)
		for tag in product_a_tags:
			product_urls.append(tag.get_attribute("href"))

	return product_urls

def get_product_info(url) -> TikiMobileProduct:
	scraper = SeleniumScraper(url=url)

	with scraper.get_driver() as (driver, wait):
		try:
			title = driver.find_element(by=By.XPATH, value='//h1[contains(@class, "Title__TitledStyled")]').text
		except:
			title = None

		try:
			price_container = driver.find_element(by=By.XPATH, value='//div[contains(@class, "product-price__current-price")]')
			price_value = price_container.text
			currency = price_container.find_element(by=By.XPATH, value='./sup').text
			price = f'{price_value} {currency}'
		except:
			price = None

		try:
			driver.execute_script("""window.scrollTo(0, document.body.scrollHeight/3)""")
			time.sleep(1)
			seller = driver.find_element(by=By.XPATH, value='//span[contains(@class, "seller-name")]/a/span').text
		except:
			seller = None

	return TikiMobileProduct(title, price, seller)

def main(): 
	num_scraped_pages = 1
	all_mobile_prd_urls = []

	start_time = time.perf_counter()

	with ThreadPoolExecutor(max_workers=4) as executor:
		futures = [executor.submit(get_all_links_of_page, i+1) for i in range(num_scraped_pages)]

	for future in as_completed(futures):
		urls = future.result()
		all_mobile_prd_urls.extend(urls)
	
	end_time_1 = time.perf_counter()
	print(f"Elapsed time of get all product detail urls of {num_scraped_pages} pages: {end_time_1 - start_time}")

	print(len(all_mobile_prd_urls))

	with ThreadPoolExecutor(max_workers=8) as executor:
		futures = [executor.submit(get_product_info, url) for url in all_mobile_prd_urls[:5]]
			
	titles, prices, sellers = [], [], []
	for future in as_completed(futures):
		product = future.result()
		titles.append(product.title)
		prices.append(product.cur_price)
		sellers.append(product.seller)
		
	end_time_2 = time.perf_counter()
	print(f"Elapsed time of get all product infos of {len(all_mobile_prd_urls[:5])} products: {end_time_2 - end_time_1}")

	df = pd.DataFrame({
		'title': titles,
		'price': prices,
		'seller': sellers,
	})	
	df.to_csv('./tiki_mobile_product.csv', index=False)


if __name__ == '__main__':
	main()