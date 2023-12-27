import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Example website (this is not for logging into Facebook)
url = 'https://web.facebook.com/login/?privacy_mutation_token=eyJ0eXBlIjowLCJjcmVhdGlvbl90aW1lIjoxNzAzNDE0MzUwLCJjYWxsc2l0ZV9pZCI6MzgxMjI5MDc5NTc1OTQ2fQ%3D%3D'

# The data that you would send in a POST request
payload = {
    'email': os.environ["FACEBOOK_EMAIL"],
    'password': os.environ["FACEBOOK_PASS"]
}

# Example POST request, not applicable to Facebook
with requests.Session() as session:
    response = session.post(url, data=payload)
    
    # Setting this for demonstration purposes
    # Facebook would need proper API access
    # response.cookies.set('foo', 'bar', domain='example.com')

    # Convert cookies to a dictionary
    cookies_dict = session.cookies.get_dict()

    # Save cookies to a .json file
    with open('fb-selenium-cookies-v1.json', 'w') as f:
        json.dump(cookies_dict, f)

print('Cookies have been saved to fb-selenium-cookies.json')