import os
import logging
import asyncio
import aioschedule
from datetime import datetime
import pytz
from app.utils.timezone import get_user_timezone, get_user_local_time
from app.utils.developers import get_developer_user_ids

logger = logging.getLogger(__name__)

async def send_initial_prompt(client, user_id):
    """Send the initial status update prompt to a user."""
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
        logger.error(f"Error sending initial prompt to {user_id}: {e}")

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

async def send_daily_reminders(app):
    """Send reminders to all developers at 5 PM in their local timezone."""
    try:
        # Get all developer user IDs
        developer_ids = await get_developer_user_ids(app._client)
        logger.info(f"Running scheduled reminder check for {len(developer_ids)} developers")
        
        for user_id in developer_ids:
            try:
                # Get user's timezone
                user_tz = await get_user_timezone(app._client, user_id)
                current_time = get_user_local_time(user_tz)
                
                # Check if it's 5 PM in their timezone
                if is_5pm_in_timezone(user_tz):
                    logger.info(f"🕔 It's 5 PM for user {user_id} in {user_tz} - Sending reminder")
                    await send_initial_prompt(app._client, user_id)
                else:
                    logger.debug(f"Not 5 PM yet for user {user_id} in {user_tz}. Current time: {current_time.strftime('%I:%M %p')}")
            
            except Exception as e:
                logger.error(f"Error processing reminder for user {user_id}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in send_daily_reminders: {e}")

async def start_reminder_scheduler(app):
    """Start the reminder scheduler."""
    logger.info("Starting reminder scheduler...")
    
    def create_reminder_task():
        """Create a task for running reminders."""
        return asyncio.create_task(send_daily_reminders(app))
    
    # Schedule the reminder check to run every minute
    aioschedule.every(1).minutes.do(create_reminder_task)
    
    while True:
        try:
            # Run pending jobs and await their completion
            for job in aioschedule.jobs:
                if job.should_run:
                    task = job.job_func()
                    if asyncio.iscoroutine(task):
                        await task
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
            await asyncio.sleep(1)  # Still sleep to prevent tight loop on error

def register_reminder_handlers(app):
    """Register all reminder-related handlers."""
    
    @app.command("/test-reminders")
    async def handle_test_reminders(ack, body, client, logger):
        """Handle the test-reminders command."""
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
                    await send_initial_prompt(client, user_id)
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