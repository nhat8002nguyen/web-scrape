import json
import os
import re
import subprocess
import time
from pathlib import Path

from appium.webdriver.common.appiumby import AppiumBy
from dotenv import load_dotenv
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

from src.waits import wait_for_any_visible

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

SKIP_TEXT = frozenset(
    {
        "",
        "Contacts",
        "Search contacts",
        "Search",
        "Create contact",
        "Fix & manage",
        "Suggestions",
        "Labels",
        "Settings",
        "Navigate up",
        "Sign in",
        "Allow",
        "Don't allow",
        "Don’t allow",
        "While using the app",
        "Only this time",
        "No thanks",
        "Dismiss",
        "Go back",
        "Sync device and SIM contacts",
        "Never lose your contacts",
        "Highlights",
        "Fix & manage",
        "•",
        "All contacts",
        "(No name)",
        "Organize",
        "Favorites",
    }
)

ROW_LOCATOR_CANDIDATES = [
    (AppiumBy.ID, "com.google.android.contacts:id/cliv_name"),
    (
        AppiumBy.XPATH,
        "//*[@resource-id='com.google.android.contacts:id/contact_list']"
        "//android.widget.TextView",
    ),
    (
        AppiumBy.XPATH,
        "//*[@resource-id='com.google.android.contacts:id/contact_list_fragment']"
        "//android.widget.TextView",
    ),
    (
        AppiumBy.ANDROID_UIAUTOMATOR,
        (
            'new UiSelector().resourceId("com.google.android.contacts:id/contact_list")'
            '.childSelector(new UiSelector().className("android.widget.TextView"))'
        ),
    ),
    (
        AppiumBy.XPATH,
        "//androidx.recyclerview.widget.RecyclerView//android.widget.TextView",
    ),
]

ONBOARDING_LABELS = (
    "No thanks",
    "Dismiss",
    "Allow",
    "While using the app",
    "Only this time",
    "Don't allow",
    "Don’t allow",
)


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(None, 1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _row_key(row: dict) -> str:
    return "|".join(
        [
            row.get("first_name", ""),
            row.get("last_name", ""),
            row.get("company", ""),
        ]
    ).lower()


def _load_checkpoint(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("keys", []))


def _save_checkpoint(path: Path, keys: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"keys": sorted(keys)}, f, indent=2)


def _grant_contacts_permissions() -> None:
    permissions = [
        "android.permission.READ_CONTACTS",
        "android.permission.WRITE_CONTACTS",
        "android.permission.POST_NOTIFICATIONS",
    ]
    for permission in permissions:
        subprocess.run(
            [
                "adb",
                "shell",
                "pm",
                "grant",
                "com.google.android.contacts",
                permission,
            ],
            check=False,
            capture_output=True,
        )


def _tap_if_visible(driver, label: str) -> bool:
    try:
        el = driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR,
            f'new UiSelector().text("{label}")',
        )
        if el.is_displayed():
            el.click()
            time.sleep(0.8)
            return True
    except NoSuchElementException:
        pass

    try:
        el = driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR,
            f'new UiSelector().textContains("{label}")',
        )
        if el.is_displayed():
            el.click()
            time.sleep(0.8)
            return True
    except NoSuchElementException:
        pass
    return False


def _prepare_contacts_screen(driver) -> None:
    """Dismiss permission prompts, sync onboarding, and import screens."""
    _grant_contacts_permissions()

    try:
        driver.activate_app("com.google.android.contacts")
    except Exception:
        pass

    time.sleep(1.5)

    for _ in range(4):
        clicked = False
        for label in ONBOARDING_LABELS:
            if _tap_if_visible(driver, label):
                clicked = True
        try:
            allow_btn = driver.find_element(
                AppiumBy.ID,
                "com.android.permissioncontroller:id/permission_allow_button",
            )
            if allow_btn.is_displayed():
                allow_btn.click()
                time.sleep(0.8)
                clicked = True
        except NoSuchElementException:
            pass

        if not clicked:
            break

    # Close stuck VCF import screen if seed script left it open
    try:
        if "ImportVCard" in (driver.current_activity or ""):
            driver.press_keycode(4)
            time.sleep(1)
    except Exception:
        pass


def _find_list_root(driver):
    candidates = [
        (AppiumBy.ID, "com.google.android.contacts:id/contact_list"),
        (AppiumBy.CLASS_NAME, "androidx.recyclerview.widget.RecyclerView"),
        (AppiumBy.CLASS_NAME, "android.widget.ListView"),
        (AppiumBy.ANDROID_UIAUTOMATOR, "new UiSelector().scrollable(true)"),
    ]
    for locator in candidates:
        elements = driver.find_elements(*locator)
        for el in elements:
            if el.is_displayed():
                return el
    return None


