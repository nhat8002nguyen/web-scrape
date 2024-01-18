# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from scrapy.exporters import CsvItemExporter
from scrapy.exceptions import DropItem
import os
from dotenv import load_dotenv


class VaidyaratnammoossPipeline:
    def __init__(self):
        load_dotenv()
        self.cover_output_path = f"{os.environ['OUTPUT_PATH']}/cover_medicines_items.csv"
        self.detail_output_path = f"{os.environ['OUTPUT_PATH']}/detail_medicines_items.csv"
        self.ids_seen = set()
        self.cover_count = 0
        self.detail_count = 0
        self.flush_count = 10

    def open_spider(self, spider):
        self.cover_file = open(self.cover_output_path, 'wb')
        self.cover_exporter = CsvItemExporter(self.cover_file)
        self.cover_exporter.start_exporting()

        self.detail_file = open(self.detail_output_path, 'wb')
        self.detail_exporter = CsvItemExporter(self.detail_file)
        self.detail_exporter.start_exporting()

    def close_spider(self, spider):
        self.cover_exporter.finish_exporting()
        self.cover_file.close()

        self.detail_exporter.finish_exporting()
        self.detail_file.close()

    def process_item(self, item, spider):
        item_dict = ItemAdapter(item).asdict()

        if item["type"] == "card":
            row = {}
            row["id"] = item_dict["id"]
            row["Product Link"] = item_dict["product_url"]
            row["Image"] = item_dict["image"]
            row["Name"] = item_dict["name"]
            row["Price"] = item_dict["price"]
            row["Pack Size"] = item_dict["pack_size"]
            row["Category"] = item_dict["cat"]

            self.cover_exporter.export_item(row)

            self.cover_count += 1
            if self.cover_count % self.flush_count == 0:
                self.cover_file.flush()

        elif item["type"] == "detail":
            if item["id"] in self.ids_seen:
                raise DropItem(f"Duplicate: {item['id']}")

            self.ids_seen.add(item["id"])

            row = {}
            row["id"] = item_dict["id"]
            row["Product Link"] = item_dict["product_url"]
            row["Category"] = item_dict['cat']
            row["Name"] = item_dict["name"]
            row["Images"] = item_dict["images"]
            row["Price"] = item_dict["price"]
            row["Pack Size"] = item_dict["pack_size"]
            row["ingredents"] = item_dict["ingredients"]
            row["description"] = item_dict["indications"]
            row["dosage"] = item_dict["dosage"]

            self.detail_exporter.export_item(row)

            self.detail_count += 1
            if self.detail_count % self.flush_count == 0:
                self.detail_file.flush()

        return item
