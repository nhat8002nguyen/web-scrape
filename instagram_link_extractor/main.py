import pandas as pd
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random

start = time.perf_counter()

# Read domains from Excel
# Replace with your actual file
df = pd.read_excel("look_for_instagram_all.xlsx")

proxyEndpoints = []
with open("proxies.txt") as file:
    lines = file.read().split("\n")
    for l in lines[:100]:
        parts = l.split(":")
        proxyEndpoints.append(
            f"{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}")


def getRequestsProxy():
    rand = random.choice(proxyEndpoints)
    return {
        'https': f"http://{rand}",
        'http': f"http://{rand}"
    }


def getSeleniumProxy():
    return random.choice(proxyEndpoints)


# Set up Selenium
chrome_options = Options()
# Run Chrome in headless mode (no GUI)
chrome_options.add_argument("--headless")
# chrome_options.add_argument("--proxy-server=%s" % getSeleniumProxy())

driver = webdriver.Chrome(options=chrome_options)
driver.set_page_load_timeout(5)


def get_instagram_links(url, depth=0, max_depth=1):
    """Recursively extracts Instagram links from a URL up to a specified depth."""

    if depth > max_depth:
        return []

    try:
        # First, try with Requests (faster if no JavaScript is needed)
        response = requests.get(url, timeout=5, proxies=getRequestsProxy())
        response.raise_for_status()  # Raise an exception for bad status codes

        soup = BeautifulSoup(response.content, 'html.parser')
        links = [a['href'] for a in soup.find_all(
            'a', href=True) if 'instagram.com' in a['href']]

        # If no Instagram links found, try with Selenium (for JavaScript-heavy sites)
        if not links:
            try:
                driver.get(url)
                WebDriverWait(driver, 5).until(EC.presence_of_element_located(
                    (By.TAG_NAME, 'body')))  # Wait for page to load

                driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)  # wait for the page to load

                soup = BeautifulSoup(driver.page_source, 'html.parser')
                links = [a['href'] for a in soup.find_all(
                    'a', href=True) if '.instagram.com' in a['href']]
            except TimeoutError:
                print(f"{url} timeout.")
            except:
                pass

        # Recursively crawl child pages
        child_links = []
        for link in soup.find_all('a', href=True):
            abs_url = urljoin(url, link['href'])
            if "/contact" in abs_url or "/about" in abs_url:
                child_links.extend(get_instagram_links(abs_url, depth + 1))

        return links + child_links

    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []


# Process each domain and store results
# Assuming your Excel column is named 'Domain'
for domain in df['Organisation - Website']:
    existLink = df.loc[df['Organisation - Website']
                       == domain, "Instagram Link 1"].count()
    if existLink > 0:
        continue

    schemed_domain = domain
    # Add 'https://' if scheme is missing
    if not domain.startswith('http://') and not domain.startswith('https://'):
        schemed_domain = 'https://' + domain

    instagram_links = get_instagram_links(schemed_domain)

    unique_ins_links = list(set(instagram_links))
    print(unique_ins_links)

    # Create new columns for each Instagram link
    for i, link in enumerate(unique_ins_links):
        col_name = f"Instagram Link {i + 1}"
        if col_name not in df:
            df[col_name] = ''

        df.loc[df['Organisation - Website'] == domain, col_name] = link

    df.to_excel("look_for_instagram_all.xlsx", index=False)

# Save results back to Excel
df.to_excel("look_for_instagram_all.xlsx", index=False)

driver.quit()  # Close the Selenium browser

print(time.perf_counter() - start)
