import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token_here")
    API_ID = int(os.getenv("API_ID", 1234567))
    API_HASH = os.getenv("API_HASH", "your_api_hash_here")
    
    # Bot Info
    BOT_USERNAME = os.getenv("BOT_USERNAME", "MovieMasterProBot")
    OWNER_ID = int(os.getenv("OWNER_ID", 1234567890))
    OWNER_USERNAME = os.getenv("OWNER_USERNAME", "asbhai_bsr")
    
    # Database
    MONGO_DB_URL = os.getenv("MONGO_DB_URL", "mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority")
    
    # Channels
    MAIN_CHANNEL = os.getenv("MAIN_CHANNEL", "MovieProChannel")
    LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", -1001234567890))
    
    # Port for Koyeb/Heroku
    PORT = int(os.getenv("PORT", 8080))
    
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
