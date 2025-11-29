#!/usr/bin/env python3
"""Generate ACD calls table for README"""
import json
import os
import re
import requests
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

def parse_date_from_pm_format(date_str):
    """Parse date from ethereum/pm format like '03 Jul 2025, 14:00 UTC' or '03 Jul 2025'"""
    # Remove time and timezone if present
    date_str = date_str.split(',')[0].strip()
    try:
        # Try format: "03 Jul 2025"
        date_obj = datetime.strptime(date_str, '%d %b %Y')
        return date_obj.strftime('%Y-%m-%d')
    except:
        try:
            # Try format: "03 Jul 2025"
            date_obj = datetime.strptime(date_str, '%d %B %Y')
            return date_obj.strftime('%Y-%m-%d')
        except:
            return None

def extract_issue_number_from_agenda(agenda_text):
    """Extract issue number from agenda link like [agenda](https://github.com/ethereum/pm/issues/1601)"""
    match = re.search(r'issues/(\d+)', agenda_text)
    if match:
        return match.group(1)
    return None

def fetch_links_from_issues(issue_numbers):
    """Fetch YouTube and Ethereum Magicians links from GitHub issue comments posted by github-actions user
    
    Args:
        issue_numbers: List of issue numbers to check
    
    Returns:
        tuple: (youtube_links_dict, discussion_links_dict)
            - youtube_links_dict: {issue_num: youtube_url} mapping
            - discussion_links_dict: {issue_num: ethmag_url} mapping
    """
    youtube_links = {}
    discussion_links = {}
    
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Warning: GITHUB_TOKEN not set, cannot fetch links from issues")
        return youtube_links, discussion_links
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # YouTube URL patterns (case-insensitive)
    youtube_patterns = [
        r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)',
        r'https?://(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]+)',
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',  # Also match without https://
    ]
    
    # Ethereum Magicians URL pattern
    ethmag_pattern = r'https?://(?:www\.)?ethereum-magicians\.org/t/[^\s\)]+'
    
    for issue_num in issue_numbers:
        if not issue_num:
            continue
        
        # Fetch comments for this issue
        comments_url = f"https://api.github.com/repos/ethereum/pm/issues/{issue_num}/comments"
        
        try:
            response = requests.get(comments_url, headers=headers, timeout=10)
            if response.status_code != 200:
                continue
            
            comments = response.json()
            
            # Look for comments by github-actions[bot] user
            for comment in comments:
                user = comment.get('user', {})
                login = user.get('login', '')
                # Check for both 'github-actions' and 'github-actions[bot]'
                if login in ['github-actions', 'github-actions[bot]']:
                    body = comment.get('body', '')
                    
                    # Search for YouTube links
                    if issue_num not in youtube_links:
                        for pattern in youtube_patterns:
                            match = re.search(pattern, body, re.IGNORECASE)
                            if match:
                                video_id = match.group(1)
                                youtube_url = f"https://youtu.be/{video_id}"
                                youtube_links[issue_num] = youtube_url
                                break
                    
                    # Search for Ethereum Magicians discussion links
                    if issue_num not in discussion_links:
                        match = re.search(ethmag_pattern, body, re.IGNORECASE)
                        if match:
                            ethmag_url = match.group(0)
                            discussion_links[issue_num] = ethmag_url
                    
                    # If we found both, no need to check more comments
                    if issue_num in youtube_links and issue_num in discussion_links:
                        break
        except Exception as e:
            # Silently continue if we can't fetch comments for this issue
            continue
    
    return youtube_links, discussion_links

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
        # Fetch calls.ts from forkcast
        url = "https://raw.githubusercontent.com/ethereum/forkcast/main/src/data/calls.ts"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        content = response.text
        
        # Dictionary to store call data: (type, num) -> {date, path, url}
        forkcast_calls = {}
        
        # Parse the calls array
        # Pattern: { type: 'acdc', date: '2025-04-03', number: '154', path: 'acdc/154' },
        pattern = r"\{\s*type:\s*['\"](acdc|acde|acdt)['\"],\s*date:\s*['\"](\d{4}-\d{2}-\d{2})['\"],\s*number:\s*['\"](\d+)['\"],\s*path:\s*['\"]([^'\"]+)['\"]\s*\}"
        
        for match in re.finditer(pattern, content):
            call_type = match.group(1).upper()  # Convert to ACDC, ACDE, ACDT
            date = match.group(2)
            number = match.group(3)
            path = match.group(4)
            
            # Build full URL
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

