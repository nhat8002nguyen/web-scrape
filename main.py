import requests
from bs4 import BeautifulSoup
from collections import Counter
from string import punctuation

# Getting content from web page
r = requests.get("https://techoid.co/contact-us")
soup = BeautifulSoup(r.content, features="lxml")

# For getting words within paragrphs
text_paragraph = (''.join(s.find_all(string=lambda s : s == s.parent.string))for s in soup.find_all('p'))
count_paragraph = Counter((x.rstrip(punctuation).lower() for y in text_paragraph for x in y.split()))

# For getting words inside div tags
text_div = (''.join(s.find_all(lambda s: s == s.parent.string))for s in soup.find_all('div'))
count_div = Counter((x.rstrip(punctuation).lower() for y in text_div for x in y.split()))

# Adding two counters for getting a list with words count (from most to less common)
total = count_div + count_paragraph
list_most_common_words = total.most_common() 

