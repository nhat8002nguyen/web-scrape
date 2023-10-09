import mechanicalsoup
import time

browser = mechanicalsoup.Browser()

url = "http://olympus.realpython.org/dice"

for i in range(4):
	page = browser.get(url)
	page_html = page.soup
	tag = page_html.select("#result")[0]
	print(f"The current number of dice is {tag.text}")

	if i < 3:
		time.sleep(3)	

