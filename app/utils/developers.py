import os
import logging
import asyncio
import json
from datetime import datetime, timedelta
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)

# Cache for developer IDs with expiration
_developer_cache = {
    "ids": None,
    "expires_at": None
}

CACHE_DURATION = timedelta(minutes=5)  # Cache developer list for 5 minutes

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

async def get_developer_user_ids(client=None):
    """Get the list of developer user IDs, either from usergroup or fallback list."""
    global _developer_cache
    
    # Check if we have a valid cache
    if _developer_cache["ids"] is not None and _developer_cache["expires_at"] is not None:
        if datetime.now() < _developer_cache["expires_at"]:
            logger.debug("Using cached developer list")
            return _developer_cache["ids"]
    
    try:
        # Try usergroup first
        usergroup_id = os.environ.get("DEVELOPER_USERGROUP_ID")
        if usergroup_id:
            logger.info(f"Developer usergroup ID from environment: {usergroup_id}")
            logger.info(f"Attempting to fetch users from usergroup {usergroup_id}")
            
            try:
                if client is None:
                    raise ValueError("Slack client is required for usergroup fetch")
                
                response = await retry_with_backoff(
                    client.usergroups_users_list,
                    usergroup=usergroup_id
                )
                
                if response["ok"]:
                    user_ids = response["users"]
                    logger.info(f"Successfully fetched {len(user_ids)} users from usergroup")
                    
                    # Update cache
                    _developer_cache["ids"] = user_ids
                    _developer_cache["expires_at"] = datetime.now() + CACHE_DURATION
                    
                    return user_ids
                else:
                    logger.error(f"Failed to fetch usergroup users: {response.get('error')}")
            except SlackApiError as e:
                if e.response["error"] == "missing_scope":
                    logger.error("Missing required scope 'usergroups:read' for the Slack app")
                elif e.response["error"] == "ratelimited":
                    logger.error("Rate limited while fetching usergroup")
                else:
                    logger.error(f"Error fetching usergroup users: {e}")
            except Exception as e:
                logger.error(f"Unexpected error fetching usergroup users: {e}")
        
        # Fallback to environment variable if usergroup fails
        fallback_ids = os.environ.get("FALLBACK_DEVELOPER_IDS", "")
        if fallback_ids:
            user_ids = [uid.strip() for uid in fallback_ids.split(",") if uid.strip()]
            logger.info(f"Using fallback list with {len(user_ids)} developers")
            
            # Update cache
            _developer_cache["ids"] = user_ids
            _developer_cache["expires_at"] = datetime.now() + CACHE_DURATION
            
            return user_ids
        
        logger.error("No developer IDs found in usergroup or fallback list")
        return []
        
    except Exception as e:
        logger.error(f"Error in get_developer_user_ids: {e}")
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