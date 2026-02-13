import asyncio
import logging
import sys
import os
import time
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ['/health', '/', '/ping']:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Movie Helper Bot - Running</title>
                <style>
                    body {{
                        font-family: 'Segoe UI', Arial, sans-serif;
                        text-align: center;
                        padding: 40px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                    }}
                    .container {{
                        background: rgba(255,255,255,0.1);
                        padding: 30px;
                        border-radius: 20px;
                        max-width: 700px;
                        margin: 0 auto;
                        backdrop-filter: blur(10px);
                    }}
                    h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
                    .status {{
                        background: #00b894;
                        color: white;
                        padding: 12px 25px;
                        border-radius: 30px;
                        display: inline-block;
                        margin: 20px 0;
                        font-weight: bold;
                    }}
                    .info {{
                        text-align: left;
                        margin-top: 25px;
                        background: rgba(255,255,255,0.1);
                        padding: 20px;
                        border-radius: 15px;
                    }}
                    .emoji {{ font-size: 1.2em; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🎬 Movie Helper Bot</h1>
                    <div class="status">✅ Bot is Running</div>
                    <p>Group management aur movie requests ke liye advanced bot!</p>
                    
                    <div class="info">
                        <h3>📊 Server Status:</h3>
                        <p>• <strong>Service:</strong> Movie Helper Bot</p>
                        <p>• <strong>Status:</strong> Active & Healthy</p>
                        <p>• <strong>Version:</strong> 2.0 (Advanced)</p>
                        <p>• <strong>Last Check:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <p>• <strong>Uptime:</strong> Continuous</p>
                    </div>
                    
                    <p style="margin-top: 30px; font-size: 0.9em;">
                        Made with ❤️ for Telegram Groups
                    </p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"✅ Health check server running on port {port}")
    server.serve_forever()

async def run_bot():
    try:
        # Import startup_tasks manually
        from bot import app, startup_tasks
        
        logger.info("🚀 Starting Movie Helper Bot...")
        
        await app.start()
        
        # Manually run startup tasks here
        logger.info("⚙️ Running startup tasks...")
        await startup_tasks()
        
        bot_info = await app.get_me()
        logger.info(f"✅ Bot started as @{bot_info.username}")
        
        logger.info("🤖 Bot is now running and ready!")
        
        # Keep bot running
        await asyncio.Event().wait()
        
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    time.sleep(2)
    
    asyncio.run(run_bot())

if __name__ == "__main__":
    main()
