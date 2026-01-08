#  config.py

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    
    # Bot Info
    BOT_USERNAME = os.getenv("BOT_USERNAME", "MovieBotProBot") # @ बिना
    OWNER_ID = int(os.getenv("OWNER_ID", 0))
    
    # Database
    MONGO_DB_URL = os.getenv("MONGO_DB_URL", "")
    
    # Channels
    LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", 0)) # Log Channel ID
    
    # Port for Koyeb/Heroku
    PORT = int(os.getenv("PORT", 8000))
