## How to run the script
1. Install Python3.10 or greater.

2. Go to project folder, and install Python dependencies using the following command:
    `$ python3 -m pip install -r requirements.txt`

3. Edit the .env file
- OUTPUT_PATH is the absolute path to the project folder, e.g OUTPUT_PATH="/your/path/to/avpayurveda"

4. Start the scraper:
    `$ scrapy crawl classical_medicines`

5. Output files will appeared in the project folder at the end, they are cover_medicines_items.csv, and detail_medicines_items.csv