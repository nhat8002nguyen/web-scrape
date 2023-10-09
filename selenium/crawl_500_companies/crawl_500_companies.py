from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

import pandas as pd
import time
import dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import threading

dotenv.load_dotenv()

chromedriver_path = '/usr/bin/chromedriver'


class SeleniumScraper:
	def __init__(self, url, wait_timeout = 5) -> None:
		self.service = Service(executable_path=chromedriver_path)

		chrome_options = Options()
		chrome_options.add_argument('--headless')
		chrome_options.add_argument('--no-sandbox')
		chrome_options.add_argument('--disable-dev-shm-usage')
		chrome_options.add_argument('--start-maximized')


		self.chrome_options = chrome_options

		self.url = url
		self.wait_timeout = wait_timeout

	@contextmanager
	def get_driver(self):
		try:
			self.driver = webdriver.Chrome(options=self.chrome_options, service=self.service)
			self.driver.get(self.url)
			self.driver_wait = WebDriverWait(self.driver, self.wait_timeout)
			yield (self.driver, self.driver_wait)
		finally:
			self.driver.close()

def scrape_all_company_urls():
	scraper = SeleniumScraper('https://www.zyxware.com/articles/4344/list-of-fortune-500-companies-and-their-websites')

	with scraper.get_driver() as (driver, wait):
		company_url_cells = driver.find_elements(by=By.XPATH, value='//table[@class="table"]/tbody/tr/td[3]')
		company_urls = [cell.text for cell in company_url_cells]
		
	return company_urls


def scrape_company_page(url: str): 
	scraper = SeleniumScraper(url=url)

	with scraper.get_driver() as (driver, wait):
		time.sleep(5)

		text = driver.find_element(by=By.XPATH, value='/html/body').text

	df = pd.DataFrame({
		'text': [text]
	})
	df.to_csv(f'./selenium/crawl_500_companies/output/{url[8:].rstrip("/")}.csv', index=False)
	
	return f'Completed scrape text from url: {url}'

def scroll_full_page(driver):
	last_height = driver.execute_script('return document.body.scrollHeight')

	top = 500
	while True:
		driver.execute_script('window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" })')
		top += 500

		time.sleep(2)

		current_height = driver.execute_script('return document.body.scrollHeight')
		if current_height == last_height:
			break
		else:
			last_height = current_height

def main(): 
	company_urls = scrape_all_company_urls()

	with ThreadPoolExecutor(max_workers=8) as executor:
		futures =  [executor.submit(scrape_company_page, url) for url in company_urls[:20]]

		for future in as_completed(futures):
			print(future.result())


	df = pd.DataFrame(data={
		'url': company_urls	
	})
	df.to_csv('./selenium/crawl_500_companies/output/500_company_urls.csv', index=False)


if __name__ == '__main__':
	main()