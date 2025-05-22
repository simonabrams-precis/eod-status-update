import os
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.web.async_client import AsyncWebClient
from datetime import datetime, time, timedelta
import pytz
import asyncio
from dotenv import load_dotenv
import logging
import aioschedule
from typing import Dict, List
import json

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load environment variables from .env file
load_dotenv()

# Initialize your Slack app with your bot token
app = AsyncApp(token=os.environ.get("SLACK_BOT_TOKEN"))
client = AsyncWebClient(token=os.environ.get("SLACK_BOT_TOKEN"))

# Handle URL verification challenge
@app.event("url_verification")
async def handle_verification(body, ack):
    await ack({"challenge": body["challenge"]})

# Add a simple health check endpoint
@app.message("health_check")
async def handle_health_check(message, say):
    await say("🤖 Bot is up and running! All systems go! 🚀")

# Add test command for scheduled reminders
@app.command("/test-reminders")
async def handle_test_reminders(ack, body, client, logger):
    await ack()
    logger.info("Test reminders command triggered")
    
    try:
        # Get all developer user IDs
        developer_ids = await get_developer_user_ids()
        if not developer_ids:
            await client.chat_postMessage(
                channel=body["user_id"],
                text="⚠️ No developer IDs found! Please check your configuration:\n"
                     "1. Add `usergroups:read` scope to your Slack app\n"
                     "2. Set `DEVELOPER_USERGROUP_ID` in your environment\n"
                     "3. Or set `FALLBACK_DEVELOPER_IDS` as a comma-separated list"
            )
            return

        logger.info(f"Found {len(developer_ids)} developers to notify")
        
        # Send test message to the command user
        await client.chat_postMessage(
            channel=body["user_id"],
            text=f"🧪 Testing reminders for {len(developer_ids)} developers...\n"
                 f"Using {'fallback' if os.environ.get('FALLBACK_DEVELOPER_IDS') else 'usergroup'} list"
        )
        
        # Force trigger reminders for all developers
        for user_id in developer_ids:
            try:
                user_tz = await get_user_timezone(user_id)
                current_time = get_user_local_time(user_tz)
                logger.info(f"Testing reminder for user {user_id} in timezone {user_tz} (current time: {current_time})")
                await send_initial_prompt(user_id)
            except Exception as e:
                logger.error(f"Error sending test reminder to user {user_id}: {e}")
                await client.chat_postMessage(
                    channel=body["user_id"],
                    text=f"❌ Error sending test reminder to <@{user_id}>: {str(e)}"
                )
        
        await client.chat_postMessage(
            channel=body["user_id"],
            text="✅ Test reminders sent! Check the logs for details."
        )
    except Exception as e:
        logger.error(f"Error in test reminders: {e}")
        await client.chat_postMessage(
            channel=body["user_id"],
            text=f"❌ Error testing reminders: {str(e)}"
        )

# Add slash command to manually trigger EOD status update
@app.command("/eod-status")
async def handle_eod_status_command(ack, body, client, logger):
    # Acknowledge the command request immediately
    await ack()
    logger.info(f"EOD status command triggered by {body['user_id']}")
    
    # Send the initial prompt to start the status update flow
    await send_initial_prompt(body["user_id"])

# Function to get the list of developer user IDs
async def get_developer_user_ids():
    """
    Fetch developer user IDs from the usergroup.
    Falls back to a hardcoded list if usergroup access is not available.
    """
    try:
        usergroup_id = os.environ.get("DEVELOPER_USERGROUP_ID")
        if not usergroup_id:
            logger.warning("DEVELOPER_USERGROUP_ID not set in environment variables")
            return get_fallback_developer_ids()

        users_in_group = await client.usergroups_users_list(usergroup=usergroup_id)
        if users_in_group and users_in_group["ok"]:
            logger.info(f"Successfully fetched {len(users_in_group['users'])} developers from usergroup")
            return users_in_group["users"]
        else:
            error = users_in_group.get('error', 'unknown error')
            if error == 'missing_scope':
                logger.warning("Missing usergroups:read scope. Using fallback developer list.")
                return get_fallback_developer_ids()
            else:
                logger.error(f"Error fetching users in group: {error}")
                return get_fallback_developer_ids()
    except Exception as e:
        logger.error(f"Error getting developer user IDs: {e}")
        return get_fallback_developer_ids()

