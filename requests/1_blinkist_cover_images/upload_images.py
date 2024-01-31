import subprocess
import time
import os
import dotenv
dotenv.load_dotenv()

PROJECT_ROOT = os.environ["PROJECT_ROOT"]


def check_screen_session(session_name):
    try:
        # Check if the screen session exists
        subprocess.check_output(["screen", "-ls", session_name])
        return True
    except subprocess.CalledProcessError:
        return False


def upload_images():
    session_name = "images_scraper"

    # Wait for the images_scraper screen session to close
    print(f"Waiting for the screen session '{session_name}' to end...")
    while check_screen_session(session_name):
        time.sleep(5)  # Wait for 5 seconds before checking again

    # Once the session is closed, run the upload command
    print(f"Starting upload in a new screen session...")
    upload_dir = f"{PROJECT_ROOT}/source/upload"
    upload_command = [
        "yarn", "dev"
    ]
    subprocess.run(upload_command, cwd=upload_dir)

    print("Upload process started in the 'uploader' screen session.")


# Call the function
upload_images()
