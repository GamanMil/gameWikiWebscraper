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

base_url = "https://minecraft.wiki"


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # specific for chrome driver - useless options that use resources

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def scrape_page(driver, url):
    driver.get(url)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'mw-page-title-main'))
        )
    except:
        print(f"Failed to load page: {url}")
        return None

    title = driver.find_element(By.CLASS_NAME, 'mw-page-title-main').text.strip()

    content = driver.find_element(By.CLASS_NAME, 'mw-parser-output').text.strip()

    infobox_data = {}
    try:
        infobox = driver.find_element(By.CLASS_NAME, 'infobox')
        for row in infobox.find_elements(By.TAG_NAME, 'tr'):
            try:
                key = row.find_element(By.TAG_NAME, 'th').text.strip()
                value = row.find_element(By.TAG_NAME, 'td').text.strip()
                infobox_data[key] = value
            except:
                continue
    except:
        pass

    return {
        "title": title,
        "content": content,
        "infobox": infobox_data
    }


def crawl_category(driver, category_url):
    driver.get(category_url)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//div[@class="mw-category-generated"]//a'))
        )
    except:
        print(f"Subpage links did not load on {category_url}")
        return []

    subpage_links = driver.find_elements(By.XPATH, '//div[@class="mw-category-generated"]//a')

    if not subpage_links:
        print(f"No subpage links found on {category_url}")
        return []

    subpage_urls = [link.get_attribute('href') for link in subpage_links]

    all_data = []
    for url in subpage_urls:
        print(f"Scraping: {url}")
        page_data = scrape_page(driver, url)
        if page_data:
            all_data.append(page_data)
        time.sleep(2)

    return all_data


def save_to_csv(data, filename):
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["Title", "Content", "Infobox"])
        for item in data:
            writer.writerow([item["title"], item["content"], json.dumps(item["infobox"], ensure_ascii=False)])


# Save data to a JSON file
def save_to_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    driver = setup_driver()

    categories = {
        "blocks": "https://minecraft.wiki/w/Category:Blocks",
        "items": "https://minecraft.wiki/w/Category:Items",
        "mobs": "https://minecraft.wiki/w/Category:Mobs"
    }

    for category_name, category_url in categories.items():
        print(f"Scraping category: {category_name}")
        data = crawl_category(driver, category_url)

        save_to_csv(data, f"{category_name}_data.csv")
        print(f"Saved {len(data)} entries to {category_name}_data.csv")

        save_to_json(data, f"{category_name}_data.json")
        print(f"Saved {len(data)} entries to {category_name}_data.json")

    driver.quit()
