import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Bot configuration
BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
APP_LEVEL_TOKEN = os.environ.get("APP_LEVEL_TOKEN")
DEVELOPER_USERGROUP_ID = os.environ.get("DEVELOPER_USERGROUP_ID")
FALLBACK_DEVELOPER_IDS = os.environ.get("FALLBACK_DEVELOPER_IDS", "").split(",")
TEST_CHANNEL = os.environ.get("TEST_CHANNEL", "#test_channel")

# Server configuration
PORT = int(os.environ.get("PORT", 3000))

# Validate required environment variables
def validate_config():
    """Validate that all required environment variables are set."""
    required_vars = {
        "SLACK_BOT_TOKEN": BOT_TOKEN,
        "APP_LEVEL_TOKEN": APP_LEVEL_TOKEN
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}\n"
            "Please set these in your .env file."
        )
    
    # Validate developer configuration
    if not DEVELOPER_USERGROUP_ID and not any(FALLBACK_DEVELOPER_IDS):
        logging.warning(
            "Neither DEVELOPER_USERGROUP_ID nor FALLBACK_DEVELOPER_IDS is set.\n"
            "The bot will not be able to identify developers."
        )

# Message templates
MESSAGES = {
    "welcome": "🤖 Welcome to the EOD Status Update Bot! I'll help you share your daily updates.",
    "not_developer": "⚠️ Sorry, this command is only available to developers.",
    "no_channels": "😕 It seems there are no project channels available to update right now.",
    "update_complete": "🎉 Awesome! Thanks for your update! Keep up the great work! 💪",
    "error_generic": "😅 Oops! Something went wrong. Please try again!",
    "reminder": "📊 Time for your daily status update! Do you have any updates to share today?"
}

# Modal configuration
MODAL_CONFIG = {
    "title": "Project Status Update",
    "submit_text": "Submit",
    "edit_title": "Edit Status Update",
    "edit_submit_text": "Update"
}

# Priority levels and their emojis
PRIORITIES = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🟢"
}

# Initialize configuration
validate_config() 