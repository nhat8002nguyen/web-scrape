import json
from selenium.webdriver.chrome.webdriver import WebDriver
from urllib.parse import unquote
from seleniumbase import Driver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium import webdriver


# def get_custom_driver(headless=False, autoclose=True) -> WebDriver:
#     driver: WebDriver = Driver(
#         uc=True, no_sandbox=True, headless=headless,
#         devtools=False,
#         cap_string="{'goog:loggingPrefs': {'performance': 'ALL'},}"
#     )
#     driver.maximize_window()
#     return driver

def get_custom_driver(headless=False, autoclose=True) -> WebDriver:
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless")
    options.set_capability("goog:loggingPrefs", {'performance': 'ALL'})
    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    return driver


class ResponseData:
    request_id: str
    request_url: str
    status_code: int
    headers: {}
    data: {}
    text_data = ""

    def __init__(
            self, request_id="", status_code=0, headers={}, data={}, request_url="", text_data=""
        ) -> None:
        self.request_id = request_id
        self.request_url = request_url
        self.status_code = status_code
        self.headers = headers
        self.data = data
        self.text_data = text_data


class DriverResponseResult:
    response: ResponseData | None
    responses: list[ResponseData]

    def __init__(self, response, responses) -> None:
        self.response = response
        self.responses = responses


def get_responses(driver: WebDriver, url: str = "") -> DriverResponseResult:
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
                resp_data.request_id = requestId
                try:
                    response_data = driver.execute_cdp_cmd(
                        'Network.getResponseBody', {'requestId': requestId})
                    if "body" in response_data:
                        resp_data.text_data: str = response_data["body"]
                        try:
                            first_curly_bracket = resp_data.text_data.index(
                                "{")
                            second_curly_bracket = resp_data.text_data.rfind(
                                "}")
                            resp_data.data = json.loads(
                                resp_data.text_data[first_curly_bracket:second_curly_bracket+1])
                        except:
                            pass
                except Exception as err:
                    pass

            responses.append(resp_data)

            if "url" in response:
                resp_data.request_url = response["url"]

                resp_url = response["url"]
                unquote_resp_url = unquote(resp_url)

                if unquote_resp_url == unquote_url:
                    cur_resp = resp_data

    return DriverResponseResult(response=cur_resp, responses=responses)
