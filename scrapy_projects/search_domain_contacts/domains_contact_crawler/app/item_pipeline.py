from itemadapter import ItemAdapter
import os
from scrapy.exceptions import DropItem
from scrapy.exporters import CsvItemExporter
from utilities import get_email_output_csv_path, get_phone_output_csv_path
from dotenv import load_dotenv
load_dotenv()

ROOT_PATH = os.environ['PROJECT_ROOT']
OUTPUT_PATH = ROOT_PATH + os.environ['OUTPUT_PATH']


class XLSXPipeline:
    def __init__(self, csv_name: str, start_index: int, end_index: int):
        self.csv_name = csv_name
        self.start_index = start_index
        self.end_index = end_index
        self.save_count = 100 if start_index - end_index + 1 > 100 else 10
        self.email_output_path = get_email_output_csv_path(
            csv_name, start_index, end_index)
        self.phone_output_path = get_phone_output_csv_path(
            csv_name, start_index, end_index
        )
        self.ids_seen = set()

        self.phone_items_count = 0
        self.email_items_count = 0
        self.flush_count = 1000

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            csv_name=crawler.settings.get("CSV_INPUT_NAME"),
            start_index=crawler.settings.get("START_INDEX"),
            end_index=crawler.settings.get("END_INDEX")
        )

    def open_spider(self, spider):
        self.email_file = open(self.email_output_path, 'wb')
        self.email_exporter = CsvItemExporter(self.email_file)
        self.email_exporter.start_exporting()

        self.phone_file = open(self.phone_output_path, 'wb')
        self.phone_exporter = CsvItemExporter(self.phone_file)
        self.phone_exporter.start_exporting()

    def close_spider(self, spider):
        self.email_exporter.finish_exporting()
        self.email_file.close()

        self.phone_exporter.finish_exporting()
        self.phone_file.close()

    def process_item(self, item, spider):
        item_dict = ItemAdapter(item).asdict()

        if item_dict["id"] in self.ids_seen:
            raise DropItem(f"Duplicate item found: {item!r}")
        else:
            self.ids_seen.add(item_dict["id"])

        if "email" in item:
            row = {}
            row["XID"] = item_dict["XID"]
            row["domain"] = item_dict["domain"]
            row["email"] = item_dict["email"]
            self.email_exporter.export_item(row)

            self.email_items_count += 1
            if self.email_items_count % self.flush_count == 0:
                self.email_file.flush()

        elif "phone" in item:
            row = {}
            row["XID"] = item_dict["XID"]
            row["domain"] = item_dict["domain"]
            row["phone"] = item_dict["phone"]
            self.phone_exporter.export_item(row)

            self.phone_items_count += 1
            if self.phone_items_count % self.flush_count == 0:
                self.phone_file.flush()

        return item