def get_fallback_developer_ids():
    """
    Fallback function to return a list of developer user IDs.
    These should be set in the environment variables as a comma-separated list.
    """
    fallback_ids = os.environ.get("FALLBACK_DEVELOPER_IDS", "").split(",")
    fallback_ids = [uid.strip() for uid in fallback_ids if uid.strip()]
    
    if fallback_ids:
        logger.info(f"Using fallback list of {len(fallback_ids)} developers")
        return fallback_ids
    else:
        logger.error("No fallback developer IDs configured. Please set FALLBACK_DEVELOPER_IDS in environment variables.")
        return []

# Modal definition for submitting status
def build_status_modal(channel_id, form_data=None):
    """
    Build the status modal with optional pre-filled data.
    form_data is only provided when editing an existing status.
    """
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"Updating status for <#{channel_id}>"}
        },
        {
            "type": "input",
            "block_id": "update_block",
            "label": {"type": "plain_text", "text": "What's your update?"},
            "element": {
                "type": "plain_text_input",
                "multiline": True,
                "action_id": "update_text",
                "initial_value": form_data.get("update_text", "") if form_data else ""
            }
        },
        {
            "type": "input",
            "block_id": "next_steps_block",
            "label": {"type": "plain_text", "text": "Next Steps"},
            "element": {
                "type": "plain_text_input",
                "multiline": True,
                "action_id": "next_steps_text",
                "initial_value": form_data.get("next_steps", "") if form_data else "",
                "placeholder": {"type": "plain_text", "text": "What needs to be done next?"}
            }
        },
        {
            "type": "input",
            "block_id": "priority_block",
            "label": {"type": "plain_text", "text": "Priority"},
            "element": {
                "type": "static_select",
                "placeholder": {"type": "plain_text", "text": "Select priority"},
                "options": [
                    {"text": {"type": "plain_text", "text": "High"}, "value": "high"},
                    {"text": {"type": "plain_text", "text": "Medium"}, "value": "medium"},
                    {"text": {"type": "plain_text", "text": "Low"}, "value": "low"}
                ],
                "action_id": "priority_select",
                "initial_option": {
                    "text": {"type": "plain_text", "text": (form_data.get("priority", "medium") if form_data else "medium").title()},
                    "value": form_data.get("priority", "medium") if form_data else "medium"
                }
            }
        },
        {
            "type": "input",
            "block_id": "technical_details_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "🤓 Dev Notes (optional)"},
            "element": {
                "type": "plain_text_input",
                "multiline": True,
                "action_id": "technical_details_text",
                "initial_value": form_data.get("technical_details", "") if form_data else ""
            }
        },
        {
            "type": "input",
            "block_id": "blockers_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "🚫 Blockers? (optional)"},
            "element": {
                "type": "static_select",
                "placeholder": {"type": "plain_text", "text": "Select an option"},
                "options": [
                    {"text": {"type": "plain_text", "text": "Yes"}, "value": "yes"},
                    {"text": {"type": "plain_text", "text": "No"}, "value": "no"}
                ],
                "action_id": "blockers_select",
                "initial_option": {
                    "text": {"type": "plain_text", "text": "Yes" if form_data and form_data.get("blockers") == "yes" else "No"},
                    "value": form_data.get("blockers", "no") if form_data else "no"
                }
            }
        },
        {
            "type": "input",
            "block_id": "blockers_details_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "Blockers Details (optional)"},
            "element": {
                "type": "plain_text_input",
                "multiline": True,
                "action_id": "blockers_details_text",
                "initial_value": form_data.get("blockers_details", "") if form_data else ""
            }
        }
    ]

    return {
        "type": "modal",
        "callback_id": "status_submission_edit" if form_data else "status_submission",
        "private_metadata": json.dumps({
            "channel_id": channel_id,
            "message_ts": form_data.get("message_ts") if form_data else None
        }) if form_data else channel_id,
        "title": {"type": "plain_text", "text": "Edit Status Update" if form_data else "Project Status Update"},
        "blocks": blocks,
        "submit": {"type": "plain_text", "text": "Update" if form_data else "Submit"}
    }

