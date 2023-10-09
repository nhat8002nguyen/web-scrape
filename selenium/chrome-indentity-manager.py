from selenium import webdriver

import time
import requests
from fake_useragent import UserAgent
import threading

lock = threading.Lock()

class ChromeIdentityManager:
	def __init__(self) -> None:
		self.user_agent_builder = UserAgent()

	def start_useragent_rotation(self):
		while True:
			lock.acquire()
			self._cur_ua = self.user_agent_builder.random
			lock.release()
			print(f'Current user-agent: {self._cur_ua}')

			time.sleep(20)

	# get new proxy server to bypass captcha, IP block
	def start_rotating_proxy_server(self):
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

			time.sleep(20)

	def get_ua(self):
		default_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/116.0'
		if self._cur_ua:
			return self._cur_ua
		return default_ua