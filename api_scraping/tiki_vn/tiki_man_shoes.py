import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import pandas

class Product:
	def __init__(self, name, price, seller_id) -> None:
		self.name = name
		self.price = price
		self.seller_id = seller_id

def get_man_shoes(page):
	response = requests.get(
		url=f'https://tiki.vn/api/personalish/v1/blocks/listings?limit=40&include=advertisement&aggregations=2&version=home-persionalized&trackity_id=4a0e9817-2c10-5833-3fa5-fae103ac6971&category=1686&page={page}&urlKey=giay-dep-nam',
		headers={
			'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
			'x-access-token': 'eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiI1NDE0NzIzIiwiaWF0IjoxNjk1ODY2NTMyLCJleHAiOjE2OTU5NTI5MzIsImlzcyI6Imh0dHBzOi8vdGlraS52biIsImN1c3RvbWVyX2lkIjoiNTQxNDcyMyIsImVtYWlsIjoibnYubmhhdDgwMDJAZ21haWwuY29tIiwiY2xpZW50X2lkIjoidGlraS1zc28iLCJuYW1lIjoiNTQxNDcyMyIsInNjb3BlIjoic3NvIn0.GZi6WjedabdZcYKuk--V6sbMA5QBcgSLr19XtYfY7alwNPoMweOxYzoTHRdeS0h1XlErneWY4pUG29P1nWEESPl7DrgpF4FQgOpx9_T3Sck-Ptb6oOOIFV7Do6M1JOU93UZodprXJewVZnADd8TdXsoYPhd3IUT3r7GHYhBIzWq9ZfKcRrNkxuZC2ZTQxqinBx2LlPAwsLamg4ObvDHWJ_o4yKY2cJEj1U9H0ku_QNTEwylo170aGaDK5H7gBxpjk3YbfF_-QvShkIYku4OSY7SlQWYFYkB39bTIBUZ4aEUw57txYnTwWkt1PWQKV37kztrD3ehaK_6xuGJgfKg3Xv-p2eUM_-MPgCxM6MnuO6_x5klqx_Z-WbNiJTNUMIsopaw1fc5GpyK_PiXVDQ2z2AxHvyKi1Gs3347tU4YTUTcVuIWEdwW3dyTLIiieLGhzNO2-OlxvRYwbcYlSsrut9CQTokfWU1gXMXNj_TedCd_roEWjaoonKX2hTWUoMHr1JEmi3r1TbrVmxY7azkUfaMCD2MYT449sebnWbc3r5WQuLphqtu2qt-ns793e3QFleWsl-COBcB1MEK30sOyTC4Gq_w65URuPVQXplcy8GY-qe9qo3JJKbvkM8DIOuRH-GESDyfQy_XSMw6EKbEp4jaaoQuc1-JBIx2WiXrXeYjk'
		}
	)	

	json_response = json.loads(response.content)

	items = []
	for item in json_response.get('data'):
		prd = Product(
			name=item.get('name'), 
			price=item.get('price'),
			seller_id=item.get('seller_id')
			)

		items.append(prd)	

	return items

def main():
	results = []
	with ThreadPoolExecutor(max_workers=4) as executor:
		futures = [executor.submit(get_man_shoes, index+1) for index in range(4)]

		for future in as_completed(futures):
			result = future.result()
			results.extend(result)

	df = pandas.DataFrame(data=results)
	df.to_json('./get_man_shoes.json')
	
if __name__ == '__main__':
	main()	