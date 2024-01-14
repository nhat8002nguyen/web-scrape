from typing import Any, Hashable
import fabric
import pandas as pd
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

ROOT_PATH = os.environ['PROJECT_ROOT']
REMOTE_ROOT_PATH = os.environ["REMOTE_ROOT"]
INPUT_PATH = ROOT_PATH + os.environ['INPUT_PATH']
CLOUD_PATH = ROOT_PATH + os.environ['CLOUD_PATH']
APP_PATH = ROOT_PATH + "/app"


class CloudInstance():
    def __init__(self, ip_address: str, username: str, key_filename: str, csv_names: [str] = None) -> None:
        self.ip_address = ip_address
        self.username = username
        self.key_filename = key_filename
        if csv_names == None:
            self.csv_names = []
        else:
            self.csv_names = csv_names


def main():
    # Load the Excel file with instance details
    df = pd.read_csv(f'{CLOUD_PATH}/instances.csv')
    # Get a list of instances
    rows = df.to_dict(orient='records')

    instances = dict[str, CloudInstance]()
    for row in rows:
        key = f"{row['ip_address']}@{row['username']}"
        if key not in instances:
            instances[key] = CloudInstance(
                row['ip_address'], row['username'], row['key_filename'], [row["csv_file"]])
        else:
            instances[key].csv_names.append(row["csv_file"])

    with ThreadPoolExecutor() as executor:
        runs = [executor.submit(setup_and_run, instances[key])
                for key in instances]

        for run in as_completed(runs):
            result = run.result()
            print(result)


def setup_and_run(instance: CloudInstance):
    # Use fabric to SSH into instances and run setup commands
    ssh_key_path = f"{CLOUD_PATH}/{instance.key_filename}"
    with fabric.Connection(
        host=instance.ip_address,
        user=instance.username,
        connect_kwargs={'key_filename': ssh_key_path},
    ) as c:
        c.run('sudo apt update -y && sudo apt upgrade -y')

        # install python3.10
        c.run("sudo add-apt-repository ppa:deadsnakes/ppa -y")
        c.run("sudo apt update -y")
        c.run("sudo apt install -y python3.10")
        c.run('sudo apt install -y python3-pip')
        c.run("sudo apt install -y python3-venv")
        c.run("sudo apt install -y python3.10-dev")
        c.run("sudo apt install -y python3.10-distutils")
        c.run("sudo apt install -y python3.10-lib2to3")

        # install google chrome
        find_google_deb = c.run(
            "find -name google-chrome-stable_current_amd64.deb")
        if len(find_google_deb.stdout) == 0:
            c.run(
                "wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb")
        try:
            c.run("sudo dpkg -i google-chrome-stable_current_amd64.deb")
        except:
            c.run("sudo apt -f install -y")

    #   Transfer the Python script
        try:
            find_email_spider = c.run("find email_spider")
        except:
            c.run(
                "mkdir email_spider && cd email_spider && mkdir domains_inputs outputs app")

        c.put(f"{ROOT_PATH}/.env.prod",
              remote=f"{REMOTE_ROOT_PATH}/email_spider/")
        c.put(f"{ROOT_PATH}/batches.json",
              remote=f"{REMOTE_ROOT_PATH}/email_spider/")

        c.put(f'{APP_PATH}/email_spider.py',
              remote=f'{REMOTE_ROOT_PATH}/email_spider/app/')
        c.put(f'{APP_PATH}/item_pipeline.py',
              remote=f'{REMOTE_ROOT_PATH}/email_spider/app/')
        c.put(f'{APP_PATH}/domain_timeout_middleware.py',
              remote=f'{REMOTE_ROOT_PATH}/email_spider/app/')
        c.put(f'{APP_PATH}/create_batches.py',
              remote=f'{REMOTE_ROOT_PATH}/email_spider/app/')

        for csv_name in instance.csv_names:
            c.put(f"{INPUT_PATH}/{csv_name}",
                  remote=f"{REMOTE_ROOT_PATH}/email_spider/domains_inputs/")

        c.put(f"{ROOT_PATH}/requirements.txt",
              remote=f"{REMOTE_ROOT_PATH}/email_spider/")

        # install pip packages
        c.run("cd ~/email_spider/ && python3.10 -m pip install -r requirements.txt")

        # Create batches.json file
        c.run("cd ~/email_spider/ && mv .env.prod .env")
        c.run(
            f"cd ~/email_spider/app && python3.10 create_batches.py {' '.join(instance.csv_names)}")

        # Run the Python script
        c.run(
            "cd ~/email_spider/ && screen -d -m -S email_spider python3.10 app/email_spider.py")

        screen_sessions = c.run("screen -ls")
        if "email_spider" in str(screen_sessions.stdout):
            return f"INFO: Done with {instance.username}@{instance.ip_address}"

        return f"WARNING: Please check the {instance.username}@{instance.ip_address}, to make sure it's running!"


if __name__ == "__main__":
    main()
