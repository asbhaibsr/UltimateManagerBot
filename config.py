# config.py

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    
    # Bot Info
    BOT_USERNAME = os.getenv("BOT_USERNAME", "MovieBotProBot")  # @ बिना
    OWNER_ID = int(os.getenv("OWNER_ID", 0))
    
    # Database
    MONGO_DB_URL = os.getenv("MONGO_DB_URL", "")
    
    # Channels
    LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", 0))  # Log Channel ID
    
    # Port for Koyeb/Heroku
    PORT = int(os.getenv("PORT", 8000))
    
    # Premium Configuration
    PREMIUM_PRICE_PER_MONTH = 50  # ₹50 per month
    AUTO_DELETE_MINUTES = 5  # Default auto delete time
    
    # AI Configuration
    AI_ENABLED = True
    G4F_MODEL = "gpt-3.5-turbo"
    
    # Request Configuration
    MAX_REQUESTS_PER_USER = 3
    REQUEST_COOLDOWN = 60  # seconds
    
    # Movie APIs
    OMDB_API_KEY = "6ed172d8"  # Added for movie search
    TMDB_API_KEY = "e547e17d4e91f3e62a571655cd1ccaff"  # Added
    IMDB_API_KEY = "966c4f4f"  # Added
    
    # Search bot URL
    SEARCH_BOT_URL = "https://t.me/asfilter_bot?start="
