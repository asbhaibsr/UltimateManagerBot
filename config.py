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
    
    # Features
    ENABLE_BIO_PROTECTION = True
    ENABLE_COPYRIGHT_PROTECTION = True
    ENABLE_CLEANJOIN = True
    ENABLE_SEARCH_FEATURES = True
