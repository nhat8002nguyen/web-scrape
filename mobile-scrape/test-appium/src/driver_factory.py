import json
import os
from pathlib import Path

from appium import webdriver
from appium.options.android import UiAutomator2Options
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_capabilities() -> dict:
    load_dotenv(PROJECT_ROOT / ".env")

    caps_path = os.getenv("CAPABILITIES_PATH", "config/capabilities.android.json")
    full_path = PROJECT_ROOT / caps_path
    with open(full_path, encoding="utf-8") as f:
        caps = json.load(f)

    device_name = os.getenv("ANDROID_DEVICE_NAME", "").strip()
    if device_name:
        caps["appium:deviceName"] = device_name

    app_package = os.getenv("APP_PACKAGE", "").strip()
    if app_package:
        caps["appium:appPackage"] = app_package

    app_activity = os.getenv("APP_ACTIVITY", "").strip()
    if app_activity:
        caps["appium:appActivity"] = app_activity

    return caps


def create_driver():
    """Create an Appium WebDriver session from capabilities + .env."""
    load_dotenv(PROJECT_ROOT / ".env")
    appium_url = os.getenv("APPIUM_URL", "http://127.0.0.1:4723")
    caps = _load_capabilities()
    options = UiAutomator2Options().load_capabilities(caps)
    return webdriver.Remote(appium_url, options=options)
