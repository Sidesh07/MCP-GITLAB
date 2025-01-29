import os
import requests
import anthropic
from gitlab_tools import (
    MongoDB,
    get_authorization_url,
    exchange_code_for_token,
    get_user_projects,
    get_user_details,
    clone_repository
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the Anthropics client
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# MongoDB instance
db = MongoDB()

def chat():
    """
    Simple chat loop to interact with the user.
    The user inputs a query, and the system will respond accordingly, 
    utilizing Claude (Anthropic) and performing GitLab-related actions.
    """
    print("Welcome to the GitLab Integration Assistant!")
    print("Ask me anything related to GitLab OAuth integration, projects, or repositories. Or ask me general questions.")

    while True:
        user_input = input("\nYou: ").lower()

        # Send the user input to Claude (Anthropic) for processing
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": user_input}],
            max_tokens=150
        )

        # Correctly access the assistant's response
        try:
            assistant_response = response.content[0].text  # Directly access 'content'
        except Exception as e:
            assistant_response = f"Error accessing response: {e}"
        # Based on user input, trigger GitLab actions if relevant
        if "auth url" in user_input:
            try:
                url = get_authorization_url()
                print(f"\nGitLab Authorization URL: {url}")
            except Exception as e:
                print(f"Error: {e}")

        elif "exchange code" in user_input:
            code = input("Please provide the GitLab authorization code: ").strip()
            try:
                token = exchange_code_for_token(code)
                username = input("Enter your GitLab username: ").strip()
                db.store_encrypted_token(username, token)
                print(f"Token successfully stored for user '{username}'.")
            except Exception as e:
                print(f"Error: {e}")

        elif "user projects" in user_input:
            username = input("Enter your GitLab username: ").strip()
            try:
                projects = get_user_projects(username, db)
                print("\nYour GitLab Projects:")
                for project in projects:
                    print(f"- {project['name']}")
            except Exception as e:
                print(f"Error: {e}")

        elif "user details" in user_input:
            username = input("Enter your GitLab username: ").strip()
            try:
                user_details = get_user_details(username, db)
                print(f"\nUser Details:\nName: {user_details['name']}\nEmail: {user_details.get('email', 'N/A')}")
            except Exception as e:
                print(f"Error: {e}")

        elif "clone repository" in user_input:
            username = input("Enter your GitLab username: ").strip()
            repo_name = input("Enter the repository name: ").strip()
            try:
                clone_url = clone_repository(username, repo_name, db)
                print(f"\nClone URL for repository '{repo_name}': {clone_url}")
            except Exception as e:
                # More detailed error handling
                if '404' in str(e):
                    print(f"Error: Repository '{repo_name}' not found or inaccessible.")
                else:
                    print(f"Error: {e}")

        elif "delete token" in user_input:
            username = input("Enter your GitLab username: ").strip()
            try:
                db.delete_token(username)
            except Exception as e:
                print(f"Error: {e}")

        elif "exit" in user_input:
            print("\nGoodbye! Have a great day!")
            break

        else:
            # If it's a general question or unrecognized command, let Claude respond
            print(f"\nClaude: {assistant_response}")


if __name__ == "__main__":
    chat()
