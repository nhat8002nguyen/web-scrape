from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

import pandas
import time
import os

def main():
	website = 'https://eventhunter.notion.site/eventhunter/9c233ae8a2544cb79631cc714ebe002d?v=5be9e321daa744a6801f3cab9008f0fd'

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
	wait = WebDriverWait(driver, 10)

	rows = wait.until(EC.presence_of_all_elements_located((
		By.XPATH, 
		"//div[@class='notion-table-view-row']",
	)))

	event_name_list = []
	organizer_type_list = []
	attendees_result_list = []
	oppotunities_list = []
	attendances_list = []
	start_time_list = []
	end_time_list = []
	websites_list = []
	sponsorship_site_list = []
	sponsor_download_list = []
	linkedin_list = []
	attendee_list_list = []
	venue_list = []
	city_list = []
	state_of_province_list = []
	country_list = []
	low_price_list = []
	high_price_list = []
	early_bird_dealine_list = []
	sponsorship_contact_email_list = []
	sponsorship_contact_name_list = []
	latest_sponsor_list_list = []
	sponsors_exhibitors_list = []
	peek_url_list = []
	notes_list = []


	for row in rows:
		cells = row.find_elements(
			by=By.XPATH,
			value=".//div[@class='notion-table-view-cell']"
		)

		try:
			event_name = cells[0].find_element(
				by=By.XPATH,
				value=".//a/span"
			).text
		except:
			event_name = ""
		event_name_list.append(event_name)

		organizer_types = cells[1].find_elements(
			by=By.XPATH,
			value=".//span"
		)
		organizer_type_list.append([item.text for item in organizer_types])

		attendees_tags = cells[2].find_elements(
			by=By.XPATH,
			value=".//span"
		)
		attendees_result_list.append([item.text for item in attendees_tags])

		oppotunities_tags = cells[3].find_elements(
			by=By.XPATH,
			value=".//span"
		)
		oppotunities_list.append([item.text for item in oppotunities_tags])

		try:
			attendances = cells[4].find_element(
				by=By.XPATH,
				value=".//span"
			).text
		except:
			attendances = ""
		attendances_list.append(attendances)

		try:
			start_time = cells[5].find_element(
				by=By.XPATH,
				value="./div/div/div/div"
			).text
		except:
			start_time = ""
		start_time_list.append(start_time)

		try:
			end_time = cells[6].find_element(
				by=By.XPATH,
				value="./div/div/div/div"
			).text
		except:
			end_time = ""
		end_time_list.append(end_time)


		try:
			websites = cells[7].find_element(
				by=By.XPATH,
				value="./div/div/div/a"
			).text
		except:
			websites = ""
		websites_list.append(websites)

		try:
			sponsorship_site = cells[8].find_element(
				by=By.XPATH,
				value="./div/div/div/a"
			).text
		except:
			sponsorship_site = ""
		sponsorship_site_list.append(sponsorship_site)

		try:
			sponsor_download = cells[9].find_element(
				by=By.XPATH,
				value="./div/div/div/div/span"
			).text
		except:
			sponsor_download = ""
		sponsor_download_list.append(sponsor_download)

		try:
			linkedin = cells[10].find_element(
				by=By.XPATH,
				value=".//span/a"
			).text
		except:
			linkedin = ""
		linkedin_list.append(linkedin)

		try:
			attendee_list = cells[11].find_element(
				by=By.XPATH,
				value=".//span/a"
			).text
		except:
			attendee_list = ""
		attendee_list_list.append(attendee_list)

		try:
			venue = cells[12].find_element(
				by=By.XPATH,
				value=".//span"
			).text
		except:
			venue = ""
		venue_list.append(venue)

		try:
			city = cells[13].find_element(
				by=By.XPATH,
				value=".//span"
			).text
		except:
			city = ""
		city_list.append(city)

		try:
			state_of_province = cells[14].find_element(
				by=By.XPATH,
				value=".//span"
			).text
		except:
			state_of_province = ""
		state_of_province_list.append(state_of_province)

		try:
			country = cells[15].find_element(
				by=By.XPATH,
				value=".//span"
			).text
		except:
			country = ""
		country_list.append(country)

		try:
			low_price = cells[16].find_element(
				by=By.XPATH,
				value=".//div[contains(text(), '$')]"
			).text
		except:
			low_price = ""
		low_price_list.append(low_price)

		try:
			high_price = cells[17].find_element(
				by=By.XPATH,
				value=".//div[contains(text(), '$')]"
			).text
		except:
			high_price = ""
		high_price_list.append(high_price)

		try:
			early_bird_dealine = cells[18].find_element(
				by=By.XPATH,
				value=".//div[contains(text(), '/')]"
			).text
		except:
			early_bird_dealine = ""
		early_bird_dealine_list.append(early_bird_dealine)

		try:
			sponsorship_contact_email = cells[19].find_element(
				by=By.XPATH,
				value=".//a[contains(text(), '@')]"
			).text
		except:
			sponsorship_contact_email = ""
		sponsorship_contact_email_list.append(sponsorship_contact_email)

		try:
			sponsorship_contact_name = cells[20].find_element(
				by=By.XPATH,
				value=".//span"
			).text
		except:
			sponsorship_contact_name = ""
		sponsorship_contact_name_list.append(sponsorship_contact_name)

		try:
			latest_sponsor_list = cells[22].find_element(
				by=By.XPATH,
				value=".//a"
			).text
		except:
			latest_sponsor_list = ""
		latest_sponsor_list_list.append(latest_sponsor_list)

		try:
			sponsors_exhibitors = cells[23].find_element(
				by=By.XPATH,
				value=".//span"
			).text
		except:
			sponsors_exhibitors = ""
		sponsors_exhibitors_list.append(sponsors_exhibitors)

		try:
			peek_url = cells[23].find_element(
				by=By.XPATH,
				value=".//a"
			).text
		except:
			peek_url = ""
		peek_url_list.append(peek_url)

		try:
			notes = cells[24].find_element(
				by=By.XPATH,
				value=".//span"
			).text
		except:
			notes = ""
		notes_list.append(notes)


	driver.close()

	df = pandas.DataFrame({
		'Event name': event_name_list,
		'Organizer type': organizer_type_list,
		'Attendees': attendees_result_list,
		'Oppotunities': oppotunities_list,
		"Attendance": attendances_list,
		"Start": start_time_list,
		"End": end_time_list,
		"Website": websites_list,
		"Sponsorship site": sponsorship_site_list,
		"Sponsor download": sponsor_download_list,
		"LinkedIn": linkedin_list,
		"Attendee list": attendee_list_list,
		"Venue": venue_list,
		"City": city_list,
		"State of province": state_of_province_list,
		"Country": country_list,
		"Low price non-members": low_price_list,
		"High price non-memebers": high_price_list,
		"Early bird deadline": early_bird_dealine_list,
		"Sponsorship contact email": sponsorship_contact_email_list,
		"Sponsorship contact name": sponsorship_contact_name_list,
		"Files and media": "",
		"Latest sponsor list": latest_sponsor_list_list,
		"Sponsors & Exhibitors": sponsors_exhibitors_list, 
		"Peek URL": peek_url_list,
		"Notes": notes_list,
	})
	df.to_csv("./notion_eventhunter.csv", index=False)

if __name__ == "__main__":
	main()