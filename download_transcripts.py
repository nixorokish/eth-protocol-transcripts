# download_transcripts.py (updated)
import requests
import os
import json
import re
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path

load_dotenv()

def download_file(url, access_token, filepath):
    """Download a file from Zoom"""
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    response = requests.get(url, headers=headers, stream=True)
    
    if response.status_code == 200:
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    else:
        print(f"    ✗ Failed to download: {response.status_code}")
        return False

def extract_meeting_info(topic):
    """Extract meeting type and number from topic"""
    # Try to extract meeting number (e.g., #56, #166, etc.)
    meeting_num_match = re.search(r'#(\d+)', topic)
    meeting_num = meeting_num_match.group(1) if meeting_num_match else None
    
    # Determine meeting type from topic
    meeting_type = "Unknown"
    
    # Map common patterns to clean folder names
    type_mappings = {
        "All Core Devs - Testing (ACDT)": "ACDT",
        "All Core Devs - Consensus (ACDC)": "ACDC", 
        "All Core Devs - Execution (ACDE)": "ACDE",
        "RPC Standards": "RPC-Standards",
        "PQ Interop": "PQ-Interop",
        "L2 Interop": "L2-Interop",
        "EIP Editing Office Hour": "EIP-Editing-Office-Hour",
        "EIP-7928": "EIP-7928",
        "FOCIL": "FOCIL",
        "Trustless Agents": "Trustless-Agents",
        "ePBS": "ePBS",
        "EVM Resource Pricing": "EVM-Resource-Pricing",
        "Portal": "Portal",
        "All Wallet Devs": "All-Wallet-Devs",
        "Roll Call": "Roll-Call",
        "ETH simulate": "ETH-simulate"
    }
    
    for pattern, folder_name in type_mappings.items():
        if pattern.lower() in topic.lower():
            meeting_type = folder_name
            break
    
    return meeting_type, meeting_num

def download_meeting_artifacts(recording, access_token, output_dir="downloads"):
    """Download transcript and chat for a recording"""
    
    # Extract meeting info
    topic = recording.get('topic', 'Unknown Meeting')
    meeting_type, meeting_num = extract_meeting_info(topic)
    
    # Get date
    meeting_date = recording.get('start_time', '').split('T')[0]
    
    # Create folder structure: meeting_type/Call-#_YYYY-MM-DD
    if meeting_num:
        folder_name = f"Call-{meeting_num}_{meeting_date}"
    else:
        folder_name = f"Call_{meeting_date}"
    
    folder_path = Path(output_dir) / meeting_type / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n  Downloading to: {folder_path}")
    
    downloaded_files = []
    
    if 'recording_files' in recording:
        for file in recording['recording_files']:
            file_type = file.get('file_type', '')
            
            if file_type == 'TRANSCRIPT':
                filename = f"transcript.vtt"
                filepath = folder_path / filename
                
                print(f"    Downloading transcript...")
                if download_file(file['download_url'], access_token, filepath):
                    print(f"      ✓ Saved: {filename}")
                    downloaded_files.append(str(filepath))
                    
            elif file_type == 'CHAT':
                filename = f"chat.txt"
                filepath = folder_path / filename
                
                print(f"    Downloading chat log...")
                if download_file(file['download_url'], access_token, filepath):
                    print(f"      ✓ Saved: {filename}")
                    downloaded_files.append(str(filepath))
    
    # Save meeting metadata
    metadata = {
        "meeting_id": recording.get('matched_meeting_id', recording.get('id')),
        "topic": topic,
        "meeting_type": meeting_type,
        "meeting_number": meeting_num,
        "start_time": recording.get('start_time'),
        "duration_minutes": recording.get('duration'),
        "recording_count": recording.get('recording_count'),
        "downloaded_at": datetime.now().isoformat(),
        "files": [f.name for f in folder_path.iterdir() if f.name != 'metadata.json']
    }
    
    metadata_path = folder_path / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"      ✓ Saved metadata.json")
    
    return folder_path

# Test download
if __name__ == "__main__":
    from zoom_fetcher import get_zoom_access_token, get_recordings_for_meeting_ids
    
    token = get_zoom_access_token()
    
    # Test with the meeting we just found
    test_meeting_ids = ["884 7930 8162"]
    test_date = "Oct 6, 2025"
    
    print(f"Fetching recording for download test...")
    recording = get_recordings_for_meeting_ids(token, test_meeting_ids, test_date)
    
    if recording:
        print(f"✓ Found recording: {recording.get('topic')}")
        download_meeting_artifacts(recording, token)
    else:
        print("✗ No recording found")