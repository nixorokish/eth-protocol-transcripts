# pmissues_monitor.py (updated date extraction)
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
        # Full month names with various formats
        r'\b(\w{3,9}\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})\b',  # September 26th, 2025 or September 26 2025
        r'\b(\d{1,2}\s+\w{3,9}\s+\d{4})\b',  # 26 September 2025
        
        # ISO and slash formats
        r'\b(\d{4}-\d{2}-\d{2})\b',  # 2025-09-29
        r'\b(\d{1,2}/\d{1,2}/\d{4})\b',  # 10/6/2025
        r'\b(\d{1,2}[-/.]\d{1,2}[-/.]\d{2})\b',  # 10-6-25 or 10/6/25
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            # Remove ordinal suffixes and extra spaces
            date_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
            date_str = re.sub(r'\s+', ' ', date_str).strip()
            
            # Try to parse to validate it's a real date
            test_formats = [
                '%B %d %Y',  # September 26 2025
                '%B %d, %Y',  # September 26, 2025
                '%b %d %Y',  # Sep 26 2025
                '%b %d, %Y',  # Sep 26, 2025
                '%d %B %Y',  # 26 September 2025
                '%d %b %Y',  # 26 Sep 2025
                '%Y-%m-%d',  # 2025-09-26
                '%m/%d/%Y',  # 09/26/2025
                '%m-%d-%Y',  # 09-26-2025
                '%m-%d-%y',  # 09-26-25
            ]
            
            for fmt in test_formats:
                try:
                    datetime.strptime(date_str, fmt)
                    return date_str
                except:
                    continue
            
            # If no format worked, still return the string
            return date_str
    
    return None

def parse_issue_for_meeting_info(issue):
    """Extract meeting name and date from issue title and body"""
    title = issue.get("title", "")
    body = issue.get("body", "")
    
    # Try to find date in title first (more reliable), then body
    meeting_date = extract_date_from_text(title)
    if not meeting_date and body:
        meeting_date = extract_date_from_text(body[:500])
    
    # Extract meeting number from title if present
    meeting_number = None
    number_match = re.search(r'#(\d+)', title)
    if number_match:
        meeting_number = number_match.group(1)
    
    # Normalize title for matching (remove spaces, lowercase)
    title_normalized = title.lower().replace(" ", "")
    
    # Find ALL matching meeting IDs for this meeting name
    matched_meetings = []
    for meeting_id, meeting_info in WHITELISTED_MEETINGS.items():
        meeting_name = meeting_info["name"]
        meeting_name_normalized = meeting_name.lower().replace(" ", "")
        
        # Check if the normalized meeting name (without spaces) appears in normalized title
        # Also check the part before parentheses
        meeting_name_base = meeting_name.split("(")[0].strip() if "(" in meeting_name else meeting_name
        meeting_name_base_normalized = meeting_name_base.lower().replace(" ", "")
        
        if any([
            meeting_name.lower() in title.lower(),  # Original exact match
            meeting_name_normalized in title_normalized,  # Space-insensitive match
            meeting_name_base_normalized in title_normalized,  # Match without parenthetical part
        ]):
            matched_meetings.append({
                "meeting_id": meeting_id,
                "meeting_name": meeting_name,
                "owner": meeting_info["owner"],
                "date_str": meeting_date,
                "meeting_number": meeting_number,
                "issue_number": issue.get("number"),
                "issue_title": title,
                "closed_at": issue.get("closed_at")
            })
    
    if matched_meetings:
        return {
            "possible_meeting_ids": [m["meeting_id"] for m in matched_meetings],
            "meeting_name": matched_meetings[0]["meeting_name"],
            "meeting_number": meeting_number,
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
    
    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=days_back)
    
    all_closed_issues = []
    page = 1
    max_pages = 20  # Fetch up to 2000 issues total
    
    print(f"  Searching for issues closed after {cutoff_date.strftime('%Y-%m-%d')}")
    
    while page <= max_pages:
        params = {
            "state": "closed",
            "per_page": 100,
            "page": page,
            "sort": "updated",
            "direction": "desc"
        }
        
        print(f"  Fetching page {page}...", end=" ")
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"\n✗ GitHub API error: {response.status_code}")
            break
        
        issues = response.json()
        print(f"got {len(issues)} issues")
        
        if not issues:
            print("  No more issues found")
            break
        
        # Add all issues closed within our window
        for issue in issues:
            if issue.get("closed_at"):
                closed_date = datetime.fromisoformat(issue["closed_at"].replace("Z", "+00:00"))
                if closed_date > cutoff_date.replace(tzinfo=closed_date.tzinfo):
                    all_closed_issues.append(issue)
        
        page += 1
    
    print(f"  ✓ Found {len(all_closed_issues)} closed issues in date range")
    return all_closed_issues

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