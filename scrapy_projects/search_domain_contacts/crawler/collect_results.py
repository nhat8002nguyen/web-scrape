from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Hashable
import paramiko
from scp import SCPClient
import time
import os
import stat
from dotenv import load_dotenv
from deploy import CloudInstance
import shutil
import pandas as pd
import glob
load_dotenv()

ROOT_PATH = os.environ['PROJECT_ROOT']
CLOUD_PATH = ROOT_PATH + os.environ['CLOUD_PATH']
REMOTE_FOLDER_ROOT_PATH = os.environ["REMOTE_ROOT"] + \
    "/email_spider/csv_outputs"
OUTPUT_PATH = os.environ["REMOTE_ROOT"] + "/remote_data"


def main():
    # Load the Excel file with instance details
    df = pd.read_csv(f'{CLOUD_PATH}/instances.csv')
    # Get a list of instances
    rows = df.to_dict(orient='records')

    instances = dict[str, CloudInstance]()
    for row in rows:
        if "for_storage" in row and row["for_storage"] == "yes":
            continue

        key = f"{row['ip_address']}@{row['username']}"
        if key not in instances:
            instances[key] = CloudInstance(
                row['ip_address'], row['username'], row['key_filename'], [row["csv_file"]])
        else:
            instances[key].csv_names.append(row["csv_file"])

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        runs = [executor.submit(load_file_from_instance, instances[key])
                for key in instances]

        for run in as_completed(runs):
            result = run.result()
            print(result)


def load_file_from_instance(instance: CloudInstance) -> str:
    # Connection information
    hostname = instance.ip_address
    username = instance.username
    key_file_path = f"{CLOUD_PATH}/{instance.key_filename}"
    remote_file_path = f"{REMOTE_FOLDER_ROOT_PATH}"
    local_file_path = f"{OUTPUT_PATH}"

    # Setup SSH client
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # added permission for .pem key
    os.chmod(key_file_path, stat.S_IRUSR)

    # Loop for connecting, transferring files, and waiting
    try:
        count = 0
        while count < 2000:
            count += 1
            try:
                # remove all existing files to receive a net set of files
                for csv_name in instance.csv_names:
                    try:
                        prefix = csv_name[:csv_name.rfind(".")]
                        pattern = f"{prefix}_*.csv"
                        files = sorted(
                            glob.glob(os.path.join(OUTPUT_PATH + "/csv_outputs", pattern)))
                        if files:  # Only proceed if there are files to concatenate
                            for file in files:
                                os.remove(file)
                    except Exception as e:
                        print(f"An error occurred: {e}")

                # Connect using the private key (.pem file)
                key = paramiko.RSAKey.from_private_key_file(key_file_path)

                print("Connecting to the cloud instance...")
                ssh.connect(hostname=hostname, username=username, pkey=key)
                print("Connected successfully!")

                # Execute a command (e.g., 'ls') just to test
                stdin, stdout, stderr = ssh.exec_command('ls')
                print("Command execution result:", stdout.read().decode())

                with SCPClient(ssh.get_transport()) as scp:
                    print(
                        f"Transferring {remote_file_path} to {local_file_path}")
                    scp.get(remote_file_path, local_file_path, recursive=True)
                    print("Transfer complete!")

                # Disconnect from the server
                ssh.close()
            except paramiko.SSHException as ssh_error:
                print(f"Connection failed: {ssh_error}")
                break  # Or remove to attempt reconnection in the next loop
            except Exception as e:
                print(f"An error occurred: {e}")
                break  # Or remove to attempt reconnection in the next loop

            print("Waiting for 5 minutes...")
            time.sleep(300)

        return f"Disconnect to {username}@{hostname}"
    except KeyboardInterrupt:
        print("Process interrupted by user.")
        return f"Disconnect to {username}@{hostname}"
    finally:
        # Ensure the connection is closed if it's still open
        if ssh.get_transport().is_active():
            ssh.close()

        return f"Disconnect to {username}@{hostname}"


if __name__ == "__main__":
    main()
