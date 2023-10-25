from bs4 import BeautifulSoup
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import pandas

common_headers = {
			"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0", 
			"Accept-Encoding":"gzip, deflate", 
			"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", 
			"DNT":"1",
			"Connection":"close", 
			"Upgrade-Insecure-Requests":"1"
		}

class User:
	def __init__(self, user_name: str, location: str, email: str, website: str, twitter: str, github: str, linkedIn: str) -> None:
		self.user_name = user_name
		self.location = location
		self.email = email
		self.website = website
		self.twitter = twitter
		self.github = github
		self.linkedIn = linkedIn

	def __str__(self) -> str:
		return f'''user_name: {self.user_name}, location: {self.location}, email: {self.email}, website: {self.website},
			twitter: {self.twitter}, github: {self.github}, linkedin: {self.linkedIn}.
		'''
	
	def clean_duplicate_spaces(self):
		self.user_name = " ".join(self.user_name.split())
		self.location = " ".join(self.location.split())
		self.email = " ".join(self.email.split())
		self.website = " ".join(self.website.split())
		self.twitter = " ".join(self.twitter.split())
		self.github = " ".join(self.github.split())
		self.linkedIn = " ".join(self.linkedIn.split())

def main():
	react_users = list[str]()
	with ThreadPoolExecutor(max_workers=8) as pool:
		futures = []
		for i in range(1000):
			future = pool.submit(get_react_user_urls, f"https://stackoverflow.com/users?page={i+1}&tab=reputation&filter=week")
			futures.append(future)

		for result in as_completed(futures):
			data = result.result()
			react_users.extend(data)

	# wait for next process
	print("Waiting for 10 seconds before proceed further!")
	time.sleep(10)

	print("Starting get users details...")
	user_infos = get_users(react_users)
	
	print("Starting saving results to file...")
	save_to_file(user_infos)

def save_to_file(users: list[User]) -> None:
	user_names = []
	locations = []
	emails = []
	websites = []
	twitters = []
	githubs = []
	linkedins = []

	for user in users:
		user_names.append(user.user_name)
		locations.append(user.location)
		emails.append(user.email)
		websites.append(user.website)
		twitters.append(user.twitter)
		githubs.append(user.github)
		linkedins.append(user.linkedIn)

	df = pandas.DataFrame({
		'user name': user_names,
		'location': locations,
		'email': emails,
		'website': websites,
		'twitter': twitters,
		'github': githubs,
		'linkedin': linkedins
	})

	df.to_csv(f"./stackoverflow_{len(users)}_react_users.csv", index=False)

def get_users(urls: list[str]) -> list[User]:
	users = list[User]()
	with ThreadPoolExecutor(max_workers=8) as pool:
		futures = []
		for url in urls:
			future = pool.submit(get_user_details, f"https://stackoverflow.com{url}")
			futures.append(future)

		for result in as_completed(futures):
			data = result.result()
			users.append(data)

	return users

def get_user_details(url: str) -> User:
	response = requests.get(
		url=url,
		headers=common_headers,
	)
	soup = BeautifulSoup(response.content, 'html.parser')	

	user = User(
		user_name="Empty",
		location="Empty",
		email="Empty",
		website="Empty",
		twitter="Empty",
		github="Empty",
		linkedIn="Empty"
	)

	user_name_tag = soup.find(
		name="div",
		attrs={"class", "fs-headline2"}
	)
	if user_name_tag is not None:
		user.user_name = user_name_tag.text
	
	location_tag = soup.find(
		name="div",
		attrs={"class", "wmx2"}
	)
	if location_tag is not None:
		user.location = location_tag.text

	lines = soup.find_all(
		name="ul",
		attrs={"class", "list-reset"}
	)
	if len(lines) > 1:
		media_container = lines[1]
		media_items = media_container.find_all(
			name="li"
		)
		for item in media_items:
			link = item.find(name="a")
			if link is None:
				continue
			url = link["href"]
			if "twitter" in url:
				user.twitter = url
			if "github" in url:
				user.github = url
			if "linkedin" in url:
				user.linkedIn = url
			if item.find(name="svg", attrs={"class", "iconLink"}) is not None:
				user.website = url

	user.clean_duplicate_spaces()
	print(user)
	return user
	

	
def get_react_user_urls(page: str) -> []:
	response = requests.get(
		url=page,
		headers=common_headers,
	)
	soup = BeautifulSoup(response.content, 'html.parser')

	users = soup.find_all(
		name="div",
		attrs={"class", "user-info"}
	)

	react_users = list[str]()
	for user in users:
		tags = user.find(
			name="div",
			attrs={"class", "user-tags"}
		)
		if "react" in tags.text:
			user_url = user.find(
				name="div",
				attrs={"class", "user-details"}
			).find(
				name="a"
			)["href"]
			print(user_url)

			react_users.append(user_url)

	return react_users

if __name__ == "__main__":
	main()