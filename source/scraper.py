from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import csv
import json

base_url = "https://minecraftitemids.com"


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def scrape_item_page(driver, url):
    driver.get(url)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'item-page-container'))
        )
    except:
        print(f"Failed to load page: {url}")
        return None

    title = driver.find_element(By.CLASS_NAME, 'item-name-title').text.strip()
    item_id = driver.find_element(By.CLASS_NAME, 'item-id-container').text.strip()
    item_data = {"Title": title, "ID": item_id}

    try:
        description = driver.find_element(By.CLASS_NAME, 'item-description').text.strip()
        item_data["Description"] = description
    except:
        item_data["Description"] = ""

    return item_data


def scrape_all_items(driver):
    driver.get(base_url + "/items/")

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'items-listing'))
        )
    except:
        print("Failed to load item list page")
        return []

    item_links = driver.find_elements(By.XPATH, '//div[@class="items-listing"]//a')
    item_urls = [link.get_attribute('href') for link in item_links]

    all_items = []
    for url in item_urls:
        print(f"Scraping: {url}")
        item_data = scrape_item_page(driver, url)
        if item_data:
            all_items.append(item_data)
        time.sleep(1)

    return all_items


def save_to_csv(data, filename):
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["Title", "ID", "Description"])
        for item in data:
            writer.writerow([item["Title"], item["ID"], item["Description"]])


def save_to_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    driver = setup_driver()
    print("Scraping all items...")
    data = scrape_all_items(driver)

    save_to_csv(data, "minecraft_items.csv")
    print(f"Saved {len(data)} entries to minecraft_items.csv")

    save_to_json(data, "minecraft_items.json")
    print(f"Saved {len(data)} entries to minecraft_items.json")

    driver.quit()
