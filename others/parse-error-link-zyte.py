import json
import pandas as pd

class ZyteLogItem():
    time: int
    level: int
    message: str

def main():
    file_path = "D:\crawl_data\logs\log_masothue_20.json"
    with open(file_path, "r") as file:
        items = json.load(file)

    urls = []

    for item in items:
        if "Error downloading" in item["message"]:
            first_index = item["message"].index("<")+5
            last_index = item["message"].index(">")
            url = item["message"][first_index:last_index]
            
            print(url)
            urls.append(url)

    df = pd.DataFrame({
        "url": urls
    }) 
    df.to_json("error_urls_20.json")


if __name__ == "__main__":
    main()