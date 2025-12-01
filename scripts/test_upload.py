from pathlib import Path
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path so we can import from scripts
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.github_uploader import batch_upload_to_github

load_dotenv()

# Find some folders in root directories to upload
folders = []
for meeting_type in ["ACDE", "ACDC", "ACDT"]:
    folders.extend(list(Path(meeting_type).glob("Call*"))[:1])
    if folders:
        break

if folders:
    print(f"Testing upload of: {folders[0]}")
    repo_owner = os.getenv("GITHUB_UPLOAD_OWNER")
    repo_name = os.getenv("GITHUB_UPLOAD_REPO")
    
    result = batch_upload_to_github(folders, repo_owner, repo_name)
    print(f"Result: {len(result)} files uploaded")
else:
    print("No folders found in root directories")