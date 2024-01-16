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
        self.concern_output_path = f"{os.environ['OUTPUT_PATH']}/cover_concern_items.csv"
        self.all_products_output_path = f"{os.environ['OUTPUT_PATH']}/cover_all_products_items.csv"

        self.detail_output_path = f"{os.environ['OUTPUT_PATH']}/detail_medicines_items.csv"
        self.ids_seen = set()
        self.cover_count_1 = 0
        self.cover_count_2 = 0
        self.cover_count_3 = 0
        self.detail_count = 0
        self.flush_count = 10

    def open_spider(self, spider):
        self.cover_file = open(self.cover_output_path, 'wb')
        self.cover_exporter = CsvItemExporter(self.cover_file)
        self.cover_exporter.start_exporting()

        self.cover_concern_file = open(self.concern_output_path, 'wb')
        self.cover_concern_exporter = CsvItemExporter(self.cover_concern_file)
        self.cover_concern_exporter.start_exporting()

        self.cover_all_products_file = open(
            self.all_products_output_path, 'wb')
        self.cover_all_products_exporter = CsvItemExporter(
            self.cover_all_products_file)
        self.cover_all_products_exporter.start_exporting()

        self.detail_file = open(self.detail_output_path, 'wb')
        self.detail_exporter = CsvItemExporter(self.detail_file)
        self.detail_exporter.start_exporting()

    def close_spider(self, spider):
        self.cover_exporter.finish_exporting()
        self.cover_file.close()

        self.cover_concern_exporter.finish_exporting()
        self.cover_concern_file.close()

        self.cover_all_products_exporter.finish_exporting()
        self.cover_all_products_file.close()

        self.detail_exporter.finish_exporting()
        self.detail_file.close()

    def process_item(self, item, spider):
        item_dict = ItemAdapter(item).asdict()

        if item["type"] == "card":
            row = {}
            row["Name"] = item_dict["name"]
            row["Basic Description"] = item_dict["basic_description"]
            row["Image"] = item_dict["image"]
            row["Price"] = item_dict["price"]
            row["Sub Category"] = item_dict["cat_name"]

            if item["sheet_number"] == 2:
                row["Main Category"] = "Classical Medicines"
                self.cover_exporter.export_item(row)

                self.cover_count_1 += 1
                if self.cover_count_1 % self.flush_count == 0:
                    self.cover_file.flush()
            elif item["sheet_number"] == 1:
                row["Main Category"] = "Shop By Concern"
                self.cover_concern_exporter.export_item(row)

                self.cover_count_2 += 1
                if self.cover_count_2 % self.flush_count == 0:
                    self.cover_concern_file.flush()
            elif item["sheet_number"] == 3:
                row["Main Category"] = "All Products"
                self.cover_all_products_exporter.export_item(row)

                self.cover_count_3 += 1
                if self.cover_count_3 % self.flush_count == 0:
                    self.cover_all_products_file.flush()

        elif item["type"] == "detail":
            if item["id"] in self.ids_seen:
                raise DropItem(f"Duplicate: {item['id']}")

            self.ids_seen.add(item["id"])

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
