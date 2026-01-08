# database.py

import motor.motor_asyncio
from config import Config
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)  # NAME CORRECT KIYA HAI

class Database:
    def __init__(self):  # INIT CORRECT KIYA HAI
        self.client = motor.motor_asyncio.AsyncIOMotorClient(Config.MONGO_DB_URL)
        self.db = self.client["MovieBotDB"]
        self.users = self.db.users
        self.groups = self.db.groups
        self.requests = self.db.requests
        self.premium = self.db.premium
        
        # Create indexes
        # Note: create_index async nahi hai, ensure_index use karna hoga
        try:
            loop = self.client.get_io_loop()
            loop.run_until_complete(self.setup_indexes())
        except:
            pass
    
    async def setup_indexes(self):
        """Create database indexes"""
        await self.users.create_index("id", unique=True)
        await self.groups.create_index("id", unique=True)
        await self.premium.create_index("group_id", unique=True)

    # --- User Handling ---
    async def add_user(self, user_id, name, username=""):
        try:
            user = await self.users.find_one({"id": user_id})
            if not user:
                await self.users.insert_one({
                    "id": user_id,
                    "name": name,
                    "username": username,
                    "joined_date": datetime.now(),
                    "last_active": datetime.now()
                })
                logger.info(f"New user added: {user_id} - {name}")
                return True
            else:
                # Update last active
                await self.users.update_one(
                    {"id": user_id},
                    {"$set": {"last_active": datetime.now()}}
                )
                return False
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False

    async def get_user(self, user_id):
        return await self.users.find_one({"id": user_id})

    async def get_all_users(self):
        cursor = self.users.find({})
        users = []
        async for user in cursor:
            users.append(user)
        return users

    async def delete_user(self, user_id):
        await self.users.delete_one({"id": user_id})

    # --- Group Handling ---
    async def add_group(self, group_id, title, owner_id):
        try:
            group = await self.groups.find_one({"id": group_id})
            if not group:
                await self.groups.insert_one({
                    "id": group_id,
                    "title": title,
                    "owner_id": owner_id,
                    "added_date": datetime.now(),
                    "settings": {
                        "welcome": True,
                        "spell_check": True,
                        "fsub": None,
                        "auto_delete_files": False,
                        "delete_after_minutes": Config.AUTO_DELETE_MINUTES
                    },
                    "stats": {
                        "total_messages": 0,
                        "total_users": 0,
                        "last_updated": datetime.now()
                    }
                })
                logger.info(f"New group added: {group_id} - {title}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error adding group: {e}")
            return False

    async def get_group(self, group_id):
        return await self.groups.find_one({"id": group_id})

    async def update_settings(self, group_id, setting_key, value):
        await self.groups.update_one(
            {"id": group_id},
            {"$set": {f"settings.{setting_key}": value}}
        )

    async def update_group_stats(self, group_id, field, increment=1):
        await self.groups.update_one(
            {"id": group_id},
            {"$inc": {f"stats.{field}": increment},
             "$set": {"stats.last_updated": datetime.now()}}
        )

    async def get_all_groups(self):
        cursor = self.groups.find({})
        groups = []
        async for group in cursor:
            groups.append(group)
        return groups

    async def delete_group(self, group_id):
        await self.groups.delete_one({"id": group_id})

    # --- Premium ---
    async def add_premium(self, group_id, months):
        expiry_date = datetime.now() + timedelta(days=30*months)
        await self.premium.update_one(
            {"group_id": group_id},
            {"$set": {
                "group_id": group_id,
                "expiry_date": expiry_date,
                "purchased_date": datetime.now(),
                "months": months,
                "amount": Config.PREMIUM_PRICE_PER_MONTH * months
            }},
            upsert=True
        )
        
        # Also update in groups collection
        await self.groups.update_one(
            {"id": group_id},
            {"$set": {"premium_expiry": expiry_date}}
        )

    async def is_premium(self, group_id):
        premium = await self.premium.find_one({"group_id": group_id})
        if premium and premium.get("expiry_date"):
            if premium["expiry_date"] > datetime.now():
                return True
        return False

    async def get_premium_info(self, group_id):
        return await self.premium.find_one({"group_id": group_id})

    async def get_all_premium(self):
        cursor = self.premium.find({})
        premiums = []
        async for premium in cursor:
            premiums.append(premium)
        return premiums

    # --- Requests ---
    async def add_request(self, user_id, group_id, movie_name):
        await self.requests.insert_one({
            "user_id": user_id,
            "group_id": group_id,
            "movie_name": movie_name,
            "timestamp": datetime.now(),
            "status": "pending"
        })

    async def get_group_requests(self, group_id, limit=50):
        cursor = self.requests.find({"group_id": group_id}).sort("timestamp", -1).limit(limit)
        requests = []
        async for req in cursor:
            requests.append(req)
        return requests

    # --- Stats ---
    async def get_stats(self):
        u_count = await self.users.count_documents({})
        g_count = await self.groups.count_documents({})
        r_count = await self.requests.count_documents({})
        
        # Active groups (last 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        active_groups = await self.groups.count_documents({
            "stats.last_updated": {"$gte": week_ago}
        })
        
        return u_count, g_count, r_count, active_groups

db = Database()
