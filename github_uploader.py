# github_uploader.py (updated for batch commits)
import os
import base64
from pathlib import Path
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def batch_upload_to_github(folders_to_upload, repo_owner, repo_name, branch="main", log_func=None):
    """Upload multiple folders to GitHub in a single commit
    
    Args:
        folders_to_upload: List of folder paths to upload
        repo_owner: GitHub repository owner
        repo_name: GitHub repository name
        branch: Branch name (default: "main")
        log_func: Optional function to log messages (takes message string)
    
    Returns:
        List of uploaded file paths, or empty list on failure
    """
    
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        log(f"    ✗ GITHUB_TOKEN not set in environment")
        return []
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Check if repo exists
    repo_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    try:
        repo_check = requests.get(repo_url, headers=headers, timeout=30)
    except requests.exceptions.RequestException as e:
        log(f"    ✗ Network error accessing repo {repo_owner}/{repo_name}: {e}")
        return []
    
    if repo_check.status_code != 200:
        log(f"    ✗ Cannot access repo {repo_owner}/{repo_name}")
        log(f"      Status: {repo_check.status_code}")
        try:
            error_response = repo_check.json()
            log(f"      Response: {error_response}")
        except:
            log(f"      Response: {repo_check.text[:200]}")
        return []
    
    # Get the current commit SHA of the branch
    ref_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/ref/heads/{branch}"
    try:
        ref_response = requests.get(ref_url, headers=headers, timeout=30)
    except requests.exceptions.RequestException as e:
        log(f"    ✗ Network error getting branch {branch}: {e}")
        return []
    
    if ref_response.status_code != 200:
        log(f"    ✗ Cannot get branch {branch}")
        log(f"      Status: {ref_response.status_code}")
        try:
            error_response = ref_response.json()
            log(f"      Response: {error_response}")
        except:
            log(f"      Response: {ref_response.text[:200]}")
        return []
    
    last_commit_sha = ref_response.json()["object"]["sha"]
    log(f"    Last commit SHA: {last_commit_sha}")
    
    # Get the tree for the last commit
    commit_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/commits/{last_commit_sha}"
    try:
        commit_response = requests.get(commit_url, headers=headers, timeout=30)
    except requests.exceptions.RequestException as e:
        log(f"    ✗ Network error getting commit: {e}")
        return []
    
    if commit_response.status_code != 200:
        log(f"    ✗ Cannot get commit")
        log(f"      Status: {commit_response.status_code}")
        try:
            error_response = commit_response.json()
            log(f"      Response: {error_response}")
        except:
            log(f"      Response: {commit_response.text[:200]}")
        return []
    
    base_tree_sha = commit_response.json()["tree"]["sha"]
    log(f"    Base tree SHA: {base_tree_sha}")
    
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
                    log(f"    ✗ Failed to read {file_path}: {e}")
                    continue
                
                # GitHub requires base64 for binary content
                encoded_content = base64.b64encode(content).decode('utf-8')
                
                # Determine if text or binary
                is_text = file_path.suffix in ['.txt', '.json', '.vtt', '.md']
                
                tree_items.append({
                    "path": github_path,
                    "mode": "100644",
                    "type": "blob",
                    "content": content.decode('utf-8') if is_text else encoded_content
                })
                
                uploaded_files.append(github_path)
    
    if not tree_items:
        log("    No files to upload")
        return []
    
    log(f"    Creating tree with {len(tree_items)} files...")
    
    # Create a new tree
    tree_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/trees"
    tree_data = {
        "base_tree": base_tree_sha,
        "tree": tree_items
    }
    
    try:
        tree_response = requests.post(tree_url, headers=headers, json=tree_data, timeout=60)
    except requests.exceptions.RequestException as e:
        log(f"    ✗ Network error creating tree: {e}")
        return []
    
    if tree_response.status_code != 201:
        log(f"    ✗ Failed to create tree: {tree_response.status_code}")
        try:
            error_response = tree_response.json()
            log(f"      Error: {error_response.get('message', 'Unknown error')}")
            if 'errors' in error_response:
                log(f"      Details: {error_response['errors']}")
        except:
            log(f"      Response: {tree_response.text[:500]}")
        return []
    
    new_tree_sha = tree_response.json()["sha"]
    log(f"    New tree SHA: {new_tree_sha}")
    
    # Create the commit
    commit_message = f"Add {len(uploaded_files)} transcript files from {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    commit_data = {
        "message": commit_message,
        "tree": new_tree_sha,
        "parents": [last_commit_sha]
    }
    
    commit_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/commits"
    try:
        commit_response = requests.post(commit_url, headers=headers, json=commit_data, timeout=30)
    except requests.exceptions.RequestException as e:
        log(f"    ✗ Network error creating commit: {e}")
        return []
    
    if commit_response.status_code != 201:
        log(f"    ✗ Failed to create commit: {commit_response.status_code}")
        try:
            error_response = commit_response.json()
            log(f"      Error: {error_response}")
        except:
            log(f"      Response: {commit_response.text[:500]}")
        return []
    
    new_commit_sha = commit_response.json()["sha"]
    log(f"    New commit SHA: {new_commit_sha}")
    
    # Update the branch reference
    ref_update_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/refs/heads/{branch}"
    ref_update_data = {
        "sha": new_commit_sha,
        "force": False
    }

    try:
        ref_update_response = requests.patch(ref_update_url, headers=headers, json=ref_update_data, timeout=30)
    except requests.exceptions.RequestException as e:
        log(f"    ✗ Network error updating branch: {e}")
        return []

    if ref_update_response.status_code == 200:
        log(f"    ✓ Successfully uploaded {len(uploaded_files)} files in single commit")
        log(f"      Commit message: {commit_message}")
        return uploaded_files
    else:
        log(f"    ✗ Failed to update branch: {ref_update_response.status_code}")
        try:
            error_response = ref_update_response.json()
            log(f"      Error: {error_response}")
        except:
            log(f"      Response: {ref_update_response.text[:500]}")
        return []