# Initial reminder with "Yes" or "No"
async def send_initial_prompt(user_id):
    try:
        await client.chat_postMessage(
            channel=user_id,
            text="Do you have any end-of-day status updates to share today?",
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "📊 *Time for your daily status update!*\nDo you have any updates to share today?"},
                    "accessory": {
                        "type": "static_select",
                        "placeholder": {"type": "plain_text", "text": "Select an option"},
                        "options": [
                            {"text": {"type": "plain_text", "text": "Yes, let's do it! ✨"}, "value": "yes_update"},
                            {"text": {"type": "plain_text", "text": "Not today 🙅‍♂️"}, "value": "no_update"}
                        ],
                        "action_id": "initial_update_choice"
                    }
                }
            ]
        )
    except Exception as e:
        print(f"Error sending initial prompt to {user_id}: {e}")

# Function to get user's timezone
async def get_user_timezone(user_id: str) -> str:
    """Get a user's timezone from their Slack profile."""
    try:
        user_info = await client.users_info(user=user_id)
        if user_info["ok"]:
            tz = user_info["user"].get("tz", "UTC")
            return tz
        return "UTC"
    except Exception as e:
        logger.error(f"Error getting timezone for user {user_id}: {e}")
        return "UTC"

# Function to fetch relevant project channels (customize this based on your workspace)
async def get_relevant_project_channels():
    """
    Fetch relevant project channels that the user can post to.
    Currently returns all public channels the bot is a member of.
    """
    try:
        # First get all channels the bot is in
        logger.info("Fetching channels...")
        channels_response = await client.conversations_list(
            types="public_channel",
            exclude_archived=True,
            limit=1000
        )
        
        logger.info(f"Channels response: {channels_response}")
        
        if not channels_response or not channels_response["ok"]:
            logger.error(f"Error fetching channels: {channels_response.get('error')}")
            return []

        # Get all channels first
        all_channels = channels_response["channels"]
        logger.info(f"Total channels found: {len(all_channels)}")
        
        # Get bot's user ID
        auth_response = await client.auth_test()
        bot_user_id = auth_response["user_id"]
        logger.info(f"Bot user ID: {bot_user_id}")
        
        # Get channels the bot is a member of
        bot_channels = []
        for channel in all_channels:
            try:
                # Check if bot is a member
                members_response = await client.conversations_members(channel=channel["id"])
                if members_response["ok"] and bot_user_id in members_response["members"]:
                    bot_channels.append(channel)
                    logger.info(f"Bot is a member of channel: {channel['name']}")
            except Exception as e:
                logger.error(f"Error checking membership for channel {channel['name']}: {e}")
                continue

        logger.info(f"Channels bot is a member of: {len(bot_channels)}")
        return bot_channels

    except Exception as e:
        logger.error(f"Error in get_relevant_project_channels: {e}")
        return []

# Function to get current time in user's timezone
def get_user_local_time(user_tz: str) -> datetime:
    """Get current time in user's timezone."""
    try:
        tz = pytz.timezone(user_tz)
        return datetime.now(tz)
    except Exception as e:
        logger.error(f"Error converting to timezone {user_tz}: {e}")
        return datetime.now(pytz.UTC)

# Handle the initial "Yes" or "No" response
@app.action("initial_update_choice")
async def handle_initial_choice(ack, body, client, logger):
    await ack()
    
    try:
        user_id = body["user"]["id"]
        choice = body["actions"][0]["selected_option"]["value"]

        if choice == "yes_update":
            project_channels = await get_relevant_project_channels()
            if project_channels:
                channel_options = [{"text": {"type": "plain_text", "text": channel["name"]}, "value": channel["id"]} for channel in project_channels]
                await client.chat_postMessage(
                    channel=user_id,
                    text="Which project channel would you like to update?",
                    blocks=[
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": "🎯 *Select the project channel you want to update:*"},
                            "accessory": {
                                "type": "static_select",
                                "placeholder": {"type": "plain_text", "text": "Choose a channel 📝"},
                                "options": channel_options,
                                "action_id": "select_project_channel"
                            }
                        }
                    ]
                )
            else:
                await client.chat_postMessage(
                    channel=user_id,
                    text="😕 It seems there are no project channels available to update right now."
                )
        elif choice == "no_update":
            await client.chat_postMessage(
                channel=user_id,
                text="👋 No worries! Have a productive day! 💪"
            )
    except Exception as e:
        logger.error(f"Error in initial choice: {e}")
        await client.chat_postEphemeral(
            channel=user_id,
            user=user_id,
            text="😅 Oops! Something went wrong while processing your choice. Please try again!"
        )

