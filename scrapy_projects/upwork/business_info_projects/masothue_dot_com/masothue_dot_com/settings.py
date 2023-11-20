# Scrapy settings for masothue_dot_com project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = "masothue_dot_com"

SPIDER_MODULES = ["masothue_dot_com.spiders"]
NEWSPIDER_MODULE = "masothue_dot_com.spiders"


# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = "masothue_dot_com (+http://www.yourdomain.com)"

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Configure maximum concurrent requests performed by Scrapy (default: 16)
#CONCURRENT_REQUESTS = 32

# Configure a delay for requests for the same website (default: 0)
# See https://docs.scrapy.org/en/latest/topics/settings.html#download-delay
# See also autothrottle settings and docs
DOWNLOAD_DELAY = 0.2 
# The download delay setting will honor only one of:
CONCURRENT_REQUESTS_PER_DOMAIN = 32
CONCURRENT_REQUESTS_PER_IP = 32
AUTOTHROTTLE_ENABLED = False

# Disable cookies (enabled by default)
#COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
#TELNETCONSOLE_ENABLED = False

# Override the default request headers:
#DEFAULT_REQUEST_HEADERS = {
#    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#    "Accept-Language": "en",
#}
DEFAULT_REQUEST_HEADERS = {
    "X-Crawlera-Profile": "desktop",
    "X-Crawlera-Cookies": "disable",
}

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
#SPIDER_MIDDLEWARES = {
#    "masothue_dot_com.middlewares.MasothueDotComSpiderMiddleware": 543,
#}

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
#    "masothue_dot_com.middlewares.MasothueDotComDownloaderMiddleware": 543,
    # use zyte smart proxy manager
	# 'scrapy_zyte_smartproxy.ZyteSmartProxyMiddleware': 610,

    # rotate proxy with a proxy rotation endpoint 
    'masothue_dot_com.middlewares.CustomProxyMiddleware': 350,

    # use proxy list file with free
    # 'rotating_proxies.middlewares.RotatingProxyMiddleware': 610,
    # 'rotating_proxies.middlewares.BanDetectionMiddleware': 620,
}

# Setting for zyte smart proxy manager
# ZYTE_SMARTPROXY_ENABLED = True
# ZYTE_SMARTPROXY_APIKEY = os.environ["ZYTE_SMART_PROXY_API_KEY"]
# AUTOTHROTTLE_ENABLED = False
# CONCURRENT_REQUESTS = 32
# CONCURRENT_REQUESTS_PER_DOMAIN = 32
DOWNLOAD_TIMEOUT = 3000

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
#HTTPCACHE_DIR = "httpcache"
#HTTPCACHE_IGNORE_HTTP_CODES = []
#HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Set settings whose default value is deprecated to a future-proof value
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

# Configure feed exporters
FEED_EXPORTERS = {     
    'xlsx': 'scrapy_xlsx.XlsxItemExporter',
}

# add proxy list path
# ROTATING_PROXY_LIST_PATH = './proxy_list.txt'

# RETRY CONFIG
RETRY_ENABLED = True
RETRY_TIMES = 1  # initial response + 2 retries = 3 requests
RETRY_HTTP_CODES = [403]