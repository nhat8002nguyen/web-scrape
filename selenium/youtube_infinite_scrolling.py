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

website = 'https://www.youtube.com/'

# path = '/usr/bin/chromedriver'
path = './chromedriver'


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

# navigate to music topic
music_button = wait.until(EC.presence_of_element_located((By.XPATH, '//yt-formatted-string[@title="Music"]')))
music_button.click()

wait.until(EC.presence_of_all_elements_located((By.XPATH, '//yt-formatted-string[@id="video-title"]')))

video_urls = []
titles = []
channels = []
num_views = []
since = []

def getVideoInfo(item):
	try:
		thumbnail_tag = item.find_element(by=By.XPATH, value='.//ytd-thumbnail//a[@id="thumbnail"]')
		video_url = thumbnail_tag.get_attribute('href')
	except:
		video_url = ""

	try:
		title_tag = item.find_element(by=By.XPATH, value='.//a[@id="video-title-link"]')
		title = title_tag.get_attribute('title')
	except:
		title = None

	try:
		channel = item.find_element(
			by=By.XPATH, 
			value='.//ytd-video-meta-block//div[contains(@class, "ytd-channel-name")]//div[@id="text-container"]'
		).text
	except:
		channel = None

	try:
		num_view = item.find_elements(
			by=By.XPATH, 
			value='.//ytd-video-meta-block//span[contains(@class, "ytd-video-meta-block")]'
		)[0].text
	except:
		num_view = None

	try:
		time_ago = item.find_elements(
			by=By.XPATH, 
			value='.//ytd-video-meta-block//span[contains(@class, "ytd-video-meta-block")]'
		)[1].text
	except:
		time_ago = None

	return [video_url, title, channel, num_view, time_ago]

last_height = driver.execute_script('return document.getElementById("contents").scrollHeight')
video_url_set = set()
offset = 0
while True:
	video_items = driver.find_elements(by=By.XPATH, value='//ytd-rich-item-renderer')
	offset += 20

	for item in video_items[offset:]:
		videoInfo = getVideoInfo(item)
		if videoInfo[0] not in video_url_set:
			video_url_set.add(videoInfo[0])

			video_urls.append(videoInfo[0])
			titles.append(videoInfo[1])
			channels.append(videoInfo[2])
			num_views.append(videoInfo[3])
			since.append(videoInfo[4])

			print(f'{videoInfo[0]} {videoInfo[1]} {videoInfo[2]} {videoInfo[3]} {videoInfo[4]}')

	driver.execute_script('window.scrollTo(0, document.getElementById("contents").scrollHeight)')

	time.sleep(2.5)

	current_height = driver.execute_script('return document.getElementById("contents").scrollHeight')
	if current_height == last_height:
		break
	else:
		last_height = current_height

driver.close()

df = pd.DataFrame({
	'video url': video_urls,
	'title': titles,
	'channel': channels,
	'num_view': num_views,
	'post_time': since
})	

df.to_csv('./youtube_infinite_scroll.csv', index=False)

	



