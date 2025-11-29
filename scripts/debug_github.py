import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("GITHUB_TOKEN")
owner = os.getenv("GITHUB_UPLOAD_OWNER")
repo = os.getenv("GITHUB_UPLOAD_REPO")
branch = "main"

headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json"
}

# Check repo exists
repo_url = f"https://api.github.com/repos/{owner}/{repo}"
print(f"Checking: {repo_url}")
r = requests.get(repo_url, headers=headers)
print(f"Repo status: {r.status_code}")
if r.status_code == 200:
    print(f"  Default branch: {r.json()['default_branch']}")
else:
    print(f"  Error: {r.json()}")

# Check branch exists
ref_url = f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{branch}"
print(f"\nChecking branch: {ref_url}")
r = requests.get(ref_url, headers=headers)
print(f"Branch status: {r.status_code}")
if r.status_code != 200:
    print(f"  Error: {r.json()}")
    print(f"\n  Try changing branch to 'master' if that's the default branch")