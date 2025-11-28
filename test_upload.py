from github_uploader import batch_upload_to_github
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Find some folders in downloads to upload
folders = list(Path("downloads").glob("*/Call*"))[:1]  # Just upload 1 folder as test

if folders:
    print(f"Testing upload of: {folders[0]}")
    repo_owner = os.getenv("GITHUB_UPLOAD_OWNER")
    repo_name = os.getenv("GITHUB_UPLOAD_REPO")
    
    result = batch_upload_to_github(folders, repo_owner, repo_name)
    print(f"Result: {len(result)} files uploaded")
else:
    print("No folders found in downloads/")