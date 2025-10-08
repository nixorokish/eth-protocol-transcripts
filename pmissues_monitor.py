# pmissues_monitor.py (updated version)
import requests
import os
import re
from dotenv import load_dotenv
from datetime import datetime, timedelta
from meetings_config import WHITELISTED_MEETINGS

load_dotenv()

def extract_date_from_text(text):
    """Extract date from title or body text"""
    date_patterns = [
        r'(\w+ \d{1,2}, \d{4})',  # September 29, 2025
        r'(\w+ \d{1,2}(?:st|nd|rd|th)?, \d{4})',  # September 26th, 2025
        r'(\d{1,2}/\d{1,2}/\d{4})',  # 10/6/2025
        r'(\d{4}-\d{2}-\d{2})',  # 2025-09-29
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(1)
            # Remove ordinal suffixes
            date_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
            return date_str
    return None

def parse_issue_for_meeting_info(issue):
    """Extract meeting name and date from issue title and body"""
    title = issue.get("title", "")
    body = issue.get("body", "")
    
    # Try to find date in title first, then body
    meeting_date = extract_date_from_text(title)
    if not meeting_date and body:
        meeting_date = extract_date_from_text(body)
    
    # Find ALL matching meeting IDs for this meeting name
    matched_meetings = []
    for meeting_id, meeting_info in WHITELISTED_MEETINGS.items():
        meeting_name = meeting_info["name"]
        # Check for various name formats
        if any([
            meeting_name.lower() in title.lower(),
            meeting_name.replace(" - ", " ").lower() in title.lower(),
            meeting_name.split("(")[0].strip().lower() in title.lower() if "(" in meeting_name else False,
        ]):
            matched_meetings.append({
                "meeting_id": meeting_id,
                "meeting_name": meeting_name,
                "owner": meeting_info["owner"],
                "date_str": meeting_date,
                "issue_number": issue.get("number"),
                "issue_title": title,
                "closed_at": issue.get("closed_at")
            })
    
    # Return all possible meeting IDs for this meeting
    if matched_meetings:
        return {
            "possible_meeting_ids": [m["meeting_id"] for m in matched_meetings],
            "meeting_name": matched_meetings[0]["meeting_name"],
            "date_str": meeting_date,
            "issue_number": issue.get("number"),
            "issue_title": title,
            "closed_at": issue.get("closed_at"),
            "owners": list(set([m["owner"] for m in matched_meetings]))
        }
    
    return None

def get_recently_closed_issues(days_back=7):
    token = os.getenv("GITHUB_TOKEN")
    
    url = "https://api.github.com/repos/ethereum/pm/issues"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    params = {
        "state": "closed",
        "since": (datetime.now() - timedelta(days=days_back)).isoformat(),
        "per_page": 100
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        print(f"✗ GitHub API error: {response.status_code}")
        return []
    
    issues = response.json()
    
    # Filter for issues closed within our time window
    recently_closed = []
    for issue in issues:
        if issue.get("closed_at"):
            closed_date = datetime.fromisoformat(issue["closed_at"].replace("Z", "+00:00"))
            if closed_date > datetime.now(closed_date.tzinfo) - timedelta(days=days_back):
                recently_closed.append(issue)
    
    return recently_closed

# Test it
if __name__ == "__main__":
    closed_issues = get_recently_closed_issues(days_back=30)
    print(f"Found {len(closed_issues)} recently closed issues\n")

    matched_meetings = []
    for issue in closed_issues:
        meeting_info = parse_issue_for_meeting_info(issue)
        if meeting_info:
            matched_meetings.append(meeting_info)
            print(f"✓ Matched: {meeting_info['issue_title']}")
            print(f"  Possible Meeting IDs: {', '.join(meeting_info['possible_meeting_ids'])}")
            print(f"  Owners: {', '.join(meeting_info['owners'])}")
            print(f"  Date: {meeting_info['date_str'] or 'No date found'}\n")

    print(f"\nTotal matched meetings from whitelist: {len(matched_meetings)}")