def fetch_ethereum_pm_data():
    """Fetch and parse ethereum/pm README to extract meeting data
    
    Returns:
        dict: {
            (type, num): {
                'date': 'YYYY-MM-DD',
                'issue_num': '123',
                'notes': '...',
                'discussion': '...',
                'recording': '...'
            }
        }
    """
    try:
        # Fetch README from ethereum/pm (try master branch first, then main)
        for branch in ['master', 'main']:
            url = f"https://raw.githubusercontent.com/ethereum/pm/{branch}/README.md"
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                break
            except requests.exceptions.HTTPError:
                continue
        else:
            raise Exception("Could not fetch README from master or main branch")
        response.raise_for_status()
        content = response.text
        
        # Dictionary to store meeting data: (type, num) -> {date, issue_num, notes, discussion, recording}
        meeting_data = {}
        
        # Parse Execution Layer table (ACDE)
        el_pattern = r'<summary>\s*Execution Layer\s*</summary>.*?\| № \| Date \| Agenda \| Notes \| Discussion \| Recording \|\s*\n\|[^|]+\|(.*?)(?=\n</details>|\n<details>)'
        el_match = re.search(el_pattern, content, re.DOTALL)
        if el_match:
            table_content = el_match.group(1)
            for line in table_content.split('\n'):
                if not line.strip().startswith('|'):
                    continue
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 7:  # | № | Date | Agenda | Notes | Discussion | Recording |
                    try:
                        num = parts[1].strip()
                        if num.isdigit():
                            date_str = parts[2].strip()
                            agenda = parts[3].strip()
                            notes = parts[4].strip()
                            discussion = parts[5].strip()
                            recording = parts[6].strip()
                            
                            # Parse date
                            parsed_date = parse_date_from_pm_format(date_str)
                            
                            # Extract issue number from agenda link
                            issue_num = extract_issue_number_from_agenda(agenda)
                            
                            meeting_data[('ACDE', num)] = {
                                'date': parsed_date,
                                'issue_num': issue_num,
                                'notes': notes if notes and notes != '-' else '',
                                'discussion': discussion if discussion and discussion != '-' else '',
                                'recording': recording if recording and recording != '-' else ''
                            }
                    except (IndexError, ValueError) as e:
                        continue
        
        # Parse Consensus Layer table (ACDC)
        cl_pattern = r'<summary>\s*Consensus Layer\s*</summary>.*?\| № \| Date \| Agenda \| Notes \| Discussion \| Recording \|\s*\n\|[^|]+\|(.*?)(?=\n</details>|\n<details>)'
        cl_match = re.search(cl_pattern, content, re.DOTALL)
        if cl_match:
            table_content = cl_match.group(1)
            for line in table_content.split('\n'):
                if not line.strip().startswith('|'):
                    continue
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 7:
                    try:
                        num = parts[1].strip()
                        if num.isdigit():
                            date_str = parts[2].strip()
                            agenda = parts[3].strip()
                            notes = parts[4].strip()
                            discussion = parts[5].strip()
                            recording = parts[6].strip()
                            
                            # Parse date
                            parsed_date = parse_date_from_pm_format(date_str)
                            
                            # Extract issue number from agenda link
                            issue_num = extract_issue_number_from_agenda(agenda)
                            
                            meeting_data[('ACDC', num)] = {
                                'date': parsed_date,
                                'issue_num': issue_num,
                                'notes': notes if notes and notes != '-' else '',
                                'discussion': discussion if discussion and discussion != '-' else '',
                                'recording': recording if recording and recording != '-' else ''
                            }
                    except (IndexError, ValueError):
                        continue
        
        return meeting_data
    except Exception as e:
        print(f"Warning: Could not fetch ethereum/pm data: {e}")
        return {}

