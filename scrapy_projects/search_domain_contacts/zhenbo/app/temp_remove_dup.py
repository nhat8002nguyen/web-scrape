import json

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
    except FileNotFoundError:
        print(f"File not found: {path}")
    except:
        print("Could not remove duplicates!")

if __name__ == "__main__":
    absolute_path = "/Users/nhatnguyen/Workspaces/web-scrape/scrapy_projects/search_domain_contacts/zhenbo"
    remove_duplicates_json(f"{absolute_path}/instances-outputs/output_0_9999.json")
    remove_duplicates_json(f"{absolute_path}/instances-outputs/output_10000_19999.json")