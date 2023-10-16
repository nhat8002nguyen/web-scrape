from zenrows import ZenRowsClient
from bs4 import BeautifulSoup
import pandas
from concurrent.futures import ThreadPoolExecutor, as_completed

class Post:
	def __init__(self, title: str, image_urls: list, host_urls: dict, description: str) -> None:
		self.title = title
		self.image_urls = image_urls
		self.host_urls = host_urls
		self.description = description

	def __str__(self) -> str:
		return f'''
			title: {self.title}, 
			image_urls: {' ,'.join(self.image_urls) if type(self.image_urls) is list else None}, 
			host_urls: {' ,'.join(self.host_urls) if type(self.host_urls) is list else None}, 
			description: {self.description}
		'''

def crawl_page(client: ZenRowsClient, page: int) -> [Post]:
	# page will start from 1
	url = f"https://jpupskirts.club/p{page}"
	params = {"js_render":"true","antibot":"true"}

	response = client.get(url, params=params)

	soup = BeautifulSoup(response.content, 'lxml')

	rows = soup.find_all(name='div', attrs={'class', 'row post'})

	row_urls = []
	for row in rows:
		try:
			row_url = row.find(name='div', attrs={'class', 'post-description col mx-2'}).find(name='a')["href"]
			row_urls.append(row_url)	
		except:
			print("Error when get a tags in post-description")

	# Create a threadpool to run all the row_urls
	posts = []
	with ThreadPoolExecutor(max_workers=4) as pool:
		results = [pool.submit(crawl_post_detail, client, url) for url in row_urls]

		for result in as_completed(results):
			data = result.result()
			posts.append(data)	

	return posts

def crawl_post_detail(client: ZenRowsClient, url: str) -> Post | None:
	params = {"js_render":"true","antibot":"true"}
	response = client.get(url, params)
	soup = BeautifulSoup(response.content, 'lxml')
	post_container = soup.find(
			name='div', attrs={'class', 'posts container'}
		)
	if post_container is None:
		return None

	print(post_container.text)

	try:	
		title = post_container.find(
			name='div', attrs={'class', 'row'}
		).find(
			name='h1'
		).text
	except:
		title = None
		pass

	try:
		img_tags = post_container.find_all(
			name='div', attrs=('class', 'row')
		)[1].find_all(
			name='img'
		)
		img_urls = [tag['src'] for tag in img_tags]
	except:
		img_urls = None
		pass

	try:
		host_divs = post_container.find(
			name='div',
			attrs={'class', 'row mt-3 ms-2'}
		).find_all(
			name='div'
		)
		host_urls = dict()
		for div in host_divs:
			host_urls[div.text] = div.find(name='a')['href']
	except:
		host_urls = None
		pass
		
	try:
		description = post_container.find(
			name='div',
			attrs={'class', 'row mt-2 px-3'}
		).text
	except:
		description = None
		pass

	post = Post(
		title=title,
		image_urls=img_urls,
		host_urls=host_urls,
		description=description
	)

	return post


def main():
	client = ZenRowsClient("97bfa5a20ea6989d3f7219834789e96a76c42611")

	posts = [Post]
	for index in range(1):
		results = crawl_page(client, index+1)
		posts.extend(results)

	with open('./others/zenrows/jpupskirts_texts.txt', 'w') as file:
		for post in posts:
			file.write(str(post))


if __name__ == "__main__":
	main()
