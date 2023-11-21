import  jpype     
import  asposecells     
jpype.startJVM() 
from asposecells.api import Workbook
import sys

def main():
    file_path = sys.argv[1]
    folder = file_path[:file_path.rfind("\\")+1]
    name = file_path[file_path.rfind("\\")+1:file_path.rfind(".")]
    workbook = Workbook(file_path)
    workbook.save(f"{folder}{name}.xlsx")
    print(f"Sucessfully converted {file_path} to xlsx file")
    jpype.shutdownJVM()

if __name__ == "__main__":
    main()