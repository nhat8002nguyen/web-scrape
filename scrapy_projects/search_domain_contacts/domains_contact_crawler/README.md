## Setup and Deploy the script
Install pip dependencies:
    $ pip install -r requirements.txt

Go to .env and edit 
    PROJECT_ROOT is absolute path to program folder of local computer
    REMOTE_ROOT is home path of the remote machine, for example: /home/ubuntu

Edit the .env.prod:
    PROJECT_ROOT is absolute path to program folder on the 'remote' machine
    REMOTE_ROOT is home path of the remote machine, for example: /home/ubuntu (the same with .env)

Download your_ssh_key.pem files and locate it in the '/clouds' folder (which contains instances.csv file)

Edit the instances.csv file: your remote machines, name of input csv, and appropriate ssh key file (example in the file).

Run the deploy.py with the command to deploy the scripts to remote machines based on instances.csv file: 
    $ python3.10 deploy.py

After running the deploy for a while, run the following command to get the data from remote to folder 'remote_data':
    $ python3.10 collect_results.py
This command will update the data after 30 seconds, end disconnect after 10 mins.