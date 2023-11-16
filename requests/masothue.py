import requests
from bs4 import BeautifulSoup

with requests.Session() as c:
    url = "https://masothue.com/"
    foo = 1
    bar = "hello"

    c.headers['User-Agent'] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"

    response = c.get(url) 
    bs = BeautifulSoup(response.content, "html.parser") 

    token_input = bs.find("input", attrs={"name": "token"}) 
    print(token_input)
	
	
