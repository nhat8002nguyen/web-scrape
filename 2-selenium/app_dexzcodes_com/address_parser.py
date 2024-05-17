import pandas as pd

ROOT = "/Users/nhatnguyen/Workspaces/web-scrape/2-selenium/app_dexzcodes_com"

# Load data from a CSV file
# Replace 'your_file.csv' with your actual file path
df = pd.read_csv(f'{ROOT}/data/PCR-tests-all.csv', delimiter=";")

# Define a function to split the address column


def split_address(address: str):
    if pd.isnull(address):
        return ['', '', '']  # Return empty parts if the address is NaN or None

    part = ['', '', '']
    part[0] = address[:address.rfind(",")]
    part[1] = address[address.rfind(",")+1:address.rfind(" ")]
    part[2] = address[address.rfind(" ")+1:]

    return part


# Apply the function to the address column and split into three new columns
df[['address', 'state', 'zipcode']] = df.apply(
    lambda row: pd.Series(split_address(row['Address'])), axis=1)

# Save the updated dataframe back to a CSV file
# Replace with your desired output file name
df.to_csv('updated_file.csv', index=False)
