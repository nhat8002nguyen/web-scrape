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
    def __init__(self, ip_address: str, username: str, key_filename: str, csv_names: [str] = None, for_storage="no") -> None:
        self.ip_address = ip_address
        self.username = username
        self.key_filename = key_filename
        if csv_names == None:
            self.csv_names = []
        else:
            self.csv_names = csv_names
        self.for_storage = for_storage


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
                row['ip_address'], row['username'], row['key_filename'], [row["csv_file"]], str(row["for_storage"]).lower())
        else:
            instances[key].csv_names.append(row["csv_file"])

    all_ssh_keys_name = set(
        [instance.key_filename for instance in list(instances.values())])

    with ThreadPoolExecutor() as executor:
        runs = [executor.submit(setup_and_run, instances[key], all_ssh_keys_name)
                for key in instances]

        for run in as_completed(runs):
            result = run.result()
            print(result)


def setup_and_run(instance: CloudInstance, all_ssh_keys_name: set[str]):
    # Use fabric to SSH into instances and run setup commands
    ssh_key_path = f"{CLOUD_PATH}/{instance.key_filename}"
    with fabric.Connection(
        host=instance.ip_address,
        user=instance.username,
        connect_kwargs={'key_filename': ssh_key_path},
    ) as c:
        try:
            find_email_spider = c.run("find email_spider")
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

            c.run(
                "mkdir email_spider && cd email_spider && mkdir domains_inputs outputs app")

        c.put(f"{ROOT_PATH}/.env.prod",
              remote=f"{REMOTE_ROOT_PATH}/email_spider/")

        c.put(f'{APP_PATH}/email_spider.py',
              remote=f'{REMOTE_ROOT_PATH}/email_spider/app/')
        c.put(f'{APP_PATH}/item_pipeline.py',
              remote=f'{REMOTE_ROOT_PATH}/email_spider/app/')
        c.put(f'{APP_PATH}/domain_timeout_middleware.py',
              remote=f'{REMOTE_ROOT_PATH}/email_spider/app/')
        c.put(f'{APP_PATH}/create_batches.py',
              remote=f'{REMOTE_ROOT_PATH}/email_spider/app/')
        c.put(f'{APP_PATH}/utilities.py',
              remote=f'{REMOTE_ROOT_PATH}/email_spider/app/')

        if instance.for_storage == "no":
            for csv_name in instance.csv_names:
                c.put(f"{INPUT_PATH}/{csv_name}",
                      remote=f"{REMOTE_ROOT_PATH}/email_spider/domains_inputs/")

        c.put(f"{ROOT_PATH}/requirements.txt",
              remote=f"{REMOTE_ROOT_PATH}/email_spider/")

        # install pip packages
        c.run("cd ~/email_spider/ && python3.10 -m pip install -r requirements.txt")

        c.run("cd ~/email_spider/ && mv .env.prod .env")

        if is_screen_session_running(c, "email_spider"):
            return f"INFO: Email spider is still running on {instance.username}@{instance.ip_address}"
        elif is_screen_session_running(c, "collect_results"):
            return f"INFO: Results collection is still running on {instance.username}@{instance.ip_address}"

        # Run the Python script
        if instance.for_storage == "no":
            # Create batches.json file
            c.run(
                f"cd ~/email_spider/app && python3.10 create_batches.py {' '.join(instance.csv_names)}")

            c.run(
                "cd ~/email_spider/ && screen -d -m -S email_spider python3.10 app/email_spider.py")

        elif instance.for_storage == "yes":
            try:
                c.run("find email_spider/remote_data/")
            except:
                c.run(
                    "cd ~/email_spider && mkdir remote_data clouds")

            c.put(f"{ROOT_PATH}/clouds/instances.csv",
                  remote=f"{REMOTE_ROOT_PATH}/email_spider/clouds/")
            c.put(f"{ROOT_PATH}/collect_results.py",
                  remote=f"{REMOTE_ROOT_PATH}/email_spider/")
            c.put(f"{ROOT_PATH}/deploy.py",
                  remote=f"{REMOTE_ROOT_PATH}/email_spider/")

            try:
                for ssh_key in all_ssh_keys_name:
                    c.put(f"{ROOT_PATH}/clouds/{ssh_key}",
                          remote=f"{REMOTE_ROOT_PATH}/email_spider/clouds/")
            except PermissionError as err:
                print("INFO: Keys already in there!")

            c.run(
                "cd ~/email_spider/ && screen -d -m -S collect_results python3.10 collect_results.py")

        if is_screen_session_running(c, "email_spider"):
            return f"INFO: Successfully setup email spider done with {instance.username}@{instance.ip_address}"
        elif is_screen_session_running(c, "collect_results"):
            return f"INFO: Successfully setup results collection done with {instance.username}@{instance.ip_address}"

        return f"WARNING: Please check the {instance.username}@{instance.ip_address}, to make sure it's running!"


def is_screen_session_running(conn, session_name):
    result = conn.run(
        "screen -ls | grep {}".format(session_name), warn=True, hide=True)
    return result.ok and session_name in result.stdout


if __name__ == "__main__":
    main()
