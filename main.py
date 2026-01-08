# main.py

import asyncio
from pyrogram import Client, idle
from config import Config
from utils import web_server
from aiohttp import web

# Plugins folder define
plugins = dict(root="plugins")

app = Client(
    "MovieBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=plugins
)

async def start_services():
    print("Starting Bot...")
    await app.start()
    
    print("Starting Web Server for Koyeb...")
    # Setup aiohttp runner
    server = await web_server()
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', Config.PORT)
    await site.start()
    
    print("Bot and Server Started Successfully!")
    
    # Keep the bot running
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_services())
