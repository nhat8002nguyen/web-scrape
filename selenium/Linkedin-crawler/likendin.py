import seleniumwire.undetected_chromedriver as uc
import pickle
import time
import json
from seleniumwire.utils import decode , decoder

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from datetime import datetime, timedelta
import re
from job_boards import insertJobBoardObject
from chrome_web_driver import get_custom_driver, get_responses 

def extract_numbers_from_string(input_string):
    # Use regular expression to find all numeric substrings
    numbers = re.findall(r'\d+', input_string)
    
    # Convert the strings to integers
    numbers = list(map(int, numbers))

    return numbers


def calculate_posted_date(date):
    current_date = datetime.now()

    # Calculate dates 2 minutes, 2 days, 2 hours, and 2 weeks ago
    if "minute" in date:
        n = extract_numbers_from_string(date)
        minutes_ago = current_date - timedelta(minutes=n[0])
        return minutes_ago
    if "day" in date:
        n = extract_numbers_from_string(date)
        days_ago = current_date - timedelta(days=n[0])
        return days_ago
    if "hour" in date :
        n = extract_numbers_from_string(date)
        hours_ago = current_date - timedelta(hours=n[0])
        return hours_ago
    if "week" in date :
        n = extract_numbers_from_string(date)
        weeks_ago = current_date - timedelta(weeks=n[0])
        return weeks_ago
    return current_date


def login_linkedin(driver):
    try :
        driver.get("https://www.linkedin.com/")
        cookies = pickle.load(open("linkedin_cookies.pkl", "rb"))
        for cookie in cookies:
            driver.add_cookie(cookie)

        driver.refresh()
        time.sleep(5)
        return driver
    except FileNotFoundError :
        input('please login to your account :')
        pickle.dump(driver.get_cookies(), open("linkedin_cookies.pkl", "wb"))
        return driver
   

#
def get_job_ids_month(driver):
    page = 0
    job_ids = []
    companies = {}
    while True :
        print("Start getting job ids and doing paginations ... ")
        print("please wait to download all job id FROM AJAX API.")
        #f_TPR=r2592000 one month
        keywords = "Dynamics 365"
        url = f'https://www.linkedin.com/jobs/search/?f_TPR=r2592000&keywords={keywords}&location=United%20Kingdom&origin=JOB_SEARCH_PAGE_JOB_FILTER&start={page}'
        driver.get(url)
        time.sleep(5)
        i =1

        resp, resps = get_responses(driver=driver, url=url)

        for request in driver.requests:
                
            if  f"/voyager/api/voyagerJobsDashJobCards?" in request.url:
                if request.response:
                    
                    print(f"getting from API : {request.url}",request.response.status_code)
                    #dict_keys(['data', 'meta', 'included'])
                    # try:
                    body = decode(request.response.body,encoding=request.response.headers.get('Content-Encoding'))
            
                # Load the JSON
                    result = json.loads(body.decode('utf-8'))['included']
                    
                    for r in result:
                        
                        try:
                            job_id = r['jobPostingUrn'].replace('urn:li:fsd_jobPosting:','')
                            lenght_list_helper = len(job_ids)
                            if job_id not in job_ids: 
                                job_ids.append(job_id)
                            companies[job_id]= r['primaryDescription']['text']
                        except KeyError:
                            pass
        if lenght_list_helper == len(job_ids):
            return [job_ids,driver,companies]
        else :
            lenght_list_helper == len(job_ids)

        page = page +25


def get_job_ids_day(driver):
    page = 0
    job_ids = []
    companies = {}
    while True :
        print("Start getting job ids and doing paginations ... ")
        print("please wait to download all job id FROM AJAX API.")
        #&f_TPR=r86400 24 hours
        keywords = "Dynamics 365"
        driver.get(f'https://www.linkedin.com/jobs/search/?f_TPR=r86400&keywords={keywords}&location=United%20Kingdom&origin=JOB_SEARCH_PAGE_JOB_FILTER&start={page}')
        time.sleep(5)
        i =1
        for request in driver.requests:
                
            if  f"/voyager/api/voyagerJobsDashJobCards?" in request.url:
                if request.response:
                    
                    print(f"getting from API : {request.url}",request.response.status_code)
                    #dict_keys(['data', 'meta', 'included'])
                    # try:
                    body = decode(request.response.body,encoding=request.response.headers.get('Content-Encoding'))
            
                # Load the JSON
                    result = json.loads(body.decode('utf-8'))['included']
                    
                    for r in result:
                        
                        try:
                            job_id = r['jobPostingUrn'].replace('urn:li:fsd_jobPosting:','')
                            lenght_list_helper = len(job_ids)
                            if job_id not in job_ids: 
                                job_ids.append(job_id)
                            companies[job_id]= r['primaryDescription']['text']
                        except KeyError:
                            pass
        if lenght_list_helper == len(job_ids):
            return [job_ids,driver,companies]
        else :
            lenght_list_helper == len(job_ids)

        page = page +25


