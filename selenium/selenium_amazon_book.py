from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

import pandas as pd
import time

amazon_new_releases_url = 'https://www.amazon.com/kindle-dbs/browse/ref=dbs_b_def_rwt_brws_nfy_recs_pg_1?storeType=ebooks&widgetId=unified-ebooks-storefront-default_NewForYouStrategy&sourceAsin=&content-id=amzn1.sym.1a003f54-b0fb-4c1f-847d-4b886d085c2a&refTagFromService=nfy&title=New+releases+for+you&pf_rd_p=1a003f54-b0fb-4c1f-847d-4b886d085c2a&sourceType=recs&pf_rd_r=D30YX4MG2WAAPBQDR6YH&pd_rd_wg=21rpB&ref_=dbs_f_def_rwt_wigo_nfy_recs_wigo&SkipDeviceExclusion=true&pd_rd_w=WwnBo&nodeId=154606011&pd_rd_r=97666b78-714f-402d-9286-f1088dfd382a&metadata=cardAppType%3ADESKTOP%24deviceTypeID%3AA2Y8LFC259B97P%24clientRequestId%3AD30YX4MG2WAAPBQDR6YH%24deviceAppType%3ADESKTOP%24ipAddress%3A10.160.131.102%24browseNodes%3A154606011%24userAgent%3AMozilla%2F5.0+%28Windows+NT+10.0%3B+Win64%3B+x64%29+AppleWebKit%2F537.36+%28KHTML%2C+like+Gecko%29+Chrome%2F117.0.0.0+Safari%2F537.36%24cardSurfaceType%3Adesktop%24cardMobileOS%3AUnknown%24countryOfResidence%3AVN%24locale%3Aen_US%24deviceSurfaceType%3Adesktop&page=1'

website = amazon_new_releases_url
path = '/usr/bin/chromedriver'


chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--start-maximized')
# chrome_options.add_argument('--auto-open-devtools-for-tabs')

service = Service(executable_path=path)

driver = webdriver.Chrome(options=chrome_options, service=service)

driver.get(website)

wait = WebDriverWait(driver, 5)

books_name = []
ratings = []
prices = []

page = 1
while True:
	product_container = wait.until(
		EC.presence_of_element_located((By.XPATH, '//div[@id="browse-views-area"]')))

	products = wait.until(
		EC.presence_of_all_elements_located((By.XPATH, '//div[contains(@class, "browse-clickable-item")]'))
	)

	print(f"Page {page}")

	for product in products:
		try:
			book_name = product.find_element(
				by=By.XPATH, value='.//div[@id="sponsoredLabel-title"]//span[contains(@class, "a-size-base")]'
			).text
			books_name.append(book_name)
		except:
			books_name.append(None)

		try:
			rating = str(product.find_element(
				by=By.XPATH, value='.//div[@id="authors-ratings"]//span[@aria-hidden="true"]'
			).text)[1:-1]
			print(f"{rating}")
			ratings.append(rating)
		except:
			ratings.append(None)

		try:
			price = product.find_element(
				by=By.XPATH, value='.//div[@id="authors-ratings"]//span[contains(@class, "a-color-price")]'
			).text
			prices.append(price)
		except:
			prices.append(None)

	try:
		disabled_last_btn = driver.find_element(
			by=By.XPATH, value='//div[@id="pagination-section"]//li[contains(@class, "a-disabled a-last")]'
		)
		if disabled_last_btn is not None:
			break
	except:
		pass

	page += 1
	enabled_last_btn = driver.find_element(
		by=By.XPATH, value='//div[@id="pagination-section"]//li[contains(@class, "a-last")]'
	)
	enabled_last_btn.click()

	

driver.quit()

dataFrame = pd.DataFrame({
	'Name': books_name,
	'Rating': ratings,
	'Price': prices
})

dataFrame.to_csv('./src/selenium/amazon_new_book_releases.csv', index=False)	

