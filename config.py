import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    
    # Bot Info
    BOT_USERNAME = os.getenv("BOT_USERNAME", "MovieBotProBot")
    OWNER_ID = int(os.getenv("OWNER_ID", 0))
    OWNER_USERNAME = os.getenv("OWNER_USERNAME", "asbhai_bsr")
    
    # Database
    MONGO_DB_URL = os.getenv("MONGO_DB_URL", "")
    
    # Channels
    MAIN_CHANNEL = os.getenv("MAIN_CHANNEL", "MovieProChannel")
    LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", 0))
    
    # Port for Koyeb/Heroku
    PORT = int(os.getenv("PORT", 8000))
    
    # Feature Defaults
    FEATURE_DEFAULTS = {
        "spell_check": True,
        "season_check": True,
        "auto_delete": True,
        "file_cleaner": True,
        "request_system": True,
        "fsub": False,
        "force_join": False
    }
    
    # Time Options (in seconds)
    TIME_OPTIONS = {
        "2 Minutes": 120,
        "5 Minutes": 300,
        "10 Minutes": 600,
        "30 Minutes": 1800,
        "1 Hour": 3600,
        "Permanent": 0
    }
    
    DEFAULT_AUTO_DELETE_TIME = 60  # 1 minute
    REQUEST_COOLDOWN = 300  # 5 minutes between requests
    MAX_SEARCH_RESULTS = 10  # Maximum search results to show
