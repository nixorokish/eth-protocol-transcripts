# github_uploader.py (updated for batch commits)
import os
import base64
from pathlib import Path
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def batch_upload_to_github(folders_to_upload, repo_owner, repo_name, branch="main"):
    """Upload multiple folders to GitHub in a single commit"""
    
    token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Check if repo exists
    repo_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    repo_check = requests.get(repo_url, headers=headers)
    
    if repo_check.status_code != 200:
        print(f"    ✗ Cannot access repo {repo_owner}/{repo_name}")
        return []
    
    # Get the current commit SHA of the branch
    ref_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/ref/heads/{branch}"
    ref_response = requests.get(ref_url, headers=headers)
    
    if ref_response.status_code != 200:
        print(f"    ✗ Cannot get branch {branch}")
        return []
    
    last_commit_sha = ref_response.json()["object"]["sha"]
    
    # Get the tree for the last commit
    commit_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/commits/{last_commit_sha}"
    commit_response = requests.get(commit_url, headers=headers)
    base_tree_sha = commit_response.json()["tree"]["sha"]
    
    # Build the new tree with all files
    tree_items = []
    uploaded_files = []
    
    for folder_path in folders_to_upload:
        folder_path = Path(folder_path)
        
        for file_path in folder_path.rglob("*"):
            if file_path.is_file():
                # Get path relative to downloads directory
                relative_path = file_path.relative_to(Path("downloads"))
                github_path = str(relative_path).replace('\\', '/')
                
                # Read file content
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                except Exception as e:
                    print(f"    ✗ Failed to read {file_path}: {e}")
                    continue
                
                # GitHub requires base64 for binary content
                encoded_content = base64.b64encode(content).decode('utf-8')
                
                tree_items.append({
                    "path": github_path,
                    "mode": "100644",
                    "type": "blob",
                    "content": content.decode('utf-8') if file_path.suffix in ['.txt', '.json', '.vtt'] else encoded_content
                })
                
                uploaded_files.append(github_path)
    
    if not tree_items:
        print("    No files to upload")
        return []
    
    # Create a new tree
    tree_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/trees"
    tree_data = {
        "base_tree": base_tree_sha,
        "tree": tree_items
    }
    
    tree_response = requests.post(tree_url, headers=headers, json=tree_data)
    
    if tree_response.status_code != 201:
        print(f"    ✗ Failed to create tree: {tree_response.status_code}")
        print(f"      Error: {tree_response.json().get('message', 'Unknown error')}")
        return []
    
    new_tree_sha = tree_response.json()["sha"]
    
    # Create the commit
    commit_message = f"Add {len(uploaded_files)} transcript files from {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    commit_data = {
        "message": commit_message,
        "tree": new_tree_sha,
        "parents": [last_commit_sha]
    }
    
    commit_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/commits"
    commit_response = requests.post(commit_url, headers=headers, json=commit_data)
    
    if commit_response.status_code != 201:
        print(f"    ✗ Failed to create commit: {commit_response.status_code}")
        return []
    
    new_commit_sha = commit_response.json()["sha"]
    
    # Update the branch reference
    ref_update_data = {
        "sha": new_commit_sha,
        "force": False
    }
    
    ref_update_response = requests.patch(ref_url, headers=headers, json=ref_update_data)
    
    if ref_update_response.status_code == 200:
        print(f"    ✓ Successfully uploaded {len(uploaded_files)} files in single commit")
        print(f"      Commit message: {commit_message}")
        return uploaded_files
    else:
        print(f"    ✗ Failed to update branch: {ref_update_response.status_code}")
        return []

# Keep the original function for single uploads
def upload_to_github(local_path, repo_owner, repo_name, branch="main"):
    """Original single-folder upload function"""
    # Call batch upload with single folder
    return batch_upload_to_github([local_path], repo_owner, repo_name, branch)