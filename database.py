#  database.py

import motor.motor_asyncio
from config import Config
from datetime import datetime

class Database:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(Config.MONGO_DB_URL)
        self.db = self.client["MovieBotDB"]
        self.users = self.db.users
        self.groups = self.db.groups

    # --- User Handling ---
    async def add_user(self, user_id, name):
        user = await self.users.find_one({"id": user_id})
        if not user:
            await self.users.insert_one({"id": user_id, "name": name})

    async def get_all_users(self):
        return self.users.find({})
    
    async def delete_user(self, user_id):
        await self.users.delete_one({"id": user_id})

    # --- Group Handling ---
    async def add_group(self, group_id, title, owner_id):
        group = await self.groups.find_one({"id": group_id})
        if not group:
            await self.groups.insert_one({
                "id": group_id,
                "title": title,
                "owner_id": owner_id,
                "settings": {
                    "welcome": True,
                    "spell_check": True,
                    "fsub": None  # Channel ID if set
                },
                "premium_expiry": None
            })
            return True
        return False

    async def get_group(self, group_id):
        return await self.groups.find_one({"id": group_id})

    async def update_settings(self, group_id, setting_key, value):
        await self.groups.update_one({"id": group_id}, {"$set": {f"settings.{setting_key}": value}})

    async def get_all_groups(self):
        return self.groups.find({})

    async def delete_group(self, group_id):
        await self.groups.delete_one({"id": group_id})

    # --- Premium ---
    async def add_premium(self, chat_id, expiry_date):
        # expiry_date should be datetime object
        await self.groups.update_one({"id": chat_id}, {"$set": {"premium_expiry": expiry_date}})

    async def is_premium(self, chat_id):
        group = await self.groups.find_one({"id": chat_id})
        if group and group.get("premium_expiry"):
            if group["premium_expiry"] > datetime.now():
                return True
        return False

    # --- Stats ---
    async def get_stats(self):
        u_count = await self.users.count_documents({})
        g_count = await self.groups.count_documents({})
        return u_count, g_count

db = Database()
