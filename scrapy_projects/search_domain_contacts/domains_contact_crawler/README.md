## Setup and Deploy the script
- Require Python3.10 
- Folders and files you need to edit: /domains_inputs, /clouds, .env and .env.prd
- After that, run the deploy.py and look at the shell, everything will be done.

1. Install pip dependencies:
    `$ pip install -r requirements.txt`

2. Go to .env and edit 
    PROJECT_ROOT is the absolute path to program folder of your 'local' computer
    REMOTE_ROOT is the home path of the remote machine, for example: /home/ubuntu or /root, type 'pwd' to see.

3. Edit the .env.prod:
    PROJECT_ROOT is the absolute path to program folder on the 'remote' machines
    REMOTE_ROOT is the home path of the remote machine, for example: /home/ubuntu (the same with .env file)

4. Go to folder /domains_inputs folder and remove all sample files. Then add your input files to folder /domains_inputs

4. Download your_ssh_key.pem files and locate it in the '/clouds' folder (which contains instances.csv file)

5. Edit the instances.csv file: ip address, username, name of input csv, and appropriate ssh key file (example in the instances.csv).

6. Run the deploy.py with the command to deploy the scripts to remote machines based on instances.csv file: 
    `$ python3.10 deploy.py`

7. Your Storage VPS will collect data from other machines after each 5 minutes, and will be expired in 7 days.
    The data will be saved to folder ~/remote_data/outputs

8. To pull data from storage vps to local computer run:
`$ scp -i clouds/ramnode.pem -r root@167.88.113.102:/root/remote_data/csv_outputs ../remote_data`

9.In the /remote_data/combine_csv.py, edit the prefixes at line 12, and then run it. It will combine all csv files into files prefixed with 'combined_'.