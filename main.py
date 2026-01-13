import asyncio
import logging
import sys
import os
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(name)

class HealthHandler(BaseHTTPRequestHandler):
    """Simple HTTP server for health checks"""
    def do_GET(self):
        if self.path in ['/health', '/', '/ping']:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Movie Helper Bot - Status</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        text-align: center;
                        padding: 50px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                    }}
                    .container {{
                        background: rgba(255,255,255,0.1);
                        padding: 30px;
                        border-radius: 15px;
                        backdrop-filter: blur(10px);
                        max-width: 600px;
                        margin: 0 auto;
                    }}
                    h1 {{
                        font-size: 2.5em;
                        margin-bottom: 10px;
                    }}
                    .status {{
                        background: green;
                        color: white;
                        padding: 10px 20px;
                        border-radius: 25px;
                        display: inline-block;
                        margin: 20px 0;
                        font-size: 1.2em;
                    }}
                    .info {{
                        text-align: left;
                        margin-top: 20px;
                        background: rgba(255,255,255,0.1);
                        padding: 15px;
                        border-radius: 10px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🎬 Movie Helper Bot</h1>
                    <div class="status">✅ Bot is Running</div>
                    <p>This bot helps with movie recommendations, spelling correction, and more!</p>
                    
                    <div class="info">
                        <h3>📊 Server Status:</h3>
                        <p>• Service: <strong>Movie Helper Bot</strong></p>
                        <p>• Status: <strong>Active & Healthy</strong></p>
                        <p>• Health Check: <strong>Passing</strong></p>
                        <p>• Last Check: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                    </div>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()

def run_health_server():
    """Run simple HTTP server for health checks"""
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"✅ Health check server started on port {port}")
    server.serve_forever()

async def run_bot():
    """Run Telegram bot"""
    try:
        # Import bot after health server is started
        from bot import app
        
        logger.info("🚀 Starting Movie Helper Bot...")
        
        # Start the bot
        await app.start()
        
        # Get bot info
        bot_info = await app.get_me()
        logger.info(f"✅ Bot started as @{bot_info.username}")
        
        # Set bot commands
        try:
            from pyrogram.types import BotCommand
            
            commands = [
                BotCommand("start", "Start the bot"),
                BotCommand("help", "Get help"),
                BotCommand("settings", "Group settings"),
                BotCommand("stats", "Bot statistics"),
                BotCommand("ai", "Ask AI about movies"),
                BotCommand("addfsub", "Set force subscribe"),
                BotCommand("ping", "Check bot status"),
                BotCommand("id", "Get user/group ID")
            ]
            
            await app.set_bot_commands(commands)
            logger.info("✅ Bot commands set successfully")
        except Exception as e:
            logger.warning(f"⚠️ Could not set bot commands: {e}")
        
        # Send startup message to owner
        try:
            from config import Config
            await app.send_message(
                Config.OWNER_ID,
                f"🤖 Bot Started Successfully!\n\n"
                f"• Bot: @{bot_info.username}\n"
                f"• Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"• Status: ✅ Running"
            )
        except:
            pass
        
        logger.info("🤖 Bot is now running and ready to receive messages...")
        logger.info("📡 Waiting for messages...")
        
        # Keep bot running
        await idle()
        
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("⏹️ Bot stopped by user")
        await app.stop()
        sys.exit(0)

def main():
    """Main function to run both health server and bot"""
    # Start health server in separate thread
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    logger.info("⏳ Waiting 3 seconds for health server to start...")
    time.sleep(3)
    
    # Run Telegram bot
    asyncio.run(run_bot())

if __name__ == "__main__":
    main()