# Add edit button handler right here
@app.action("edit_status_update")
async def handle_edit_status(ack, body, client, logger):
    """Handle the edit button click on a status update."""
    await ack()
    logger.info(f"Edit status update triggered: {body}")
    
    try:
        # Parse the button value
        value_data = json.loads(body["actions"][0]["value"])
        channel_id = value_data["channel_id"]
        form_data = value_data["form_data"]
        message_ts = value_data["message_ts"]
        
        # Build the modal with pre-filled values, handling None values
        modal = {
            "type": "modal",
            "callback_id": "status_submission_edit",
            "private_metadata": json.dumps({
                "channel_id": channel_id,
                "message_ts": message_ts
            }),
            "title": {"type": "plain_text", "text": "Edit Status Update"},
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"Editing status update for <#{channel_id}>"}
                },
                {
                    "type": "input",
                    "block_id": "update_block",
                    "label": {"type": "plain_text", "text": "What's your update?"},
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "action_id": "update_text",
                        "initial_value": form_data.get("update_text", "")
                    }
                },
                {
                    "type": "input",
                    "block_id": "next_steps_block",
                    "label": {"type": "plain_text", "text": "Next Steps"},
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "action_id": "next_steps_text",
                        "initial_value": form_data.get("next_steps", ""),
                        "placeholder": {"type": "plain_text", "text": "What needs to be done next?"}
                    }
                },
                {
                    "type": "input",
                    "block_id": "priority_block",
                    "label": {"type": "plain_text", "text": "Priority"},
                    "element": {
                        "type": "static_select",
                        "placeholder": {"type": "plain_text", "text": "Select priority"},
                        "options": [
                            {"text": {"type": "plain_text", "text": "High"}, "value": "high"},
                            {"text": {"type": "plain_text", "text": "Medium"}, "value": "medium"},
                            {"text": {"type": "plain_text", "text": "Low"}, "value": "low"}
                        ],
                        "action_id": "priority_select",
                        "initial_option": {
                            "text": {"type": "plain_text", "text": form_data.get("priority", "medium").title()},
                            "value": form_data.get("priority", "medium")
                        }
                    }
                },
                {
                    "type": "input",
                    "block_id": "technical_details_block",
                    "optional": True,
                    "label": {"type": "plain_text", "text": "🤓 Dev Notes (optional)"},
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "action_id": "technical_details_text",
                        "initial_value": form_data.get("technical_details", "") or ""
                    }
                },
                {
                    "type": "input",
                    "block_id": "blockers_block",
                    "optional": True,
                    "label": {"type": "plain_text", "text": "🚫 Blockers? (optional)"},
                    "element": {
                        "type": "static_select",
                        "placeholder": {"type": "plain_text", "text": "Select an option"},
                        "options": [
                            {"text": {"type": "plain_text", "text": "Yes"}, "value": "yes"},
                            {"text": {"type": "plain_text", "text": "No"}, "value": "no"}
                        ],
                        "action_id": "blockers_select",
                        "initial_option": {
                            "text": {"type": "plain_text", "text": "Yes" if form_data.get("blockers") == "yes" else "No"},
                            "value": form_data.get("blockers", "no")
                        }
                    }
                },
                {
                    "type": "input",
                    "block_id": "blockers_details_block",
                    "optional": True,
                    "label": {"type": "plain_text", "text": "Blockers Details (optional)"},
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "action_id": "blockers_details_text",
                        "initial_value": form_data.get("blockers_details", "") or ""
                    }
                }
            ],
            "submit": {"type": "plain_text", "text": "Update"}
        }
        
        # Open the modal
        await client.views_open(
            trigger_id=body["trigger_id"],
            view=modal
        )
    except Exception as e:
        logger.error(f"Error handling edit status: {e}")
        logger.error(f"Full body: {body}")  # Add more detailed logging
        await client.chat_postEphemeral(
            channel=body["channel"]["id"],
            user=body["user"]["id"],
            text="😅 Sorry, there was an error opening the edit form. Please try again."
        )

