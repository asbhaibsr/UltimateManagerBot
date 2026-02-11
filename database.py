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
bot_status_col = db["bot_status"]  # New: Track bot instances

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
                "last_seen": datetime.datetime.now()
            },
            "$setOnInsert": {
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

async def delete_user(user_id):
    """Permanently delete user from database"""
    await users_col.delete_one({"_id": user_id})

# ================ GROUP FUNCTIONS (FIXED) ================
async def add_group(group_id, title=None, username=None):
    """Add group to database or update existing"""
    group = await groups_col.find_one({"_id": group_id})
    
    update_data = {
        "title": title,
        "username": username,
        "active": True,
        "last_active": datetime.datetime.now(),
        "bot_removed": False,
        "removed_at": None
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
    return True

async def get_group(group_id):
    return await groups_col.find_one({"_id": group_id})

async def get_all_groups():
    """Get all active groups where bot is present"""
    groups = []
    async for group in groups_col.find({"bot_removed": {"$ne": True}}):  # Only active groups
        groups.append(group["_id"])
    return groups

async def get_group_count():
    """Count only active groups"""
    return await groups_col.count_documents({"bot_removed": {"$ne": True}})

async def remove_group(group_id):
    """Mark group as removed instead of deleting"""
    group = await get_group(group_id)
    group_title = group.get("title", "Unknown") if group else "Unknown"
    
    await groups_col.update_one(
        {"_id": group_id},
        {
            "$set": {
                "bot_removed": True,
                "removed_at": datetime.datetime.now(),
                "active": False
            }
        },
        upsert=False
    )
    
    # Also remove force sub data
    await remove_force_sub(group_id)
    
    await log_deletion("group", group_id, group_title)

async def mark_bot_removed(group_id, status=True):
    """Mark that bot was removed from group"""
    await groups_col.update_one(
        {"_id": group_id},
        {
            "$set": {
                "bot_removed": status,
                "removed_at": datetime.datetime.now() if status else None,
                "active": not status
            }
        }
    )
    
    # Also remove force sub if bot removed
    if status:
        await remove_force_sub(group_id)

async def verify_group_active(client, group_id):
    """Verify if bot is actually in group"""
    try:
        await client.get_chat_member(group_id, (await client.get_me()).id)
        return True
    except:
        await mark_bot_removed(group_id, True)
        return False

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
            "copyright_mode": False,
            "delete_time": 0,
            "welcome_enabled": True,
            "clean_join": False,
            "bio_check": True,
            "ai_chat_on": False
        }
        try:
            await settings_col.insert_one(default_settings)
        except:
            pass
        return default_settings
    
    # Ensure new keys exist
    updates = {}
    if "bio_check" not in settings: updates["bio_check"] = True
    if "clean_join" not in settings: updates["clean_join"] = False
    if "copyright_mode" not in settings: updates["copyright_mode"] = settings.get("auto_delete_on", False)
    
    if updates:
        await settings_col.update_one({"_id": chat_id}, {"$set": updates})
        
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

# ================ FORCE SUB FUNCTIONS (FIXED) ================
async def set_force_sub(chat_id, channel_id):
    """Set force subscribe channel for a group"""
    await force_sub_col.update_one(
        {"_id": chat_id},
        {"$set": {"channel_id": channel_id, "created_at": datetime.datetime.now()}},
        upsert=True
    )

async def get_force_sub(chat_id):
    """Get force sub channel for group"""
    return await force_sub_col.find_one({"_id": chat_id})

async def remove_force_sub(chat_id):
    """Remove force sub for group"""
    await force_sub_col.delete_one({"_id": chat_id})

# ================ CLEAR JUNK FUNCTION (FIXED) ================
async def clear_junk():
    """Clear all junk data - Groups where bot removed, banned users, etc."""
    deleted_count = {
        "banned_users": 0,
        "inactive_groups": 0,
        "old_warnings": 0,
        "old_requests": 0
    }
    
    try:
        # 1. Delete banned users
        result = await users_col.delete_many({"banned": True})
        deleted_count["banned_users"] = result.deleted_count
        
        # 2. Delete groups marked as bot_removed
        result = await groups_col.delete_many({"bot_removed": True})
        deleted_count["inactive_groups"] = result.deleted_count
        
        # 3. Clean old warnings (older than 30 days)
        month_ago = datetime.datetime.now() - timedelta(days=30)
        result = await warnings_col.delete_many({"last_warning": {"$lt": month_ago}})
        deleted_count["old_warnings"] = result.deleted_count
        
        # 4. Clean old requests
        week_ago = datetime.datetime.now() - timedelta(days=7)
        result = await movie_requests_col.delete_many({
            "status": {"$in": ["completed", "rejected"]},
            "updated_at": {"$lt": week_ago}
        })
        deleted_count["old_requests"] = result.deleted_count
        
        # 5. Also clean force sub for removed groups
        removed_groups = await groups_col.find({"bot_removed": True}).to_list(length=None)
        for group in removed_groups:
            await remove_force_sub(group["_id"])
        
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
    result = await movie_requests_col.insert_one({
        "chat_id": chat_id,
        "user_id": user_id,
        "movie_name": movie_name,
        "status": "pending",
        "requested_at": datetime.datetime.now()
    })
    return result.inserted_id

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

# ================ GET BOT STATS (FIXED) ================
async def get_bot_stats():
    """Get comprehensive bot statistics - Only count active groups"""
    stats = {
        "total_users": await users_col.count_documents({"banned": False}),
        "total_groups": await groups_col.count_documents({"bot_removed": {"$ne": True}}),  # Only active
        "banned_users": await users_col.count_documents({"banned": True}),
        "premium_groups": 0,
        "active_groups": await groups_col.count_documents({"active": True, "bot_removed": {"$ne": True}}),
        "pending_requests": await movie_requests_col.count_documents({"status": "pending"}),
        "total_requests": await movie_requests_col.count_documents({})
    }
    
    # Count premium groups among active groups
    async for group in groups_col.find({"bot_removed": {"$ne": True}}):
        if group.get("is_premium", False):
            expiry = group.get("premium_expiry")
            if expiry and expiry > datetime.datetime.now():
                stats["premium_groups"] += 1
            else:
                await remove_premium(group["_id"])
    
    return stats

# ================ BOT INSTANCE TRACKING ================
async def set_bot_instance(bot_id, status="running"):
    """Track current bot instance"""
    await bot_status_col.update_one(
        {"_id": "current_bot"},
        {"$set": {
            "bot_id": bot_id,
            "status": status,
            "last_updated": datetime.datetime.now()
        }},
        upsert=True
    )

async def get_bot_instance():
    """Get current bot instance info"""
    return await bot_status_col.find_one({"_id": "current_bot"})
