import requests
import base64
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

def get_zoom_access_token():
    account_id = os.getenv("ZOOM_ACCOUNT_ID")
    client_id = os.getenv("ZOOM_CLIENT_ID")
    client_secret = os.getenv("ZOOM_CLIENT_SECRET")
    
    url = "https://zoom.us/oauth/token"
    
    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "account_credentials",
        "account_id": account_id
    }
    
    response = requests.post(url, headers=headers, data=data)
    return response.json().get("access_token")

def get_cloud_recordings(access_token, days_back=30):
    # Get recordings from the last 30 days
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    url = "https://api.zoom.us/v2/users/me/recordings"
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    params = {
        "from": from_date,
        "to": to_date
    }
    
    response = requests.get(url, headers=headers, params=params)
    return response.json()

# Test it
token = get_zoom_access_token()
recordings = get_cloud_recordings(token)

if "meetings" in recordings:
    print(f"✓ Found {len(recordings['meetings'])} recordings")
    for meeting in recordings['meetings'][:3]:  # Show first 3
        print(f"  - Meeting ID: {meeting.get('id')}, Topic: {meeting.get('topic')