@app.action("select_project_channel")
async def handle_project_selection(ack, body, client, logger):
    await ack()
    
    try:
        user_id = body["user"]["id"]
        channel_id = body["actions"][0]["selected_option"]["value"]
        
        # Build the initial modal without any pre-filled data
        modal = build_status_modal(channel_id)
        
        # Open the modal
        await client.views_open(
            trigger_id=body["trigger_id"],
            view=modal
        )
    except Exception as e:
        logger.error(f"Error in project selection: {e}")
        logger.error(f"Full body: {body}")  # Add more detailed logging
        await client.chat_postEphemeral(
            channel=user_id,
            user=user_id,
            text="😅 Sorry, there was an error opening the status form. Please try again."
        )

def get_form_data(view_state):
    """
    Safely extract form data from the view state, handling empty and optional fields.
    """
    try:
        # Required fields with safe gets
        update_text = view_state["update_block"]["update_text"]["value"]
        next_steps = view_state["next_steps_block"]["next_steps_text"]["value"]
        
        # Priority with safe fallback
        priority_block = view_state["priority_block"]["priority_select"]
        priority = "medium"  # default
        if priority_block.get("selected_option"):
            priority = priority_block["selected_option"]["value"]

        # Optional fields with safe gets
        technical_details = None
        if "technical_details_block" in view_state:
            tech_block = view_state["technical_details_block"].get("technical_details_text", {})
            if tech_block and isinstance(tech_block, dict):
                technical_details = tech_block.get("value")

        blockers = None
        if "blockers_block" in view_state:
            blockers_block = view_state["blockers_block"].get("blockers_select", {})
            if blockers_block and isinstance(blockers_block, dict):
                selected_option = blockers_block.get("selected_option")
                if selected_option and isinstance(selected_option, dict):
                    blockers = selected_option.get("value")

        blockers_details = None
        if "blockers_details_block" in view_state:
            blockers_details_block = view_state["blockers_details_block"].get("blockers_details_text", {})
            if blockers_details_block and isinstance(blockers_details_block, dict):
                blockers_details = blockers_details_block.get("value")

        return {
            "update_text": update_text,
            "next_steps": next_steps,
            "priority": priority,
            "technical_details": technical_details,
            "blockers": blockers,
            "blockers_details": blockers_details
        }
    except Exception as e:
        logger.error(f"Error extracting form data: {e}")
        logger.error(f"View state: {view_state}")
        raise

@app.view("status_submission")
async def handle_status_submission(ack, body, view, client, logger):
    await ack()
    
    try:
        user_id = body["user"]["id"]
        channel_id = body["view"]["private_metadata"]
        
        # Get all the form values using the safe extraction function
        form_data = get_form_data(view["state"]["values"])
        
        # Get user's timezone
        user_tz = await get_user_timezone(user_id)
        current_time = get_user_local_time(user_tz)
        
        # Build the message with improved formatting
        priority_emoji = {
            "high": "🔴",
            "medium": "🟡",
            "low": "🟢"
        }.get(form_data["priority"], "🟡")

        message = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Status Update from <@{user_id}>*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🕒 *Local Time:* {current_time.strftime('%I:%M %p')} ({user_tz})\n"
            f"🎯 *Priority:* {priority_emoji} {form_data['priority'].upper()}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 *Update:*\n"
            f"{form_data['update_text']}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏭️ *Next Steps:*\n"
            f"{form_data['next_steps']}\n"
        )
        
        # Add optional sections with clear separation
        if form_data["technical_details"] and form_data["technical_details"].strip():
            message += (
                f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤓 *Dev Notes:*\n"
                f"{form_data['technical_details']}\n"
            )

        if form_data["blockers"] == "yes":
            message += (
                f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🚫 *Blockers:* Yes\n"
            )
            if form_data["blockers_details"] and form_data["blockers_details"].strip():
                message += f"⚠️ *Blockers Details:*\n{form_data['blockers_details']}\n"
        elif form_data["blockers"] == "no":
            message += (
                f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ *Blockers:* No\n"
            )

        # Add a final separator
        message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        # Post the message with an edit button
        response = await client.chat_postMessage(
            channel=channel_id,
            text=message,
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message}
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✏️ Edit Update", "emoji": True},
                            "style": "primary",
                            "action_id": "edit_status_update",
                            "value": json.dumps({
                                "channel_id": channel_id,
                                "form_data": form_data,
                                "message_ts": None  # Will be set after message is posted
                            })
                        }
                    ]
                }
            ]
        )

        # Update the button value with the message timestamp
        if response["ok"]:
            message_ts = response["ts"]
            await client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=message,
                blocks=[
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": message}
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "✏️ Edit Update", "emoji": True},
                                "style": "primary",
                                "action_id": "edit_status_update",
                                "value": json.dumps({
                                    "channel_id": channel_id,
                                    "form_data": form_data,
                                    "message_ts": message_ts
                                })
                            }
                        ]
                    }
                ]
            )

        # Ask if they have another project to update
        await client.chat_postMessage(
            channel=user_id,
            text="Do you have another project you'd like to provide an update for?",
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "🔄 *Want to update another project?*"},
                    "accessory": {
                        "type": "static_select",
                        "placeholder": {"type": "plain_text", "text": "Make your choice ✨"},
                        "options": [
                            {"text": {"type": "plain_text", "text": "Yes, one more! 🚀"}, "value": "yes_another"},
                            {"text": {"type": "plain_text", "text": "That's all! 🎉"}, "value": "no_another"}
                        ],
                        "action_id": "another_update_choice"
                    }
                }
            ]
        )
    except Exception as e:
        logger.error(f"Error in status submission: {e}")
        logger.error(f"View state: {view['state']['values']}")
        await client.chat_postEphemeral(
            channel=user_id,
            user=user_id,
            text="😅 Oops! Something went wrong while posting your update. Please try again!"
        )