def generate_table_string():
    """Generate the ACD calls table as a string
    
    Returns:
        tuple: (table_string, flagged_calls_list)
            - table_string: The markdown table
            - flagged_calls_list: List of calls that have both notes and forkcast
    """
    # Fetch data from ethereum/pm README
    pm_data = fetch_ethereum_pm_data()
    
    # Fetch forkcast calls data
    forkcast_calls = fetch_forkcast_calls()
    
    # Track calls with both summary and forkcast
    flagged_calls = []
    
    # Load processed meetings (ones we have logs for)
    with open('processed_meetings.json', 'r') as f:
        meetings = json.load(f)

    # Track which meetings we have logs for
    meetings_with_logs = {}
    for key, data in meetings.items():
        meeting_type = data.get('meeting_type', '')
        if meeting_type in ['ACDE', 'ACDT', 'ACDC']:
            meeting_num = data.get('meeting_num')
            if meeting_num:
                meetings_with_logs[(meeting_type, str(meeting_num))] = {
                    'type': meeting_type,
                    'num': meeting_num,
                    'date': data.get('date'),
                    'issue_num': key.split('_')[0]  # Extract issue number from key
                }

    # Build combined list of all meetings
    acd_meetings = []
    
    # Add meetings from ethereum/pm README (includes ones we don't have logs for)
    pm_meeting_keys = set()
    for (mtype, num), data in pm_data.items():
        if mtype in ['ACDE', 'ACDC']:  # ACDT not in pm README
            # Skip ACDE 0 - it's duplicate data from ACDE 1
            if mtype == 'ACDE' and num == '0':
                continue
            
            pm_meeting_keys.add((mtype, num))
            
            # Fix ACDC 80 date to January 27, 2022
            date = data.get('date')
            if mtype == 'ACDC' and num == '80' and not date:
                date = '2022-01-27'
            
            acd_meetings.append({
                'type': mtype,
                'num': num,
                'date': date,
                'issue_num': data.get('issue_num'),
                'has_logs': (mtype, num) in meetings_with_logs,
                'pm_data': data
            })
    
    # Add ACDE/ACDC/ACDT meetings from our processed meetings that aren't in pm README
    for (mtype, num), data in meetings_with_logs.items():
        # Skip if already added from pm_data
        if (mtype, num) not in pm_meeting_keys:
            acd_meetings.append({
                'type': mtype,
                'num': data['num'],
                'date': data['date'],
                'issue_num': data['issue_num'],
                'has_logs': True,
                'pm_data': {}  # Not in pm README yet
            })
    
    # Collect all issue numbers to fetch YouTube and discussion links for
    issue_numbers = set()
    for (mtype, num), data in pm_data.items():
        issue_num = data.get('issue_num')
        if issue_num:
            issue_numbers.add(issue_num)
    
    # Also collect from meetings_with_logs
    for (mtype, num), data in meetings_with_logs.items():
        issue_num = data.get('issue_num')
        if issue_num:
            issue_numbers.add(issue_num)
    
    # Fetch YouTube and discussion links from issue comments (only for issues from July 2025 onwards)
    # We'll filter by date when using the links
    youtube_links, discussion_links = fetch_links_from_issues(list(issue_numbers))

    # Sort by date (newest first), then by type, then by number
    def sort_key(x):
        # Parse date for sorting (YYYY-MM-DD format)
        date_str = x.get('date', '0000-00-00')
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            date_sort = date_obj.timestamp()
        except:
            date_sort = 0
        
        type_order = {'ACDE': 0, 'ACDT': 1, 'ACDC': 2}
        num = int(x['num']) if x['num'] else 0
        # Negative date_sort for descending (newest first)
        return (-date_sort, type_order.get(x['type'], 99), -num)

    acd_meetings.sort(key=sort_key)

    # Get repo info
    repo_owner = os.getenv('GITHUB_UPLOAD_OWNER', 'ethereum')
    repo_name = os.getenv('GITHUB_UPLOAD_REPO', 'pm')

    # Generate table
    table_lines = []
    table_lines.append('| Date | Type | № | Issue | Summary | Discussion | Recording | Logs |')
    table_lines.append('| --- | --- | --- | --- | --- | --- | --- | --- |')

    for m in acd_meetings:
        num = m['num'] or '-'
        mtype = m['type']
        date_str = m['date']
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                # Format: "03 Jul 2025" (no time since we don't have it)
                formatted_date = date_obj.strftime('%d %b %Y')
            except:
                formatted_date = date_str
        else:
            formatted_date = '-'
        
        # Build issue link
        issue_num = m.get('issue_num')
        if issue_num:
            issue_link = f'[#{issue_num}](https://github.com/ethereum/pm/issues/{issue_num})'
        else:
            issue_link = '-'
        
        # Get data from ethereum/pm README
        summary = '-'
        discussion = '-'
        recording = '-'
        has_existing_summary = False
        has_forkcast = False
        
        pm_data_entry = m.get('pm_data', {})
        if pm_data_entry:
            # Use notes as summary if it's a GitHub link
            if pm_data_entry.get('notes'):
                notes_text = pm_data_entry['notes']
                # Convert relative path to full GitHub URL
                if '[notes](' in notes_text:
                    # Extract the path from [notes](path)
                    path_match = re.search(r'\[notes\]\(([^)]+)\)', notes_text)
                    if path_match:
                        rel_path = path_match.group(1)
                        # If it's not already a full URL, convert it
                        if 'github.com' not in rel_path:
                            full_url = f'https://github.com/ethereum/pm/blob/master/{rel_path}'
                            notes_text = f'[notes]({full_url})'
                        else:
                            # Already a full URL, keep as is
                            notes_text = f'[notes]({rel_path})'
                
                # Only use as summary if it's a GitHub link (after conversion)
                if 'github.com' in notes_text:
                    summary = notes_text
                    has_existing_summary = True
                else:
                    summary = '-'
            else:
                summary = '-'
            
            discussion = pm_data_entry.get('discussion', '-') if pm_data_entry.get('discussion') else '-'
            recording = pm_data_entry.get('recording', '-') if pm_data_entry.get('recording') else '-'
        
        # If discussion is still empty and we have an issue number, check for Ethereum Magicians link from comments
        # Only for calls from July 2025 onwards (approximately issue #1600+)
        if discussion == '-' and issue_num:
            try:
                issue_num_int = int(issue_num)
                # Check if this issue is from July 2025 onwards (roughly issue #1600+)
                # Also check if we have a discussion link for this issue
                if issue_num_int >= 1600 and issue_num in discussion_links:
                    ethmag_url = discussion_links[issue_num]
                    discussion = f'[EthMag]({ethmag_url})'
            except (ValueError, TypeError):
                pass
        
        # If recording is still empty and we have an issue number, check for YouTube link from comments
        # Only for calls from July 2025 onwards (approximately issue #1600+)
        if recording == '-' and issue_num:
            try:
                issue_num_int = int(issue_num)
                # Check if this issue is from July 2025 onwards (roughly issue #1600+)
                # Also check if we have a YouTube link for this issue
                if issue_num_int >= 1600 and issue_num in youtube_links:
                    youtube_url = youtube_links[issue_num]
                    recording = f'[video]({youtube_url})'
            except (ValueError, TypeError):
                pass
        
        # Check for forkcast call page
        # Handle zero-padding: forkcast uses '040', '048' for ACDT but our data uses '40', '48'
        forkcast_key = None
        forkcast_url = None
        
        if m['num']:
            num_str = str(m['num'])
            # Try exact match first
            forkcast_key = (mtype, num_str)
            if forkcast_key in forkcast_calls:
                forkcast_url = forkcast_calls[forkcast_key]['url']
            else:
                # Try zero-padded version (for ACDT: '48' -> '048')
                if mtype == 'ACDT' and len(num_str) < 3:
                    padded_num = num_str.zfill(3)
                    forkcast_key = (mtype, padded_num)
                    if forkcast_key in forkcast_calls:
                        forkcast_url = forkcast_calls[forkcast_key]['url']
                # Also try without zero-padding (for other types that might have padding)
                elif len(num_str) == 3 and num_str.startswith('0'):
                    unpadded_num = str(int(num_str))  # Remove leading zeros
                    forkcast_key = (mtype, unpadded_num)
                    if forkcast_key in forkcast_calls:
                        forkcast_url = forkcast_calls[forkcast_key]['url']
        
        if forkcast_url:
            has_forkcast = True
            
            # If there's already a summary, flag it but don't change
            if has_existing_summary:
                # Flag: both exist (we'll track this but not change the summary)
                flagged_calls.append({
                    'type': mtype,
                    'num': m['num'],
                    'date': formatted_date,
                    'summary': summary,
                    'forkcast': forkcast_url
                })
            else:
                # Add forkcast link to summary
                summary = f'[forkcast]({forkcast_url})'
        
        # Build logs link (after summary is determined)
        logs_link = '-'
        
        # Check if we have our own logs
        if m.get('has_logs') and m['date']:
            if m['num']:
                folder_name = f'Call-{int(m["num"]):03d}_{m["date"]}'
            else:
                folder_name = f'Call_{m["date"]}'
            logs_link = f'[logs](https://github.com/{repo_owner}/{repo_name}/tree/main/{mtype}/{folder_name})'
        # Check if summary has a notes link to AllCoreDevs-EL-Meetings or AllCoreDevs-CL-Meetings
        # (those contain both notes and transcripts, so duplicate the link to logs)
        elif summary != '-' and ('AllCoreDevs-EL-Meetings' in summary or 'AllCoreDevs-CL-Meetings' in summary):
            # Extract the link from summary and use it for logs (but label it as "logs")
            link_match = re.search(r'\[notes\]\(([^)]+)\)', summary)
            if link_match:
                notes_url = link_match.group(1)
                logs_link = f'[logs]({notes_url})'
        
        table_lines.append(f'| {formatted_date} | {mtype} | {num} | {issue_link} | {summary} | {discussion} | {recording} | {logs_link} |')
    
    return '\n'.join(table_lines), flagged_calls

