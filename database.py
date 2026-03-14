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
user_channels_col = db["user_channels"]  # New: user ke channels store karne ke liye

# ================ USER FUNCTIONS ================
async def add_user(user_id, username=None, first_name=None):
    await users_col.update_one(
        {"_id": user_id},
        {"$set": {
            "username": username,
            "first_name": first_name,
            "banned": False,
            "last_seen": datetime.datetime.now()
        }, "$setOnInsert": {"joined_at": datetime.datetime.now()}},
        upsert=True
    )

async def get_user(user_id):
    return await users_col.find_one({"_id": user_id})

async def get_all_users():
    return [u["_id"] async for u in users_col.find({"banned": False})]

async def ban_user(user_id):
    await users_col.update_one({"_id": user_id}, {"$set": {"banned": True}})

async def unban_user(user_id):
    await users_col.update_one({"_id": user_id}, {"$set": {"banned": False}})

async def delete_user(user_id):
    await users_col.delete_one({"_id": user_id})

# ================ GROUP FUNCTIONS ================
async def add_group(group_id, title=None, username=None):
    await groups_col.update_one(
        {"_id": group_id},
        {"$set": {
            "title": title,
            "username": username,
            "active": True,
            "last_active": datetime.datetime.now()
        }, "$setOnInsert": {
            "added_at": datetime.datetime.now(),
            "is_premium": False,
            "premium_expiry": None
        }},
        upsert=True
    )

async def get_group(group_id):
    return await groups_col.find_one({"_id": group_id})

async def get_all_groups():
    return [g["_id"] async for g in groups_col.find({})]

async def remove_group(group_id):
    await groups_col.delete_one({"_id": group_id})

# ================ PREMIUM FUNCTIONS ================
async def add_premium(group_id, months):
    expiry = datetime.datetime.now() + timedelta(days=30 * int(months))
    await groups_col.update_one(
        {"_id": group_id},
        {"$set": {"is_premium": True, "premium_expiry": expiry}},
        upsert=True
    )
    return expiry

async def remove_premium(group_id):
    await groups_col.update_one(
        {"_id": group_id},
        {"$set": {"is_premium": False, "premium_expiry": None}}
    )

async def check_is_premium(group_id):
    group = await groups_col.find_one({"_id": group_id})
    if not group or not group.get("is_premium"):
        return False
    expiry = group.get("premium_expiry")
    if expiry and expiry > datetime.datetime.now():
        return True
    await remove_premium(group_id)
    return False

# ================ SETTINGS FUNCTIONS ================
async def get_settings(chat_id):
    settings = await settings_col.find_one({"_id": chat_id})
    if not settings:
        default = {
            "_id": chat_id,
            "spelling_on": True,
            "spelling_mode": "simple",
            "auto_delete_on": False,
            "delete_time": 0,
            "welcome_enabled": True,
            "welcome_text": "",
            "welcome_photo": None,
            "welcome_buttons": [],
            "ai_enabled": True,
            "link_protection": True,
            "abuse_protection": True,
        }
        try:
            await settings_col.insert_one(default)
        except:
            pass
        return default
    return settings

async def update_settings(chat_id, key, value):
    await settings_col.update_one(
        {"_id": chat_id},
        {"$set": {key: value}},
        upsert=True
    )

# ================ WELCOME FUNCTIONS ================
async def set_welcome_message(chat_id, text, photo_id=None, buttons=None):
    await settings_col.update_one(
        {"_id": chat_id},
        {"$set": {
            "welcome_text": text,
            "welcome_photo": photo_id,
            "welcome_buttons": buttons or [],
            "welcome_enabled": True
        }},
        upsert=True
    )

async def get_welcome_message(chat_id):
    s = await settings_col.find_one({"_id": chat_id})
    if s and (s.get("welcome_text") or s.get("welcome_photo")):
        return {
            "text": s.get("welcome_text", ""),
            "photo_id": s.get("welcome_photo"),
            "buttons": s.get("welcome_buttons", [])
        }
    return None

# ================ FORCE SUB (GROUP) ================
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

# ================ USER CHANNELS (AUTO ACCEPT) ================
async def add_user_channel(user_id, channel_id, channel_title, channel_username=None):
    """User ke channel ko save karo"""
    await user_channels_col.update_one(
        {"user_id": user_id, "channel_id": channel_id},
        {"$set": {
            "channel_title": channel_title,
            "channel_username": channel_username,
            "auto_accept": True,
            "connected": True,
            "added_at": datetime.datetime.now()
        }},
        upsert=True
    )

async def get_user_channels(user_id):
    """User ke saare channels fetch karo"""
    channels = []
    async for ch in user_channels_col.find({"user_id": user_id}):
        channels.append(ch)
    return channels

async def get_user_channel(user_id, channel_id):
    return await user_channels_col.find_one({"user_id": user_id, "channel_id": channel_id})

async def remove_user_channel(user_id, channel_id):
    await user_channels_col.delete_one({"user_id": user_id, "channel_id": channel_id})
    # Auto accept bhi band karo
    await auto_accept_col.delete_one({"_id": channel_id})

async def toggle_channel_auto_accept(user_id, channel_id, status: bool):
    await user_channels_col.update_one(
        {"user_id": user_id, "channel_id": channel_id},
        {"$set": {"auto_accept": status, "connected": status}}
    )
    if status:
        await auto_accept_col.update_one(
            {"_id": channel_id},
            {"$set": {"enabled": True}},
            upsert=True
        )
    else:
        await auto_accept_col.update_one(
            {"_id": channel_id},
            {"$set": {"enabled": False}},
            upsert=True
        )

# ================ AUTO ACCEPT ================
async def set_auto_accept(chat_id, status: bool):
    await auto_accept_col.update_one(
        {"_id": chat_id},
        {"$set": {"enabled": status}},
        upsert=True
    )

async def get_auto_accept(chat_id):
    data = await auto_accept_col.find_one({"_id": chat_id})
    return data.get("enabled", False) if data else False

# ================ WARNING SYSTEM ================
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

# ================ MOVIE REQUESTS ================
async def add_movie_request(chat_id, user_id, movie_name):
    await movie_requests_col.insert_one({
        "chat_id": chat_id,
        "user_id": user_id,
        "movie_name": movie_name,
        "status": "pending",
        "requested_at": datetime.datetime.now()
    })

async def update_request_status(request_id, status):
    from bson import ObjectId
    await movie_requests_col.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {"status": status, "updated_at": datetime.datetime.now()}}
    )

# ================ BOT STATS ================
async def get_bot_stats():
    stats = {
        "total_users": await users_col.count_documents({"banned": False}),
        "total_groups": await groups_col.count_documents({}),
        "banned_users": await users_col.count_documents({"banned": True}),
        "premium_groups": await groups_col.count_documents({"is_premium": True}),
        "total_requests": await movie_requests_col.count_documents({}),
        "pending_requests": await movie_requests_col.count_documents({"status": "pending"}),
    }
    return stats

# ================ CLEANUP ================
async def clear_junk():
    counts = {"banned_users": 0, "old_warnings": 0, "old_requests": 0}
    r = await users_col.delete_many({"banned": True})
    counts["banned_users"] = r.deleted_count
    week_ago = datetime.datetime.now() - timedelta(days=7)
    r = await warnings_col.delete_many({"last_warning": {"$lt": week_ago}})
    counts["old_warnings"] = r.deleted_count
    r = await movie_requests_col.delete_many({
        "status": {"$in": ["completed", "rejected"]},
        "updated_at": {"$lt": week_ago}
    })
    counts["old_requests"] = r.deleted_count
    return counts
