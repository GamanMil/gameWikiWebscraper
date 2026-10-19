# Minecraft Wiki Webscraper

This project collects Minecraft item information from
[`minecraftitemids.com`](https://minecraftitemids.com).

## Setup

Use Python 3.10 or newer and install the dependencies:

```text
python -m pip install -r requirements.txt
```

Chrome must be installed. `webdriver-manager` downloads a compatible Chrome
driver the first time the scraper runs.

## Run

Run the complete item scrape:

```text
python source/scraper.py --output-dir data
```

Useful options:

```text
python source/scraper.py --limit 25 --delay 0.5
python source/scraper.py --visible --log-level DEBUG
python source/scraper.py --timeout 30 --retries 5
```

The command writes `minecraft_items.csv` and `minecraft_items.json` to the
selected output directory. If individual pages fail after all retries, their
URLs are written to `failed_urls.txt` and the process exits with status `2`.