def _scroll_down(driver) -> None:
    list_root = _find_list_root(driver)
    if list_root is not None:
        rect = list_root.rect
        left = rect["x"] + int(rect["width"] * 0.1)
        top = rect["y"] + int(rect["height"] * 0.2)
        width = int(rect["width"] * 0.8)
        height = int(rect["height"] * 0.6)
    else:
        size = driver.get_window_size()
        left = int(size["width"] * 0.1)
        top = int(size["height"] * 0.25)
        width = int(size["width"] * 0.8)
        height = int(size["height"] * 0.5)

    driver.execute_script(
        "mobile: scrollGesture",
        {
            "left": left,
            "top": top,
            "width": width,
            "height": height,
            "direction": "down",
            "percent": 0.75,
        },
    )


def _looks_like_contact_name(text: str) -> bool:
    if not text or text in SKIP_TEXT:
        return False
    if len(text) < 2 or len(text) > 80:
        return False
    if re.match(r"^[A-Z]$", text):
        return False
    if text.startswith("http"):
        return False
    if text.startswith("(") and text.endswith(")"):
        return False
    if "@" in text and " " not in text:
        return False
    if re.match(r"^Demo Contact \d{3}$", text):
        return True
    if " " not in text and not re.match(r"^Demo Contact \d{3}$", text):
        return False
    if any(
        phrase in text
        for phrase in (
            "Google Contacts",
            "sync",
            "backup",
            "settings",
            "Learn more",
            "SIM",
            "device",
        )
    ):
        return False
    return True


def _parse_visible_rows(driver) -> list[dict]:
    rows = []
    seen_text = set()

    for locator in ROW_LOCATOR_CANDIDATES:
        try:
            elements = driver.find_elements(*locator)
        except Exception:
            continue

        for el in elements:
            try:
                if not el.is_displayed():
                    continue
                text = (el.text or "").strip()
                if not _looks_like_contact_name(text) or text in seen_text:
                    continue
                seen_text.add(text)
                first, last = _split_name(text)
                rows.append(
                    {
                        "first_name": first,
                        "last_name": last,
                        "job_title": "",
                        "company": "",
                        "linkedin_url": "",
                        "masterclass_attendance": "Unknown",
                    }
                )
            except StaleElementReferenceException:
                continue

        if rows:
            break

    return rows


def scrape_contacts(
    driver,
    max_rows: int = 100,
    checkpoint_path: Path | None = None,
    scroll_pause_sec: float = 1.0,
    max_stale_scrolls: int = 5,
) -> list[dict]:
    """
    Scroll the Contacts list, parse visible names, dedupe, and honor checkpoint.
    """
    load_dotenv(PROJECT_ROOT / ".env")
    if checkpoint_path is None:
        checkpoint_path = Path(
            os.getenv("CHECKPOINT_PATH", "output/checkpoint.json")
        )
    if not checkpoint_path.is_absolute():
        checkpoint_path = PROJECT_ROOT / checkpoint_path

    stale_scrolls = int(os.getenv("MAX_STALE_SCROLLS", max_stale_scrolls))
    pause = float(os.getenv("SCROLL_PAUSE_SEC", scroll_pause_sec))

    _prepare_contacts_screen(driver)
    try:
        wait_for_any_visible(driver, ROW_LOCATOR_CANDIDATES, timeout=20)
    except Exception:
        pass

    known_keys = _load_checkpoint(checkpoint_path)
    collected: list[dict] = []
    collected_keys: set[str] = set(known_keys)
    no_new_streak = 0

    while len(collected) < max_rows and no_new_streak < stale_scrolls:
        batch = _parse_visible_rows(driver)
        new_in_batch = 0

        for row in batch:
            key = _row_key(row)
            if key in collected_keys or not key.replace("|", "").strip():
                continue
            collected_keys.add(key)
            collected.append(row)
            new_in_batch += 1
            if len(collected) >= max_rows:
                break

        if len(collected) >= max_rows:
            break

        if new_in_batch == 0:
            no_new_streak += 1
        else:
            no_new_streak = 0
            _save_checkpoint(checkpoint_path, collected_keys)

        _scroll_down(driver)
        time.sleep(pause)

    _save_checkpoint(checkpoint_path, collected_keys)
    return collected[:max_rows]
