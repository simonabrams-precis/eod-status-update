import logging
import pytz
from datetime import datetime
from slack_sdk.web.async_client import AsyncWebClient

logger = logging.getLogger(__name__)

def setup_timezone():
    """Set up timezone handling for the application."""
    # Ensure UTC is available
    if 'UTC' not in pytz.all_timezones:
        logger.warning("UTC timezone not found in pytz database")
    logger.info("Timezone handling initialized")

async def get_user_timezone(client: AsyncWebClient, user_id: str) -> str:
    """Get a user's timezone from their Slack profile."""
    try:
        user_info = await client.users_info(user=user_id)
        if user_info["ok"]:
            tz = user_info["user"].get("tz", "UTC")
            logger.debug(f"Got timezone {tz} for user {user_id}")
            return tz
        logger.warning(f"Could not get timezone for user {user_id}, defaulting to UTC")
        return "UTC"
    except Exception as e:
        logger.error(f"Error getting timezone for user {user_id}: {e}")
        return "UTC"

def get_user_local_time(user_tz: str) -> datetime:
    """Get current time in user's timezone."""
    try:
        tz = pytz.timezone(user_tz)
        current_time = datetime.now(tz)
        logger.debug(f"Current time in {user_tz}: {current_time.strftime('%I:%M %p')}")
        return current_time
    except Exception as e:
        logger.error(f"Error converting to timezone {user_tz}: {e}")
        return datetime.now(pytz.UTC)

def format_time_for_display(dt: datetime, include_timezone: bool = True) -> str:
    """Format a datetime object for display in messages."""
    try:
        if include_timezone:
            return dt.strftime("%I:%M %p %Z")
        return dt.strftime("%I:%M %p")
    except Exception as e:
        logger.error(f"Error formatting time {dt}: {e}")
        return "Unknown time" 