import asyncio
import logging
import sys
import os
import time
import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
                        <p>• Platform: <strong>Koyeb Cloud</strong></p>
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
    
    def log_message(self, format, *args):
        # Disable default logging
        pass

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
        from database import initialize_database
        
        logger.info("🚀 Starting Movie Helper Bot...")
        
        # Initialize database
        logger.info("🔧 Initializing database...")
        await initialize_database()
        logger.info("✅ Database initialized successfully!")
        
        # Start the bot
        await app.start()
        
        # Get bot info
        bot_info = await app.get_me()
        logger.info(f"✅ Bot started as @{bot_info.username}")
        logger.info(f"✅ Bot ID: {bot_info.id}")
        
        # Set bot commands
        try:
            from pyrogram.types import BotCommand
            
            commands = [
                BotCommand("start", "Start the bot"),
                BotCommand("help", "Get help"),
                BotCommand("settings", "Group settings"),
                BotCommand("request", "Request a movie"),
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
            
            # Database stats
            from database import get_database_stats
            stats = await get_database_stats()
            
            startup_message = (
                f"🤖 **Bot Started Successfully!**\n\n"
                f"**📊 Bot Info:**\n"
                f"• Name: @{bot_info.username}\n"
                f"• ID: `{bot_info.id}`\n"
                f"• Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"• Server: Koyeb Cloud\n"
                f"• Status: ✅ Running\n\n"
                f"**📈 Database Stats:**\n"
                f"• Users: {stats['active_users']}\n"
                f"• Groups: {stats['active_groups']}\n"
                f"• Premium: {stats['premium_groups']['active']}\n\n"
                f"**🔗 Health Check:**\n"
                f"http://0.0.0.0:8080/health\n\n"
                f"**✅ Bot is ready to receive messages!**"
            )
            
            await app.send_message(Config.OWNER_ID, startup_message)
            logger.info("✅ Startup message sent to owner")
            
        except Exception as e:
            logger.error(f"⚠️ Could not send startup message: {e}")
        
        logger.info("🤖 Bot is now running and ready to receive messages...")
        logger.info("📡 Waiting for messages...")
        
        print("\n" + "="*60)
        print("🎬 MOVIE HELPER BOT - RUNNING")
        print("="*60)
        print(f"Bot: @{bot_info.username}")
        print(f"ID: {bot_info.id}")
        print(f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Status: 🟢 ONLINE")
        print("="*60 + "\n")
        
        # Keep bot running forever
        try:
            while True:
                # Check database connection periodically
                try:
                    from database import get_database_stats
                    stats = await get_database_stats()
                    
                    # Log periodic stats every 6 hours
                    current_hour = datetime.datetime.now().hour
                    if current_hour % 6 == 0:
                        logger.info(
                            f"📊 Periodic Stats - "
                            f"Users: {stats['active_users']}, "
                            f"Groups: {stats['active_groups']}, "
                            f"Premium: {stats['premium_groups']['active']}"
                        )
                        
                        # Cleanup old data every 24 hours
                        if current_hour == 0:
                            from database import cleanup_all_old_data
                            cleaned = await cleanup_all_old_data()
                            if cleaned > 0:
                                logger.info(f"🧹 Cleaned {cleaned} old records")
                except Exception as e:
                    logger.error(f"Periodic check error: {e}")
                
                await asyncio.sleep(3600)  # Sleep for 1 hour
                
        except KeyboardInterrupt:
            logger.info("⏹️ Bot stopped by user")
            
            # Send shutdown message to owner
            try:
                from config import Config
                await app.send_message(
                    Config.OWNER_ID,
                    f"⏹️ **Bot Stopped**\n\n"
                    f"Bot @{bot_info.username} has been stopped.\n"
                    f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            except:
                pass
            
            await app.stop()
            logger.info("✅ Bot stopped gracefully")
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"❌ Bot runtime error: {e}")
            await app.stop()
            sys.exit(1)
            
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.error("Please check if all required files exist:")
        logger.error("- bot.py")
        logger.error("- config.py")
        logger.error("- database.py")
        logger.error("- utils.py")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ Bot startup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    """Main function to run both health server and bot"""
    print("\n" + "="*60)
    print("🎬 MOVIE HELPER BOT - STARTING")
    print("="*60)
    print("✅ All features implemented:")
    print("   1. Welcome Messages Fixed")
    print("   2. /request Command with Admin Tagging")
    print("   3. Admin-only Buttons")
    print("   4. Professional Design")
    print("   5. Force Subscribe System")
    print("   6. Auto Accept Join Requests")
    print("   7. Spelling Correction")
    print("   8. AI Movie Chat")
    print("   9. Database Integration")
    print("   10.Premium Features")
    print("="*60)
    
    # Start health server in separate thread
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    logger.info("⏳ Waiting 3 seconds for health server to start...")
    time.sleep(3)
    
    # Run Telegram bot
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\n⏹️ Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Main function error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
