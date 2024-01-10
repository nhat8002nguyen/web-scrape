import fabric
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

ROOT_PATH = os.environ['PROJECT_ROOT']
REMOTE_ROOT_PATH = os.environ["REMOTE_ROOT"]
INPUT_PATH = ROOT_PATH + os.environ['INPUT_PATH']
CLOUD_PATH = ROOT_PATH + os.environ['CLOUD_PATH']
PRIVATE_KEY_PATH = ROOT_PATH + os.environ['PRIVATE_KEY_PATH']
APP_PATH = ROOT_PATH + "/app"

# Load the Excel file with instance details
df = pd.read_csv(f'{CLOUD_PATH}/instances.csv')
# Get a list of instances
instances = df.to_dict(orient='records')


for instance in instances:
    # Use fabric to SSH into instances and run setup commands
    with fabric.Connection(
        host=instance['ip_address'],
        user=instance['username'],
        connect_kwargs={'key_filename': PRIVATE_KEY_PATH},
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

        c.put(f"{INPUT_PATH}/{instance['csv_file']}",
              remote=f"{REMOTE_ROOT_PATH}/email_spider/domains_inputs/")
        c.put(f"{ROOT_PATH}/requirements.txt",
              remote=f"{REMOTE_ROOT_PATH}/email_spider/")

        # install pip packages
        c.run("cd ~/email_spider/ && python3.10 -m pip install -r requirements.txt")

        # Create batches.json file
        c.run("cd ~/email_spider/ && mv .env.prod .env")
        c.run(
            f"cd ~/email_spider/app && python3.10 create_batches.py --csv {instance['csv_file']}")

        # Run the Python script
        c.run(
            "cd ~/email_spider/ && screen -d -m -S email_spider python3.10 app/email_spider.py")
