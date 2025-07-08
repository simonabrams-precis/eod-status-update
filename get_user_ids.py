#!/usr/bin/env python3
"""
Utility script to help get Slack user IDs for the fallback developer list.
This script will list all users in your workspace so you can identify developers.
"""

import os
import asyncio
from dotenv import load_dotenv
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

# Load environment variables
load_dotenv()

async def get_all_users():
    """Get all users from Slack workspace."""
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    if not bot_token:
        print("❌ SLACK_BOT_TOKEN not found in environment variables")
        return
    
    client = AsyncWebClient(token=bot_token)
    
    try:
        print("🔍 Fetching all users from Slack workspace...")
        response = await client.users_list()
        
        if response["ok"]:
            users = response["users"]
            print(f"✅ Found {len(users)} users in workspace")
            print("\n👥 All Users:")
            print("-" * 60)
            
            for user in users:
                # Skip bots and deleted users
                if user.get("is_bot") or user.get("deleted"):
                    continue
                
                user_id = user["id"]
                real_name = user.get("real_name", "Unknown")
                display_name = user.get("profile", {}).get("display_name", "")
                email = user.get("profile", {}).get("email", "")
                
                print(f"ID: {user_id}")
                print(f"Name: {real_name}")
                if display_name:
                    print(f"Display: {display_name}")
                if email:
                    print(f"Email: {email}")
                print("-" * 60)
            
            print("\n💡 To create your fallback list:")
            print("1. Copy the user IDs of developers you want to include")
            print("2. Add them to your .env file like this:")
            print("   FALLBACK_DEVELOPER_IDS=U1234567890,U0987654321,U1122334455")
            
        else:
            print(f"❌ Error fetching users: {response.get('error')}")
            
    except SlackApiError as e:
        print(f"❌ Slack API error: {e.response['error']}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(get_all_users()) 