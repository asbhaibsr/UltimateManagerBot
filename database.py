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
                "ads_enabled": False
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
    
    # ========== FSUB SYSTEM ==========
    async def set_fsub_channel(self, chat_id: int, channel_username: str, channel_id: int):
        """Set force subscribe channel for group"""
        await self.db.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "fsub_enabled": True,
                "fsub_channel": channel_username,
                "fsub_channel_id": channel_id
            }},
            upsert=True
        )
    
    async def disable_fsub(self, chat_id: int):
        """Disable force subscribe"""
        await self.db.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {"fsub_enabled": False}}
        )
    
    async def get_fsub_channel(self, chat_id: int):
        """Get FSUB channel info"""
        group = await self.db.groups.find_one({"chat_id": chat_id})
        if group and group.get("fsub_enabled"):
            return {
                "channel": group.get("fsub_channel"),
                "channel_id": group.get("fsub_channel_id")
            }
        return None
    
    # ========== FORCE JOIN SYSTEM ==========
    async def set_force_join(self, chat_id: int, count: int):
        """Set force join requirements"""
        await self.db.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "force_join_enabled": count > 0,
                "force_join_count": count,
                "force_join_members": []
            }},
            upsert=True
        )
    
    async def disable_force_join(self, chat_id: int):
        """Disable force join"""
        await self.db.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "force_join_enabled": False,
                "force_join_count": 0
            }}
        )
    
    async def add_invited_member(self, chat_id: int, inviter_id: int, invited_id: int):
        """Add invited member for force join tracking"""
        await self.db.force_join.update_one(
            {"chat_id": chat_id, "inviter_id": inviter_id},
            {"$addToSet": {"invited_members": invited_id}},
            upsert=True
        )
    
    async def get_invited_count(self, chat_id: int, user_id: int):
        """Get how many members user has invited"""
        record = await self.db.force_join.find_one(
            {"chat_id": chat_id, "inviter_id": user_id}
        )
        if record and record.get("invited_members"):
            return len(record["invited_members"])
        return 0
    
    # ========== USER MANAGEMENT ==========
    async def add_user(self, user_id: int, username: str = ""):
        await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "username": username,
                "joined": datetime.now(),
                "last_active": datetime.now(),
                "blocked": False,
                "is_owner": user_id == Config.OWNER_ID,
                "requests_today": 0,
                "last_request": None
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
                "ads_enabled": True,
                "features": Config.FEATURE_DEFAULTS.copy(),
                "auto_delete_time": Config.DEFAULT_AUTO_DELETE_TIME,
                "file_clean_time": 300,
                "fsub_enabled": False,
                "fsub_channel": None,
                "fsub_channel_id": None,
                "force_join_enabled": False,
                "force_join_count": 0,
                "cooldown_time": Config.REQUEST_COOLDOWN,
                "created": datetime.now()
            }
            await self.db.groups.insert_one(default_settings)
            return default_settings
        
        # Ensure features exist
        if "features" not in settings:
            settings["features"] = Config.FEATURE_DEFAULTS.copy()
        
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
    
    # ========== REQUEST SYSTEM ==========
    async def add_request(self, chat_id: int, user_id: int, movie_name: str):
        request_id = f"{chat_id}_{user_id}_{int(datetime.now().timestamp())}"
        
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
    
    # ========== STATISTICS ==========
    async def get_bot_stats(self):
        total_users = await self.db.users.count_documents({})
        total_groups = await self.db.groups.count_documents({})
        total_requests = await self.db.requests.count_documents({})
        pending_requests = await self.db.requests.count_documents({"status": "pending"})
        
        # Today's requests
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_requests = await self.db.requests.count_documents({
            "requested_at": {"$gte": today}
        })
        
        return {
            "total_users": total_users,
            "total_groups": total_groups,
            "total_requests": total_requests,
            "pending_requests": pending_requests,
            "today_requests": today_requests
        }

# Global instance
db = Database()
