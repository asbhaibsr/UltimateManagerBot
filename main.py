#  main.py

import asyncio
import logging
from bot import app, flask_app
from threading import Thread
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_flask():
    """Run Flask server"""
    flask_app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

async def run_bot():
    """Run Telegram bot"""
    logger.info("Starting Telegram Bot...")
    await app.start()
    
    bot_info = await app.get_me()
    logger.info(f"Bot started as @{bot_info.username}")
    
    # Keep bot running
    logger.info("Bot is now running...")
    await asyncio.sleep(86400)  # Run for 24 hours
    
    await app.stop()
    logger.info("Bot stopped")

def main():
    """Main function to run both Flask and Bot"""
    # Start Flask server in separate thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask server started on port 8080")
    
    # Wait for Flask to start
    time.sleep(2)
    
    # Run Telegram bot
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")

if __name__ == "__main__":
    main()
