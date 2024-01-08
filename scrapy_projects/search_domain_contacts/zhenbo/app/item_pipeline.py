from itemadapter import ItemAdapter
from openpyxl import Workbook
import os
from scrapy.exceptions import DropItem


class XLSXPipeline:
    def __init__(self, file_path: str, start_index: int, end_index: int):
        self.file_path = file_path
        self.start_index = start_index
        self.end_index = end_index
        self.count = 0
        self.save_count = 10
        self.output_path = f'{os.environ["OUTPUT_PATH"]}/output_{self.start_index}_{self.end_index}.xlsx'
        self.ids_seen = set()
        self.emails_seen = set()

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            file_path=crawler.settings.get("OUTPUT_FILE_PATH"),
            start_index=crawler.settings.get("START_INDEX"),
            end_index=crawler.settings.get("END_INDEX")
        )

    def open_spider(self, spider):
        self.workbook = Workbook()
        self.sheet = self.workbook.active
        self.sheet.append(["domain", "email", "phones"])

    def close_spider(self, spider):
        self.workbook.save(self.output_path)
        self.workbook.close()

    def process_item(self, item, spider):
        item_dict = ItemAdapter(item).asdict()

        if item_dict["id"] in self.ids_seen:
            raise DropItem(f"Duplicate item found: {item!r}")
        else:
            self.ids_seen.add(item_dict["id"])

        row = []
        row.append(item_dict["domain"])
        if item_dict["email"] in self.emails_seen:
            row.append("")
        else:
            row.append(item_dict["email"])
            self.emails_seen.add(item_dict["email"])

        row.append(item_dict["phones"] if "phones" in item_dict else "")
        self.sheet.append(row)

        self.count += 1
        if (self.count - self.start_index) % ((self.end_index-self.start_index+1)/self.save_count):
            self.workbook.save(self.output_path)

        return item
