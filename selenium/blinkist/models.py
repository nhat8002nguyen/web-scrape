import pandas as pd
import os

class Book:
    def __init__(
        self,
        author: str = "",
        author_about: str = "",
        book_name: str = "",
        intro_title: str = "",
        short_summary: str = "",
        time: str = "",
        num_key_ideas: int = 0,
        cat0: str = "",
        cat1: str = "",
        cat2: str = "",
        cat3: str = "",
        cat4: str = "",
        introduction: str = "",
        key_ideas: list[str] = None  # Change to None
    ):
        self.author = author
        self.author_about = author_about
        self.book_name = book_name
        self.intro_title = intro_title
        self.short_summary = short_summary
        self.time = time
        self.num_key_ideas = num_key_ideas
        self.cat0 = cat0
        self.cat1 = cat1
        self.cat2 = cat2
        self.cat3 = cat3
        self.cat4 = cat4
        self.introduction = introduction
        self.key_ideas = key_ideas if key_ideas is not None else []


class ExportFrame():
    def __init__(self):
        self.author_list = []
        self.book_name_list = []
        self.author_about_list = []
        self.intro_title_list = []
        self.short_summary_list = []
        self.time_list = []
        self.num_key_ideas_list = []
        self.cat0_list = []
        self.cat1_list = []
        self.cat2_list = []
        self.cat3_list = []
        self.cat4_list = []
        self.introduction_list = []
        self.section0s = []
        self.section1s = []
        self.section2s = []
        self.section3s = []
        self.section4s = []
        self.section5s = []
        self.section6s = []
        self.section7s = []
        self.section8s = []
        self.section9s = []
        self.section10s = []
        self.section11s = []
        self.section12s = []
        self.section13s = []
        self.section14s = []
        self.section15s = []
        self.section16s = []
        self.section17s = []
        self.section18s = []
        self.section19s = []

    def exportXLSX(self, cat_num: int, start_index: int, end_index: int):
        self.df = pd.DataFrame({
            "Author": self.author_list,
            "Book Name": self.book_name_list,

            # additional info
            "About Author": self.author_about_list,
            "Intro Title": self.intro_title_list,
            "Short Summary": self.short_summary_list,
            "Time": self.time_list,
            "Key Ideas": self.num_key_ideas_list,
            "Category 1": self.cat0_list,
            "Category 2": self.cat1_list,
            "Category 3": self.cat2_list,
            "Category 4": self.cat3_list,
            "Category 5": self.cat4_list,

            "Introduction": self.introduction_list,
            "Section 1": self.section0s,
            "Section 2": self.section1s,
            "Section 3": self.section2s,
            "Section 4": self.section3s,
            "Section 5": self.section4s,
            "Section 6": self.section5s,
            "Section 7": self.section6s,
            "Section 8": self.section7s,
            "Section 9": self.section8s,
            "Section 10": self.section9s,
            "Section 11": self.section10s,
            "Section 12": self.section11s,
            "Section 13": self.section12s,
            "Section 14": self.section13s,
            "Section 15": self.section14s,
            "Section 16": self.section15s,
            "Section 17": self.section16s,
            "Section 18": self.section17s,
            "Section 19": self.section18s,
            "Section 20": self.section19s,
        })

        self.df.to_excel(
            f"{os.environ['ABSOLUTE_PATH']}/blinkist-output-categ-{cat_num+1}-{start_index}-{end_index}.xlsx", index=False)

        self.clear()

    def exportJson(self, cat_num: int, start_index: int, end_index: int):
        if self.df != None:
            self.df.to_json(
                f"{os.environ['ABSOLUTE_PATH']}/blinkist-output-categ-{cat_num+1}-{start_index}-{end_index}.json", index=False)

        self.clear()

    def clear(self):
        self.author_list = list[str]()
        self.book_name_list = list[str]()

        self.author_about_list = list()
        self.intro_title_list = list()
        self.short_summary_list = list()
        self.time_list = list()
        self.num_key_ideas_list = list()
        self.cat0_list = list()
        self.cat1_list = list()
        self.cat2_list = list()
        self.cat3_list = list()
        self.cat4_list = list()

        self.introduction_list = list[str]()
        self.section0s = list[str]()
        self.section1s = list[str]()
        self.section2s = list[str]()
        self.section3s = list[str]()
        self.section4s = list[str]()
        self.section5s = list[str]()
        self.section6s = list[str]()
        self.section7s = list[str]()
        self.section8s = list[str]()
        self.section9s = list[str]()
        self.section10s = list[str]()
        self.section11s = list[str]()
        self.section12s = list[str]()
        self.section13s = list[str]()
        self.section14s = list[str]()
        self.section15s = list[str]()
        self.section16s = list[str]()
        self.section17s = list[str]()
        self.section18s = list[str]()
        self.section19s = list[str]()