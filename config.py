import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    
    # Bot Info
    BOT_USERNAME = os.getenv("BOT_USERNAME", "MovieHelper_asBot")
    OWNER_ID = int(os.getenv("OWNER_ID", 7315805581))
    
    # Database
    MONGO_DB_URL = os.getenv("MONGO_DB_URL", "")
    
    # AI Configuration
    G4F_MODEL = "gpt-3.5-turbo"
    
    # OMDb API Key (free)
    OMDB_API_KEY = os.getenv("OMDB_API_KEY", "6ed172d8")
    
    # Additional Config
    AUTO_DELETE_TIME = 300  # Seconds to auto-delete bot messages
    BROADCAST_DELAY = 0.5  # Seconds between broadcasts to avoid flood
    
    # Force Sub Channel
    FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL", "@asbhai_bsr")
    
    # Logs Channel
    LOGS_CHANNEL = int(os.getenv("LOGS_CHANNEL", -1002352329534)
