import motor.motor_asyncio
import datetime
from datetime import timedelta
from config import Config
import logging

logger = logging.getLogger(__name__)

# MongoDB connection
client = motor.motor_asyncio.AsyncIOMotorClient(Config.MONGO_DB_URL)
db = client["movie_helper_bot"]

# Collections
users_col = db["users"]
groups_col = db["groups"]
settings_col = db["settings"]
force_sub_col = db["force_sub"]
warnings_col = db["warnings"]
auto_accept_col = db["auto_accept"]
movie_requests_col = db["movie_requests"]
spelling_settings_col = db["spelling_settings"]  # NEW: For advanced spelling

# ================ NEW: SPELLING SETTINGS ================
async def get_spelling_settings(chat_id):
    """Get advanced spelling settings"""
    settings = await spelling_settings_col.find_one({"_id": chat_id})
    if not settings:
        default_settings = {
            "_id": chat_id,
            "advanced_spelling": False,  # Simple vs Advanced spelling check
            "auto_correct": True,  # Auto suggest corrections
            "sources": ["local", "omdb"]  # Sources to use
        }
        try:
            await spelling_settings_col.insert_one(default_settings)
        except:
            pass
        return default_settings
    return settings

async def update_spelling_settings(chat_id, key, value):
    """Update spelling settings"""
    await spelling_settings_col.update_one(
        {"_id": chat_id},
        {"$set": {key: value}},
        upsert=True
    )

# ================ USER FUNCTIONS ================
async def add_user(user_id, username=None, first_name=None, last_name=None):
    await users_col.update_one(
        {"_id": user_id},
        {
            "$set": {
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "banned": False,
                "last_seen": datetime.datetime.now(),
                "joined_at": datetime.datetime.now()
            }
        },
        upsert=True
    )

async def get_user(user_id):
    return await users_col.find_one({"_id": user_id})

async def get_all_users():
    users = []
    async for user in users_col.find({"banned": False}):
        users.append(user["_id"])
    return users

async def get_user_count():
    return await users_col.count_documents({"banned": False})

async def ban_user(user_id):
    await users_col.update_one({"_id": user_id}, {"$set": {"banned": True}})

async def unban_user(user_id):
    await users_col.update_one({"_id": user_id}, {"$set": {"banned": False}})

# ================ GROUP FUNCTIONS ================
async def add_group(group_id, title=None, username=None):
    group = await groups_col.find_one({"_id": group_id})
    
    update_data = {
        "title": title,
        "username": username,
        "active": True,
        "updated_at": datetime.datetime.now(),
        "last_check": datetime.datetime.now()  # For junk cleanup
    }
    
    if not group:
        update_data["added_at"] = datetime.datetime.now()
        update_data["is_premium"] = False
        update_data["premium_expiry"] = None
    
    await groups_col.update_one(
        {"_id": group_id},
        {"$set": update_data},
        upsert=True
    )

async def get_group(group_id):
    return await groups_col.find_one({"_id": group_id})

async def get_all_groups():
    groups = []
    async for group in groups_col.find({}):
        groups.append(group["_id"])
    return groups

async def get_group_count():
    return await groups_col.count_documents({})

async def remove_group(group_id):
    await groups_col.delete_one({"_id": group_id})

# ================ CLEAR JUNK FUNCTION (FIXED) ================
async def clear_junk():
    """Actually clear junk data: banned users and inactive groups"""
    deleted_count = 0
    
    try:
        # 1. Delete banned users (more than 30 days old)
        cutoff_date = datetime.datetime.now() - timedelta(days=30)
        result_users = await users_col.delete_many({
            "banned": True,
            "last_seen": {"$lt": cutoff_date}
        })
        deleted_count += result_users.deleted_count
        logger.info(f"Cleared {result_users.deleted_count} banned users")
        
        # 2. Delete groups where bot was removed (inactive for 7 days)
        cutoff_group = datetime.datetime.now() - timedelta(days=7)
        result_groups = await groups_col.delete_many({
            "active": False,
            "last_check": {"$lt": cutoff_group}
        })
        deleted_count += result_groups.deleted_count
        logger.info(f"Cleared {result_groups.deleted_count} inactive groups")
        
        # 3. Clean old warnings (older than 30 days)
        result_warnings = await warnings_col.delete_many({
            "created_at": {"$lt": cutoff_date}
        })
        logger.info(f"Cleared {result_warnings.deleted_count} old warnings")
        
        # 4. Clean old movie requests (completed older than 15 days)
        cutoff_requests = datetime.datetime.now() - timedelta(days=15)
        result_requests = await movie_requests_col.delete_many({
            "status": {"$in": ["completed", "rejected"]},
            "updated_at": {"$lt": cutoff_requests}
        })
        logger.info(f"Cleared {result_requests.deleted_count} old requests")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"Clear junk error: {e}")
        return 0

