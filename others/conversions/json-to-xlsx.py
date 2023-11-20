import  jpype     
import  asposecells     
jpype.startJVM() 
from asposecells.api import Workbook

name = "items_masothue_13"
workbook = Workbook(f"D:\crawl_data\{name}.json")
workbook.save(f"{name}.xlsx")
jpype.shutdownJVM()