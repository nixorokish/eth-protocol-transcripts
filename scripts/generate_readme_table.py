#!/usr/bin/env python3
"""
Generate ACD calls table for README (append-only approach).

This script only ADDS new rows for new meetings. It does not modify existing rows.
Historical data is preserved as-is in the README.
"""
import json
import os
import re
import requests
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()


def fetch_forkcast_calls():
    """Fetch and parse forkcast calls data
    
    Returns:
        dict: {
            (type, num): {
                'date': 'YYYY-MM-DD',
                'path': 'acdc/154',
                'url': 'https://forkcast.org/calls/acdc/154'
            }
        }
    """
    try:
        url = "https://raw.githubusercontent.com/ethereum/forkcast/main/src/data/calls.ts"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        content = response.text
        
        forkcast_calls = {}
        pattern = r"\{\s*type:\s*['\"](acdc|acde|acdt)['\"],\s*date:\s*['\"](\d{4}-\d{2}-\d{2})['\"],\s*number:\s*['\"](\d+)['\"],\s*path:\s*['\"]([^'\"]+)['\"]\s*\}"
        
        for match in re.finditer(pattern, content):
            call_type = match.group(1).upper()
            date = match.group(2)
            number = match.group(3)
            path = match.group(4)
            url = f'https://forkcast.org/calls/{path}'
            
            forkcast_calls[(call_type, number)] = {
                'date': date,
                'path': path,
                'url': url
            }
        
        return forkcast_calls
    except Exception as e:
        print(f"Warning: Could not fetch forkcast calls: {e}")
        return {}


