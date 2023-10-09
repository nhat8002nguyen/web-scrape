from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import pandas as pd
import time


website = 'https://www.adamchoi.co.uk/overs/detailed'
path = '/usr/bin/chromedriver'


chrome_options = Options()
# chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--start-maximized')
# chrome_options.add_argument('--auto-open-devtools-for-tabs')

service = Service(executable_path=path)

d = webdriver.Chrome(options=chrome_options, service=service)

d.get(website)

all_matches_btn = d.find_element(by=By.XPATH, value='//label[@analytics-event="All matches"]')
all_matches_btn.click()

match_dates = []
team1s = []
match_results = [] 
team2s = []

countriesDropdown = Select(d.find_element(by=By.ID, value='country'))
countriesDropdown.select_by_visible_text('France')

time.sleep(1)

leaguesDropdown = Select(d.find_element(by=By.ID, value='league'))
leaguesDropdown.select_by_visible_text('Ligue 2')

time.sleep(3)

row_matches = d.find_elements(by=By.XPATH, value='//tr')

for m in row_matches:
	date = m.find_element(by=By.XPATH, value="./td[1]").text
	match_dates.append(date)

	team = m.find_element(by=By.XPATH, value="./td[2]").text
	team1s.append(team)

	match_result = m.find_element(by=By.XPATH, value="./td[3]").text
	match_results.append(match_result)

	team2 = m.find_element(by=By.XPATH, value="./td[4]").text
	team2s.append(team2)

	print(f'{date} {team} {match_result} {team2}')

d.quit()

matches = {'Match date': match_dates, 'Team 1': team1s, 'Result': match_results, 'Team 2': team2s}

df = pd.DataFrame(matches)

df.to_csv("./test_chrome_driver_1.csv", index=False)

