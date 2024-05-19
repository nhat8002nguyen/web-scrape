import time
import pandas as pd
import os
import dotenv
dotenv.load_dotenv()

CSV_INPUT_PATH = os.environ["PROJECT_ROOT"] + "/" + "domains_inputs"
CSV_OUTPUT_PATH = os.environ["PROJECT_ROOT"] + "/" + "csv_outputs"


def combine_email_phone(prefix: str):

    input_file = f'{prefix}.csv'
    email_file = f'combined_{prefix}_email_output.csv'
    phone_file = f'combined_{prefix}_phone_output.csv'
    final_file = f'combined_{prefix}_output.csv'
    # Read the CSV files
    # assuming the file is named emails.csv
    df_emails = pd.read_csv(f'{CSV_OUTPUT_PATH}/{email_file}')
    # assuming the file is named phones.csv
    df_phones = pd.read_csv(f'{CSV_OUTPUT_PATH}/{phone_file}')

    # Sort the dataframes just in case they are not sorted
    df_emails = df_emails.sort_values(by=['domain', 'email'])
    df_phones = df_phones.sort_values(by=['domain', 'phone'])

   # Sort the dataframes to ensure the first found phone numbers are considered first
    df_phones = df_phones.sort_values(by=['domain', 'XID'])

    # Remove duplicate phone numbers within each domain
    df_phones = df_phones.drop_duplicates(subset=['domain', 'phone'])

    # Create a ranking column within each domain for the emails
    df_emails['rank'] = df_emails.groupby('domain').cumcount()

    # Create a ranking column within each domain for the phones, we'll use this rank to merge with emails
    df_phones['rank'] = df_phones.groupby('domain').cumcount()

    # Merge the emails and phones dataframes on domain and rank
    df_merged = pd.merge(df_emails, df_phones, on=[
                         'domain', 'rank'], how='left')

    # Drop the rank columns as it's no longer needed
    df_merged.drop('rank', axis=1, inplace=True)

    # Remove duplicate columns
    df_merged.drop('XID_y', axis=1, inplace=True)
    df_merged = df_merged.rename(columns={'XID_x': 'XID'})

    # Load the data from both CSV files
    # Replace with your actual file path
    first_csv = pd.read_csv(f'{CSV_INPUT_PATH}/{input_file}')

    # Merge the two DataFrames on the XID column
    merged_csv = pd.merge(
        df_merged, first_csv[['XID', 'NAME', 'ORG']], on='XID', how='left')

    # Save the merged DataFrame to a new CSV file
    # Replace with your desired file path
    merged_csv.to_csv(f'{CSV_OUTPUT_PATH}/{final_file}', index=False)

    print("Merged file, and added additional values successfully!")
