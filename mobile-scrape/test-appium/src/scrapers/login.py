"""
Stub for real-app login flows.

When you have the target app, implement perform_login(driver) with
locators discovered via Appium Inspector (resource-id preferred).
"""


def perform_login(driver) -> None:
    """
    Example placeholders — replace with real selectors.

    # from appium.webdriver.common.appiumby import AppiumBy
    # email = driver.find_element(AppiumBy.ACCESSIBILITY_ID, "email")
    # email.send_keys(os.environ["APP_EMAIL"])
    # driver.find_element(AppiumBy.ACCESSIBILITY_ID, "login").click()
    """
    raise NotImplementedError(
        "Login is not required for the Contacts demo. "
        "Implement perform_login() when automating a real app."
    )
