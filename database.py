from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from datetime import datetime
import asyncio

class Database:
    def __init__(self):
        self.client = None
        self.db = None
        
    async def init_db(self):
        """Initialize database connection"""
        try:
            self.client = AsyncIOMotorClient(Config.MONGO_DB_URL)
            self.db = self.client.movie_bot
            print("✅ MongoDB Connected Successfully!")
            return True
        except Exception as e:
            print(f"❌ MongoDB Connection Error: {e}")
            return False
    
    # User Management
    async def add_user(self, user_id, username=""):
        """Add new user to database"""
        await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "username": username,
                "joined": datetime.now(),
                "blocked": False
            }},
            upsert=True
        )
    
    async def get_user(self, user_id):
        """Get user data"""
        return await self.db.users.find_one({"user_id": user_id})
    
    async def total_users(self):
        """Count total users"""
        return await self.db.users.count_documents({"blocked": False})
    
    async def get_all_users(self):
        """Get all users"""
        return await self.db.users.find({"blocked": False}).to_list(length=None)
    
    # Group Management
    async def add_group(self, chat_id, title=""):
        """Add group to database"""
        await self.db.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "chat_id": chat_id,
                "title": title,
                "added": datetime.now()
            }},
            upsert=True
        )
    
    async def total_groups(self):
        """Count total groups"""
        return await self.db.groups.count_documents({})
    
    # FSub Settings
    async def set_fsub(self, chat_id, channels):
        """Set force subscribe channels"""
        await self.db.settings.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "fsub": channels,
                "fsub_enabled": True
            }},
            upsert=True
        )
    
    async def get_fsub(self, chat_id):
        """Get FSub settings"""
        data = await self.db.settings.find_one({"chat_id": chat_id})
        if data and data.get("fsub_enabled", False):
            return data.get("fsub", [])
        return []
    
    async def disable_fsub(self, chat_id):
        """Disable FSub"""
        await self.db.settings.update_one(
            {"chat_id": chat_id},
            {"$set": {"fsub_enabled": False}}
        )
    
    # Force Join Settings
    async def set_force_join(self, chat_id, count):
        """Set force join member count"""
        await self.db.settings.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "force_join": count,
                "force_join_enabled": True
            }},
            upsert=True
        )
    
    async def get_force_join(self, chat_id):
        """Get force join settings"""
        data = await self.db.settings.find_one({"chat_id": chat_id})
        if data and data.get("force_join_enabled", False):
            return data.get("force_join", 0)
        return 0
    
    async def disable_force_join(self, chat_id):
        """Disable force join"""
        await self.db.settings.update_one(
            {"chat_id": chat_id},
            {"$set": {"force_join_enabled": False}}
        )
    
    # User Verification
    async def set_verified(self, chat_id, user_id):
        """Mark user as verified"""
        await self.db.verification.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"$set": {"verified": True, "time": datetime.now()}},
            upsert=True
        )
    
    async def is_verified(self, chat_id, user_id):
        """Check if user is verified"""
        data = await self.db.verification.find_one(
            {"chat_id": chat_id, "user_id": user_id}
        )
        return data.get("verified", False) if data else False
    
    # Broadcast Tracking
    async def add_broadcast(self, message_id, total_users):
        """Add broadcast record"""
        await self.db.broadcasts.insert_one({
            "message_id": message_id,
            "total_users": total_users,
            "sent": 0,
            "failed": 0,
            "time": datetime.now()
        })
    
    # Cleanup
    async def clear_junk(self):
        """Remove blocked/deleted users"""
        result = await self.db.users.delete_many({"blocked": True})
        return result.deleted_count
    
    async def get_stats(self):
        """Get bot statistics"""
        return {
            "users": await self.total_users(),
            "groups": await self.total_groups(),
            "blocked": await self.db.users.count_documents({"blocked": True})
        }

# Create global instance
db = Database()
