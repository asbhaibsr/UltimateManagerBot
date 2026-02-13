import motor.motor_asyncio
import datetime
from datetime import timedelta
from config import Config
import logging
from typing import Optional, Dict, List, Any, Union

logger = logging.getLogger(__name__)

# MongoDB Connection
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
bot_status_col = db["bot_status"]
bio_warnings_col = db["bio_warnings"]
spelling_cache_col = db["spelling_cache"]
filters_col = db["filters"]
notes_col = db["notes"]
greetings_col = db["greetings"]
antispam_col = db["antispam"]
blacklist_col = db["blacklist"]

# Indexes
async def create_indexes():
    """Create indexes for better performance"""
    try:
        await users_col.create_index("banned")
        await users_col.create_index("last_seen")
        
        await groups_col.create_index("bot_removed")
        await groups_col.create_index("active")
        await groups_col.create_index("is_premium")
        
        await warnings_col.create_index([("chat_id", 1), ("user_id", 1)])
        await warnings_col.create_index("last_warning")
        
        await bio_warnings_col.create_index([("chat_id", 1), ("user_id", 1)])
        await bio_warnings_col.create_index("last_warning")
        
        await movie_requests_col.create_index([("chat_id", 1), ("status", 1)])
        await movie_requests_col.create_index("requested_at")
        
        await spelling_cache_col.create_index("cached_at", expireAfterSeconds=Config.CACHE_TTL)
        
        logger.info("✅ Database indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")

