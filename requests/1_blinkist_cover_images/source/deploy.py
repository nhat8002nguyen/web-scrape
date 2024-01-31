import os
from dotenv import load_dotenv
from fabric import Connection
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import time

load_dotenv()

PROJECT_ROOT = os.environ['PROJECT_ROOT']
REMOTE_ROOT_PATH = os.environ["REMOTE_ROOT"]
CLOUD_PATH = os.environ['CLOUD_PATH']


class CloudInstance():
    def __init__(self, ip_address: str, username: str, key_filename: str, start_index: int, end_index: int) -> None:
        self.ip_address = ip_address
        self.username = username
        self.key_filename = key_filename
        self.start_index = start_index
        self.end_index = end_index


def main():
    df = pd.read_csv(f'{CLOUD_PATH}/instances.csv')
    rows = df.to_dict(orient='records')

    instances = [CloudInstance(row['ip_address'], row['username'], row['key_filename'],
                               row['start_index'], row['end_index']) for row in rows]

    with ThreadPoolExecutor() as executor:
        runs = [executor.submit(deploy_and_run_script, instance)
                for instance in instances]

        for run in as_completed(runs):
            result = run.result()
            print(result)


def deploy_and_run_script(instance: CloudInstance):
    ssh_key_path = f"{CLOUD_PATH}/{instance.key_filename}"
    with Connection(
        host=instance.ip_address,
        user=instance.username,
        connect_kwargs={'key_filename': ssh_key_path}
    ) as c:
        try:
            c.run("find 1_blinkist_cover_images")
        except:
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

            # Install nodejs and yarn
            c.run('curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -')
            c.run('sudo apt-get install -y nodejs')
            c.run('sudo npm install -g yarn')

        # Create the new folder
        c.run(
            "mkdir -p 1_blinkist_cover_images/source/{images_scraper,upload}")
        c.run("mkdir -p 1_blinkist_cover_images/cover_images")

        # Upload input file
        try:
            c.run(
                f"find {REMOTE_ROOT_PATH}/1_blinkist_cover_images/27-categories-books.xlsx")
        except:
            c.put(f"{PROJECT_ROOT}/27-categories-books.xlsx",
                  remote=f"{REMOTE_ROOT_PATH}/1_blinkist_cover_images/27-categories-books.xlsx")
        c.put(f"{PROJECT_ROOT}/cookies.json",
              remote=f"{REMOTE_ROOT_PATH}/1_blinkist_cover_images/cookies.json")

        # Upload your scripts and requirements.txt
        c.put(f"{PROJECT_ROOT}/.env.prod",
              remote=f"{REMOTE_ROOT_PATH}/1_blinkist_cover_images/.env")
        c.put(f"{PROJECT_ROOT}/source/images_scraper/main.py",
              remote=f"{REMOTE_ROOT_PATH}/1_blinkist_cover_images/source/images_scraper/main.py")
        c.put(f"{PROJECT_ROOT}/requirements.txt",
              remote=f"{REMOTE_ROOT_PATH}/1_blinkist_cover_images/requirements.txt")
        c.put(f"{PROJECT_ROOT}/source/upload/package.json",
              remote=f"{REMOTE_ROOT_PATH}/1_blinkist_cover_images/source/upload/package.json")
        c.put(f"{PROJECT_ROOT}/source/upload/uploadS3.js",
              remote=f"{REMOTE_ROOT_PATH}/1_blinkist_cover_images/source/upload/uploadS3.js")
        c.put(f"{PROJECT_ROOT}/source/upload/.env.prod",
              remote=f"{REMOTE_ROOT_PATH}/1_blinkist_cover_images/source/upload/.env")
        c.put(f"{PROJECT_ROOT}/upload_images.py",
              remote=f"{REMOTE_ROOT_PATH}/1_blinkist_cover_images/upload_images.py")

        # Install required Python packages
        c.run(
            f"cd 1_blinkist_cover_images && python3 -m pip install -r requirements.txt")

        # Install JavaScript dependencies
        c.run(
            f'cd 1_blinkist_cover_images/source/upload && yarn install')

        # Start running the Python script in a screen session
        c.run(
            f'screen -d -m -S images_scraper -L python3.10 1_blinkist_cover_images/source/images_scraper/main.py --start {instance.start_index} --end {instance.end_index}')

        c.run(
            f'screen -d -m -S upload_images -L python3.10 1_blinkist_cover_images/upload_images.py')

        # The scripts are running inside screen sessions which remain after disconnection

    return f"Deployment completed on {instance.username}@{instance.ip_address}"

# Add a method for checking whether the image scraper is done, since the 'wait-for-previous-task' command is a placeholder


if __name__ == "__main__":
    main()
