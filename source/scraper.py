"""Scrape item data from minecraftitemids.com.

The scraper keeps Selenium-specific code in this module, but exposes small
functions that can be tested independently and reused by other entry points.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


LOGGER = logging.getLogger(__name__)
DEFAULT_BASE_URL = "https://minecraftitemids.com"
DEFAULT_LIST_PATH = "/items/"
CSV_FIELDS = ("Title", "ID", "Description")


@dataclass(frozen=True)
class ScraperConfig:
    base_url: str = DEFAULT_BASE_URL
    list_path: str = DEFAULT_LIST_PATH
    timeout: int = 15
    retries: int = 3
    delay: float = 1.0
    limit: int | None = None
    headless: bool = True


def setup_driver(headless: bool = True) -> webdriver.Chrome:
    """Create a Chrome driver with options suitable for local and CI runs."""
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-component-update")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

    service = Service(ChromeDriverManager().install(), log_output=os.devnull)
    return webdriver.Chrome(service=service, options=chrome_options)


def _wait_for_page(driver: webdriver.Chrome, selector: tuple[str, str], timeout: int) -> None:
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located(selector)
    )


def scrape_item_page(
    driver: webdriver.Chrome,
    url: str,
    timeout: int = 15,
    retries: int = 3,
) -> dict[str, str] | None:
    """Scrape one item page, retrying transient browser failures."""
    for attempt in range(1, retries + 1):
        try:
            driver.get(url)
            _wait_for_page(
                driver,
                (By.CLASS_NAME, "item-page-container"),
                timeout,
            )

            title = driver.find_element(By.CLASS_NAME, "item-name-title").text.strip()
            item_id = driver.find_element(By.CLASS_NAME, "item-id-container").text.strip()
            try:
                description = driver.find_element(
                    By.CLASS_NAME, "item-description"
                ).text.strip()
            except NoSuchElementException:
                description = ""

            if not title or not item_id:
                LOGGER.warning("Required fields missing for %s", url)
                return None

            return {"Title": title, "ID": item_id, "Description": description}
        except (TimeoutException, NoSuchElementException, WebDriverException) as exc:
            if attempt == retries:
                LOGGER.error("Failed to scrape %s after %d attempts: %s", url, retries, exc)
                return None
            wait_seconds = min(2**(attempt - 1), 8)
            LOGGER.warning(
                "Attempt %d/%d failed for %s; retrying in %ds",
                attempt,
                retries,
                url,
                wait_seconds,
            )
            time.sleep(wait_seconds)

    return None


def discover_item_urls(
    driver: webdriver.Chrome,
    config: ScraperConfig,
) -> list[str]:
    """Load the listing page and return unique absolute item URLs."""
    listing_url = urljoin(config.base_url.rstrip("/") + "/", config.list_path.lstrip("/"))
    driver.get(listing_url)
    _wait_for_page(driver, (By.CLASS_NAME, "items-listing"), config.timeout)

    urls: list[str] = []
    seen: set[str] = set()
    for link in driver.find_elements(By.XPATH, '//div[@class="items-listing"]//a'):
        href = link.get_attribute("href")
        if href and href not in seen:
            seen.add(href)
            urls.append(href)

    if config.limit is not None:
        urls = urls[: config.limit]
    return urls


def scrape_all_items(
    driver: webdriver.Chrome,
    config: ScraperConfig = ScraperConfig(),
) -> tuple[list[dict[str, str]], list[str]]:
    """Scrape all discovered items and return successful records and failures."""
    item_urls = discover_item_urls(driver, config)
    records: list[dict[str, str]] = []
    failed_urls: list[str] = []

    LOGGER.info("Discovered %d item URLs", len(item_urls))
    for index, url in enumerate(item_urls, start=1):
        LOGGER.info("Scraping %d/%d: %s", index, len(item_urls), url)
        item_data = scrape_item_page(
            driver,
            url,
            timeout=config.timeout,
            retries=config.retries,
        )
        if item_data is None:
            failed_urls.append(url)
        else:
            records.append(item_data)
        if index < len(item_urls):
            time.sleep(config.delay)

    return records, failed_urls


def _write_text_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


def save_to_csv(data: Iterable[dict[str, Any]], filename: str | Path) -> None:
    rows = list(data)
    with io.StringIO(newline="") as buffer:
        writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in CSV_FIELDS} for row in rows)
        _write_text_atomically(Path(filename), buffer.getvalue())


def save_to_json(data: Iterable[dict[str, Any]], filename: str | Path) -> None:
    content = json.dumps(list(data), indent=4, ensure_ascii=False) + "\n"
    _write_text_atomically(Path(filename), content)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--list-path", default=DEFAULT_LIST_PATH)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--visible", action="store_true", help="Show Chrome while scraping")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    if args.timeout <= 0 or args.retries <= 0 or args.delay < 0:
        raise ValueError("timeout and retries must be positive; delay cannot be negative")

    config = ScraperConfig(
        base_url=args.base_url,
        list_path=args.list_path,
        timeout=args.timeout,
        retries=args.retries,
        delay=args.delay,
        limit=args.limit,
        headless=not args.visible,
    )
    driver = setup_driver(config.headless)
    try:
        LOGGER.info("Starting scrape")
        data, failed_urls = scrape_all_items(driver, config)
    finally:
        driver.quit()

    output_dir = args.output_dir
    save_to_csv(data, output_dir / "minecraft_items.csv")
    save_to_json(data, output_dir / "minecraft_items.json")
    if failed_urls:
        _write_text_atomically(output_dir / "failed_urls.txt", "\n".join(failed_urls) + "\n")
    LOGGER.info(
        "Saved %d records; %d URLs failed",
        len(data),
        len(failed_urls),
    )
    return 0 if not failed_urls else 2


if __name__ == "__main__":
    raise SystemExit(main())