# ================ USER FUNCTIONS ================
async def add_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> bool:
    """Add or update user in database"""
    try:
        await users_col.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "last_seen": datetime.datetime.now()
                },
                "$setOnInsert": {
                    "joined_at": datetime.datetime.now(),
                    "banned": False,
                    "total_requests": 0,
                    "warnings": 0
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error adding user {user_id}: {e}")
        return False

async def get_user(user_id: int) -> Optional[Dict]:
    """Get user by ID"""
    return await users_col.find_one({"_id": user_id})

async def get_all_users(include_banned: bool = False) -> List[int]:
    """Get all user IDs"""
    query = {} if include_banned else {"banned": False}
    users = []
    async for user in users_col.find(query, {"_id": 1}):
        users.append(user["_id"])
    return users

async def get_user_count(include_banned: bool = False) -> int:
    """Get total user count"""
    query = {} if include_banned else {"banned": False}
    return await users_col.count_documents(query)

async def ban_user(user_id: int) -> bool:
    """Ban a user"""
    try:
        await users_col.update_one({"_id": user_id}, {"$set": {"banned": True}})
        return True
    except Exception as e:
        logger.error(f"Error banning user {user_id}: {e}")
        return False

async def unban_user(user_id: int) -> bool:
    """Unban a user"""
    try:
        await users_col.update_one({"_id": user_id}, {"$set": {"banned": False}})
        return True
    except Exception as e:
        logger.error(f"Error unbanning user {user_id}: {e}")
        return False

async def delete_user(user_id: int) -> bool:
    """Delete user from database"""
    try:
        await users_col.delete_one({"_id": user_id})
        return True
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        return False

async def update_user_stats(user_id: int, **kwargs) -> bool:
    """Update user statistics"""
    try:
        await users_col.update_one(
            {"_id": user_id},
            {"$inc": kwargs}
        )
        return True
    except Exception as e:
        logger.error(f"Error updating user stats {user_id}: {e}")
        return False

# ================ GROUP FUNCTIONS ================
async def add_group(group_id: int, title: str = None, username: str = None) -> bool:
    """Add or update group in database"""
    try:
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
            update_data["total_requests"] = 0
            update_data["members_count"] = 0
        
        await groups_col.update_one(
            {"_id": group_id},
            {"$set": update_data},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error adding group {group_id}: {e}")
        return False

async def get_group(group_id: int) -> Optional[Dict]:
    """Get group by ID"""
    return await groups_col.find_one({"_id": group_id})

async def get_all_groups(include_removed: bool = False) -> List[int]:
    """Get all active group IDs"""
    query = {} if include_removed else {"bot_removed": {"$ne": True}}
    groups = []
    async for group in groups_col.find(query, {"_id": 1}):
        groups.append(group["_id"])
    return groups

async def get_group_count(include_removed: bool = False) -> int:
    """Get total groups count"""
    query = {} if include_removed else {"bot_removed": {"$ne": True}}
    return await groups_col.count_documents(query)

async def mark_bot_removed(group_id: int, status: bool = True) -> bool:
    """Mark bot as removed from group"""
    try:
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
        
        if status:
            await remove_force_sub(group_id)
            await remove_all_filters(group_id)
            await remove_all_notes(group_id)
        
        return True
    except Exception as e:
        logger.error(f"Error marking bot removed {group_id}: {e}")
        return False

async def update_group_stats(group_id: int, **kwargs) -> bool:
    """Update group statistics"""
    try:
        await groups_col.update_one(
            {"_id": group_id},
            {"$inc": kwargs}
        )
        return True
    except Exception as e:
        logger.error(f"Error updating group stats {group_id}: {e}")
        return False

# ================ PREMIUM FUNCTIONS ================
async def add_premium(group_id: int, months: int) -> Optional[datetime.datetime]:
    """Add premium to group"""
    try:
        expiry_date = datetime.datetime.now() + timedelta(days=30 * months)
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
    except Exception as e:
        logger.error(f"Error adding premium to {group_id}: {e}")
        return None

async def remove_premium(group_id: int) -> bool:
    """Remove premium from group"""
    try:
        await groups_col.update_one(
            {"_id": group_id},
            {
                "$set": {
                    "is_premium": False,
                    "premium_expiry": None
                }
            }
        )
        return True
    except Exception as e:
        logger.error(f"Error removing premium from {group_id}: {e}")
        return False

async def check_is_premium(group_id: int) -> bool:
    """Check if group has premium"""
    try:
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
    except Exception as e:
        logger.error(f"Error checking premium for {group_id}: {e}")
        return False

# ================ SETTINGS FUNCTIONS ================
DEFAULT_SETTINGS = {
    "spelling_on": True,
    "spelling_mode": "simple",
    "copyright_mode": False,
    "delete_time": 0,
    "welcome_enabled": True,
    "clean_join": True,
    "bio_check": True,
    "bio_action": "mute",
    "ai_chat_on": False,
    "bad_words_filter": True,
    "link_filter": True,
    "welcome_photo": True,
    "antispam": True,
    "captcha": False,
    "welcome_text": None,
    "goodbye_text": None,
    "rules": None
}

async def get_settings(chat_id: int) -> Dict:
    """Get group settings with defaults"""
    try:
        settings = await settings_col.find_one({"_id": chat_id})
        if not settings:
            # Create default settings
            default_settings = DEFAULT_SETTINGS.copy()
            default_settings["_id"] = chat_id
            await settings_col.insert_one(default_settings)
            return default_settings
        
        # Ensure all keys exist
        updated = False
        for key, value in DEFAULT_SETTINGS.items():
            if key not in settings:
                settings[key] = value
                updated = True
        
        if updated:
            await settings_col.update_one({"_id": chat_id}, {"$set": settings})
        
        return settings
    except Exception as e:
        logger.error(f"Error getting settings for {chat_id}: {e}")
        return DEFAULT_SETTINGS.copy()

async def update_settings(chat_id: int, key: str, value: Any) -> bool:
    """Update a single setting"""
    try:
        await settings_col.update_one(
            {"_id": chat_id},
            {"$set": {key: value}},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error updating settings for {chat_id}: {e}")
        return False

async def update_multiple_settings(chat_id: int, settings_dict: Dict) -> bool:
    """Update multiple settings at once"""
    try:
        await settings_col.update_one(
            {"_id": chat_id},
            {"$set": settings_dict},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error updating multiple settings for {chat_id}: {e}")
        return False

async def reset_settings(chat_id: int) -> bool:
    """Reset settings to default"""
    try:
        default_settings = DEFAULT_SETTINGS.copy()
        default_settings["_id"] = chat_id
        await settings_col.replace_one({"_id": chat_id}, default_settings, upsert=True)
        return True
    except Exception as e:
        logger.error(f"Error resetting settings for {chat_id}: {e}")
        return False

# ================ WELCOME FUNCTIONS ================
async def set_welcome_message(chat_id: int, text: str, photo_id: str = None) -> bool:
    """Set custom welcome message"""
    try:
        data = {
            "text": text,
            "photo_id": photo_id,
            "enabled": True,
            "updated_at": datetime.datetime.now()
        }
        await settings_col.update_one(
            {"_id": chat_id},
            {"$set": {"welcome_data": data, "welcome_enabled": True}},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error setting welcome for {chat_id}: {e}")
        return False

async def get_welcome_message(chat_id: int) -> Optional[Dict]:
    """Get custom welcome message"""
    try:
        settings = await settings_col.find_one({"_id": chat_id})
        if settings and "welcome_data" in settings:
            return settings["welcome_data"]
        return None
    except Exception as e:
        logger.error(f"Error getting welcome for {chat_id}: {e}")
        return None

async def disable_welcome(chat_id: int) -> bool:
    """Disable welcome message"""
    try:
        await update_settings(chat_id, "welcome_enabled", False)
        return True
    except Exception as e:
        logger.error(f"Error disabling welcome for {chat_id}: {e}")
        return False

# ================ GOODBYE FUNCTIONS ================
async def set_goodbye_message(chat_id: int, text: str, photo_id: str = None) -> bool:
    """Set custom goodbye message"""
    try:
        data = {
            "text": text,
            "photo_id": photo_id,
            "enabled": True,
            "updated_at": datetime.datetime.now()
        }
        await greetings_col.update_one(
            {"_id": chat_id},
            {"$set": data},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error setting goodbye for {chat_id}: {e}")
        return False

async def get_goodbye_message(chat_id: int) -> Optional[Dict]:
    """Get custom goodbye message"""
    return await greetings_col.find_one({"_id": chat_id})

# ================ RULES FUNCTIONS ================
async def set_rules(chat_id: int, rules_text: str) -> bool:
    """Set group rules"""
    try:
        await update_settings(chat_id, "rules", rules_text)
        return True
    except Exception as e:
        logger.error(f"Error setting rules for {chat_id}: {e}")
        return False

async def get_rules(chat_id: int) -> Optional[str]:
    """Get group rules"""
    settings = await get_settings(chat_id)
    return settings.get("rules")

# ================ FORCE SUB FUNCTIONS ================
async def set_force_sub(chat_id: int, channel_id: int, channel_title: str = None) -> bool:
    """Set force subscribe channel"""
    try:
        await force_sub_col.update_one(
            {"_id": chat_id},
            {
                "$set": {
                    "channel_id": channel_id,
                    "channel_title": channel_title,
                    "created_at": datetime.datetime.now()
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error setting force sub for {chat_id}: {e}")
        return False

async def get_force_sub(chat_id: int) -> Optional[Dict]:
    """Get force subscribe data"""
    return await force_sub_col.find_one({"_id": chat_id})

async def remove_force_sub(chat_id: int) -> bool:
    """Remove force subscribe"""
    try:
        await force_sub_col.delete_one({"_id": chat_id})
        return True
    except Exception as e:
        logger.error(f"Error removing force sub for {chat_id}: {e}")
        return False

async def get_all_force_sub_channels() -> List[Dict]:
    """Get all force sub entries"""
    channels = []
    async for entry in force_sub_col.find():
        channels.append(entry)
    return channels

# ================ BIO WARNINGS ================
async def add_bio_warning(chat_id: int, user_id: int) -> int:
    """Add bio warning for user"""
    try:
        data = await bio_warnings_col.find_one({"chat_id": chat_id, "user_id": user_id})
        count = (data["count"] + 1) if data else 1
        
        await bio_warnings_col.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {
                "$set": {
                    "count": count,
                    "last_warning": datetime.datetime.now()
                }
            },
            upsert=True
        )
        return count
    except Exception as e:
        logger.error(f"Error adding bio warning: {e}")
        return 1

async def get_bio_warnings(chat_id: int, user_id: int) -> int:
    """Get bio warning count"""
    data = await bio_warnings_col.find_one({"chat_id": chat_id, "user_id": user_id})
    return data["count"] if data else 0

async def reset_bio_warnings(chat_id: int, user_id: int) -> bool:
    """Reset bio warnings"""
    try:
        await bio_warnings_col.delete_one({"chat_id": chat_id, "user_id": user_id})
        return True
    except Exception as e:
        logger.error(f"Error resetting bio warnings: {e}")
        return False

# ================ SPELLING CACHE ================
async def get_spelling_cache(key: str) -> Optional[Any]:
    """Get from spelling cache"""
    try:
        cache = await spelling_cache_col.find_one({"_id": key})
        if cache:
            cache_time = cache.get("cached_at")
            if cache_time and (datetime.datetime.now() - cache_time).seconds < Config.CACHE_TTL:
                return cache.get("data")
        return None
    except Exception as e:
        logger.error(f"Error getting cache: {e}")
        return None

async def set_spelling_cache(key: str, data: Any, ttl: int = None) -> bool:
    """Set in spelling cache"""
    try:
        if not ttl:
            ttl = Config.CACHE_TTL
        
        await spelling_cache_col.update_one(
            {"_id": key},
            {
                "$set": {
                    "data": data,
                    "cached_at": datetime.datetime.now()
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error setting cache: {e}")
        return False

async def clear_expired_cache() -> int:
    """Clear expired cache entries"""
    try:
        expiry_time = datetime.datetime.now() - timedelta(seconds=Config.CACHE_TTL)
        result = await spelling_cache_col.delete_many({"cached_at": {"$lt": expiry_time}})
        return result.deleted_count
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return 0

# ================ WARNING SYSTEM ================
async def get_warnings(chat_id: int, user_id: int) -> int:
    """Get warning count for user in group"""
    data = await warnings_col.find_one({"chat_id": chat_id, "user_id": user_id})
    return data["count"] if data else 0

async def add_warning(chat_id: int, user_id: int, reason: str = None) -> int:
    """Add warning for user"""
    try:
        data = await warnings_col.find_one({"chat_id": chat_id, "user_id": user_id})
        count = (data["count"] + 1) if data else 1
        
        await warnings_col.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {
                "$set": {
                    "count": count,
                    "last_warning": datetime.datetime.now(),
                    "last_reason": reason
                },
                "$push": {
                    "warnings_history": {
                        "count": count,
                        "reason": reason,
                        "time": datetime.datetime.now()
                    }
                }
            },
            upsert=True
        )
        return count
    except Exception as e:
        logger.error(f"Error adding warning: {e}")
        return 1

async def reset_warnings(chat_id: int, user_id: int) -> bool:
    """Reset warnings for user"""
    try:
        await warnings_col.delete_one({"chat_id": chat_id, "user_id": user_id})
        return True
    except Exception as e:
        logger.error(f"Error resetting warnings: {e}")
        return False

async def get_all_warnings(chat_id: int) -> List[Dict]:
    """Get all warnings in a group"""
    warnings = []
    async for warn in warnings_col.find({"chat_id": chat_id}):
        warnings.append(warn)
    return warnings

# ================ AUTO ACCEPT SYSTEM ================
async def set_auto_accept(chat_id: int, status: bool) -> bool:
    """Set auto accept status"""
    try:
        await auto_accept_col.update_one(
            {"_id": chat_id},
            {"$set": {"enabled": status}},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error setting auto accept: {e}")
        return False

async def get_auto_accept(chat_id: int) -> bool:
    """Get auto accept status"""
    data = await auto_accept_col.find_one({"_id": chat_id})
    return data.get("enabled", False) if data else False

# ================ MOVIE REQUESTS ================
async def add_movie_request(chat_id: int, user_id: int, movie_name: str) -> Optional[str]:
    """Add a movie request"""
    try:
        result = await movie_requests_col.insert_one({
            "chat_id": chat_id,
            "user_id": user_id,
            "movie_name": movie_name,
            "status": "pending",
            "requested_at": datetime.datetime.now(),
            "updated_at": datetime.datetime.now()
        })
        
        # Update user stats
        await update_user_stats(user_id, total_requests=1)
        await update_group_stats(chat_id, total_requests=1)
        
        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"Error adding movie request: {e}")
        return None

async def get_pending_requests(chat_id: int) -> List[Dict]:
    """Get pending requests for group"""
    requests = []
    async for req in movie_requests_col.find(
        {"chat_id": chat_id, "status": "pending"}
    ).sort("requested_at", -1):
        requests.append(req)
    return requests

async def get_user_requests(user_id: int, limit: int = 10) -> List[Dict]:
    """Get user's requests"""
    requests = []
    async for req in movie_requests_col.find(
        {"user_id": user_id}
    ).sort("requested_at", -1).limit(limit):
        requests.append(req)
    return requests

async def update_request_status(request_id: str, status: str, admin_id: int = None) -> bool:
    """Update request status"""
    try:
        update_data = {
            "status": status,
            "updated_at": datetime.datetime.now()
        }
        if admin_id:
            update_data["admin_id"] = admin_id
        
        await movie_requests_col.update_one(
            {"_id": request_id},
            {"$set": update_data}
        )
        return True
    except Exception as e:
        logger.error(f"Error updating request status: {e}")
        return False

async def get_request_stats(chat_id: int = None) -> Dict:
    """Get request statistics"""
    try:
        match = {"chat_id": chat_id} if chat_id else {}
        
        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        stats = {
            "pending": 0,
            "completed": 0,
            "rejected": 0,
            "total": 0
        }
        
        async for result in movie_requests_col.aggregate(pipeline):
            stats[result["_id"]] = result["count"]
            stats["total"] += result["count"]
        
        return stats
    except Exception as e:
        logger.error(f"Error getting request stats: {e}")
        return {"pending": 0, "completed": 0, "rejected": 0, "total": 0}

# ================ FILTERS SYSTEM ================
async def add_filter(chat_id: int, trigger: str, response: str, file_id: str = None) -> bool:
    """Add a custom filter"""
    try:
        await filters_col.update_one(
            {"chat_id": chat_id, "trigger": trigger.lower()},
            {
                "$set": {
                    "response": response,
                    "file_id": file_id,
                    "created_at": datetime.datetime.now()
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error adding filter: {e}")
        return False

async def get_filter(chat_id: int, trigger: str) -> Optional[Dict]:
    """Get a specific filter"""
    return await filters_col.find_one({"chat_id": chat_id, "trigger": trigger.lower()})

async def get_all_filters(chat_id: int) -> List[Dict]:
    """Get all filters for a group"""
    filters = []
    async for filter_data in filters_col.find({"chat_id": chat_id}):
        filters.append(filter_data)
    return filters

async def remove_filter(chat_id: int, trigger: str) -> bool:
    """Remove a filter"""
    try:
        await filters_col.delete_one({"chat_id": chat_id, "trigger": trigger.lower()})
        return True
    except Exception as e:
        logger.error(f"Error removing filter: {e}")
        return False

async def remove_all_filters(chat_id: int) -> bool:
    """Remove all filters for a group"""
    try:
        await filters_col.delete_many({"chat_id": chat_id})
        return True
    except Exception as e:
        logger.error(f"Error removing all filters: {e}")
        return False

# ================ NOTES SYSTEM ================
async def add_note(chat_id: int, name: str, content: str, file_id: str = None) -> bool:
    """Add a note"""
    try:
        await notes_col.update_one(
            {"chat_id": chat_id, "name": name.lower()},
            {
                "$set": {
                    "content": content,
                    "file_id": file_id,
                    "created_at": datetime.datetime.now()
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error adding note: {e}")
        return False

async def get_note(chat_id: int, name: str) -> Optional[Dict]:
    """Get a note"""
    return await notes_col.find_one({"chat_id": chat_id, "name": name.lower()})

async def get_all_notes(chat_id: int) -> List[Dict]:
    """Get all notes for a group"""
    notes = []
    async for note in notes_col.find({"chat_id": chat_id}):
        notes.append(note)
    return notes

async def remove_note(chat_id: int, name: str) -> bool:
    """Remove a note"""
    try:
        await notes_col.delete_one({"chat_id": chat_id, "name": name.lower()})
        return True
    except Exception as e:
        logger.error(f"Error removing note: {e}")
        return False

async def remove_all_notes(chat_id: int) -> bool:
    """Remove all notes for a group"""
    try:
        await notes_col.delete_many({"chat_id": chat_id})
        return True
    except Exception as e:
        logger.error(f"Error removing all notes: {e}")
        return False

# ================ ANTISPAM SYSTEM ================
async def add_spam_count(user_id: int) -> int:
    """Increment spam count for user"""
    try:
        result = await antispam_col.update_one(
            {"_id": user_id},
            {
                "$inc": {"count": 1},
                "$set": {"last_seen": datetime.datetime.now()},
                "$setOnInsert": {"first_seen": datetime.datetime.now()}
            },
            upsert=True
        )
        
        if result.upserted_id:
            return 1
        
        user = await antispam_col.find_one({"_id": user_id})
        return user.get("count", 1)
    except Exception as e:
        logger.error(f"Error adding spam count: {e}")
        return 1

async def get_spam_count(user_id: int) -> int:
    """Get spam count for user"""
    user = await antispam_col.find_one({"_id": user_id})
    return user.get("count", 0) if user else 0

async def reset_spam_count(user_id: int) -> bool:
    """Reset spam count for user"""
    try:
        await antispam_col.delete_one({"_id": user_id})
        return True
    except Exception as e:
        logger.error(f"Error resetting spam count: {e}")
        return False

# ================ BLACKLIST SYSTEM ================
async def add_to_blacklist(user_id: int, reason: str = None) -> bool:
    """Add user to global blacklist"""
    try:
        await blacklist_col.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "reason": reason,
                    "blacklisted_at": datetime.datetime.now()
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error adding to blacklist: {e}")
        return False

async def remove_from_blacklist(user_id: int) -> bool:
    """Remove user from blacklist"""
    try:
        await blacklist_col.delete_one({"_id": user_id})
        return True
    except Exception as e:
        logger.error(f"Error removing from blacklist: {e}")
        return False

async def is_blacklisted(user_id: int) -> bool:
    """Check if user is blacklisted"""
    user = await blacklist_col.find_one({"_id": user_id})
    return user is not None

async def get_all_blacklisted() -> List[Dict]:
    """Get all blacklisted users"""
    users = []
    async for user in blacklist_col.find():
        users.append(user)
    return users

# ================ BOT STATS ================
async def get_bot_stats() -> Dict:
    """Get comprehensive bot statistics"""
    try:
        # Clean expired premium
        now = datetime.datetime.now()
        async for group in groups_col.find({
            "is_premium": True,
            "premium_expiry": {"$lt": now}
        }):
            await remove_premium(group["_id"])
        
        stats = {
            "total_users": await users_col.count_documents({"banned": False}),
            "total_groups": await groups_col.count_documents({"bot_removed": {"$ne": True}}),
            "banned_users": await users_col.count_documents({"banned": True}),
            "premium_groups": 0,
            "active_groups": 0,
            "pending_requests": await movie_requests_col.count_documents({"status": "pending"}),
            "total_requests": await movie_requests_col.count_documents({}),
            "total_filters": await filters_col.count_documents({}),
            "total_notes": await notes_col.count_documents({}),
            "blacklisted_users": await blacklist_col.count_documents({}),
            "active_today": 0,
            "new_users_today": 0,
            "new_groups_today": 0
        }
        
        # Premium groups
        async for group in groups_col.find({
            "is_premium": True,
            "bot_removed": {"$ne": True}
        }):
            if group.get("premium_expiry") and group["premium_expiry"] > now:
                stats["premium_groups"] += 1
        
        # Active groups
        day_ago = now - timedelta(days=1)
        stats["active_groups"] = await groups_col.count_documents({
            "last_active": {"$gte": day_ago},
            "bot_removed": {"$ne": True}
        })
        
        # New today
        stats["new_users_today"] = await users_col.count_documents({
            "joined_at": {"$gte": day_ago}
        })
        
        stats["new_groups_today"] = await groups_col.count_documents({
            "added_at": {"$gte": day_ago}
        })
        
        return stats
    except Exception as e:
        logger.error(f"Error getting bot stats: {e}")
        return {}

# ================ BOT INSTANCE TRACKING ================
async def set_bot_instance(bot_id: int, status: str = "running") -> bool:
    """Track current bot instance"""
    try:
        await bot_status_col.update_one(
            {"_id": "current_bot"},
            {
                "$set": {
                    "bot_id": bot_id,
                    "status": status,
                    "last_updated": datetime.datetime.now()
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error setting bot instance: {e}")
        return False

async def get_bot_instance() -> Optional[Dict]:
    """Get current bot instance info"""
    return await bot_status_col.find_one({"_id": "current_bot"})

# ================ CLEANUP FUNCTIONS ================
async def clear_junk() -> Dict:
    """Clear all junk data"""
    deleted_count = {
        "banned_users": 0,
        "inactive_groups": 0,
        "old_warnings": 0,
        "old_requests": 0,
        "bio_warnings": 0,
        "expired_cache": 0,
        "spam_records": 0
    }
    
    try:
        # Delete banned users
        result = await users_col.delete_many({"banned": True})
        deleted_count["banned_users"] = result.deleted_count
        
        # Delete inactive groups
        result = await groups_col.delete_many({"bot_removed": True})
        deleted_count["inactive_groups"] = result.deleted_count
        
        # Delete old warnings (30+ days)
        month_ago = datetime.datetime.now() - timedelta(days=30)
        result = await warnings_col.delete_many({"last_warning": {"$lt": month_ago}})
        deleted_count["old_warnings"] = result.deleted_count
        
        # Delete old bio warnings
        result = await bio_warnings_col.delete_many({"last_warning": {"$lt": month_ago}})
        deleted_count["bio_warnings"] = result.deleted_count
        
        # Delete old completed requests (7+ days)
        week_ago = datetime.datetime.now() - timedelta(days=7)
        result = await movie_requests_col.delete_many({
            "status": {"$in": ["completed", "rejected"]},
            "updated_at": {"$lt": week_ago}
        })
        deleted_count["old_requests"] = result.deleted_count
        
        # Clear expired cache
        deleted_count["expired_cache"] = await clear_expired_cache()
        
        # Clear old spam records (7+ days)
        result = await antispam_col.delete_many({
            "last_seen": {"$lt": week_ago}
        })
        deleted_count["spam_records"] = result.deleted_count
        
        logger.info(f"Cleanup completed: {deleted_count}")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Clear junk error: {e}")
        return deleted_count

# Initialize indexes on startup
async def init_db():
    await create_indexes()
