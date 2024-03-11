# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
# import openpyxl
import xlsxwriter  # Import the xlsxwriter library
from itemadapter import ItemAdapter
# from scrapy.exceptions import DropItem
# from scrapy.exporters import CsvItemExporter
import os
import dotenv
dotenv.load_dotenv()


# class DebankComPipeline:
#     def __init__(self):
#         self.sheet1_output_path = f"{os.environ['OUTPUT_PATH']}/sheet1_medicines_items.csv"
#         self.sheet2_output_path = f"{os.environ['OUTPUT_PATH']}/sheet2_medicines_items.csv"
#         self.ids_seen = set()
#         self.sheet1_count = 0
#         self.sheet2_count = 0
#         self.flush_count = 10

#     def open_spider(self, spider):
#         self.sheet1_file = open(self.sheet1_output_path, 'ab')
#         self.sheet1_exporter = CsvItemExporter(self.sheet1_file)
#         self.sheet1_exporter.start_exporting()

#         self.sheet2_file = open(self.sheet2_output_path, 'ab')
#         self.sheet2_exporter = CsvItemExporter(self.sheet2_file)
#         self.sheet2_exporter.start_exporting()

#     def close_spider(self, spider):
#         self.sheet1_exporter.finish_exporting()
#         self.sheet1_file.close()

#         self.sheet2_exporter.finish_exporting()
#         self.sheet2_file.close()

#     def process_item(self, item, spider):
#         item_dict = ItemAdapter(item).asdict()

#         if item["type"] == "syve":
#             row = {}
#             row["Wallet"] = item_dict["wallet"]
#             row["Total Profit"] = item_dict["total_profit"],
#             row["Tokens Traded"] = item_dict["tokens_traded"],
#             row["Total Investment"] = item_dict["total_investment"],
#             row["Realized Profit"] = item_dict["realized_profit"],
#             row["Unrealized Profit"] = item_dict["unrealized_profit"],
#             row["Win rate"] = item_dict["win_rate"],
#             row["Total Return"] = item_dict["total_return"]

#             self.sheet1_exporter.export_item(row)

#             self.sheet1_count += 1
#             if self.sheet1_count % self.flush_count == 0:
#                 self.sheet1_file.flush()

#         elif item["type"] == "debank":
#             row = {}
#             row["Wallet"] = item_dict["wallet"]
#             row["Debank"] = item_dict["debank"]

#             self.sheet2_exporter.export_item(row)

#             self.sheet2_count += 1
#             if self.sheet2_count % self.flush_count == 0:
#                 self.sheet2_file.flush()

#         return item


class DebankComPipeline:
    def open_spider(self, spider):
        self.sheet1_output_path = f"{os.environ['OUTPUT_PATH']}/{spider.name}_output.xlsx"
        self.ids_seen = set()
        self.sheet1_workbook = xlsxwriter.Workbook(
            self.sheet1_output_path)  # Create XLSX workbooks
        self.sheet1_worksheet = self.sheet1_workbook.add_worksheet()  # Add worksheets
        self.sheet1_worksheet.write_row(0, 0, [
            "Wallet", "Debank", "Total Profit", "Tokens Traded", "Total Investment", "Realized Profit",
            "Unrealized Profit", "Win Rate", "Total Return"
        ])
        self.sheet1_row = 1

    def close_spider(self, spider):
        self.sheet1_workbook.close()  # Close workbooks

    def process_item(self, item, spider):
        item_dict = ItemAdapter(item).asdict()

        if item_dict["wallet"] in self.ids_seen:
            return item

        self.ids_seen.add(item_dict["wallet"])

        row = [
            item_dict["wallet"],
            item_dict["debank"],
            item_dict["total_profit"],
            item_dict["tokens_traded"],
            item_dict["total_investment"],
            item_dict["realized_profit"],
            item_dict["unrealized_profit"],
            item_dict["win_rate"],
            item_dict["total_return"]
        ]
        self.sheet1_worksheet.write_row(
            self.sheet1_row, 0, row)  # Write row to worksheet
        self.sheet1_row += 1

        return item
