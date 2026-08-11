# zoom_fetcher.py (whitelist moved to ZOOM_ACCOUNT_EMAILS env var)
import requests
import os
import base64
from dotenv import load_dotenv
from datetime import datetime, timedelta
from dateutil import parser
from .meetings_config import WHITELISTED_MEETINGS

load_dotenv()

# Whitelist of users who host meetings, from the ZOOM_ACCOUNT_EMAILS env var
# (comma-separated, e.g. "a@example.org,b@example.org"). Kept out of the repo.
WHITELISTED_HOSTS = [
    email.strip()
    for email in os.getenv("ZOOM_ACCOUNT_EMAILS", "").split(",")
    if email.strip()
]

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
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=30)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"✗ Failed to get Zoom access token: {response.status_code}")
            if response.text:
                print(f"  Error: {response.text[:200]}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"✗ Network error getting Zoom access token: {e}")
        return None

def get_all_recordings_in_range(access_token, from_date, to_date, debug=False):
    """Get ALL recordings in a date range from whitelisted users"""
    all_meetings = []
    
    if debug:
        print(f"  Debug: Checking recordings for {len(WHITELISTED_HOSTS)} whitelisted users")
    
    # For each whitelisted user, get their recordings
    for user_email in WHITELISTED_HOSTS:
        if debug:
            print(f"  Debug: Checking recordings for {user_email}")
        
        page_token = None
        while True:
            # Use the email directly in the endpoint
            url = f"https://api.zoom.us/v2/users/{user_email}/recordings"
            
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            
            params = {
                "from": from_date,
                "to": to_date,
                "page_size": 300
            }
            
            if page_token:
                params["next_page_token"] = page_token
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                if "meetings" in data:
                    meetings = data["meetings"]
                    # Add host info to each meeting
                    for meeting in meetings:
                        meeting["host_email"] = user_email
                    
                    all_meetings.extend(meetings)
                    
                    if debug and len(meetings) > 0:
                        print(f"    Found {len(meetings)} recordings")
                
                # Check if there are more pages
                page_token = data.get("next_page_token")
                if not page_token:
                    break
            elif response.status_code == 404:
                # User not found - skip
                if debug:
                    print(f"    User not found (might not have Zoom account)")
                break
            else:
                # Other error - skip this user
                if debug:
                    print(f"    Error {response.status_code} for user")
                break
    
    return all_meetings

def get_recordings_for_meeting_ids(access_token, meeting_ids, meeting_date, debug=False):
    """Fetch recordings for multiple possible meeting IDs around a specific date"""
    
    # Parse the date and create a wider search window
    try:
        # Try multiple date formats
        # First try with original string (for formats with commas)
        # Then try with comma removed (for formats without commas)
        target_date = None
        
        # Formats that expect commas
        for fmt in ['%B %d, %Y', '%b %d, %Y']:
            try:
                target_date = datetime.strptime(meeting_date, fmt)
                break
            except:
                continue
        
        # If no match, try formats without commas (after removing comma from input)
        if not target_date:
            date_no_comma = meeting_date.replace(',', '')
            for fmt in ['%B %d %Y', '%b %d %Y', '%Y-%m-%d', '%m/%d/%Y']:
                try:
                    target_date = datetime.strptime(date_no_comma, fmt)
                    break
                except:
                    continue
        
        # Fall back to dateutil parser if nothing else works
        if not target_date:
            target_date = parser.parse(meeting_date)
        
        # Use a 3-day window to account for timezone differences
        from_date = (target_date - timedelta(days=2)).strftime("%Y-%m-%d")
        to_date = (target_date + timedelta(days=2)).strftime("%Y-%m-%d")
    except Exception as e:
        print(f"  ✗ Could not parse date '{meeting_date}': {e}")
        return None
    
    if debug:
        print(f"  Debug: Parsed '{meeting_date}' as {target_date.strftime('%Y-%m-%d')}")
        print(f"  Debug: Searching from {from_date} to {to_date}")
    
    # Get all recordings in date range from whitelisted users
    all_meetings = get_all_recordings_in_range(access_token, from_date, to_date, debug)
    
    if debug:
        print(f"  Debug: Found {len(all_meetings)} total recordings across whitelisted users")
    
    all_matching_recordings = []
    
    # Clean up meeting IDs for comparison
    clean_meeting_ids = []
    for mid in meeting_ids:
        # Remove all spaces and dashes
        clean_id = mid.replace(" ", "").replace("-", "")
        clean_meeting_ids.append(clean_id)
    
    # Filter for recordings matching any of our meeting IDs
    for meeting in all_meetings:
        meeting_id_from_zoom = str(meeting.get("id", ""))
        zoom_id_clean = meeting_id_from_zoom.replace(" ", "").replace("-", "")
        
        if debug:
            topic = meeting.get('topic', '')[:50]
            duration = meeting.get('duration')
            start = meeting.get('start_time')
            host = meeting.get('host_email', 'unknown')
            print(f"    Debug: ID={meeting_id_from_zoom}, Topic={topic}, Duration={duration} min, Host={host}")
        
        if zoom_id_clean in clean_meeting_ids:
            # Find the original meeting ID
            for i, clean_id in enumerate(clean_meeting_ids):
                if zoom_id_clean == clean_id:
                    meeting["matched_meeting_id"] = meeting_ids[i]
                    break
            
            all_matching_recordings.append(meeting)
            if debug:
                print(f"      ✓ Matched! (Meeting ID: {meeting.get('matched_meeting_id', 'unknown')})")
    
    if not all_matching_recordings:
        if debug:
            print(f"  Debug: No recordings matched IDs: {', '.join(meeting_ids)}")
        return None
    
    # Find the longest recording
    longest_recording = max(all_matching_recordings, key=lambda x: x.get("duration", 0))
    
    if longest_recording.get("duration", 0) < 10:
        print(f"  ⚠ Longest recording only {longest_recording.get('duration')} minutes - might be a test")
    
    return longest_recording


def get_meeting_participants(access_token, meeting_instance_uuid):
    """
    Get participant list for a past meeting instance.
    meeting_instance_uuid: from a Zoom recording/meeting object (the instance uuid).
    Uses Past Meetings API; requires scope: meeting:read:list_past_participants:admin
    """
    from urllib.parse import quote
    encoded_uuid = quote(meeting_instance_uuid, safe="")
    url = f"https://api.zoom.us/v2/past_meetings/{encoded_uuid}/participants"
    headers = {"Authorization": f"Bearer {access_token}"}
    participants = []
    next_page_token = None
    try:
        while True:
            params = {"page_size": 300}
            if next_page_token:
                params["next_page_token"] = next_page_token
            response = requests.get(url, headers=headers, params=params, timeout=30)
            if response.status_code != 200:
                return None
            data = response.json()
            participants.extend(data.get("participants", []))
            next_page_token = data.get("next_page_token")
            if not next_page_token:
                break
        return participants
    except requests.exceptions.RequestException:
        return None


# Test with debugging
if __name__ == "__main__":
    token = get_zoom_access_token()
    
    print("✓ Got access token\n")
    
    # Test the problematic meetings
    test_cases = [
        (["842 6574 5580"], "September 23, 2025"),  # FOCIL (Nico)
        (["842 5123 7513"], "Sep 22, 2025"),  # ACDT #54 (Nico)
    ]
    
    for meeting_ids, date in test_cases:
        print(f"Testing: {', '.join(meeting_ids)} on {date}")
        recording = get_recordings_for_meeting_ids(token, meeting_ids, date, debug=True)
        
        if recording:
            print(f"\n✓ Found best recording:")
            print(f"  - Matched Meeting ID: {recording.get('matched_meeting_id')}")
            print(f"  - Topic: {recording.get('topic')}")
            print(f"  - Duration: {recording.get('duration')} minutes")
            print(f"  - Host: {recording.get('host_email')}")
        else:
            print("\n✗ No suitable recording found")
        print("-" * 60)