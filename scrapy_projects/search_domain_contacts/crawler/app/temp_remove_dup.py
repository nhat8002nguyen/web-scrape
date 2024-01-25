import json
import os
import re
from pandas import DataFrame
from time import sleep


OUTPUT_PATH = "/Users/nhatnguyen/Workspaces/web-scrape/scrapy_projects/search_domain_contacts/zhenbo/instance-1-outputs/outputs1"
XLSX_OUTPUT_PATH = "/Users/nhatnguyen/Workspaces/web-scrape/scrapy_projects/search_domain_contacts/zhenbo/instance-1-outputs/xlsx"

def remove_duplicates_of_files():
    folder_path = OUTPUT_PATH
    output_file_pattern = re.compile(r"output_\d+_\d+\.json")

    # Ensure the path is valid
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        # Iterate over all files in the folder
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)

            # Check if it's a file (not a directory)
            if os.path.isfile(file_path) and output_file_pattern.match(filename):
                remove_duplicates_json(file_path)

    # If the path is not valid, print an error message
    else:
        print("Invalid folder path.")


def remove_duplicates_json(path: str):
    try:
        # Assuming the JSON data is in a file called 'data.json'
        with open(path, 'r') as file:
            data = json.load(file)

        # Use a set to track unique entries
        unique_entries = set()
        cleaned_data = []

        for entry in data:
            # Create a tuple of the dictionary values to track uniqueness
            identifier = tuple(entry.values())

            if identifier not in unique_entries:
                cleaned_data.append(entry)
                unique_entries.add(identifier)

        # Now `cleaned_data` contains unique entries
        # Write the cleaned data back to a file or use it as needed
        with open(f'{path[:path.rfind(".")]}_cleaned.json', 'w') as file:
            json.dump(cleaned_data, file, indent=4)

        # Print the cleaned data for review
        print(json.dumps(cleaned_data, indent=4))
        print(f"Cleaned {path} successfully!")
    except FileNotFoundError:
        print(f"File not found: {path}")
    except:
        print("Could not remove duplicates!")


def convert_json_to_xlsx_files():
    folder_path = OUTPUT_PATH
    output_file_pattern = re.compile(r"output_\d+_\d+_cleaned\.json")

    # Ensure the path is valid
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        # Iterate over all files in the folder
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)

            # Check if it's a file (not a directory)
            if os.path.isfile(file_path) and output_file_pattern.match(filename):
                data = None
                with open(file_path, "r") as file:
                    # Parse JSON
                    data = json.loads(file.read())

                if data == None:
                    continue

                # Create a DataFrame from the JSON data
                df = DataFrame(data)

                # Specify the output XLSX file path
                output_path = f"{XLSX_OUTPUT_PATH}/{filename[:filename.rfind('.')]}.xlsx"

                # Write the DataFrame to an Excel file
                df.to_excel(output_path, index=False)

                print(f"Excel file '{output_path}' created successfully.")


if __name__ == "__main__":
    print("Started!")
    remove_duplicates_of_files()
    sleep(3)
    convert_json_to_xlsx_files()
