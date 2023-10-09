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
import requests
from fake_useragent import UserAgent

dotenv.load_dotenv()

chromedriver_path = '/usr/bin/chromedriver'


class SeleniumScraper:
	def __init__(self, url, wait_timeout = 5) -> None:
		self.service = Service(executable_path=chromedriver_path)

		chrome_options = Options()
		# chrome_options.add_argument('--headless')
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

class ChromeIdentityManager:
	def __init__(self) -> None:
		self.user_agent_builder = UserAgent()

	def start_intervals_change_indentity(self):
		with ThreadPoolExecutor(max_workers=2) as executor:
			executor.submit(self._start_useragent_rotation)
			executor.submit(self._start_rotating_proxy_server)

			return

	def _start_useragent_rotation(self):
		while True:
			self._cur_ua = self.user_agent_builder.random
			print(f'Current user-agent: {self._cur_ua}')

			time.sleep(10)

	# get new proxy server to bypass captcha, IP block
	def _start_rotating_proxy_server(self):
		while True:
			proxy = requests.get(
				"https://ipv4.webshare.io/",
				proxies={
					"http": "http://uuwboduo-rotate:i4h001ld3d7q@p.webshare.io:80/",
					"https": "http://uuwboduo-rotate:i4h001ld3d7q@p.webshare.io:80/"
				}
			).text

			webdriver.DesiredCapabilities.CHROME['proxy'] = {
				"httpProxy": proxy,
				"ftpProxy": proxy,
				"sslProxy": proxy,
				"proxyType": "MANUAL",
			}
			webdriver.DesiredCapabilities.CHROME['acceptSslCerts']=True
			print(f"Current proxy is: {proxy}")

			time.sleep(10)

	def get_ua(self):
		return self._cur_ua


def scrape_all_company_urls():
	scraper = SeleniumScraper('https://www.zyxware.com/articles/4344/list-of-fortune-500-companies-and-their-websites')

	with scraper.get_driver() as (driver, wait):
		company_url_cells = driver.find_elements(by=By.XPATH, value='//table[@class="table"]/tbody/tr/td[3]')
		company_urls = [cell.text for cell in company_url_cells]
		
	return company_urls


def scrape_company_page(url: str, chrome_identity_manager: ChromeIdentityManager): 
	scraper = SeleniumScraper(url=url)
	scraper.chrome_options.add_argument(f'--user-agent={chrome_identity_manager.get_ua()}')

	with scraper.get_driver() as (driver, wait):
		time.sleep(5)

		scroll_full_page(driver=driver)

		text = driver.find_element(by=By.XPATH, value='/html/body').text

	df = pd.DataFrame({
		'text': [text]
	})
	df.to_csv(f'./selenium/crawl_500_companies/{url[8:].rstrip("/")}.csv', index=False)
	
	return f'Completed scrape text from url: {url}'

def scroll_full_page(driver):
	last_height = driver.execute_script('return document.body.scrollHeight')

	top = 500
	while True:
		driver.execute_script('window.scrollTo({ top: {0}, behavior: "smooth" })'.format(top))
		top += 500

		time.sleep(2)

		current_height = driver.execute_script('return document.body.scrollHeight')
		if current_height == last_height:
			break
		else:
			last_height = current_height

def main(): 
	# company_urls = scrape_all_company_urls()
	company_urls = ['https://www.walmart.com/']

	chrome_indentity_manager = ChromeIdentityManager()

	with ThreadPoolExecutor(max_workers=6) as executor:
		executor.submit(chrome_indentity_manager.start_intervals_change_indentity)

		futures =  [executor.submit(scrape_company_page, url, chrome_indentity_manager) for url in company_urls[:1]]

		for future in as_completed(futures):
			print(future.result())


	df = pd.DataFrame(data={
		'url': company_urls	
	})
	df.to_csv('./selenium/crawl_500_companies/500_company_urls.csv', index=False)


if __name__ == '__main__':
	main()