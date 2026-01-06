import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram Credentials
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    
    # Database (MongoDB Free Cluster)
    MONGO_DB_URL = os.getenv("MONGO_DB_URL", "")
    
    # Bot Settings
    OWNER_ID = int(os.getenv("OWNER_ID", 0))
    BOT_USERNAME = os.getenv("BOT_USERNAME", "MovieMasterProBot")
    
    # Channels
    MAIN_CHANNEL = os.getenv("MAIN_CHANNEL", "@asbhai_bsr")
    LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", 0))
    
    # Default Settings
    DEFAULT_AUTO_DELETE_TIME = 300  # 5 minutes
    DEFAULT_FSUB_CHANNELS = []
    DEFAULT_FORCE_JOIN = 0
    
    # Time Options (Seconds)
    TIME_OPTIONS = {
        "2 minute": 120,
        "5 minute": 300,
        "10 minute": 600,
        "30 minute": 1800,
        "1 hour": 3600,
        "Permanent": 0
    }
    
    # Feature Defaults
    FEATURE_DEFAULTS = {
        "spell_check": True,
        "season_check": True,
        "auto_delete": True,
        "request_system": True,
        "file_cleaner": True
    }
    
    # Premium Settings
    PREMIUM_PRICES = {
        "5": 300,      # 5 months for ₹300
        "12": 500,     # 1 year for ₹500
        "24": 1000     # 2 years for ₹1000
    }
    
    # Server Settings
    PORT = int(os.getenv("PORT", 8080))
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
    
    # Request Cooldown (Seconds)
    REQUEST_COOLDOWN = 300  # 5 minutes

config = Config()
