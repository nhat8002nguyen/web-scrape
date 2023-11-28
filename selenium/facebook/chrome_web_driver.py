import json
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.chrome.service import Service
from urllib.parse import unquote
from selenium.webdriver.chrome.options import Options


def get_custom_driver(headless=False, autoclose=True) -> WebDriver:
    options = Options()
    # options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--start-maximized')
    # options.add_argument(f"--user-data-dir={user_data_dir}")
    # options.add_argument('--auto-open-devtools-for-tabs')

    if headless:
        options.add_argument("--headless")
    options.set_capability("goog:loggingPrefs", {'performance': 'ALL'})
    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    return driver

class ResponseData:
    request_url: str
    status_code: int
    headers: {}
    data: {}

    def __init__(self, status_code=0, headers={}, data={}, request_url="") -> None:
        self.request_url = request_url
        self.status_code = status_code
        self.headers = headers
        self.data = data


class DriverResponseResult:
    response: ResponseData | None
    responses: list[ResponseData]

    def __init__(self, response, responses) -> None:
        self.response = response
        self.responses = responses


def get_responses(driver: WebDriver, url: str) -> DriverResponseResult:
    responses = list[ResponseData]()
    cur_resp = None
    unquote_url = unquote(url)
    perfLog = driver.get_log('performance')
    for logIndex in range(0, len(perfLog)):
        logMessage: {} = json.loads(perfLog[logIndex]["message"])["message"]
        if 'Network.response' in logMessage["method"]:
            if "params" not in logMessage:
                continue

            resp_data = None
            response = {}
            params: {} = logMessage["params"]
            resp_data = ResponseData()
            if "statusCode" in params:
                resp_data.status_code = params["statusCode"]
            if "headers" in params:
                resp_data.headers = params["headers"]

            if "response" in params:
                response = params["response"]
                if "status" in response:
                    resp_data.status_code = response["status"]
                if "headers" in response:
                    resp_data.headers = response["headers"]

            if "requestId" in params:
                requestId = params["requestId"]
                try:
                    response_data = driver.execute_cdp_cmd(
                        'Network.getResponseBody', {'requestId': requestId})
                    if "body" in response_data:
                        data = json.loads(response_data["body"])
                        if "included" in data:
                            resp_data.data = data
                except:
                    pass

            responses.append(resp_data)

            if "url" in response:
                resp_data.request_url = response["url"]

                resp_url = response["url"]
                unquote_resp_url = unquote(resp_url)

                if unquote_resp_url == unquote_url:
                    cur_resp = resp_data

    return DriverResponseResult(response=cur_resp, responses=responses)
