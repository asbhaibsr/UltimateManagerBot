# main.py

import asyncio
from pyrogram import Client, idle
from config import Config
from utils import web_server
from aiohttp import web
import logging
from database import db  # ADDED THIS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

plugins = dict(root="plugins")

app = Client(
    "MovieBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=plugins
)

async def start_services():
    logger.info("Starting Bot...")
    
    # Initialize database - ADDED THIS
    await db.setup_indexes()
    logger.info("Database initialized")
    
    await app.start()
    
    # Get bot info
    bot = await app.get_me()
    logger.info(f"Bot Started: @{bot.username}")
    
    logger.info("Starting Web Server for Koyeb...")
    server = await web_server()
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', Config.PORT)
    await site.start()
    logger.info(f"Server running on port {Config.PORT}")
    
    logger.info("Bot and Server Started Successfully!")
    
    # Send startup message to log channel
    try:
        await app.send_message(
            Config.LOG_CHANNEL,
            f"✅ **Bot Started Successfully!**\n\n"
            f"🤖 **Bot:** @{bot.username}\n"
            f"🆔 **ID:** `{bot.id}`\n"
            f"📊 **Database:** ✅ Connected\n"
            f"⏰ **Start Time:** {asyncio.get_event_loop().time()}"
        )
    except:
        pass
    
    await idle()
    
    logger.info("Stopping Bot...")
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        loop.close()
