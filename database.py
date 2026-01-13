import motor.motor_asyncio
from config import Config

# MongoDB connection
client = motor.motor_asyncio.AsyncIOMotorClient(Config.MONGO_DB_URL)
db = client["movie_helper_bot"]

# Collections
users_col = db["users"]
groups_col = db["groups"]
settings_col = db["settings"]
force_sub_col = db["force_sub"]

# User Functions
async def add_user(user_id, username=None, first_name=None, last_name=None):
    await users_col.update_one(
        {"_id": user_id},
        {
            "$set": {
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "banned": False,
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

# Group Functions
async def add_group(group_id, title=None, username=None):
    await groups_col.update_one(
        {"_id": group_id},
        {
            "$set": {
                "title": title,
                "username": username,
                "added_at": datetime.datetime.now()
            }
        },
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

# Settings Functions
async def get_settings(chat_id):
    settings = await settings_col.find_one({"_id": chat_id})
    if not settings:
        default_settings = {
            "_id": chat_id,
            "spelling_on": True,
            "auto_delete_on": False,
            "delete_time": 0,
            "welcome_enabled": True,
            "force_sub_enabled": False
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

# Force Subscribe Functions
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

# Utility Functions
async def clear_junk():
    result = await users_col.delete_many({"banned": True})
    return result.deleted_count

import datetime
