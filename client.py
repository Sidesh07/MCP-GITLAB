import anthropic
import os
import dotenv
import json
from gitlab_tools import (
    clone_project,
    get_authorization_url,
    exchange_code_for_token,
    get_user_projects,
    get_user_details,
    system_message
)

dotenv.load_dotenv()

# Initialize the Anthropics client
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Tools configuration
tools = [
    {
        "name": "get_authorization_url",
        "description": "Call the associate function to return URL to the user",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "exchange_code_for_token",
        "description": "Exchange authorization code for access token and store it securely in MongoDB.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The authorization code provided by GitHub after user authorization."}
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_user_projects",
        "description": "Fetch the projects of the authenticated user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "The GitHub username of the authenticated user."}
            },
            "required": ["username"]
        }
    },
    {
        "name": "get_user_profile",
        "description": "Fetch the authenticated user's GitHub profile.",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "The GitHub username of the authenticated user."}
            },
            "required": ["username"]
        }
    },
    {
        "name": "clone_project",
        "description": "Clone a GitHub project by its name for the authenticated user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "The GitHub username of the authenticated user."},
                "repo_name": {"type": "string", "description": "The name of the project to be cloned."}
            },
            "required": ["username", "repo_name"]
        }
    }
]

def process_tool_call(tool_name, tool_input):
    """Process tool calls based on the specified tool name."""
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

def simple_chat():
    """Interactive chat loop for user queries with Claude and tool integrations."""
    print("\nWelcome to the GitLab Integration Assistant!")
    print("Ask me anything related to GitLab OAuth integration, projects, repositories, or general queries.")
    
    messages = []
    while True:
        user_message = input("\nUser: ")
        if user_message.lower() == "exit":
            print("\nGoodbye! Have a great day!")
            break
        
        messages.append({"role": "user", "content": user_message})
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            system=system_message,
            max_tokens=4096,
            tools=tools,
            messages=messages
        )
        messages.append({"role": "assistant", "content": response.content})
        
        if response.stop_reason == "tool_use":
            tool_use = response.content[-1]
            tool_name = tool_use.name
            tool_input = tool_use.input
            print(f"\n====== Claude wants to use the {tool_name} tool ======")
            tool_result = process_tool_call(tool_name, tool_input)
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": str(tool_result),
                }],
            })
        else:
            print(f"\nRapid-Ops Support: {response.content[0].text}")

def chat():
    """Enhanced chat loop that interacts with the user and handles GitLab OAuth processes."""
    print("\nWelcome to the GitLab Integration Assistant!")
    print("Ask me anything related to GitLab OAuth, projects, repositories, or general queries.")
    
    while True:
        user_input = input("\nYou: ").strip().lower()
        if user_input == "exit":
            print("\nGoodbye! Have a great day!")
            break
        
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": user_input}],
            max_tokens=150
        )
        try:
            assistant_response = response.content[0].text
        except Exception as e:
            assistant_response = f"Error accessing response: {e}"
        
        if "auth url" in user_input:
            print(f"\nGitLab Authorization URL: {get_authorization_url()}")
        elif "exchange code" in user_input:
            code = input("Please provide the GitLab authorization code: ").strip()
            print(f"Token stored: {exchange_code_for_token(code)}")
        elif "user projects" in user_input:
            username = input("Enter your GitLab username: ").strip()
            print(f"\nYour GitLab Projects: {get_user_projects(username)}")
        elif "user details" in user_input:
            username = input("Enter your GitLab username: ").strip()
            print(f"\nUser Details: {get_user_details(username)}")
        elif "clone repository" in user_input:
            username = input("Enter your GitLab username: ").strip()
            repo_name = input("Enter the repository name: ").strip()
            print(f"\nClone URL: {clone_project(username, repo_name)}")
        else:
            print(f"\nClaude: {assistant_response}")

# Start the chat interface
if __name__ == "__main__":
    chat()
