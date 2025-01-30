import os
import sys
import requests
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from pymongo import MongoClient  # type: ignore
from typing import Optional
from fastmcp import FastMCP
import git
import subprocess


# Load environment variables
load_dotenv(".env")

# MCP Server Initialization
mcp = FastMCP("gitlab_oauth")

system_message = """
You are Rapid-Ops support Bot, a GitLab integration assistant. Your role is to assist users with secure GitLab authentication and data retrieval. Follow these guidelines:

Authentication Flow:
- When the user needs to authorize with GitLab, immediately use get_authorization_url.
- After getting the URL, ALWAYS display it in this format: "GitLab Authorization URL: [EXACT_URL_HERE]"
- Never proceed without explicitly showing the full URL.

**User Interaction**  
- Identify authentication needs before operations.  
- Offer authorization help to new users.  
- Verify token status for returning users.  

**Capabilities**  
- Generate GitLab OAuth URLs.  
- Exchange codes for access tokens.  
- Fetch user profiles and repository listings.  
- Manage token storage securely.   

**Error Handling**  
- Provide actionable feedback.  
- Explain errors and resolution steps clearly.  
- Maintain a helpful, concise tone.  

Start by assessing user needs, then guide them step-by-step from authentication to data retrieval.
"""

# GitLab API Endpoints
GITLAB_AUTH_URL = "https://gitlab.com/oauth/authorize"
GITLAB_TOKEN_URL = "https://gitlab.com/oauth/token"
GITLAB_API_URL = "https://gitlab.com/api/v4"

# Environment Variables
CLIENT_ID = os.getenv("GITLAB_CLIENT_ID")
CLIENT_SECRET = os.getenv("GITLAB_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GITLAB_REDIRECT_URI")
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
MASTER_KEY = os.getenv("MASTER_KEY")

if not MASTER_KEY:
    print("Error: MASTER_KEY is not set in the .env file!")
    sys.exit(1)

master_key = MASTER_KEY.encode()
master_cipher = Fernet(master_key)

# MongoDB Setup
client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

def store_encrypted_token(username: str, gitlab_token: str):
    """Encrypt and store GitLab access token in the database."""
    encrypted_token = master_cipher.encrypt(gitlab_token.encode())
    collection.update_one(
        {"username": username},
        {"$set": {"encrypted_token": encrypted_token.decode()}},
        upsert=True
    )

def fetch_decrypted_token(username: str) -> Optional[str]:
    """Fetch and decrypt the GitLab access token from the database."""
    record = collection.find_one({"username": username})
    if record and "encrypted_token" in record:
        encrypted_token = record["encrypted_token"].encode()
        return master_cipher.decrypt(encrypted_token).decode()
    return None

def delete_token(username: str):
    """Delete the stored access token for a user."""
    collection.update_one({"username": username}, {"$unset": {"encrypted_token": ""}})

@mcp.tool()
def get_authorization_url() -> str:
    """Generate GitLab authorization URL."""
    return (
        f"{GITLAB_AUTH_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=read_user+api"
    )

@mcp.tool()
def exchange_code_for_token(code: str) -> str:
    """Exchange authorization code for access token and store it securely in MongoDB."""
    url = GITLAB_TOKEN_URL
    headers = {"Accept": "application/json"}
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI
    }

    response = requests.post(url, headers=headers, data=data)
    if response.status_code != 200:
        return "Failed to exchange code for an access token. Please try again."

    token_data = response.json()
    access_token = token_data.get("access_token")

    if not access_token:
        return "No access token returned. Please check your credentials."

    # Fetch the username using the access token
    user_data_response = requests.get(
        f"{GITLAB_API_URL}/user",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if user_data_response.status_code != 200:
        return "Failed to fetch user details. Please reauthorize."

    user_data = user_data_response.json()
    username = user_data.get("username")

    if not username:
        return "Unable to retrieve username. Please try again."

    # Store the token in the database
    store_encrypted_token(username, access_token)
    return f"Authorization successful! Token saved for user '{username}'."

@mcp.tool()
def get_user_details(username: str) -> str:
    """Fetch GitLab user details."""
    access_token = fetch_decrypted_token(username)

    if not access_token:
        return "No access token found. Please reauthorize."

    response = requests.get(
        f"{GITLAB_API_URL}/user",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    if response.status_code == 401:
        delete_token(username)
        return "Access token is invalid or expired. Please reauthorize."

    if response.status_code == 200:
        user_data = response.json()
        return (
            f"Username: {user_data.get('username')}, Name: {user_data.get('name')}, "
            f"Email: {user_data.get('email')}, Projects: {user_data.get('projects_limit')}"
        )

    return "Failed to fetch user details."


@mcp.tool()
def get_user_projects(username: str) -> str:
    """
    Fetch the projects of the authenticated user, including private repositories.
    """
    access_token = fetch_decrypted_token(username)

    if not access_token:
        raise RuntimeError(f"No access token found for user: {username}. Please reauthorize.")

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{GITLAB_API_URL}/projects?owned=true", headers=headers)

    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch user projects: {response.text}")

    projects = response.json()
    if not projects:
        return "No projects found."

    return "\n".join(project["name"] for project in projects)


@mcp.tool()
def clone_project(username: str, project_name: str) -> str:
    """
    Clone a repository of the authenticated user directly.
    """
    access_token = fetch_decrypted_token(username)

    if not access_token:
        raise RuntimeError(f"No access token found for user: {username}. Please reauthorize.")

    headers = {"Authorization": f"Bearer {access_token}"}

    # Fetch all projects owned by the user
    response = requests.get(f"{GITLAB_API_URL}/projects?owned=true", headers=headers)
    
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch repositories: {response.text}")

    projects = response.json()
    repo_data = next((proj for proj in projects if proj["name"].lower() == project_name.lower()), None)

    if not repo_data:
        raise RuntimeError(f"Error: Repository '{project_name}' not found or inaccessible.")

    visibility = repo_data.get("visibility", "unknown")
    clone_url = repo_data.get("http_url_to_repo")

    # Modify the clone URL to include authentication for private repositories
    if visibility == "private":
        clone_url = clone_url.replace("https://", f"https://oauth2:{access_token}@")

    print(f"Cloning repository '{project_name}' ({visibility.capitalize()})...")

    # Run the git clone command
    try:
        subprocess.run(["git", "clone", clone_url], check=True)
        return f"Repository '{project_name}' cloned successfully!"
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to clone repository '{project_name}': {e}")


if __name__ == "__main__":
    mcp.run(transport="stdio")
