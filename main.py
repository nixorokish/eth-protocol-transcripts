# main.py (updated with logging and caching)
import os
import json
import requests
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path

from scripts.pmissues_monitor import get_recently_closed_issues, parse_issue_for_meeting_info
from scripts.zoom_fetcher import get_zoom_access_token, get_recordings_for_meeting_ids
from scripts.download_transcripts import download_meeting_artifacts, extract_meeting_info

load_dotenv()

def get_processed_meetings_cache():
    """Load cache of already processed meetings"""
    cache_file = Path("processed_meetings.json")
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            return json.load(f)
    return {}

def save_processed_meetings_cache(cache):
    """Save cache of processed meetings"""
    with open("processed_meetings.json", 'w') as f:
        json.dump(cache, f, indent=2)

def get_meeting_key(meeting_info):
    """Generate unique key for a meeting"""
    # Use issue number and closed date as unique identifier
    return f"{meeting_info.get('issue_number')}_{meeting_info.get('closed_at', '')[:10]}"

def check_if_exists_on_github(repo_owner, repo_name, meeting_type, meeting_num, date):
    """Check if meeting already exists in GitHub repo"""
    try:
        token = os.getenv("GITHUB_TOKEN")
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Build the expected path
        if meeting_num:
            folder_name = f"Call-{meeting_num}_{date}"
        else:
            folder_name = f"Call_{date}"
        
        path = f"{meeting_type}/{folder_name}/metadata.json"
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{path}"
        
        response = requests.get(url, headers=headers, timeout=10)
        return response.status_code == 200
    except Exception as e:
        # If check fails, assume it doesn't exist (safer to try uploading)
        print(f"    ⚠ Warning: Could not check if exists on GitHub: {e}")
        return False