# Handle the "Yes" or "No" for another update
@app.action("another_update_choice")
async def handle_another_update(ack, body, client, logger):
    await ack()
    
    try:
        user_id = body["user"]["id"]
        choice = body["actions"][0]["selected_option"]["value"]

        if choice == "yes_another":
            project_channels = await get_relevant_project_channels()
            if project_channels:
                channel_options = [{"text": {"type": "plain_text", "text": channel["name"]}, "value": channel["id"]} for channel in project_channels]
                await client.chat_postMessage(
                    channel=user_id,
                    text="Which project channel would you like to update?",
                    blocks=[
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": "🔄 *Select another project channel to update:*"},
                            "accessory": {
                                "type": "static_select",
                                "placeholder": {"type": "plain_text", "text": "Choose a channel 📝"},
                                "options": channel_options,
                                "action_id": "select_project_channel"
                            }
                        }
                    ]
                )
            else:
                await client.chat_postMessage(
                    channel=user_id,
                    text="😕 It seems there are no more project channels available to update."
                )
        elif choice == "no_another":
            await client.chat_postMessage(
                channel=user_id,
                text="🎉 Awesome! Thanks for all your updates! Keep up the great work! 💪"
            )
    except Exception as e:
        logger.error(f"Error in another update choice: {e}")
        await client.chat_postEphemeral(
            channel=user_id,
            user=user_id,
            text="😅 Oops! Something went wrong while processing your choice. Please try again!"
        )

# Function to check if it's 5 PM in user's timezone
def is_5pm_in_timezone(user_tz: str) -> bool:
    """Check if it's 5 PM in the user's timezone."""
    try:
        current_time = get_user_local_time(user_tz)
        is_5pm = current_time.hour == 17 and current_time.minute == 0
        logger.debug(f"Time check for {user_tz}: {current_time.strftime('%I:%M %p')} - Is 5 PM? {is_5pm}")
        return is_5pm
    except Exception as e:
        logger.error(f"Error checking time for timezone {user_tz}: {e}")
        return False

# Function to send reminders to all developers
async def send_daily_reminders():
    """Send reminders to all developers at 5 PM in their local timezone."""
    try:
        # Get all developer user IDs
        developer_ids = await get_developer_user_ids()
        logger.info(f"Running scheduled reminder check for {len(developer_ids)} developers")
        
        for user_id in developer_ids:
            try:
                # Get user's timezone
                user_tz = await get_user_timezone(user_id)
                current_time = get_user_local_time(user_tz)
                
                # Check if it's 5 PM in their timezone
                if is_5pm_in_timezone(user_tz):
                    logger.info(f"🕔 It's 5 PM for user {user_id} in {user_tz} - Sending reminder")
                    await send_initial_prompt(user_id)
                else:
                    logger.debug(f"Not 5 PM yet for user {user_id} in {user_tz}. Current time: {current_time.strftime('%I:%M %p')}")
            
            except Exception as e:
                logger.error(f"Error processing reminder for user {user_id}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in send_daily_reminders: {e}")

