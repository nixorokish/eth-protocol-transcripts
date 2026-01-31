# pmissues_monitor.py (updated date extraction)
import requests
import os
import re
from dotenv import load_dotenv
from datetime import datetime, timedelta
from .meetings_config import WHITELISTED_MEETINGS

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

def parse_meeting_datetime(date_str):
    """Parse date string to datetime. Assumes meetings are ~14:00 UTC if no time given."""
    if not date_str:
        return None
    
    formats = [
        '%B %d, %Y', '%B %d %Y', '%b %d, %Y', '%b %d %Y',
        '%d %B %Y', '%d %b %Y', '%Y-%m-%d', '%m/%d/%Y',
        '%m-%d-%Y', '%m-%d-%y'
    ]
    
    # Clean up the date string
    date_str_clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
    date_str_clean = re.sub(r'\s+', ' ', date_str_clean).strip()
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str_clean, fmt)
            # Assume 14:00 UTC meeting time if not specified
            return dt.replace(hour=14, minute=0)
        except:
            continue
    return None


def get_recently_closed_issues(days_back=7):
    """Legacy function - fetches only closed issues. Use get_meetings_ready_to_process() instead."""
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


def get_meetings_ready_to_process(days_back=7, buffer_hours=2):
    """Get meetings where the scheduled time has passed.
    
    Instead of requiring issues to be closed, this checks if the meeting's
    scheduled date/time + buffer has passed. This allows processing meetings
    even if someone forgets to close the issue.
    
    Args:
        days_back: How far back to look for meetings
        buffer_hours: Hours after meeting time before we try to process
    
    Returns:
        List of issues that are ready to process
    """
    token = os.getenv("GITHUB_TOKEN")
    url = "https://api.github.com/repos/ethereum/pm/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    now = datetime.now()
    cutoff_date = now - timedelta(days=days_back)
    ready_threshold = now - timedelta(hours=buffer_hours)
    
    print(f"  Looking for meetings from {cutoff_date.strftime('%Y-%m-%d')} to {ready_threshold.strftime('%Y-%m-%d %H:%M')}")
    
    all_issues = []
    
    # Fetch both open and closed issues
    for state in ["open", "closed"]:
        page = 1
        max_pages = 10
        while page <= max_pages:
            params = {
                "state": state,
                "per_page": 100,
                "page": page,
                "sort": "created",
                "direction": "desc"
            }
            
            print(f"  Fetching {state} issues page {page}...", end=" ")
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code != 200:
                print(f"\n✗ GitHub API error: {response.status_code}")
                break
            
            issues = response.json()
            print(f"got {len(issues)} issues")
            
            if not issues:
                break
            
            all_issues.extend(issues)
            
            # Stop if we're getting issues older than our cutoff
            # (they're sorted by created desc)
            oldest_in_batch = issues[-1]
            created_at = oldest_in_batch.get("created_at", "")
            if created_at:
                try:
                    created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    if created_date.replace(tzinfo=None) < cutoff_date:
                        print(f"  Reached issues older than cutoff, stopping {state} fetch")
                        break
                except:
                    pass
            
            page += 1
    
    print(f"  Fetched {len(all_issues)} total issues, filtering by meeting date...")
    
    # Filter to meetings where time has passed
    ready_issues = []
    skipped_no_date = 0
    skipped_future = 0
    skipped_too_old = 0
    
    for issue in all_issues:
        # First check if this matches a whitelisted meeting
        meeting_info = parse_issue_for_meeting_info(issue)
        if not meeting_info:
            continue
        
        date_str = meeting_info.get('date_str')
        if not date_str:
            skipped_no_date += 1
            continue
        
        # Parse the meeting date
        meeting_date = parse_meeting_datetime(date_str)
        if not meeting_date:
            skipped_no_date += 1
            continue
        
        # Check if meeting is too old
        if meeting_date < cutoff_date:
            skipped_too_old += 1
            continue
        
        # Check if meeting time + buffer has passed
        if meeting_date > ready_threshold:
            skipped_future += 1
            continue
        
        ready_issues.append(issue)
    
    print(f"  ✓ Found {len(ready_issues)} meetings ready to process")
    print(f"    (skipped: {skipped_no_date} no date, {skipped_future} future, {skipped_too_old} too old)")
    
    return ready_issues

# Test it
if __name__ == "__main__":
    print("=== Testing new time-based function ===\n")
    ready_issues = get_meetings_ready_to_process(days_back=30, buffer_hours=2)
    print(f"\nFound {len(ready_issues)} meetings ready to process\n")

    for issue in ready_issues:
        meeting_info = parse_issue_for_meeting_info(issue)
        if meeting_info:
            print(f"✓ Ready: {meeting_info['issue_title']}")
            print(f"  Meeting IDs: {', '.join(meeting_info['possible_meeting_ids'])}")
            print(f"  Date: {meeting_info['date_str'] or 'No date found'}")
            print(f"  Issue state: {issue.get('state')}\n")

    print("\n=== Comparing with old closed-issues function ===\n")
    closed_issues = get_recently_closed_issues(days_back=30)
    print(f"Old method found {len(closed_issues)} closed issues")