import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from datetime import datetime, time
import pytz
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize your Slack app with your bot token
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))

# Handle URL verification challenge
@app.event("url_verification")
def handle_verification(body, ack):
    ack({"challenge": body["challenge"]})

# Add a simple health check endpoint
@app.message("health_check")
def handle_health_check(message, say):
    say("Bot is up and running!")

# Add slash command to manually trigger EOD status update
@app.command("/eod-status")
def handle_eod_status_command(ack, body, client, logger):
    # Acknowledge the command request immediately
    ack()
    logger.info(f"EOD status command triggered by {body['user_id']}")
    
    # Use asyncio to run the async function in a new event loop
    async def _send_prompt():
        try:
            await send_initial_prompt(body["user_id"])
        except Exception as e:
            logger.error(f"Error in eod-status command: {e}")
            try:
                await client.chat_postEphemeral(
                    channel=body["channel_id"],
                    user=body["user_id"],
                    text="Sorry, there was an error processing your request. Please try again."
                )
            except Exception as e2:
                logger.error(f"Error sending error message: {e2}")

    # Create a new event loop and run the async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_send_prompt())
    finally:
        loop.close()

# Function to get the list of developer user IDs (replace with your logic)
def get_developer_user_ids():
    try:
        usergroup_id = os.environ.get("DEVELOPER_USERGROUP_ID")  # Get from environment variable
        users_in_group = client.usergroups.users.list(usergroup=usergroup_id)
        if users_in_group and users_in_group["ok"]:
            return users_in_group["users"]
        else:
            print(f"Error fetching users in group: {users_in_group.get('error')}")
            return []
    except Exception as e:
        print(f"Error getting developer user IDs: {e}")
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
        client.chat_postMessage(
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
async def handle_initial_choice(ack, body, client):
    await ack()
    user_id = body["user"]["id"]
    choice = body["actions"][0]["value"]

    if choice == "yes_update":
        # Get a list of relevant project channels (you'll need to define this logic)
        # For now, let's assume you have a function to get these
        project_channels = await get_relevant_project_channels()
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
    # Example: Fetch all public channels. You might want to filter based on naming conventions or user group membership.
    try:
        channels_response = await client.conversations_list(types="public_channel")
        if channels_response and channels_response["ok"]:
            return channels_response["channels"]
        else:
            print(f"Error fetching channels: {channels_response.get('error')}")
            return []
    except Exception as e:
        print(f"Error getting project channels: {e}")
        return []

# Handle the selection of the project channel
@app.action("select_project_channel")
async def handle_project_selection(ack, body, client):
    await ack()
    user_id = body["user"]["id"]
    channel_id = body["actions"][0]["selected_option"]["value"]
    await client.views_open(
        trigger_id=body["trigger_id"],
        view=build_status_modal(channel_id)
    )

# Handle the modal submission
@app.view("status_submission")
async def handle_status_submission(ack, body, view, client):
    await ack()
    user_id = body["user"]["id"]
    channel_id = body["view"]["private_metadata"]
    update_text = view["state"]["values"]["update_block"]["update_text"]["value"]
    technical_details = view["state"]["values"]["technical_details_block"]["technical_details_text"]["value"] if "technical_details_block" in view["state"]["values"] and "technical_details_text" in view["state"]["values"]["technical_details_block"] else None

    message = f"*Status Update from <@{user_id}>:*\n{update_text}"
    if technical_details:
        message += f"\n*Technical Details:*\n{technical_details}"

    try:
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
        print(f"Error sending status update to {channel_id}: {e}")
        await client.chat_postEphemeral(
            channel=user_id,
            text=f"There was an error posting your update to <#{channel_id}>. Please try again."
        )

# Handle the "Yes" or "No" for another update
@app.action("another_update_choice")
async def handle_another_update(ack, body, client):
    await ack()
    user_id = body["user"]["id"]
    choice = body["actions"][0]["value"]

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

# Schedule the daily reminders (adjust time as needed)
async def schedule_reminders():
    target_reminder_time = time(16, 0, 0)  # 4:00 PM EST
    ny_tz = pytz.timezone("America/New_York")

    while True:
        now = datetime.now(ny_tz).time()
        today = datetime.now(ny_tz).date()
        if today.weekday() < 5: # Monday to Friday
            if now.hour == target_reminder_time.hour and now.minute == target_reminder_time.minute and now.second == 0:
                developers = get_developer_user_ids()
                for dev_id in developers:
                    await send_initial_prompt(dev_id)
        await asyncio.sleep(60) # Check every minute

async def main():
    # Set up the app to listen on the specified port
    port = int(os.environ.get("PORT", 3000))
    
    # Start the Slack Bolt app
    from threading import Thread
    bolt_thread = Thread(target=lambda: app.start(port=port))
    bolt_thread.daemon = True
    bolt_thread.start()
    
    # Start the reminder schedule
    await schedule_reminders()

if __name__ == "__main__":
    # Environment variables are now loaded from .env file
    # Send a test message if needed
    try:
        test_channel = os.environ.get("TEST_CHANNEL", "#test_channel")
        client.chat_postMessage(channel=test_channel, text="Bot is starting up!")
    except Exception as e:
        print(f"Could not send test message: {e}")
    
    # Run the main function
    asyncio.run(main(), debug=True)