import os
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.web.async_client import AsyncWebClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_app():
    """Create and configure the Slack bot application."""
    # Initialize the app with bot token
    app = AsyncApp(token=os.environ.get("SLACK_BOT_TOKEN"))
    
    # Create client and store it in app's context
    client = AsyncWebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
    app._client = client  # Store client in private attribute
    
    # Register handlers
    from app.handlers.status import register_status_handlers
    from app.handlers.reminders import register_reminder_handlers
    from app.handlers.commands import register_command_handlers
    
    register_status_handlers(app)
    register_reminder_handlers(app)
    register_command_handlers(app)
    
    return app

async def start_app(app):
    """Start the bot in socket mode."""
    handler = AsyncSocketModeHandler(app, os.environ.get("APP_LEVEL_TOKEN"))
    await handler.start_async() 