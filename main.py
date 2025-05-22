import asyncio
import logging
from app.bot import create_app, start_app
from app.handlers.reminders import start_reminder_scheduler
from app.utils.timezone import setup_timezone

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main entry point for the application."""
    try:
        # Set up timezone handling
        setup_timezone()
        
        # Create and start the app
        app = create_app()
        
        # Start the reminder scheduler in the background
        asyncio.create_task(start_reminder_scheduler(app))
        
        # Start the app
        await start_app(app)
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 