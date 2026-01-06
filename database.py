from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from datetime import datetime, timedelta
import asyncio
from typing import Dict, List, Optional

class Database:
    def __init__(self):
        self.client = None
        self.db = None
        
    async def init_db(self):
        try:
            self.client = AsyncIOMotorClient(Config.MONGO_DB_URL)
            self.db = self.client.movie_bot_pro
            print("✅ Database Connected!")
            return True
        except Exception as e:
            print(f"❌ DB Error: {e}")
            return False
    
    # ========== PREMIUM SYSTEM ==========
    async def set_premium(self, chat_id: int, months: int):
        """Activate premium for a group"""
        expiry_date = datetime.now() + timedelta(days=months * 30)
        await self.db.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "is_premium": True,
                "premium_expiry": expiry_date,
                "premium_start": datetime.now(),
                "premium_months": months,
                "ads_enabled": False  # No ads for premium
            }},
            upsert=True
        )
        return expiry_date
    
    async def check_premium(self, chat_id: int):
        """Check if group has active premium"""
        group = await self.db.groups.find_one({"chat_id": chat_id})
        
        if not group or not group.get("is_premium"):
            return False
        
        # Check if expired
        if datetime.now() > group.get("premium_expiry", datetime.min):
            await self.db.groups.update_one(
                {"chat_id": chat_id},
                {"$set": {
                    "is_premium": False,
                    "ads_enabled": True
                }}
            )
            return False
        return True
    
    async def get_premium_stats(self):
        """Get premium statistics"""
        total_premium = await self.db.groups.count_documents({"is_premium": True})
        active_premium = await self.db.groups.count_documents({
            "is_premium": True,
            "premium_expiry": {"$gt": datetime.now()}
        })
        expired_premium = await self.db.groups.count_documents({
            "is_premium": True,
            "premium_expiry": {"$lt": datetime.now()}
        })
        
        return {
            "total_premium": total_premium,
            "active_premium": active_premium,
            "expired_premium": expired_premium
        }
    
    # ========== USER MANAGEMENT ==========
    async def add_user(self, user_id: int, username: str = ""):
        await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "username": username,
                "first_name": "",
                "joined": datetime.now(),
                "last_active": datetime.now(),
                "blocked": False,
                "is_owner": user_id == Config.OWNER_ID,
                "requests_today": 0,
                "last_request": None,
                "is_premium_user": False,
                "premium_expiry": None
            }},
            upsert=True
        )
    
    async def update_user_activity(self, user_id: int):
        await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": {"last_active": datetime.now()}}
        )
    
    async def get_user(self, user_id: int):
        return await self.db.users.find_one({"user_id": user_id})
    
    # ========== GROUP MANAGEMENT ==========
    async def get_group_settings(self, chat_id: int):
        settings = await self.db.groups.find_one({"chat_id": chat_id})
        if not settings:
            # Create default settings
            default_settings = {
                "chat_id": chat_id,
                "title": "",
                "is_premium": False,
                "premium_expiry": None,
                "premium_start": None,
                "premium_months": 0,
                "ads_enabled": True,  # Show ads by default
                "features": Config.FEATURE_DEFAULTS.copy(),
                "auto_delete_time": Config.DEFAULT_AUTO_DELETE_TIME,
                "file_clean_time": 300,  # 5 minutes for files
                "fsub_channels": [],
                "fsub_enabled": False,
                "force_join_count": 0,
                "force_join_enabled": False,
                "request_channel": None,
                "cooldown_time": Config.REQUEST_COOLDOWN,
                "welcome_message": "Welcome! Request movies with /request",
                "created": datetime.now()
            }
            await self.db.groups.insert_one(default_settings)
            return default_settings
        return settings
    
    async def update_group_settings(self, chat_id: int, updates: dict):
        await self.db.groups.update_one(
            {"chat_id": chat_id},
            {"$set": updates},
            upsert=True
        )
    
    # ========== FEATURE TOGGLE SYSTEM ==========
    async def toggle_feature(self, chat_id: int, feature: str, value: bool):
        settings = await self.get_group_settings(chat_id)
        settings["features"][feature] = value
        await self.update_group_settings(chat_id, {"features": settings["features"]})
        return value
    
    async def get_feature_status(self, chat_id: int, feature: str):
        settings = await self.get_group_settings(chat_id)
        return settings["features"].get(feature, True)
    
    # ========== TIME SETTINGS ==========
    async def set_auto_delete_time(self, chat_id: int, seconds: int):
        await self.update_group_settings(chat_id, {"auto_delete_time": seconds})
    
    async def set_file_clean_time(self, chat_id: int, seconds: int):
        await self.update_group_settings(chat_id, {"file_clean_time": seconds})
    
    # ========== REQUEST SYSTEM ==========
    async def add_request(self, chat_id: int, user_id: int, movie_name: str):
        request_id = f"{chat_id}_{user_id}_{datetime.now().timestamp()}"
        
        await self.db.requests.insert_one({
            "request_id": request_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "movie_name": movie_name,
            "status": "pending",
            "requested_at": datetime.now(),
            "completed_at": None,
            "completed_by": None,
            "notes": ""
        })
        
        # Update user's last request time
        await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": {"last_request": datetime.now()}}
        )
        
        return request_id
    
    async def get_pending_requests(self, chat_id: int, limit: int = 10):
        return await self.db.requests.find({
            "chat_id": chat_id,
            "status": "pending"
        }).sort("requested_at", 1).limit(limit).to_list(length=None)
    
    async def complete_request(self, request_id: str, admin_id: int):
        await self.db.requests.update_one(
            {"request_id": request_id},
            {"$set": {
                "status": "completed",
                "completed_at": datetime.now(),
                "completed_by": admin_id
            }}
        )
    
    # ========== FILE CLEANER ==========
    async def add_file_to_cleaner(self, chat_id: int, message_id: int, delete_after: int):
        await self.db.file_cleaner.insert_one({
            "chat_id": chat_id,
            "message_id": message_id,
            "delete_at": datetime.now() + timedelta(seconds=delete_after),
            "added_at": datetime.now(),
            "deleted": False
        })
    
    async def get_files_to_clean(self):
        return await self.db.file_cleaner.find({
            "delete_at": {"$lt": datetime.now()},
            "deleted": False
        }).to_list(length=None)
    
    async def mark_file_cleaned(self, message_id: int):
        await self.db.file_cleaner.update_one(
            {"message_id": message_id},
            {"$set": {"deleted": True}}
        )
    
    # ========== VERIFICATION SYSTEM ==========
    async def set_verified_user(self, chat_id: int, user_id: int):
        await self.db.verified_users.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"$set": {"verified_at": datetime.now()}},
            upsert=True
        )
    
    async def is_verified(self, chat_id: int, user_id: int):
        doc = await self.db.verified_users.find_one({
            "chat_id": chat_id,
            "user_id": user_id
        })
        return doc is not None
    
    # ========== STATISTICS ==========
    async def get_bot_stats(self):
        total_users = await self.db.users.count_documents({"blocked": False})
        total_groups = await self.db.groups.count_documents({})
        blocked_users = await self.db.users.count_documents({"blocked": True})
        total_requests = await self.db.requests.count_documents({})
        pending_requests = await self.db.requests.count_documents({"status": "pending"})
        
        # Premium stats
        premium_stats = await self.get_premium_stats()
        
        # Today's requests
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_requests = await self.db.requests.count_documents({
            "requested_at": {"$gte": today}
        })
        
        return {
            "total_users": total_users,
            "total_groups": total_groups,
            "blocked_users": blocked_users,
            "total_requests": total_requests,
            "pending_requests": pending_requests,
            "today_requests": today_requests,
            "premium_stats": premium_stats
        }
    
    # ========== CLEANUP ==========
    async def cleanup_old_data(self):
        """Clean old data to save space"""
        # Delete requests older than 30 days
        month_ago = datetime.now() - timedelta(days=30)
        result1 = await self.db.requests.delete_many({
            "requested_at": {"$lt": month_ago}
        })
        
        # Delete cleaned files older than 7 days
        week_ago = datetime.now() - timedelta(days=7)
        result2 = await self.db.file_cleaner.delete_many({
            "added_at": {"$lt": week_ago}
        })
        
        return {
            "old_requests": result1.deleted_count,
            "old_files": result2.deleted_count
        }

# Global instance
db = Database()
