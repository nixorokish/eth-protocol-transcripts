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
    """Generate the ACD calls table as a string"""
    # Fetch data from ethereum/pm README
    pm_data = fetch_ethereum_pm_data()
    
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
    for (mtype, num), data in pm_data.items():
        if mtype in ['ACDE', 'ACDC']:  # ACDT not in pm README
            acd_meetings.append({
                'type': mtype,
                'num': num,
                'date': data.get('date'),
                'issue_num': data.get('issue_num'),
                'has_logs': (mtype, num) in meetings_with_logs,
                'pm_data': data
            })
    
    # Add ACDT meetings from our processed meetings (not in pm README)
    for (mtype, num), data in meetings_with_logs.items():
        if mtype == 'ACDT':
            acd_meetings.append({
                'type': mtype,
                'num': data['num'],
                'date': data['date'],
                'issue_num': data['issue_num'],
                'has_logs': True,
                'pm_data': {}  # ACDT not in pm README
            })

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
        
        # Build logs link (only if we have logs)
        if m.get('has_logs') and m['date']:
            if m['num']:
                folder_name = f'Call-{int(m["num"]):03d}_{m["date"]}'
            else:
                folder_name = f'Call_{m["date"]}'
            logs_link = f'[logs](https://github.com/{repo_owner}/{repo_name}/tree/main/{mtype}/{folder_name})'
        else:
            logs_link = '-'
        
        # Get data from ethereum/pm README
        summary = '-'
        discussion = '-'
        recording = '-'
        
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
                else:
                    summary = '-'
            else:
                summary = '-'
            
            discussion = pm_data_entry.get('discussion', '-') if pm_data_entry.get('discussion') else '-'
            recording = pm_data_entry.get('recording', '-') if pm_data_entry.get('recording') else '-'
        
        table_lines.append(f'| {formatted_date} | {mtype} | {num} | {issue_link} | {summary} | {discussion} | {recording} | {logs_link} |')

    return '\n'.join(table_lines)

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
    new_table = generate_table_string()
    
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
    print(generate_table_string())

