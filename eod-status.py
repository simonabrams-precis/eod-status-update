import os
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.web.async_client import AsyncWebClient
from datetime import datetime, time
import pytz
import asyncio
from dotenv import load_dotenv
import logging

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
    await say("Bot is up and running!")

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
    try:
        usergroup_id = os.environ.get("DEVELOPER_USERGROUP_ID")
        users_in_group = await client.usergroups_users_list(usergroup=usergroup_id)
        if users_in_group and users_in_group["ok"]:
            return users_in_group["users"]
        else:
            logger.error(f"Error fetching users in group: {users_in_group.get('error')}")
            return []
    except Exception as e:
        logger.error(f"Error getting developer user IDs: {e}")
        return []

# Modal definition for submitting status
def build_status_modal(channel_id):
    return {
        "type": "modal",
        "callback_id": "status_submission",
        "private_metadata": channel_id,
        "title": {"type": "plain_text", "text": "Project Status Update"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"Updating status for <#{channel_id}>"}
            },
            {
                "type": "input",
                "block_id": "update_block",
                "label": {"type": "plain_text", "text": "What's your update?"},
                "element": {"type": "plain_text_input", "multiline": True, "action_id": "update_text"}
            },
            {
                "type": "input",
                "block_id": "technical_details_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "Technical Details (optional)"},
                "element": {"type": "plain_text_input", "multiline": True, "action_id": "technical_details_text"}
            }
        ],
        "submit": {"type": "plain_text", "text": "Submit"}
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
                    "text": {"type": "mrkdwn", "text": "Do you have any status updates for today?"},
                    "accessory": {
                        "type": "static_select",
                        "placeholder": {"type": "plain_text", "text": "Select an option"},
                        "options": [
                            {"text": {"type": "plain_text", "text": "Yes"}, "value": "yes_update"},
                            {"text": {"type": "plain_text", "text": "No"}, "value": "no_update"}
                        ],
                        "action_id": "initial_update_choice"
                    }
                }
            ]
        )
    except Exception as e:
        print(f"Error sending initial prompt to {user_id}: {e}")

# Handle the initial "Yes" or "No" response
@app.action("initial_update_choice")
async def handle_initial_choice(ack, body, client, logger):
    # Log the incoming request body for debugging
    logger.info(f"Initial choice body: {body}")
    
    # Acknowledge the request immediately
    await ack()
    
    user_id = body["user"]["id"]
    choice = body["actions"][0]["selected_option"]["value"]

    if choice == "yes_update":
        project_channels = await get_relevant_project_channels()
        # log the project channels
        logger.info(f"Project channels: {project_channels}")
        if project_channels:
            channel_options = [{"text": {"type": "plain_text", "text": channel["name"]}, "value": channel["id"]} for channel in project_channels]
            await client.chat_postMessage(
                channel=user_id,
                text="Which project channel would you like to update?",
                blocks=[
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "Please select the project channel:"},
                        "accessory": {
                            "type": "static_select",
                            "placeholder": {"type": "plain_text", "text": "Select a channel"},
                            "options": channel_options,
                            "action_id": "select_project_channel"
                        }
                    }
                ]
            )
        else:
            await client.chat_postMessage(
                channel=user_id,
                text="It seems there are no project channels available to update right now."
            )
    elif choice == "no_update":
        await client.chat_postMessage(
            channel=user_id,
            text="Okay, no problem. Have a productive day!"
        )

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

# Handle the selection of the project channel
@app.action("select_project_channel")
async def handle_project_selection(ack, body, client, logger):
    await ack()
    
    try:
        user_id = body["user"]["id"]
        channel_id = body["actions"][0]["selected_option"]["value"]
        await client.views_open(
            trigger_id=body["trigger_id"],
            view=build_status_modal(channel_id)
        )
    except Exception as e:
        logger.error(f"Error in project selection: {e}")
        await client.chat_postEphemeral(
            channel=user_id,
            user=user_id,
            text="Sorry, there was an error opening the status form. Please try again."
        )

# Handle the modal submission
@app.view("status_submission")
async def handle_status_submission(ack, body, view, client, logger):
    await ack()
    
    try:
        user_id = body["user"]["id"]
        channel_id = body["view"]["private_metadata"]
        update_text = view["state"]["values"]["update_block"]["update_text"]["value"]
        technical_details = view["state"]["values"]["technical_details_block"]["technical_details_text"]["value"] if "technical_details_block" in view["state"]["values"] and "technical_details_text" in view["state"]["values"]["technical_details_block"] else None

        message = f"*Status Update from <@{user_id}>:*\n{update_text}"
        if technical_details:
            message += f"\n*Technical Details:*\n{technical_details}"

        await client.chat_postMessage(
            channel=channel_id,
            text=message
        )
        
        # Ask if they have another project to update
        await client.chat_postMessage(
            channel=user_id,
            text="Do you have another project you'd like to provide an update for?",
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Another update?"},
                    "accessory": {
                        "type": "static_select",
                        "placeholder": {"type": "plain_text", "text": "Select an option"},
                        "options": [
                            {"text": {"type": "plain_text", "text": "Yes"}, "value": "yes_another"},
                            {"text": {"type": "plain_text", "text": "No"}, "value": "no_another"}
                        ],
                        "action_id": "another_update_choice"
                    }
                }
            ]
        )
    except Exception as e:
        logger.error(f"Error in status submission: {e}")
        await client.chat_postEphemeral(
            channel=user_id,
            user=user_id,
            text="Sorry, there was an error posting your update. Please try again."
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
                            "text": {"type": "mrkdwn", "text": "Please select another project channel:"},
                            "accessory": {
                                "type": "static_select",
                                "placeholder": {"type": "plain_text", "text": "Select a channel"},
                                "options": channel_options,
                                "action_id": "select_project_channel"
                            }
                        }
                    ]
                )
            else:
                await client.chat_postMessage(
                    channel=user_id,
                    text="It seems there are no project channels available to update right now."
                )
        elif choice == "no_another":
            await client.chat_postMessage(
                channel=user_id,
                text="Got it. Thanks for your updates!"
            )
    except Exception as e:
        logger.error(f"Error in another update choice: {e}")
        await client.chat_postEphemeral(
            channel=user_id,
            user=user_id,
            text="Sorry, there was an error processing your choice. Please try again."
        )

async def main():
    # Set up the app to listen on the specified port
    port = int(os.environ.get("PORT", 3000))
    
    # Initialize Socket Mode handler
    handler = AsyncSocketModeHandler(app, os.environ.get("APP_LEVEL_TOKEN"))
    
    # Start the app in Socket Mode
    await handler.start_async()
    
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
            await client.chat_postMessage(channel=test_channel, text="Bot is starting up!")
        except Exception as e:
            logger.error(f"Could not send test message: {e}")
    
    # Run the main function
    asyncio.run(main(), debug=True)