import json
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.chrome.service import Service

def get_custom_driver(headless=False, autoclose=True) -> WebDriver:
    options = webdriver.ChromeOptions()
    options.headless = headless
    options.set_capability("goog:loggingPrefs", {'performance': 'ALL'}) 
    driver = webdriver.Chrome(
        options=options
    )
    driver.maximize_window()
    return driver

def get_responses(driver: WebDriver, url: str):
    responses = []  # list to store each response
    response = None
    perfLog = driver.get_log('performance')
    for logIndex in range(0, len(perfLog)):  # Parse the Chrome Performance logs
        logMessage = json.loads(perfLog[logIndex]["message"])["message"]
        if logMessage["method"] == "Network.responseReceived":  # Filter out HTTP responses
            # append each response to self.responses
            responses.append(logMessage["params"]["response"])
            # create instance attributes containing the response call for self.url
            print(logMessage["params"]["response"]["url"])
            if logMessage["params"]["response"]["url"] == url:
                response = logMessage["params"]["response"]

    """TODO: normallize urls and compare:
    https://www.linkedin.com/jobs/search/?f_TPR=r2592000&keywords=Dynamics%20365&location=United%20Kingdom&origin=JOB_SEARCH_PAGE_JOB_FILTER&start=0
    https://www.linkedin.com/jobs/search/?f_TPR=r2592000&keywords=Dynamics 365&location=United%20Kingdom&origin=JOB_SEARCH_PAGE_JOB_FILTER&start=0
    """

    return (response, responses)
