import asyncio
import logging
import sys
import os
import time
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ['/', '/health', '/ping']:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = f"""<!DOCTYPE html>
<html>
<head><title>Movie Helper Bot</title>
<style>
body{{font-family:Arial,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);color:white;}}
.card{{background:rgba(255,255,255,0.08);padding:40px;border-radius:20px;text-align:center;max-width:500px;backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.1);}}
h1{{font-size:2em;margin:0 0 10px;}}
.badge{{background:#00b09b;padding:8px 20px;border-radius:20px;display:inline-block;margin:15px 0;font-weight:bold;}}
p{{color:rgba(255,255,255,0.7);}}
.time{{font-size:0.85em;color:rgba(255,255,255,0.4);margin-top:20px;}}
</style></head>
<body>
<div class="card">
<h1>🎬 Movie Helper Bot</h1>
<div class="badge">✅ Running</div>
<p>Telegram groups ke liye ek smart bot</p>
<p>• Spelling Check • Auto Accept • AI Chat • Protection</p>
<p class="time">Last checked: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
</div>
</body>
</html>"""
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass

def run_health_server():
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"Health server: port {port}")
    server.serve_forever()

async def run_bot():
    try:
        from bot import app
        logger.info("🚀 Bot start ho raha hai...")
        await app.start()
        bot_info = await app.get_me()
        logger.info(f"✅ @{bot_info.username} ready!")

        try:
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            await app.stop()
            sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Bot crash: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    Thread(target=run_health_server, daemon=True).start()
    time.sleep(2)
    asyncio.run(run_bot())

if __name__ == "__main__":
    main()
