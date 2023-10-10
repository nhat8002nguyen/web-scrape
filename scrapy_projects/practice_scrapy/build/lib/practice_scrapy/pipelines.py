# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import dotenv, os
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import sqlite3

class PracticeScrapyPipeline:
    def process_item(self, item, spider):
        return item

class MongodbPipeline:
    def __init__(self) -> None:
        dotenv.load_dotenv()
        mongodb_pass = os.environ.get('MONGODB_PASS')
        self.uri = f"mongodb+srv://nathan:{mongodb_pass}@cluster0.bgumwjq.mongodb.net/?retryWrites=true&w=majority"

    def open_spider(self, spider):
        self.connection = MongoClient(host=self.uri, server_api=ServerApi('1'))
        db = self.connection.get_database(name='scraping_db')
        self.collection = db.get_collection('audible_search')

    def close_spider(self, spider):
        self.connection.close() 

    def process_item(self, item, spider):
        self.collection.insert_one(item)
        return item

class SQLitePipeline:
    def open_spider(self, spider):
        self.db = sqlite3.connect(database="audible_search.db")
        cursor_obj = self.db.cursor()

        # Drop the GEEK table if already exists.
        cursor_obj.execute("DROP TABLE IF EXISTS AUDIBLE")
 
        # Creating table
        table = """ CREATE TABLE AUDIBLE (
                    title VARCHAR(255),
                    authors VARCHAR(255),
                    length VARCHAR(255)
                ); """

        cursor_obj.execute(table)

    def close_spider(self, spider):
        self.db.close()

    def process_item(self, item, spider):
        db_cursor = self.db.cursor()
        db_cursor.execute(f'''
            INSERT INTO AUDIBLE (title, authors, length) VALUES (?, ?, ?);
        ''', (
            item["title"], ", ".join(item["authors"]), item["length"],
        ))
        self.db.commit()
        return item