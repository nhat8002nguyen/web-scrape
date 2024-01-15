## How to run the script

1. Go to this link: https://scrapeops.io/python-scrapy-playbook/scrapy-splash/#1-download-scrapy-splash
And then Install & Run Scrapy Splash
Make sure running the following command before starting the scraper.
    `$ docker run -it -p 8050:8050 --rm scrapinghub/splash`

2. Install Python3.10 or higher.

3. Go to project folder, and install Python dependencies using the following command:
    `$ python3 -m pip install -r requirements.txt`

4. Edit the .env file
- OUTPUT_PATH is the absolute path to the project folder, e.g OUTPUT_PATH="/your/path/to/avpayurveda"

4. Start the scraper:
    `$ scrapy crawl classical_medicines`

5. Output files will appeared in the project folder at the end, they are cover_medicines_items.csv, and detail_medicines_items.csv