def get_items(driver,compagnies,job_ids):
    items = []
    for job_id in job_ids:
        d = {}
        print(f"download data of job with id : {job_id}")
        driver.get(f'https://www.linkedin.com/jobs/view/{job_id}')
        d['job_id'] = f"linkedin{job_id}"
        d['source'] = "linkedin"
        d['source'] = "linkedin"
        d['address'] = "FROM JALIL"
        d['joblocationinput'] = "United Kingdom"
       

        d['jobtitle'] = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//h1'))
        ).text
        # d['compagny_name'] = WebDriverWait(driver, 10).until(
        #     EC.presence_of_element_located((By.XPATH, '//div[@class="job-details-jobs-unified-top-card__primary-description"]//a'))
        # ).text
        d['company'] = compagnies[job_id]
        # d['description'] = WebDriverWait(driver, 10).until(
        #     EC.presence_of_element_located((By.XPATH, '//article'))
        # ).text.strip()
        
        spans = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//div[@class="job-details-jobs-unified-top-card__primary-description"]//span'))
        )
        for span in spans:
            if "week" in span.text or "day" in span.text or "hour" in  span.text or "minute" in span.text:
                d['posted'] = calculate_posted_date(span.text)
        time.sleep(5)
        request_count = 0
        requests = driver.requests
        for request in requests:
                request_count = request_count + 1
                    
                if  f"/api/jobs/jobPostings/{job_id}" in request.url:
                    if request.response:

                        print(request.url,request.response.status_code)
                        #dict_keys(['data', 'meta', 'included'])
                        # try:
                        body = decode(request.response.body,encoding=request.response.headers.get('Content-Encoding'))
                
                    # Load the JSON
                        result = json.loads(body.decode('utf-8'))['data']['description']['text']
                        
                        d['description'] = result
                        if d['description'] and  request_count == len (requests):
                            break
                        elif request_count == len (requests) :
                            driver.refresh()
                            requests = driver.requests
                        else :
                            pass
        try:        
            if d['description'] :
                pass
            else :
                d['description'] = driver.find_element_by_tag_name('body').text.split('About the job')[1] 
        except KeyError:
            d['description'] = driver.find_element_by_tag_name('body').text.split('About the job')[1]

        print(d)
        insertJobBoardObject(d)
        items.append(d)
    return items

chrome_options = uc.ChromeOptions()
chrome_options.headless = True
# chrome_options.add_argument({'headless':False})
chrome_options.add_argument("--start-maximized")

driver = uc.Chrome(
    options=chrome_options,
    seleniumwire_options={}
)

# service = Service(ChromeDriverManager().install())
# driver = webdriver.Chrome(
#     options=chrome_options,
#     service=service
# )
# driver.maximize_window()
# driver = login_linkedin(driver=driver)

# while True:
#     print("getting jobs for the last month...")
#     job_ids = get_job_ids_month(driver=driver)[0]
#     driver = get_job_ids_month(driver=driver)[1]
#     compagnies = get_job_ids_month(driver=driver)[2]
#     items = get_items(driver=driver,job_ids=job_ids,compagnies=compagnies)
#     print(items)
#     while True :
#         print("getting jobs for the last 24 hours...")
#         job_ids = get_job_ids_month(driver=driver)[0]
#         driver = get_job_ids_month(driver=driver)[1]
#         compagnies = get_job_ids_month(driver=driver)[2]
#         items = get_items(driver=driver,job_ids=job_ids,compagnies=compagnies)
#         print(items)

def main():
    driver = get_custom_driver()

    driver = login_linkedin(driver)

    while True:
        print("getting jobs for the last month...")
        job_ids = get_job_ids_month(driver=driver)[0]
        driver = get_job_ids_month(driver=driver)[1]
        compagnies = get_job_ids_month(driver=driver)[2]
        items = get_items(driver=driver,job_ids=job_ids,compagnies=compagnies)
        print(items)
        while True :
            print("getting jobs for the last 24 hours...")
            job_ids = get_job_ids_month(driver=driver)[0]
            driver = get_job_ids_month(driver=driver)[1]
            compagnies = get_job_ids_month(driver=driver)[2]
            items = get_items(driver=driver,job_ids=job_ids,compagnies=compagnies)
            print(items)

if __name__ == "__main__":
    main()


    
    

                
    