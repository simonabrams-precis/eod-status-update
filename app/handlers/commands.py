import logging
from app.utils.developers import is_developer, get_developer_user_ids
from app.handlers.reminders import send_initial_prompt

logger = logging.getLogger(__name__)

def register_command_handlers(app):
    """Register all slash command handlers."""
    
    @app.command("/eod-status")
    async def handle_eod_status_command(ack, body, client, logger):
        """Handle the /eod-status command."""
        # Acknowledge the command request immediately
        await ack()
        user_id = body["user_id"]
        logger.info(f"EOD status command triggered by {user_id}")
        
        # Get developer IDs to check if user is authorized
        developer_ids = await get_developer_user_ids(client)
        if not developer_ids:
            logger.warning("No developer IDs found! Please configure DEVELOPER_USERGROUP_ID or FALLBACK_DEVELOPER_IDS")
            await client.chat_postMessage(
                channel=user_id,
                text="⚠️ Bot configuration error: No developer IDs found! Please check your configuration:\n"
                     "1. Add `usergroups:read` scope to your Slack app\n"
                     "2. Set `DEVELOPER_USERGROUP_ID` in your environment\n"
                     "3. Or set `FALLBACK_DEVELOPER_IDS` as a comma-separated list"
            )
            return
        
        # Check if user is a developer
        if user_id not in developer_ids:
            logger.warning(f"Non-developer user {user_id} attempted to use /eod-status command")
            await client.chat_postEphemeral(
                channel=user_id,
                user=user_id,
                text="Sorry, this command is only available to developers."
            )
            return
        
        # Send the initial prompt to start the status update flow
        await send_initial_prompt(client, user_id)

    @app.message("health_check")
    async def handle_health_check(message, say):
        """Handle the health check message."""
        await say("🤖 Bot is up and running! All systems go! 🚀")

    @app.event("url_verification")
    async def handle_verification(body, ack):
        """Handle Slack's URL verification challenge."""
        await ack({"challenge": body["challenge"]}) 