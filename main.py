import logging
from pyrogram import Client
from aiohttp import web
import asyncio
from config import Config
from database import db
import nest_asyncio

# Apply nest_asyncio to fix event loop issues
nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize bot
app = Client(
    "MovieBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="plugins")
)

# Web server for Koyeb health check
async def web_server():
    async def handle_home(request):
        return web.Response(text="Bot is Running and Healthy!", status=200)

    async def handle_health(request):
        return web.json_response({"status": "ok", "bot": "running"})

    server = web.Application()
    server.add_routes([
        web.get('/', handle_home),
        web.get('/health', handle_health)
    ])
    return server

async def main():
    # Initialize database
    await db.init_db()
    logger.info("Database initialized")
    
    # Start web server
    server = await web_server()
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', Config.PORT)
    await site.start()
    logger.info(f"Web server started on port {Config.PORT}")
    
    # Start bot
    await app.start()
    me = await app.get_me()
    logger.info(f"Bot Started: @{me.username}")
    logger.info("Bot and Server Started Successfully!")
    
    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