def upload_readme_to_github(repo_owner, repo_name, branch="main", log_func=None):
    """Upload README.md to GitHub repository
    
    Args:
        repo_owner: GitHub repository owner
        repo_name: GitHub repository name
        branch: Branch name (default: "main")
        log_func: Optional function to log messages (takes message string)
    
    Returns:
        True if successful, False otherwise
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)
    
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        log(f"    ✗ GITHUB_TOKEN not set in environment")
        return False
    
    readme_path = Path('README.md')
    if not readme_path.exists():
        log(f"    ✗ README.md not found")
        return False
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Read README content
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            readme_content = f.read()
    except Exception as e:
        log(f"    ✗ Failed to read README.md: {e}")
        return False
    
    # Get the current commit SHA of the branch
    ref_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/ref/heads/{branch}"
    try:
        ref_response = requests.get(ref_url, headers=headers, timeout=30)
    except requests.exceptions.RequestException as e:
        log(f"    ✗ Network error getting branch ref: {e}")
        return False
    
    if ref_response.status_code != 200:
        log(f"    ✗ Cannot access branch {branch}: {ref_response.status_code}")
        return False
    
    base_commit_sha = ref_response.json()['object']['sha']
    
    # Get the base tree SHA
    commit_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/commits/{base_commit_sha}"
    try:
        commit_response = requests.get(commit_url, headers=headers, timeout=30)
    except requests.exceptions.RequestException as e:
        log(f"    ✗ Network error getting commit: {e}")
        return False
    
    if commit_response.status_code != 200:
        log(f"    ✗ Cannot access commit: {commit_response.status_code}")
        return False
    
    base_tree_sha = commit_response.json()['tree']['sha']
    
    # Create a new tree with README.md
    tree_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/trees"
    tree_data = {
        "base_tree": base_tree_sha,
        "tree": [{
            "path": "README.md",
            "mode": "100644",
            "type": "blob",
            "content": readme_content
        }]
    }
    
    try:
        tree_response = requests.post(tree_url, headers=headers, json=tree_data, timeout=60)
    except requests.exceptions.RequestException as e:
        log(f"    ✗ Network error creating tree: {e}")
        return False
    
    if tree_response.status_code != 201:
        log(f"    ✗ Failed to create tree: {tree_response.status_code}")
        try:
            error_response = tree_response.json()
            log(f"      Error: {error_response}")
        except:
            log(f"      Response: {tree_response.text[:500]}")
        return False
    
    new_tree_sha = tree_response.json()['sha']
    
    # Create a new commit
    commit_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/commits"
    commit_message = "Update README table with latest ACD calls"
    commit_data = {
        "message": commit_message,
        "tree": new_tree_sha,
        "parents": [base_commit_sha]
    }
    
    try:
        commit_response = requests.post(commit_url, headers=headers, json=commit_data, timeout=30)
    except requests.exceptions.RequestException as e:
        log(f"    ✗ Network error creating commit: {e}")
        return False
    
    if commit_response.status_code != 201:
        log(f"    ✗ Failed to create commit: {commit_response.status_code}")
        try:
            error_response = commit_response.json()
            log(f"      Error: {error_response}")
        except:
            log(f"      Response: {commit_response.text[:500]}")
        return False
    
    new_commit_sha = commit_response.json()['sha']
    
    # Update the branch reference
    ref_update_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/refs/heads/{branch}"
    ref_update_data = {
        "sha": new_commit_sha
    }
    
    try:
        ref_update_response = requests.patch(ref_update_url, headers=headers, json=ref_update_data, timeout=30)
    except requests.exceptions.RequestException as e:
        log(f"    ✗ Network error updating branch: {e}")
        return False
    
    if ref_update_response.status_code == 200:
        log(f"    ✓ Successfully uploaded README.md")
        return True
    else:
        log(f"    ✗ Failed to update branch: {ref_update_response.status_code}")
        try:
            error_response = ref_update_response.json()
            log(f"      Error: {error_response}")
        except:
            log(f"      Response: {ref_update_response.text[:500]}")
        return False

# Keep the original function for single uploads
def upload_to_github(local_path, repo_owner, repo_name, branch="main", log_func=None):
    """Original single-folder upload function"""
    # Call batch upload with single folder
    return batch_upload_to_github([local_path], repo_owner, repo_name, branch, log_func=log_func)