"""Utility to check and verify Slack bot permissions."""
import os
from typing import List, Dict
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

REQUIRED_SCOPES = [
    "channels:manage",      # Create and manage channels
    "channels:read",        # View channels
    "chat:write",          # Send messages
    "groups:write",        # Send messages to private channels
    "incoming-webhook",     # Post messages via webhooks
]

def verify_slack_permissions(token: str = None) -> Dict[str, bool]:
    """Verify that our Slack bot has all required permissions.
    
    Args:
        token: Slack bot token. If not provided, uses SLACK_BOT_TOKEN env var
        
    Returns:
        Dict mapping permission scopes to boolean indicating if we have them
    """
    token = token or os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise ValueError("No Slack token provided")
        
    client = WebClient(token=token)
    
    try:
        # Get bot info
        auth_info = client.auth_test()
        bot_id = auth_info["bot_id"]
        
        # Get bot scopes
        bot_info = client.bots_info(bot=bot_id)
        current_scopes = bot_info["bot"]["scopes"]
        
        # Check each required scope
        permissions = {}
        for scope in REQUIRED_SCOPES:
            permissions[scope] = scope in current_scopes
            
        return permissions
        
    except SlackApiError as e:
        print(f"Error checking permissions: {e.response['error']}")
        return {scope: False for scope in REQUIRED_SCOPES}

def print_missing_permissions(permissions: Dict[str, bool]) -> None:
    """Print human-readable list of missing permissions."""
    missing = [scope for scope, has_it in permissions.items() if not has_it]
    
    if not missing:
        print("✅ Bot has all required permissions!")
        return
        
    print("❌ Missing required Slack permissions:")
    for scope in missing:
        print(f"  - {scope}")
    
    print("\nTo fix this:")
    print("1. Go to https://api.slack.com/apps")
    print("2. Select your app")
    print("3. Navigate to 'OAuth & Permissions'")
    print("4. Under 'Scopes', add these Bot Token Scopes:")
    for scope in missing:
        print(f"   - {scope}")
    print("5. Reinstall your app to the workspace")

def main():
    """Check Slack permissions and print report."""
    try:
        permissions = verify_slack_permissions()
        print_missing_permissions(permissions)
    except ValueError as e:
        print(f"Error: {str(e)}")
        print("Set SLACK_BOT_TOKEN environment variable or pass token as argument")

if __name__ == "__main__":
    main()
