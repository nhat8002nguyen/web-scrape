from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def wait_for_presence(driver, locator, timeout=15):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located(locator)
    )


def wait_for_visible(driver, locator, timeout=15):
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located(locator)
    )


def wait_for_any_visible(driver, locators, timeout=15):
    """Return the first locator that becomes visible."""

    def _any_visible(drv):
        for locator in locators:
            elements = drv.find_elements(*locator)
            for el in elements:
                if el.is_displayed():
                    return el
        return False

    return WebDriverWait(driver, timeout).until(_any_visible)
