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


class AvpayurvedaPipeline:
    def __init__(self):
        load_dotenv()
        self.cover_output_path = f"{os.environ['OUTPUT_PATH']}/cover_medicines_items.csv"
        self.detail_output_path = f"{os.environ['OUTPUT_PATH']}/detail_medicines_items.csv"
        self.ids_seen = set()
        self.cover_count = 0
        self.detail_count = 0
        self.flush_count = 20

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

        if item_dict["id"] in self.ids_seen:
            raise DropItem(f"Duplicate item found: {item!r}")
        else:
            self.ids_seen.add(item_dict["id"])

        if item["type"] == "card":
            row = {}
            row["Name"] = item_dict["name"]
            row["Basic Description"] = item_dict["basic_description"]
            row["Image"] = item_dict["image"]
            row["Price"] = item_dict["price"]
            self.cover_exporter.export_item(row)

            self.cover_count += 1
            if self.cover_count % self.flush_count == 0:
                self.cover_file.flush()

        elif item["type"] == "detail":
            row = {}
            row["Name"] = item_dict["name"]
            row["Price"] = item_dict["price"]
            row["Main Image"] = item_dict["image"]
            row["Images"] = item_dict["sub_images"]
            row["Product Description"] = item_dict["product_description"]
            row["Key Ingredient"] = item_dict["key_ingredient"]

            self.detail_exporter.export_item(row)

            self.detail_count += 1
            if self.detail_count % self.flush_count == 0:
                self.detail_file.flush()

        return item