def fetch_links_from_issue(issue_num):
    """Fetch YouTube and Ethereum Magicians links from a single GitHub issue
    
    Returns:
        tuple: (youtube_url or None, ethmag_url or None)
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token or not issue_num:
        return None, None
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    youtube_patterns = [
        r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)',
        r'https?://(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]+)',
    ]
    ethmag_pattern = r'https?://(?:www\.)?ethereum-magicians\.org/t/[^\s\)]+'
    
    youtube_url = None
    ethmag_url = None
    
    try:
        comments_url = f"https://api.github.com/repos/ethereum/pm/issues/{issue_num}/comments"
        response = requests.get(comments_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None, None
        
        comments = response.json()
        
        for comment in comments:
            user = comment.get('user', {})
            login = user.get('login', '')
            if login in ['github-actions', 'github-actions[bot]']:
                body = comment.get('body', '')
                
                if not youtube_url:
                    for pattern in youtube_patterns:
                        match = re.search(pattern, body, re.IGNORECASE)
                        if match:
                            video_id = match.group(1)
                            youtube_url = f"https://youtu.be/{video_id}"
                            break
                
                if not ethmag_url:
                    match = re.search(ethmag_pattern, body, re.IGNORECASE)
                    if match:
                        ethmag_url = match.group(0)
                
                if youtube_url and ethmag_url:
                    break
    except Exception:
        pass
    
    return youtube_url, ethmag_url


def parse_existing_meetings(readme_content):
    """Parse existing README to find which meetings are already in the table.
    
    Returns:
        set: Set of (type, num) tuples for existing meetings
    """
    existing = set()
    
    # Find the table after "# ACD calls"
    pattern = r'# ACD calls\s*\n\n\|[^\n]+\|\n\| ---[^\n]+\|\n((?:\|[^\n]+\|\n)*)'
    match = re.search(pattern, readme_content)
    
    if match:
        table_content = match.group(1)
        for line in table_content.split('\n'):
            if not line.strip().startswith('|'):
                continue
            parts = [p.strip() for p in line.split('|')]
            # Format: | Date | Type | № | Issue | Summary | Discussion | Recording | Logs |
            if len(parts) >= 4:
                meeting_type = parts[2].strip()
                num = parts[3].strip()
                if meeting_type in ['ACDE', 'ACDC', 'ACDT'] and num.isdigit():
                    existing.add((meeting_type, num))
    
    return existing


def generate_row(meeting_type, num, date, issue_num, forkcast_calls, repo_owner, repo_name):
    """Generate a single table row for a new meeting."""
    
    # Format date
    if date:
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d %b %Y')
        except:
            formatted_date = date
    else:
        formatted_date = '-'
    
    # Issue link
    if issue_num:
        issue_link = f'[#{issue_num}](https://github.com/ethereum/pm/issues/{issue_num})'
    else:
        issue_link = '-'
    
    # Fetch links from GitHub issue
    youtube_url, ethmag_url = fetch_links_from_issue(issue_num)
    
    # Summary (prefer forkcast)
    summary = '-'
    num_str = str(num)
    
    # Try to find forkcast link
    forkcast_key = (meeting_type, num_str)
    if forkcast_key in forkcast_calls:
        summary = f'[forkcast]({forkcast_calls[forkcast_key]["url"]})'
    else:
        # Try zero-padded version for ACDT
        if meeting_type == 'ACDT' and len(num_str) < 3:
            padded_num = num_str.zfill(3)
            forkcast_key = (meeting_type, padded_num)
            if forkcast_key in forkcast_calls:
                summary = f'[forkcast]({forkcast_calls[forkcast_key]["url"]})'
    
    # Discussion
    if ethmag_url:
        discussion = f'[EthMag]({ethmag_url})'
    else:
        discussion = '-'
    
    # Recording
    if youtube_url:
        recording = f'[video]({youtube_url})'
    else:
        recording = '-'
    
    # Logs link
    folder_name = f'Call-{int(num):03d}_{date}'
    logs_link = f'[logs](https://github.com/{repo_owner}/{repo_name}/tree/main/{meeting_type}/{folder_name})'
    
    return f'| {formatted_date} | {meeting_type} | {num} | {issue_link} | {summary} | {discussion} | {recording} | {logs_link} |'


def update_readme_table():
    """Update the README.md file by prepending new meetings only.
    
    Returns:
        bool: True if changes were made, False otherwise
    """
    readme_path = Path('README.md')
    
    if not readme_path.exists():
        print("README.md not found, skipping update")
        return False
    
    # Read current README
    with open(readme_path, 'r') as f:
        readme_content = f.read()
    
    # Parse existing meetings
    existing_meetings = parse_existing_meetings(readme_content)
    print(f"Found {len(existing_meetings)} existing meetings in README")
    
    # Load processed meetings (ones we have logs for)
    with open('processed_meetings.json', 'r') as f:
        processed = json.load(f)
    
    # Find new ACD meetings
    new_meetings = []
    for key, data in processed.items():
        meeting_type = data.get('meeting_type', '')
        if meeting_type not in ['ACDE', 'ACDT', 'ACDC']:
            continue
        
        meeting_num = data.get('meeting_num')
        if not meeting_num:
            continue
        
        if (meeting_type, str(meeting_num)) not in existing_meetings:
            new_meetings.append({
                'type': meeting_type,
                'num': str(meeting_num),
                'date': data.get('date'),
                'issue_num': key.split('_')[0]  # Extract issue number from key
            })
    
    if not new_meetings:
        print("No new meetings to add")
        return False
    
    print(f"Found {len(new_meetings)} new meetings to add")
    
    # Fetch forkcast data
    forkcast_calls = fetch_forkcast_calls()
    
    # Get repo info
    repo_owner = os.getenv('GITHUB_UPLOAD_OWNER', 'nixorokish')
    repo_name = os.getenv('GITHUB_UPLOAD_REPO', 'eth-protocol-transcripts')
    
    # Sort new meetings by date (newest first)
    def sort_key(x):
        try:
            date_obj = datetime.strptime(x['date'], '%Y-%m-%d')
            return -date_obj.timestamp()
        except:
            return 0
    
    new_meetings.sort(key=sort_key)
    
    # Generate rows for new meetings
    new_rows = []
    for m in new_meetings:
        row = generate_row(
            m['type'], m['num'], m['date'], m['issue_num'],
            forkcast_calls, repo_owner, repo_name
        )
        new_rows.append(row)
        print(f"  Adding: {m['type']} {m['num']} ({m['date']})")
    
    # Find the table header and insert new rows after it
    # Pattern: # ACD calls\n\n| Date | Type | ... |\n| --- | --- | ... |\n
    pattern = r'(# ACD calls\s*\n\n\|[^\n]+\|\n\| ---[^\n]+\|\n)'
    
    match = re.search(pattern, readme_content)
    if not match:
        print("Could not find table header in README.md")
        return False
    
    # Insert new rows after the header
    header_end = match.end()
    new_content = (
        readme_content[:header_end] +
        '\n'.join(new_rows) + '\n' +
        readme_content[header_end:]
    )
    
    # Write updated README
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"README.md updated with {len(new_rows)} new rows")
    return True


if __name__ == '__main__':
    update_readme_table()