async def mark_group_inactive(group_id):
    """Mark group as inactive (bot removed)"""
    await groups_col.update_one(
        {"_id": group_id},
        {"$set": {"active": False, "last_check": datetime.datetime.now()}}
    )

# ================ PREMIUM FUNCTIONS ================
async def add_premium(group_id, months):
    expiry_date = datetime.datetime.now() + timedelta(days=30 * int(months))
    await groups_col.update_one(
        {"_id": group_id},
        {
            "$set": {
                "is_premium": True,
                "premium_expiry": expiry_date
            }
        },
        upsert=True
    )
    return expiry_date

async def remove_premium(group_id):
    await groups_col.update_one(
        {"_id": group_id},
        {
            "$set": {
                "is_premium": False,
                "premium_expiry": None
            }
        }
    )

async def check_is_premium(group_id):
    group = await groups_col.find_one({"_id": group_id})
    if not group:
        return False
    
    if group.get("is_premium", False):
        expiry = group.get("premium_expiry")
        if expiry and expiry > datetime.datetime.now():
            return True
        else:
            await remove_premium(group_id)
            return False
    return False

# ================ SETTINGS FUNCTIONS ================
async def get_settings(chat_id):
    settings = await settings_col.find_one({"_id": chat_id})
    if not settings:
        default_settings = {
            "_id": chat_id,
            "spelling_on": True,
            "advanced_spelling": False,  # NEW: Advanced spelling toggle
            "auto_delete_on": False,
            "delete_time": 0,
            "welcome_enabled": True,
            "force_sub_enabled": False,
            "ai_enabled": True,
            "welcome_with_photo": True  # NEW: Welcome with photo option
        }
        try:
            await settings_col.insert_one(default_settings)
        except:
            pass
        return default_settings
    return settings

async def update_settings(chat_id, key, value):
    await settings_col.update_one(
        {"_id": chat_id},
        {"$set": {key: value}},
        upsert=True
    )

# ================ OTHER FUNCTIONS (Same as before) ================
async def set_force_sub(chat_id, channel_id):
    await force_sub_col.update_one(
        {"_id": chat_id},
        {"$set": {"channel_id": channel_id}},
        upsert=True
    )

async def get_force_sub(chat_id):
    return await force_sub_col.find_one({"_id": chat_id})

async def remove_force_sub(chat_id):
    await force_sub_col.delete_one({"_id": chat_id})

async def get_warnings(chat_id, user_id):
    data = await warnings_col.find_one({"chat_id": chat_id, "user_id": user_id})
    return data["count"] if data else 0

async def add_warning(chat_id, user_id):
    data = await warnings_col.find_one({"chat_id": chat_id, "user_id": user_id})
    count = (data["count"] + 1) if data else 1
    await warnings_col.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"count": count, "created_at": datetime.datetime.now()}},
        upsert=True
    )
    return count

async def reset_warnings(chat_id, user_id):
    await warnings_col.delete_one({"chat_id": chat_id, "user_id": user_id})

async def set_auto_accept(chat_id, status: bool):
    await auto_accept_col.update_one(
        {"_id": chat_id},
        {"$set": {"enabled": status}},
        upsert=True
    )

async def get_auto_accept(chat_id):
    data = await auto_accept_col.find_one({"_id": chat_id})
    return data.get("enabled", False) if data else False

async def add_movie_request(chat_id, user_id, movie_name):
    await movie_requests_col.insert_one({
        "chat_id": chat_id,
        "user_id": user_id,
        "movie_name": movie_name,
        "status": "pending",
        "requested_at": datetime.datetime.now(),
        "updated_at": datetime.datetime.now()
    })

async def get_pending_requests(chat_id):
    requests = []
    async for req in movie_requests_col.find({"chat_id": chat_id, "status": "pending"}):
        requests.append(req)
    return requests

async def update_request_status(request_id, status):
    await movie_requests_col.update_one(
        {"_id": request_id},
        {"$set": {"status": status, "updated_at": datetime.datetime.now()}}
                   )