# Function to schedule the reminder checks
async def schedule_reminders():
    """Schedule the reminder checks to run every minute."""
    logger.info("Starting reminder scheduler...")
    # Schedule the reminder check to run every minute
    aioschedule.every(1).minutes.do(send_daily_reminders)
    
    while True:
        try:
            await aioschedule.run_pending()
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
            await asyncio.sleep(1)  # Still sleep to prevent tight loop on error

async def main():
    # Set up the app to listen on the specified port
    port = int(os.environ.get("PORT", 3000))
    
    # Initialize Socket Mode handler
    handler = AsyncSocketModeHandler(app, os.environ.get("APP_LEVEL_TOKEN"))
    
    # Start the app in Socket Mode
    await handler.start_async()
    
    # Start the reminder scheduler in the background
    asyncio.create_task(schedule_reminders())
    
    # Also start the HTTP server for slash commands and interactivity
    from slack_bolt.adapter.asgi import SlackRequestHandler
    from asgiref.wsgi import WsgiToAsgi
    from flask import Flask, request
    
    flask_app = Flask(__name__)
    slack_handler = SlackRequestHandler(app)
    
    @flask_app.route("/slack/events", methods=["POST"])
    async def slack_events():
        return await slack_handler.handle(request)
    
    # Start Flask in a separate thread
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    
    config = Config()
    config.bind = [f"0.0.0.0:{port}"]
    
    await serve(flask_app, config)

if __name__ == "__main__":
    # Environment variables are now loaded from .env file
    # Send a test message if needed
    async def send_test_message():
        try:
            test_channel = os.environ.get("TEST_CHANNEL", "#test_channel")
            await client.chat_postMessage(channel=test_channel, text="🤖 Bot is starting up! Ready to help with status updates! 🚀")
        except Exception as e:
            logger.error(f"Could not send test message: {e}")
    
    # Run the main function
    asyncio.run(main(), debug=True)

# Add handler for the edit submission
@app.view("status_submission_edit")
async def handle_status_edit_submission(ack, body, view, client, logger):
    """Handle the submission of an edited status update."""
    await ack()
    logger.info(f"Edit submission received: {body}")
    
    try:
        # Get the metadata
        metadata = json.loads(view["private_metadata"])
        channel_id = metadata["channel_id"]
        message_ts = metadata["message_ts"]
        user_id = body["user"]["id"]
        
        # Process the form data using the safe extraction function
        form_data = get_form_data(view["state"]["values"])
        
        # Get user's timezone
        user_tz = await get_user_timezone(user_id)
        current_time = get_user_local_time(user_tz)
        
        # Build the message (same as original submission)
        priority_emoji = {
            "high": "🔴",
            "medium": "🟡",
            "low": "🟢"
        }.get(form_data["priority"], "🟡")

        message = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Status Update from <@{user_id}>* (edited)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🕒 *Local Time:* {current_time.strftime('%I:%M %p')} ({user_tz})\n"
            f"🎯 *Priority:* {priority_emoji} {form_data['priority'].upper()}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 *Update:*\n"
            f"{form_data['update_text']}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏭️ *Next Steps:*\n"
            f"{form_data['next_steps']}\n"
        )
        
        if form_data["technical_details"] and form_data["technical_details"].strip():
            message += (
                f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤓 *Dev Notes:*\n"
                f"{form_data['technical_details']}\n"
            )

        if form_data["blockers"] == "yes":
            message += (
                f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🚫 *Blockers:* Yes\n"
            )
            if form_data["blockers_details"] and form_data["blockers_details"].strip():
                message += f"⚠️ *Blockers Details:*\n{form_data['blockers_details']}\n"
        elif form_data["blockers"] == "no":
            message += (
                f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ *Blockers:* No\n"
            )

        message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        # Update the original message
        await client.chat_update(
            channel=channel_id,
            ts=message_ts,
            text=message,
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message}
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✏️ Edit Update", "emoji": True},
                            "style": "primary",
                            "action_id": "edit_status_update",
                            "value": json.dumps({
                                "channel_id": channel_id,
                                "form_data": form_data,
                                "message_ts": message_ts
                            })
                        }
                    ]
                }
            ]
        )

        # Notify the user
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="✅ Your status update has been edited!"
        )
    except Exception as e:
        logger.error(f"Error in status edit submission: {e}")
        logger.error(f"Full body: {body}")
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="😅 Sorry, there was an error updating your status. Please try again."
        )
