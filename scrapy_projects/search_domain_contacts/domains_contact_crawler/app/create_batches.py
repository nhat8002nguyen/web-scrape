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

    parser.add_argument('csv_file_names', metavar='string', nargs="+", type=str,
                        help='A list of input file names')

    args = parser.parse_args()

    csv_names = args.csv_file_names

    cpu_count = os.cpu_count()

    batches = []
    for csv_name in csv_names:
        batch = dict()
        batch["input"] = csv_name
        batch["batches"] = []

        with open(f"{INPUT_PATH}/{csv_name}") as csv_file:
            reader = csv.DictReader(csv_file)
            rows = list(reader)
            batch_size = len(rows) // cpu_count

        for i in range(cpu_count):
            batch['batches'].append({
                "start": i*batch_size,
                "end": (i+1)*batch_size-1
            })

        batches.append(batch)

    with open(f"{PROJECT_ROOT}/batches.json", 'w') as json_file:
        json.dump(batches, json_file, indent=4)


if __name__ == "__main__":
    create_batches()
