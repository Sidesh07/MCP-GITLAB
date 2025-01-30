import anthropic
import os
import dotenv
import pymongo
import json
from gitlab_tools import (
    get_authorization_url,
    exchange_code_for_token,
    get_user_projects,
    get_user_details,
    clone_project
)
from fastmcp import FastMCP

# Load environment variables from .env file
dotenv.load_dotenv()

# Retrieve environment variables
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Initialize MongoDB connection
client_mongo = pymongo.MongoClient(MONGO_URI)
db = client_mongo[DATABASE_NAME]
collection = db[COLLECTION_NAME]

# Initialize the Anthropics client
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Initialize FastMCP for GitLab Authentication
mcp = FastMCP("gitlab_integration")

# Tools configuration for GitLab integration
tools = [
    {
        "name": "get_authorization_url",
        "description": "Get the GitLab OAuth authorization URL for user login.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "exchange_code_for_token",
        "description": "Exchange authorization code for access token and store it securely in MongoDB.",
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "The GitLab authorization code."}},
            "required": ["code"]
        }
    },
    {
        "name": "get_user_projects",
        "description": "Fetch the projects of the authenticated user.",
        "input_schema": {
            "type": "object",
            "properties": {"username": {"type": "string", "description": "GitLab username."}},
            "required": ["username"]
        }
    },
    {
        "name": "get_user_profile",
        "description": "Fetch the authenticated user's GitLab profile.",
        "input_schema": {
            "type": "object",
            "properties": {"username": {"type": "string", "description": "GitLab username."}},
            "required": ["username"]
        }
    },
    {
        "name": "clone_project",
        "description": "Clone a GitLab project for the authenticated user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "GitLab username."},
                "repo_name": {"type": "string", "description": "The repository name to clone."}
            },
            "required": ["username", "repo_name"]
        }
    }
]

# Function to handle tool calls
def process_tool_call(tool_name, tool_input):
    if tool_name == "get_authorization_url":
        return get_authorization_url()
    elif tool_name == "exchange_code_for_token":
        return exchange_code_for_token(tool_input["code"])
    elif tool_name == "get_user_projects":
        return get_user_projects(tool_input["username"])
    elif tool_name == "get_user_profile":
        return get_user_details(tool_input["username"])
    elif tool_name == "clone_project":
        return clone_project(tool_input["username"], tool_input["repo_name"])

# GitLab chatbot function
def chat():
    """
    GitLab chatbot for OAuth authentication, project retrieval, and repository management.
    """
    print("🚀 Welcome to the GitLab Integration Assistant!")
    print("💡 Ask me anything related to GitLab OAuth integration, projects, or repositories.")
    print("🔹 Type 'exit' to quit.")

    while True:
        user_input = input("\nYou: ").strip()  # Trim spaces

        # Ensure input is not empty
        if not user_input:
            print("\n⚠️ Please enter a valid message.")
            continue

        # Send the user input to Claude (Anthropic AI) for processing
        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                messages=[{"role": "user", "content": user_input}],
                max_tokens=150
            )

            # Extract Claude's response
            assistant_response = response.content[0].text if response.content else "⚠️ No response from Claude."
        except Exception as e:
            assistant_response = f"Error accessing response: {e}"

        # Handle GitLab-related actions
        if "auth url" in user_input:
            try:
                url = get_authorization_url()
                print(f"\n🔗 GitLab Authorization URL: {url}")
            except Exception as e:
                print(f"❌ Error: {e}")

        elif "exchange code" in user_input:
            code = input("🔑 Please provide the GitLab authorization code: ").strip()
            try:
                message = exchange_code_for_token(code)  # Handles token storage internally
                print(f"✅ {message}")
            except Exception as e:
                print(f"❌ Error: {e}")

        elif "user projects" in user_input:
            username = input("👤 Enter your GitLab username: ").strip()
            try:
                projects = get_user_projects(username)
                print("\n📂 Your GitLab Projects:")
                print(projects)
            except Exception as e:
                print(f"❌ Error: {e}")

        elif "user details" in user_input:
            username = input("👤 Enter your GitLab username: ").strip()
            try:
                user_details = get_user_details(username)
                print(f"🛠 DEBUG: User Details API Response -> {user_details}")  # Debug print
                print(f"\n👤 {user_details}")
            except Exception as e:
                print(f"❌ Error: {e}")

        elif "clone repository" in user_input:
            username = input("👤 Enter your GitLab username: ").strip()
            repo_name = input("📂 Enter the repository name: ").strip()
            try:
                clone_message = clone_project(username, repo_name)
                print(f"\n✅ {clone_message}")
            except Exception as e:
                print(f"❌ Error: {e}")

        elif "exit" in user_input:
            print("\n👋 Goodbye! Have a great day!")
            break

        else:
            print(f"\n🤖 Claude: {assistant_response}")

# Run the chatbot immediately when the script executes
if __name__ == "__main__":
    chat()
