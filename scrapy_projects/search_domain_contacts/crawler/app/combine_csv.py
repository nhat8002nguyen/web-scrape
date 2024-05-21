from combine_email_phone import combine_email_phone
import pandas as pd
import os
import glob
import dotenv
from pandas.errors import EmptyDataError
dotenv.load_dotenv()

# Define the folder where the CSV files are located
# Replace with your folder path
folder_path = f'{os.environ["PROJECT_ROOT"]}/csv_outputs'
success_urls_path = f'{os.environ["PROJECT_ROOT"]}/outputs'


def concatenate_files(files, output_filename):
    # Initialize an empty list to hold data frames
    dfs = []

    for i, file in enumerate(files):
        try:
            if i == 0:  # For the first file, keep the header
                df = pd.read_csv(file)
            else:  # For subsequent files, ignore the header row
                df = pd.read_csv(file, header=0)
            dfs.append(df)
        except EmptyDataError:
            continue

    # Concatenate all data frames
    combined_csv = pd.concat(dfs, ignore_index=True)

    combined_csv.to_csv(os.path.join(
        folder_path, output_filename), index=False)


def combine_files(prefix) -> bool:
    # Iterate over the prefixes and types and process the files
    for output_type in ['email', 'phone']:
        # Find the relevant CSV files with the current prefix and output type
        pattern = f"{prefix}_{output_type}_output_*.csv"
        files = sorted(glob.glob(os.path.join(folder_path, pattern)))

        # Concatenate and save the files with the same prefix and output type
        if files:  # Only proceed if there are files to concatenate
            output_filename = f"combined_{prefix}_{output_type}_output.csv"
            concatenate_files(files, output_filename)

    combine_email_phone(prefix=prefix)
    remove_email_phone_files(prefix)
    return True


def remove_email_phone_files(prefix: str):
    try:
        os.remove(f"{folder_path}/combined_{prefix}_email_output.csv")
        os.remove(f"{folder_path}/combined_{prefix}_phone_output.csv")
    except:
        print("Failed to remove combined email/phone outputs")


def delete_sub_files(prefix):
    for output_type in ['email', 'phone']:
        # Find the relevant CSV files with the current prefix and output type
        pattern = f"{prefix}_{output_type}_output_*.csv"
        files = sorted(glob.glob(os.path.join(folder_path, pattern)))

        # Concatenate and save the files with the same prefix and output type
        if files:  # Only proceed if there are files to concatenate
            for file in files:
                os.remove(file)


def delete_successful_urls_files(prefix: str):
    pattern = f"{prefix}_success_urls_*.json"
    files = sorted(glob.glob(os.path.join(success_urls_path, pattern)))

    # Concatenate and save the files with the same prefix and output type
    if files:  # Only proceed if there are files to concatenate
        for file in files:
            os.remove(file)
