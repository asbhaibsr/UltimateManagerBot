# database.py - COMPLETE FILE
import motor.motor_asyncio
import datetime
from datetime import timedelta
from config import Config

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
deleted_data_col = db["deleted_data"]

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
                "joined_at": datetime.datetime.now(),
                "last_seen": datetime.datetime.now()
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
    await log_deletion("user", user_id, "Banned by admin")

async def unban_user(user_id):
    await users_col.update_one({"_id": user_id}, {"$set": {"banned": False}})

async def delete_user(user_id):
    """Permanently delete user from database"""
    await users_col.delete_one({"_id": user_id})

# ================ GROUP FUNCTIONS ================
async def add_group(group_id, title=None, username=None):
    group = await groups_col.find_one({"_id": group_id})
    
    update_data = {
        "title": title,
        "username": username,
        "active": True,
        "updated_at": datetime.datetime.now(),
        "last_active": datetime.datetime.now()
    }
    
    if not group:
        update_data["added_at"] = datetime.datetime.now()
        update_data["is_premium"] = False
        update_data["premium_expiry"] = None
        update_data["bot_removed"] = False
    
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
    group = await get_group(group_id)
    if group:
        await log_deletion("group", group_id, group.get("title", "Unknown"))
    await groups_col.delete_one({"_id": group_id})

async def mark_bot_removed(group_id, status=True):
    await groups_col.update_one(
        {"_id": group_id},
        {"$set": {"bot_removed": status, "removed_at": datetime.datetime.now()}}
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
            "spelling_mode": "simple",
            "auto_delete_on": False,
            "delete_time": 0,
            "welcome_enabled": True,
            "force_sub_enabled": False,
            "ai_enabled": True,
            "ai_chat_on": False,
            "bio_protection": False,
            "clean_join": True
        }
        try:
            await settings_col.insert_one(default_settings)
        except:
            pass
        return default_settings
    
    if "spelling_mode" not in settings:
        settings["spelling_mode"] = "simple"
    if "bio_protection" not in settings:
        settings["bio_protection"] = False
    if "clean_join" not in settings:
        settings["clean_join"] = True
        
    return settings

async def update_settings(chat_id, key, value):
    await settings_col.update_one(
        {"_id": chat_id},
        {"$set": {key: value}},
        upsert=True
    )

# ================ WELCOME FUNCTIONS ================
async def set_welcome_message(chat_id, text, photo_id=None):
    """Set custom welcome message and photo"""
    data = {
        "text": text,
        "photo_id": photo_id,
        "enabled": True
    }
    await settings_col.update_one(
        {"_id": chat_id},
        {"$set": {"welcome_data": data, "welcome_enabled": True}},
        upsert=True
    )

async def get_welcome_message(chat_id):
    """Get custom welcome message"""
    settings = await settings_col.find_one({"_id": chat_id})
    if settings and "welcome_data" in settings:
        return settings["welcome_data"]
    return None

# ================ FORCE SUB FUNCTIONS ================
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

# ================ CLEAR JUNK FUNCTION ================
async def clear_junk():
    """Clear all junk data: banned users, removed bots, inactive groups"""
    deleted_count = {
        "banned_users": 0,
        "removed_bots": 0,
        "inactive_groups": 0
    }
    
    try:
        result = await users_col.delete_many({"banned": True})
        deleted_count["banned_users"] = result.deleted_count
        
        result = await groups_col.delete_many({"bot_removed": True})
        deleted_count["inactive_groups"] = result.deleted_count
        
        week_ago = datetime.datetime.now() - timedelta(days=7)
        await warnings_col.delete_many({"last_warning": {"$lt": week_ago}})
        
        await movie_requests_col.delete_many({
            "status": {"$in": ["completed", "rejected"]},
            "updated_at": {"$lt": week_ago}
        })
        
        return deleted_count
        
    except Exception as e:
        print(f"Clear junk error: {e}")
        return deleted_count

# ================ LOG DELETION FUNCTION ================
async def log_deletion(deletion_type, item_id, item_name):
    """Log all deletions for tracking"""
    await deleted_data_col.insert_one({
        "type": deletion_type,
        "item_id": item_id,
        "item_name": item_name,
        "deleted_at": datetime.datetime.now()
    })

# ================ WARNING SYSTEM ================
async def get_warnings(chat_id, user_id):
    data = await warnings_col.find_one({"chat_id": chat_id, "user_id": user_id})
    return data["count"] if data else 0

async def add_warning(chat_id, user_id):
    data = await warnings_col.find_one({"chat_id": chat_id, "user_id": user_id})
    count = (data["count"] + 1) if data else 1
    await warnings_col.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"count": count, "last_warning": datetime.datetime.now()}},
        upsert=True
    )
    return count

async def reset_warnings(chat_id, user_id):
    await warnings_col.delete_one({"chat_id": chat_id, "user_id": user_id})

# ================ AUTO ACCEPT SYSTEM ================
async def set_auto_accept(chat_id, status: bool):
    await auto_accept_col.update_one(
        {"_id": chat_id},
        {"$set": {"enabled": status}},
        upsert=True
    )

async def get_auto_accept(chat_id):
    data = await auto_accept_col.find_one({"_id": chat_id})
    return data.get("enabled", False) if data else False

# ================ MOVIE REQUESTS ================
async def add_movie_request(chat_id, user_id, movie_name):
    await movie_requests_col.insert_one({
        "chat_id": chat_id,
        "user_id": user_id,
        "movie_name": movie_name,
        "status": "pending",
        "requested_at": datetime.datetime.now()
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

# ================ GET BOT STATS ================
async def get_bot_stats():
    """Get comprehensive bot statistics"""
    stats = {
        "total_users": await users_col.count_documents({"banned": False}),
        "total_groups": await groups_col.count_documents({}),
        "banned_users": await users_col.count_documents({"banned": True}),
        "premium_groups": 0,
        "active_groups": 0,
        "pending_requests": await movie_requests_col.count_documents({"status": "pending"}),
        "total_requests": await movie_requests_col.count_documents({})
    }
    
    async for group in groups_col.find({}):
        if group.get("is_premium", False):
            stats["premium_groups"] += 1
        if group.get("active", False):
            stats["active_groups"] += 1
    
    return stats
