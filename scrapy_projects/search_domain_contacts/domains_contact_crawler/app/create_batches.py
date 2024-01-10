import os
from dotenv import load_dotenv
import json
import csv
import argparse
load_dotenv()

PROJECT_ROOT = os.environ["PROJECT_ROOT"]
INPUT_PATH = PROJECT_ROOT + os.environ['INPUT_PATH']


def create_batches():
    parser = argparse.ArgumentParser(description='Description of your script.')

    parser.add_argument('--csv', dest='csv_name',
                        required=True, help='Name of the input file')

    args = parser.parse_args()

    csv_name = args.csv_name

    cpu_count = os.cpu_count()

    batches = dict()
    batches["input"] = csv_name
    batches["batches"] = []

    with open(f"{INPUT_PATH}/{csv_name}") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
        # TODO: is debugging
        batch_size = len(rows[0:4000]) // cpu_count

    for i in range(cpu_count):
        batches['batches'].append({
            "start": i*batch_size,
            "end": (i+1)*batch_size-1
        })

    with open(f"{PROJECT_ROOT}/batches.json", 'w') as json_file:
        json.dump(batches, json_file, indent=4)


if __name__ == "__main__":
    create_batches()
