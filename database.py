from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from datetime import datetime, timedelta
import asyncio
from typing import Dict, List, Optional, Any
import pytz

IST = pytz.timezone('Asia/Kolkata')

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
        expiry_date = datetime.now(IST) + timedelta(days=months * 30)
        await self.db.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "is_premium": True,
                "premium_expiry": expiry_date,
                "premium_start": datetime.now(IST),
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
        expiry = group.get("premium_expiry")
        if expiry and datetime.now(IST) > expiry:
            await self.db.groups.update_one(
                {"chat_id": chat_id},
                {"$set": {
                    "is_premium": False,
                    "ads_enabled": True
                }}
            )
            return False
        return True
    
    async def get_premium_info(self, chat_id: int):
        """Get premium details"""
        group = await self.db.groups.find_one({"chat_id": chat_id})
        if group and group.get("is_premium"):
            return {
                "is_premium": True,
                "expiry": group.get("premium_expiry"),
                "start": group.get("premium_start"),
                "months": group.get("premium_months", 0)
            }
        return {"is_premium": False}
    
    # ========== FSUB SYSTEM ==========
    async def set_fsub_channel(self, chat_id: int, channel_username: str, channel_id: int):
        """Set force subscribe channel for group"""
        # Remove @ if present
        if channel_username.startswith('@'):
            channel_username = channel_username[1:]
        
        await self.db.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "fsub_enabled": True,
                "fsub_channel": channel_username,
                "fsub_channel_id": channel_id
            }},
            upsert=True
        )
        return True
    
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
                "channel_id": group.get("fsub_channel_id"),
                "enabled": True
            }
        return {"enabled": False}
    
    async def check_user_fsub_status(self, user_id: int, channel_id: int):
        """Check if user is subscribed to channel"""
        # This requires bot to be admin in channel
        # We'll track via database when user joins
        user_status = await self.db.fsub_status.find_one({
            "user_id": user_id,
            "channel_id": channel_id
        })
        return user_status.get("is_member", False) if user_status else False
    
    async def update_fsub_status(self, user_id: int, channel_id: int, is_member: bool):
        """Update user's subscription status"""
        await self.db.fsub_status.update_one(
            {"user_id": user_id, "channel_id": channel_id},
            {"$set": {
                "is_member": is_member,
                "last_checked": datetime.now(IST)
            }},
            upsert=True
        )
    
    # ========== FORCE JOIN SYSTEM ==========
    async def set_force_join(self, chat_id: int, count: int):
        """Set force join requirements"""
        await self.db.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "force_join_enabled": count > 0,
                "force_join_count": count,
                "force_join_members": [],
                "force_join_waiting": []
            }},
            upsert=True
        )
        return True
    
    async def disable_force_join(self, chat_id: int):
        """Disable force join"""
        await self.db.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "force_join_enabled": False,
                "force_join_count": 0
            }}
        )
    
    async def add_user_to_waiting(self, chat_id: int, user_id: int, username: str = ""):
        """Add user to waiting list until they invite members"""
        await self.db.groups.update_one(
            {"chat_id": chat_id},
            {"$addToSet": {
                "force_join_waiting": {
                    "user_id": user_id,
                    "username": username,
                    "joined_at": datetime.now(IST),
                    "invited_count": 0
                }
            }},
            upsert=True
        )
    
    async def remove_user_from_waiting(self, chat_id: int, user_id: int):
        """Remove user from waiting list"""
        await self.db.groups.update_one(
            {"chat_id": chat_id},
            {"$pull": {
                "force_join_waiting": {"user_id": user_id}
            }}
        )
    
    async def get_waiting_user(self, chat_id: int, user_id: int):
        """Get waiting user info"""
        group = await self.db.groups.find_one({"chat_id": chat_id})
        if group and group.get("force_join_waiting"):
            for user in group.get("force_join_waiting", []):
                if user.get("user_id") == user_id:
                    return user
        return None
    
    async def update_invited_count(self, chat_id: int, user_id: int, invited_id: int):
        """Update invited member count"""
        # Add to invited members list
        await self.db.invitations.update_one(
            {
                "chat_id": chat_id,
                "inviter_id": user_id,
                "invited_id": invited_id
            },
            {"$set": {
                "invited_at": datetime.now(IST),
                "status": "pending"
            }},
            upsert=True
        )
        
        # Count how many unique users this user has invited
        count = await self.db.invitations.count_documents({
            "chat_id": chat_id,
            "inviter_id": user_id
        })
        
        # Update waiting user's count
        await self.db.groups.update_one(
            {"chat_id": chat_id, "force_join_waiting.user_id": user_id},
            {"$set": {"force_join_waiting.$.invited_count": count}}
        )
        
        return count
    
    async def get_invited_count(self, chat_id: int, user_id: int):
        """Get how many members user has invited"""
        return await self.db.invitations.count_documents({
            "chat_id": chat_id,
            "inviter_id": user_id
        })
    
    async def mark_invitation_completed(self, chat_id: int, invited_id: int):
        """Mark invitation as completed when user joins"""
        await self.db.invitations.update_one(
            {"chat_id": chat_id, "invited_id": invited_id},
            {"$set": {"status": "completed"}}
        )
    
    # ========== USER MANAGEMENT ==========
    async def add_user(self, user_id: int, username: str = ""):
        await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "username": username,
                "joined": datetime.now(IST),
                "last_active": datetime.now(IST),
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
            {"$set": {"last_active": datetime.now(IST)}}
        )
    
    async def get_user(self, user_id: int):
        return await self.db.users.find_one({"user_id": user_id})
    
    async def increment_request_count(self, user_id: int):
        """Increment user's request count for today"""
        today = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
        user = await self.get_user(user_id)
        
        if user:
            last_request = user.get("last_request")
            if last_request and last_request >= today:
                new_count = user.get("requests_today", 0) + 1
            else:
                new_count = 1
            
            await self.db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "requests_today": new_count,
                    "last_request": datetime.now(IST)
                }}
            )
            return new_count
        return 1
    
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
                "force_join_waiting": [],
                "cooldown_time": Config.REQUEST_COOLDOWN,
                "created": datetime.now(IST)
            }
            await self.db.groups.insert_one(default_settings)
            return default_settings
        
        # Ensure features exist
        if "features" not in settings:
            settings["features"] = Config.FEATURE_DEFAULTS.copy()
        
        # Ensure force_join_waiting exists
        if "force_join_waiting" not in settings:
            settings["force_join_waiting"] = []
        
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
        request_id = f"{chat_id}_{user_id}_{int(datetime.now(IST).timestamp())}"
        
        await self.db.requests.insert_one({
            "request_id": request_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "movie_name": movie_name,
            "status": "pending",
            "requested_at": datetime.now(IST),
            "completed_at": None,
            "completed_by": None,
            "notes": ""
        })
        
        return request_id
    
    # ========== MOVIE SEARCH SYSTEM ==========
    async def save_search_results(self, query: str, results: list):
        """Save movie search results for quick access"""
        search_id = f"search_{int(datetime.now(IST).timestamp())}"
        
        await self.db.search_cache.insert_one({
            "search_id": search_id,
            "query": query,
            "results": results,
            "created_at": datetime.now(IST),
            "expires_at": datetime.now(IST) + timedelta(hours=24)
        })
        
        return search_id
    
    async def get_search_results(self, search_id: str):
        """Get cached search results"""
        cache = await self.db.search_cache.find_one({"search_id": search_id})
        if cache and datetime.now(IST) < cache.get("expires_at"):
            return cache.get("results", [])
        return None
    
    # ========== STATISTICS ==========
    async def get_bot_stats(self):
        total_users = await self.db.users.count_documents({})
        total_groups = await self.db.groups.count_documents({})
        total_requests = await self.db.requests.count_documents({})
        pending_requests = await self.db.requests.count_documents({"status": "pending"})
        
        # Today's requests
        today = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
        today_requests = await self.db.requests.count_documents({
            "requested_at": {"$gte": today}
        })
        
        # Premium groups
        premium_groups = await self.db.groups.count_documents({"is_premium": True})
        
        return {
            "total_users": total_users,
            "total_groups": total_groups,
            "total_requests": total_requests,
            "pending_requests": pending_requests,
            "today_requests": today_requests,
            "premium_groups": premium_groups
        }
    
    async def get_group_stats(self, chat_id: int):
        """Get statistics for a specific group"""
        group_requests = await self.db.requests.count_documents({"chat_id": chat_id})
        today_requests = await self.db.requests.count_documents({
            "chat_id": chat_id,
            "requested_at": {"$gte": datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)}
        })
        
        group = await self.get_group_settings(chat_id)
        
        return {
            "total_requests": group_requests,
            "today_requests": today_requests,
            "is_premium": group.get("is_premium", False),
            "member_count": 0,  # Will be filled by bot
            "created": group.get("created")
        }

# Global instance
db = Database()
