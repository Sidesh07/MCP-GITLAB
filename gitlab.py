import os
import requests
from pymongo import MongoClient, errors

class MongoDB:
    def __init__(self):
        # MongoDB URI, database, and collection names
        mongo_uri = os.getenv("MONGO_URI")
        database_name = "gitlab_app"  # Explicitly setting the database name
        collection_name = "tokens"   # Explicitly setting the collection name

        if not mongo_uri:
            raise ValueError("MONGO_URI is not set. Ensure your .env file is loaded and contains a valid MONGO_URI.")

        # Initialize MongoDB client
        try:
            self.client = MongoClient(mongo_uri)
            self.db = self.client[database_name]
            self.collection = self.db[collection_name]
        except errors.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to MongoDB: {e}")

    def store_encrypted_token(self, username, encrypted_token):
        """
        Store or update an encrypted token for a user in the database.
        """
        if not username or not encrypted_token:
            raise ValueError("Both username and encrypted_token are required.")

        try:
            self.collection.update_one(
                {"username": username},
                {"$set": {"encrypted_token": encrypted_token}},
                upsert=True
            )
            print(f"Token successfully stored for user: {username}")
        except errors.PyMongoError as e:
            raise RuntimeError(f"Failed to store token: {e}")

    def fetch_decrypted_token(self, username):
        """
        Fetch an encrypted token for a user from the database.
        """
        if not username:
            raise ValueError("Username is required to fetch the token.")

        try:
            record = self.collection.find_one({"username": username})
            if record and "encrypted_token" in record:
                return record["encrypted_token"]
            else:
                print(f"No token found for user: {username}")
                return None
        except errors.PyMongoError as e:
            raise RuntimeError(f"Failed to fetch token: {e}")

    def delete_token(self, username):
        """
        Delete a stored token for a user.
        """
        if not username:
            raise ValueError("Username is required to delete the token.")

        try:
            result = self.collection.delete_one({"username": username})
            if result.deleted_count > 0:
                print(f"Token successfully deleted for user: {username}")
            else:
                print(f"No token found to delete for user: {username}")
        except errors.PyMongoError as e:
            raise RuntimeError(f"Failed to delete token: {e}")


# GitLab API helper functions
GITLAB_AUTH_URL = "https://gitlab.com/oauth/authorize"
GITLAB_TOKEN_URL = "https://gitlab.com/oauth/token"
GITLAB_API_URL = "https://gitlab.com/api/v4"

def get_authorization_url():
    """
    Generate the GitLab authorization URL.
    """
    client_id = os.getenv("GITLAB_CLIENT_ID")
    redirect_uri = os.getenv("GITLAB_REDIRECT_URI")

    if not client_id or not redirect_uri:
        raise ValueError("GITLAB_CLIENT_ID and GITLAB_REDIRECT_URI must be set in the .env file.")

    return f"{GITLAB_AUTH_URL}?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope=read_user+read_api+write_repository"

def exchange_code_for_token(code):
    """
    Exchange the authorization code for an access token.
    """
    response = requests.post(
        GITLAB_TOKEN_URL,
        data={
            "client_id": os.getenv("GITLAB_CLIENT_ID"),
            "client_secret": os.getenv("GITLAB_CLIENT_SECRET"),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": os.getenv("GITLAB_REDIRECT_URI"),
        },
    )
    if response.status_code != 200:
        raise RuntimeError(f"Failed to exchange code for token: {response.text}")
    return response.json().get("access_token")

def get_user_projects(username, db):
    """
    Fetch the projects of the authenticated user.
    """
    token = db.fetch_decrypted_token(username)
    if not token:
        raise RuntimeError(f"No token found for user: {username}")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{GITLAB_API_URL}/projects?membership=true", headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch user projects: {response.text}")
    return response.json()

def get_user_details(username, db):
    """
    Fetch the details of the authenticated user.
    """
    token = db.fetch_decrypted_token(username)
    if not token:
        raise RuntimeError(f"No token found for user: {username}")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{GITLAB_API_URL}/user", headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch user details: {response.text}")
    return response.json()

def clone_repository(username, repo_name, db):
    """
    Clone a repository of the authenticated user.
    """
    token = db.fetch_decrypted_token(username)
    if not token:
        raise RuntimeError(f"No token found for user: {username}")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{GITLAB_API_URL}/projects/{repo_name}", headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch repository: {response.text}")

    repo_data = response.json()
    clone_url = repo_data.get("http_url_to_repo")
    return f"Repository '{repo_name}' clone URL: {clone_url}"