# main.py (complete updated function)
def process_recent_meetings(days_back=7, dry_run=False, force_reprocess=False):
    """Main orchestration function with caching and logging"""
    
    # Set up logging
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"process_log_{timestamp}.txt"
    failed_matches_file = log_dir / f"failed_matches_{timestamp}.json"
    
    failed_matches = []
    processed_cache = get_processed_meetings_cache() if not force_reprocess else {}
    
    def log(message, also_print=True):
        """Log to file and optionally print"""
        with open(log_file, 'a') as f:
            f.write(f"{datetime.now().isoformat()} - {message}\n")
        if also_print:
            print(message)
    
    log(f"=== Processing meetings from last {days_back} days ===")
    
    # Get Zoom token
    zoom_token = get_zoom_access_token()
    if not zoom_token:
        log("✗ Failed to get Zoom access token")
        return
    
    # Get GitHub repo settings
    repo_owner = os.getenv("GITHUB_UPLOAD_OWNER")
    repo_name = os.getenv("GITHUB_UPLOAD_REPO")
    
    if not repo_owner or not repo_name:
        log("✗ Please set GITHUB_UPLOAD_OWNER and GITHUB_UPLOAD_REPO in .env")
        return
    
    # Step 1: Get recently closed issues
    log("Step 1: Fetching closed GitHub issues...")
    closed_issues = get_recently_closed_issues(days_back=days_back)
    
    matched_meetings = []
    unmatched_issues = []
    
    for issue in closed_issues:
        meeting_info = parse_issue_for_meeting_info(issue)
        if meeting_info:
            matched_meetings.append(meeting_info)
        else:
            # Log unmatched issues that might be meetings
            title = issue.get('title', '')
            potential_meeting_keywords = ['call', 'meeting', 'breakout', 'devs', 'interop', 'eip']
            if any(keyword in title.lower() for keyword in potential_meeting_keywords):
                unmatched_issues.append({
                    'issue_number': issue.get('number'),
                    'title': title,
                    'body_preview': issue.get('body', '')[:200] if issue.get('body') else '',
                    'closed_at': issue.get('closed_at')
                })
    
    log(f"  ✓ Found {len(matched_meetings)} matched meetings")
    log(f"  ⚠ Found {len(unmatched_issues)} potential meetings that didn't match", also_print=False)
    
    # Save unmatched issues for debugging
    if unmatched_issues:
        with open(failed_matches_file, 'w') as f:
            json.dump(unmatched_issues, f, indent=2)
        log(f"  Saved {len(unmatched_issues)} unmatched issues to {failed_matches_file}")
    
    if dry_run:
        log("DRY RUN - Would process these meetings:")
        for meeting in matched_meetings:
            log(f"  - {meeting['issue_title']}")
        return
    
    # Step 2: Process each meeting and collect folders for batch upload
    processed_folders = []  # Collect all downloaded folders
    processed_count = 0
    skipped_cached = 0
    skipped_no_recording = 0
    skipped_short = 0
    
    for i, meeting in enumerate(matched_meetings, 1):
        meeting_key = get_meeting_key(meeting)
        
        log(f"\n{'='*60}")
        log(f"[{i}/{len(matched_meetings)}] Processing: {meeting['issue_title']}")
        
        # Check cache
        if meeting_key in processed_cache and not force_reprocess:
            log(f"  ⏭ Already processed (cached)")
            skipped_cached += 1
            continue
        
        if not meeting['date_str']:
            log("  ⚠ Skipping - no date found")
            failed_matches.append({
                'issue': meeting['issue_title'],
                'reason': 'No date found in issue',
                'issue_number': meeting['issue_number']
            })
            continue
        
        # Step 3: Find Zoom recording
        log(f"  Meeting IDs: {', '.join(meeting['possible_meeting_ids'])}")
        log(f"  Date: {meeting['date_str']}")
        
        recording = get_recordings_for_meeting_ids(
            zoom_token, 
            meeting['possible_meeting_ids'], 
            meeting['date_str']
        )
        
        if not recording:
            log("  ⚠ No recording found")
            skipped_no_recording += 1
            failed_matches.append({
                'issue': meeting['issue_title'],
                'reason': 'No Zoom recording found',
                'meeting_ids': meeting['possible_meeting_ids'],
                'date': meeting['date_str']
            })
            continue
        
        if recording.get('duration', 0) < 10:
            log(f"  ⚠ Skipping short recording ({recording.get('duration')} min)")
            skipped_short += 1
            continue
        
        # Extract meeting info for GitHub check
        meeting_type, meeting_num = extract_meeting_info(recording.get('topic', ''))
        meeting_date = recording.get('start_time', '').split('T')[0]
        
        # Check if already exists on GitHub
        if check_if_exists_on_github(repo_owner, repo_name, meeting_type, meeting_num, meeting_date):
            log(f"  ⏭ Already exists on GitHub")
            # Add to cache so we don't check again
            processed_cache[meeting_key] = {
                'processed_at': datetime.now().isoformat(),
                'meeting_type': meeting_type,
                'meeting_num': meeting_num,
                'date': meeting_date
            }
            skipped_cached += 1
            continue
        
        # Step 4: Download artifacts (but don't upload yet)
        log(f"  Recording found: {recording.get('duration')} minutes")
        try:
            # Pass the meeting number from the GitHub issue if available
            folder_path = download_meeting_artifacts(
                recording, 
                zoom_token,
                override_meeting_num=meeting.get('meeting_number')  # Add this parameter
            )
            processed_folders.append(folder_path)
            processed_count += 1
            
            # Add to cache (mark as downloaded, not uploaded yet)
            processed_cache[meeting_key] = {
                'processed_at': datetime.now().isoformat(),
                'meeting_type': meeting_type,
                'meeting_num': meeting_num,
                'date': meeting_date,
                'status': 'downloaded'
            }
        except Exception as e:
            log(f"  ✗ Failed to download: {e}")
            failed_matches.append({
                'issue': meeting['issue_title'],
                'reason': f'Download failed: {e}',
                'meeting_ids': meeting['possible_meeting_ids']
            })
            continue
    
    # Step 5: Batch upload all downloaded folders in a single commit
    if processed_folders:
        log(f"\n{'='*60}")
        log(f"Uploading {len(processed_folders)} meeting folders to GitHub in single commit...")
        
        from scripts.github_uploader import batch_upload_to_github
        
        try:
            uploaded = batch_upload_to_github(processed_folders, repo_owner, repo_name, log_func=log)
            
            if uploaded:
                log(f"✓ Successfully uploaded {len(uploaded)} files in single commit")
                
                # Check if any ACD calls were uploaded in this batch
                uploaded_acd = False
                for key, value in processed_cache.items():
                    if value.get('status') == 'downloaded' and value.get('meeting_type') in ['ACDE', 'ACDT', 'ACDC']:
                        uploaded_acd = True
                        break
                
                # Update cache to mark as uploaded
                for key, value in processed_cache.items():
                    if value.get('status') == 'downloaded':
                        value['status'] = 'uploaded'
                        value['uploaded_at'] = datetime.now().isoformat()
                
                # Update README table if any ACD calls were uploaded
                if uploaded_acd:
                    try:
                        from scripts.generate_readme_table import update_readme_table
                        from scripts.github_uploader import upload_readme_to_github
                        
                        if update_readme_table():
                            log(f"✓ Updated README table with new ACD calls")
                            # Upload README to GitHub
                            if upload_readme_to_github(repo_owner, repo_name, log_func=log):
                                log(f"✓ Uploaded README.md to GitHub")
                            else:
                                log(f"⚠ Could not upload README.md to GitHub (check manually)")
                        else:
                            log(f"⚠ Could not update README table (check manually)")
                    except Exception as e:
                        log(f"⚠ Failed to update README table: {e}")
            else:
                log(f"✗ Failed to batch upload - batch_upload_to_github returned empty list")
                log(f"  This could indicate an API error, authentication issue, or network problem")
                log(f"  Check the console output above for detailed error messages")
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            log(f"✗ Upload error: {e}")
            log(f"  Full traceback:\n{error_details}")

    else:
        log("\nNo new meetings to upload")
    
    # Save updated cache
    save_processed_meetings_cache(processed_cache)
    
    # Save failed matches for debugging
    if failed_matches:
        with open(log_dir / f"failed_processing_{timestamp}.json", 'w') as f:
            json.dump(failed_matches, f, indent=2)
    
    # Final summary
    log(f"\n{'='*60}")
    log("=== SUMMARY ===")
    log(f"✓ Successfully processed: {processed_count}")
    log(f"⏭ Skipped (cached/exists): {skipped_cached}")
    log(f"⚠ No recording found: {skipped_no_recording}")
    log(f"⚠ Skipped short recordings: {skipped_short}")
    log(f"\nLog saved to: {log_file}")
    
    if unmatched_issues:
        log(f"Unmatched issues saved to: {failed_matches_file}")
    if failed_matches:
        log(f"Failed processing saved to: {log_dir / f'failed_processing_{timestamp}.json'}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--dry-run":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            process_recent_meetings(days_back=days, dry_run=True)
        elif sys.argv[1] == "--force":
            # Force reprocess, ignoring cache
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            process_recent_meetings(days_back=days, force_reprocess=True)
        elif sys.argv[1] == "--test":
            # Test mode: fetch and download a single meeting
            from zoom_fetcher import get_zoom_access_token, get_recordings_for_meeting_ids
            from download_transcripts import download_meeting_artifacts
            
            token = get_zoom_access_token()
            if not token:
                print("✗ Failed to get Zoom access token")
                sys.exit(1)
            
            test_meeting_ids = ["884 7930 8162"]
            test_date = "Oct 6, 2025"
            
            print(f"Testing: Fetching recording for {test_meeting_ids} on {test_date}")
            recording = get_recordings_for_meeting_ids(token, test_meeting_ids, test_date)
            
            if recording:
                print(f"✓ Found recording: {recording.get('topic')}")
                folder_path = download_meeting_artifacts(recording, token)
                print(f"✓ Downloaded to: {folder_path}")
            else:
                print("✗ No recording found")
        else:
            days = int(sys.argv[1])
            process_recent_meetings(days_back=days)
    else:
        process_recent_meetings(days_back=7)