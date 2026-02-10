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
    AI_TIMEOUT = 20  # Seconds timeout for AI responses
    
    # OMDb API Key (free)
    OMDB_API_KEY = os.getenv("OMDB_API_KEY", "6ed172d8")
    
    # Additional Config
    AUTO_DELETE_TIME = 300  # Seconds to auto-delete bot messages
    BROADCAST_DELAY = 0.5  # Seconds between broadcasts
    SPELLING_CHECK_TIMEOUT = 10  # Timeout for spelling checks
    
    # Security Settings
    MAX_WARNINGS = 3  # For abuse/link warnings
    CLEANUP_INTERVAL = 3600  # 1 Hour for background tasks
    
    # New Settings
    BIO_WARN_LIMIT = 3  # Bio link warnings before penalty
    COPYRIGHT_WARN_LIMIT = 2  # Copyright warnings before ban
    
    # Force Sub Channel
    FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL", "@asbhai_bsr")
    
    # Logs Channel
    LOGS_CHANNEL = int(os.getenv("LOGS_CHANNEL", -1002352329534))
    
    # Welcome Settings
    WELCOME_WITH_PHOTO = True  # Default welcome with photo
    
    # New Feature Flags
    ENABLE_BIO_PROTECTION = True
    ENABLE_COPYRIGHT_PROTECTION = True
    ENABLE_CLEAN_JOIN = True
    ENABLE_FUN_COMMANDS = True
    ENABLE_SEARCH_COMMANDS = True