def update_readme_table():
    """Update the README.md file with the latest table"""
    readme_path = Path('README.md')
    
    if not readme_path.exists():
        print("README.md not found, skipping update")
        return False
    
    # Read current README
    with open(readme_path, 'r') as f:
        readme_content = f.read()
    
    # Generate new table
    new_table, flagged_calls = generate_table_string()
    
    # Report flagged calls (both summary and forkcast exist)
    if flagged_calls:
        print(f"\n⚠ Found {len(flagged_calls)} calls with both notes and forkcast (not changed):")
        for call in flagged_calls:
            print(f"  {call['type']} {call['num']} ({call['date']}): has notes summary AND forkcast page")
    
    # Find the table section (between <details> tags)
    # Pattern: <details>...<summary>ACD calls</summary>\n\nTABLE_CONTENT\n\n</details>
    pattern = r'(<details>\s*<summary>ACD calls</summary>\s*\n\n)(.*?)(\n\n</details>)'
    
    replacement = r'\1' + new_table + r'\3'
    
    if re.search(pattern, readme_content, re.DOTALL):
        updated_content = re.sub(pattern, replacement, readme_content, flags=re.DOTALL)
        
        # Write updated README
        with open(readme_path, 'w') as f:
            f.write(updated_content)
        
        return True
    else:
        print("Could not find table section in README.md")
        return False

if __name__ == '__main__':
    # If run as script, print table (for manual use)
    table, flagged = generate_table_string()
    print(table)
    if flagged:
        print(f"\n⚠ Found {len(flagged)} calls with both notes and forkcast")

