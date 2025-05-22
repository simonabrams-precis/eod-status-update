import os
import logging
import asyncio
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)

async def retry_with_backoff(func, max_retries=3, initial_delay=1, *args, **kwargs):
    """
    Retry a function with exponential backoff.
    """
    delay = initial_delay
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except SlackApiError as e:
            last_error = e
            if e.response["error"] == "ratelimited":
                retry_after = int(e.response.get("headers", {}).get("Retry-After", delay))
                logger.warning(f"Rate limited. Retrying after {retry_after} seconds...")
                await asyncio.sleep(retry_after)
                delay *= 2  # Exponential backoff
            else:
                raise
        except Exception as e:
            last_error = e
            logger.error(f"Error in attempt {attempt + 1}: {e}")
            await asyncio.sleep(delay)
            delay *= 2
    
    logger.error(f"All retry attempts failed. Last error: {last_error}")
    raise last_error

async def get_developer_user_ids(client: AsyncWebClient) -> list[str]:
    """Get list of developer user IDs from the usergroup."""
    try:
        # Try to get developers from usergroup first
        usergroup_id = os.environ.get("DEVELOPER_USERGROUP_ID")
        logger.info(f"Developer usergroup ID from environment: {usergroup_id}")
        
        if usergroup_id:
            try:
                logger.info(f"Attempting to fetch users from usergroup {usergroup_id}")
                # Call the Slack API method directly with retry wrapper
                response = await retry_with_backoff(
                    client.usergroups_users_list,
                    usergroup=usergroup_id
                )
                
                if response["ok"]:
                    users = response["users"]
                    logger.info(f"Successfully fetched {len(users)} users from usergroup")
                    return users
                else:
                    error = response.get('error', 'unknown error')
                    if error == 'missing_scope':
                        logger.warning("Missing usergroups:read scope. Using fallback developer list.")
                    else:
                        logger.error(f"Error in usergroup response: {error}")
            except SlackApiError as e:
                if e.response["error"] == "missing_scope":
                    logger.error("Missing 'usergroups:read' scope in Slack app permissions")
                elif e.response["error"] == "ratelimited":
                    logger.error("Rate limited by Slack API")
                else:
                    logger.error(f"Slack API error fetching usergroup users: {e.response['error']}")
            except Exception as e:
                logger.error(f"Error fetching usergroup users: {e}")
        
        # Fallback to environment variable if usergroup fails
        fallback_ids = get_fallback_developer_ids()
        if fallback_ids:
            logger.info("Using fallback developer IDs from environment")
            return fallback_ids
        
        logger.warning("No developer IDs found! Please configure DEVELOPER_USERGROUP_ID or FALLBACK_DEVELOPER_IDS")
        return []
    except Exception as e:
        logger.error(f"Error getting developer IDs: {e}")
        return []

def get_fallback_developer_ids() -> list[str]:
    """Get fallback developer IDs from environment variable."""
    try:
        fallback_ids = os.environ.get("FALLBACK_DEVELOPER_IDS", "")
        if fallback_ids:
            ids = [id.strip() for id in fallback_ids.split(",") if id.strip()]
            logger.info(f"Using fallback list of {len(ids)} developers")
            return ids
        logger.error("No fallback developer IDs configured. Please set FALLBACK_DEVELOPER_IDS in environment variables.")
        return []
    except Exception as e:
        logger.error(f"Error getting fallback developer IDs: {e}")
        return []

async def is_developer(client: AsyncWebClient, user_id: str) -> bool:
    """Check if a user ID belongs to a developer."""
    try:
        developer_ids = await get_developer_user_ids(client)
        return user_id in developer_ids
    except Exception as e:
        logger.error(f"Error checking if user {user_id} is a developer: {e}")
        return False

async def get_relevant_project_channels(client: AsyncWebClient) -> list[dict]:
    """Get list of relevant project channels for status updates."""
    try:
        # Get all channels the bot is in with retry logic
        response = await retry_with_backoff(
            client.conversations_list,
            types="public_channel,private_channel",
            exclude_archived=True
        )
        
        if not response["ok"]:
            logger.error(f"Error fetching channels: {response.get('error')}")
            return []
        
        # Filter channels based on naming convention or other criteria
        channels = []
        for channel in response["channels"]:
            # Skip channels that start with '#' (archived) or are general
            if channel["name"].startswith("#") or channel["name"] == "general":
                continue
            channels.append({
                "id": channel["id"],
                "name": channel["name"]
            })
        
        logger.info(f"Found {len(channels)} relevant project channels")
        return channels
    except Exception as e:
        logger.error(f"Error getting project channels: {e}")
        return [] 