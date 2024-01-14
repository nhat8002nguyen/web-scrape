import os
import dotenv
dotenv.load_dotenv()

ROOT_PATH = os.environ['PROJECT_ROOT']
OUTPUT_PATH = ROOT_PATH + os.environ['OUTPUT_PATH']


def get_email_output_csv_path(csv_name: str, start_index: int, end_index: int):
    return f'{OUTPUT_PATH}/{csv_name[:csv_name.rfind(".")]}_email_output_{start_index}_{end_index}.csv'


def get_single_email_output_path(csv_name: str):
    return f"{OUTPUT_PATH}/{csv_name[:csv_name.rfind('.')]}_email_output.csv"


def get_phone_output_csv_path(csv_name: str, start_index: int, end_index: int):
    return f'{OUTPUT_PATH}/{csv_name[:csv_name.rfind(".")]}_phone_output_{start_index}_{end_index}.csv'


def get_single_phone_output_path(csv_name: str):
    return f"{OUTPUT_PATH}/{csv_name[:csv_name.rfind('.')]}_phone_output.csv"
