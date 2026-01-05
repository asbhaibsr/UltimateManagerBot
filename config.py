import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram Credentials
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    
    # Database
    MONGO_DB_URL = os.getenv("MONGO_DB_URL", "")
    
    # Bot Settings
    OWNER_ID = int(os.getenv("OWNER_ID", 0))
    BOT_USERNAME = os.getenv("BOT_USERNAME", "")
    
    # Your Channels
    CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "asbhai_bsr")
    MOVIE_CHANNEL = os.getenv("MOVIE_CHANNEL", "@asfilter_bot")
    
    # URLs
    START_IMAGE = os.getenv("START_IMAGE", "https://images.unsplash.com/photo-1635805737707-575885ab0820?w=800")
    PORT = int(os.getenv("PORT", 8080))
    
    # Time Settings (Seconds)
    AUTO_DELETE_TIME = 300  # 5 minutes
    FSUB_CHECK_TIME = 60    # 1 minute
    
    # Limits
    MAX_FSUB_CHANNELS = 3
    FORCE_JOIN_OPTIONS = [1, 2, 3, 5, 10]
    
    # APIs
    SPELLCHECK_API = "https://api.dictionaryapi.dev/api/v2/entries/en/"
    TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
    
    # Logging
    LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", 0))

config = Config()
