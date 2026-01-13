from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

client = AsyncIOMotorClient(Config.MONGO_DB_URL)
db = client["movie_bot"]

# Collections
users_col = db["users"]
groups_col = db["groups"]
settings_col = db["settings"]
force_sub_col = db["force_sub"]

async def add_user(user_id, username=None, first_name=None):
    await users_col.update_one(
        {"_id": user_id},
        {"$set": {"username": username, "first_name": first_name, "banned": False}},
        upsert=True
    )

async def get_user(user_id):
    return await users_col.find_one({"_id": user_id})

async def ban_user(user_id):
    await users_col.update_one({"_id": user_id}, {"$set": {"banned": True}})

async def unban_user(user_id):
    await users_col.update_one({"_id": user_id}, {"$set": {"banned": False}})

async def add_group(group_id, title=None, username=None):
    await groups_col.update_one(
        {"_id": group_id},
        {"$set": {"title": title, "username": username}},
        upsert=True
    )

async def remove_group(group_id):
    await groups_col.delete_one({"_id": group_id})

async def get_group(group_id):
    return await groups_col.find_one({"_id": group_id})

async def get_all_users():
    cursor = users_col.find({"banned": False})
    return [doc["_id"] async for doc in cursor]

async def get_all_groups():
    cursor = groups_col.find({})
    return [doc["_id"] async for doc in cursor]

async def get_user_count():
    return await users_col.count_documents({"banned": False})

async def get_group_count():
    return await groups_col.count_documents({})

async def get_settings(chat_id):
    settings = await settings_col.find_one({"_id": chat_id})
    if not settings:
        default_settings = {
            "_id": chat_id,
            "spelling_on": True,
            "auto_delete_on": False,
            "delete_time": 0,
            "welcome_enabled": True
        }
        await settings_col.insert_one(default_settings)
        return default_settings
    return settings

async def update_settings(chat_id, key, value):
    await settings_col.update_one(
        {"_id": chat_id},
        {"$set": {key: value}},
        upsert=True
    )

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

async def clear_junk():
    # Remove users who have blocked the bot (simulated by banned flag)
    await users_col.delete_many({"banned": True})
    # Remove groups where bot is no longer member (this would need external checking)
    # For now, just return count
    return await users_col.count_documents({"banned": True})
