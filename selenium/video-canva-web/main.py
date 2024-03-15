from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, MoveTargetOutOfBoundsException
from selenium.webdriver.common.by import By
from seleniumbase import Driver

from time import sleep, perf_counter
from selenium.webdriver.common.action_chains import ActionChains
import easyocr


def main():
    # Using selenium
    print("Started the program!")

    driver: WebDriver = Driver(headless=False, no_sandbox=True, uc=True)
    driver.maximize_window()

    wait = WebDriverWait(driver, 120)

    driver.get("https://demo.luckystreaklive.com")

    sleep(120)

    body = driver.find_element(by=By.CSS_SELECTOR, value="body")

    # Get the size of the body element
    size = body.size

    middle_x = size['width'] // 2
    bottom_y = size['height'] - 10
    middle_y = size['height'] // 2 + 20
    actions = ActionChains(driver)
    actions.move_by_offset(middle_x, bottom_y)

    keepPlayingActions = ActionChains(driver)
    keepPlayingActions.move_by_offset(middle_x, middle_y)

    while True:
        if driver.window_handles[1] != None:
            driver.switch_to.window(driver.window_handles[1])
        driver.save_screenshot("./room.png")

        reader = easyocr.Reader(['en'])  # specify language(s)
        results = reader.readtext('./room.png')
        for (bbox, text, prob) in results:
            if text == "REBET":
                try:
                    actions.click()
                    actions.perform()
                    print("Clicked the button REBET!")

                    break
                except MoveTargetOutOfBoundsException as e:
                    print("Move target failed, retrying...")

            if str(text).lower() == "keep playing":
                try:
                    keepPlayingActions.click()
                    keepPlayingActions.perform()
                    break
                except:
                    pass

        sleep(5)


if __name__ == "__main__":
    main()
