import motor.motor_asyncio
import datetime
from datetime import timedelta
from bson import ObjectId
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
premium_logs_col = db["premium_logs"]
admin_logs_col = db["admin_logs"]

# Indexes Creation (First time setup)
async def create_indexes():
    """Create necessary indexes for better performance"""
    try:
        # Users collection indexes
        await users_col.create_index("_id")
        await users_col.create_index("username")
        await users_col.create_index("banned")
        await users_col.create_index("joined_at")
        
        # Groups collection indexes
        await groups_col.create_index("_id")
        await groups_col.create_index("is_premium")
        await groups_col.create_index("premium_expiry")
        await groups_col.create_index("active")
        
        # Settings collection indexes
        await settings_col.create_index("_id")
        
        # Force sub collection indexes
        await force_sub_col.create_index("_id")
        
        # Warnings collection indexes
        await warnings_col.create_index([("chat_id", 1), ("user_id", 1)], unique=True)
        
        # Auto accept collection indexes
        await auto_accept_col.create_index("_id")
        
        # Movie requests collection indexes
        await movie_requests_col.create_index([("chat_id", 1), ("user_id", 1)])
        await movie_requests_col.create_index("status")
        await movie_requests_col.create_index("requested_at")
        
        # Premium logs indexes
        await premium_logs_col.create_index("group_id")
        await premium_logs_col.create_index("action_date")
        
        print("✅ Database indexes created successfully!")
    except Exception as e:
        print(f"⚠️ Warning creating indexes: {e}")

# ================ USER FUNCTIONS ================
async def add_user(user_id, username=None, first_name=None, last_name=None):
    """Add or update user in database"""
    user_data = {
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "banned": False,
        "joined_at": datetime.datetime.now(),
        "last_seen": datetime.datetime.now()
    }
    
    # Clean None values
    user_data = {k: v for k, v in user_data.items() if v is not None}
    
    await users_col.update_one(
        {"_id": user_id},
        {"$set": user_data},
        upsert=True
    )
    return True

async def get_user(user_id):
    """Get user details"""
    return await users_col.find_one({"_id": user_id})

async def update_user_last_seen(user_id):
    """Update user's last seen time"""
    await users_col.update_one(
        {"_id": user_id},
        {"$set": {"last_seen": datetime.datetime.now()}}
    )

async def get_all_users():
    """Get all active user IDs"""
    users = []
    async for user in users_col.find({"banned": False}):
        users.append(user["_id"])
    return users

async def get_user_count():
    """Get total active users count"""
    return await users_col.count_documents({"banned": False})

async def get_user_stats():
    """Get user statistics"""
    total_users = await users_col.count_documents({})
    active_users = await users_col.count_documents({"banned": False})
    banned_users = await users_col.count_documents({"banned": True})
    
    # Get today's new users
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    new_users_today = await users_col.count_documents({
        "joined_at": {"$gte": today}
    })
    
    return {
        "total": total_users,
        "active": active_users,
        "banned": banned_users,
        "new_today": new_users_today
    }

async def ban_user(user_id):
    """Ban a user"""
    await users_col.update_one(
        {"_id": user_id},
        {"$set": {"banned": True, "banned_at": datetime.datetime.now()}}
    )
    
    # Log ban action
    await admin_logs_col.insert_one({
        "action": "ban_user",
        "user_id": user_id,
        "action_date": datetime.datetime.now()
    })
    
    return True

async def unban_user(user_id):
    """Unban a user"""
    await users_col.update_one(
        {"_id": user_id},
        {"$set": {"banned": False, "unbanned_at": datetime.datetime.now()}}
    )
    
    # Log unban action
    await admin_logs_col.insert_one({
        "action": "unban_user",
        "user_id": user_id,
        "action_date": datetime.datetime.now()
    })
    
    return True

async def search_users(query):
    """Search users by username or name"""
    users = []
    regex_query = {"$regex": query, "$options": "i"}
    
    async for user in users_col.find({
        "$or": [
            {"username": regex_query},
            {"first_name": regex_query},
            {"last_name": regex_query}
        ],
        "banned": False
    }).limit(50):
        users.append(user)
    
    return users

# ================ GROUP FUNCTIONS ================
async def add_group(group_id, title=None, username=None):
    """Add or update group in database"""
    group_data = {
        "title": title,
        "username": username,
        "active": True,
        "updated_at": datetime.datetime.now()
    }
    
    # Check if group exists
    existing_group = await groups_col.find_one({"_id": group_id})
    
    if not existing_group:
        # New group - set default values
        group_data["added_at"] = datetime.datetime.now()
        group_data["is_premium"] = False
        group_data["premium_expiry"] = None
        group_data["settings_configured"] = False
    else:
        # Existing group - preserve premium status
        group_data["is_premium"] = existing_group.get("is_premium", False)
        group_data["premium_expiry"] = existing_group.get("premium_expiry")
    
    # Clean None values
    group_data = {k: v for k, v in group_data.items() if v is not None}
    
    await groups_col.update_one(
        {"_id": group_id},
        {"$set": group_data},
        upsert=True
    )
    
    # Update settings collection
    await get_settings(group_id)  # This will create default settings if not exists
    
    return True

async def get_group(group_id):
    """Get group details"""
    return await groups_col.find_one({"_id": group_id})

async def get_group_details(group_id):
    """Get complete group details with settings"""
    group = await groups_col.find_one({"_id": group_id})
    if not group:
        return None
    
    settings = await get_settings(group_id)
    force_sub = await get_force_sub(group_id)
    auto_accept = await get_auto_accept(group_id)
    is_premium = await check_is_premium(group_id)
    
    return {
        **group,
        "settings": settings,
        "force_sub": force_sub,
        "auto_accept": auto_accept,
        "is_premium": is_premium
    }

async def get_all_groups():
    """Get all group IDs"""
    groups = []
    async for group in groups_col.find({}):
        groups.append(group["_id"])
    return groups

async def get_active_groups():
    """Get active groups only"""
    groups = []
    async for group in groups_col.find({"active": True}):
        groups.append(group["_id"])
    return groups

async def get_group_count():
    """Get total groups count"""
    return await groups_col.count_documents({})

async def get_group_stats():
    """Get group statistics"""
    total_groups = await groups_col.count_documents({})
    active_groups = await groups_col.count_documents({"active": True})
    premium_groups = 0
    
    async for group in groups_col.find({"is_premium": True}):
        if await check_is_premium(group["_id"]):
            premium_groups += 1
    
    # Get today's new groups
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    new_groups_today = await groups_col.count_documents({
        "added_at": {"$gte": today}
    })
    
    return {
        "total": total_groups,
        "active": active_groups,
        "premium": premium_groups,
        "new_today": new_groups_today
    }

async def remove_group(group_id):
    """Remove group from database"""
    result = await groups_col.delete_one({"_id": group_id})
    
    # Also clean related data
    await settings_col.delete_one({"_id": group_id})
    await force_sub_col.delete_one({"_id": group_id})
    await auto_accept_col.delete_one({"_id": group_id})
    await warnings_col.delete_many({"chat_id": group_id})
    await movie_requests_col.delete_many({"chat_id": group_id})
    
    return result.deleted_count > 0

async def deactivate_group(group_id):
    """Mark group as inactive"""
    await groups_col.update_one(
        {"_id": group_id},
        {"$set": {"active": False, "deactivated_at": datetime.datetime.now()}}
    )
    return True

async def search_groups(query):
    """Search groups by title"""
    groups = []
    regex_query = {"$regex": query, "$options": "i"}
    
    async for group in groups_col.find({
        "title": regex_query,
        "active": True
    }).limit(50):
        groups.append(group)
    
    return groups

# ================ PREMIUM FUNCTIONS ================
async def add_premium(group_id, months):
    """Add premium to a group"""
    # Calculate expiry date
    expiry_date = datetime.datetime.now() + timedelta(days=30 * int(months))
    
    await groups_col.update_one(
        {"_id": group_id},
        {
            "$set": {
                "is_premium": True,
                "premium_expiry": expiry_date,
                "premium_added_at": datetime.datetime.now(),
                "premium_months": months
            }
        },
        upsert=True
    )
    
    # Log premium addition
    await premium_logs_col.insert_one({
        "group_id": group_id,
        "action": "add",
        "months": months,
        "expiry_date": expiry_date,
        "action_date": datetime.datetime.now()
    })
    
    return expiry_date

async def remove_premium(group_id):
    """Remove premium from a group"""
    group = await groups_col.find_one({"_id": group_id})
    if not group:
        return False
    
    await groups_col.update_one(
        {"_id": group_id},
        {
            "$set": {
                "is_premium": False,
                "premium_expiry": None,
                "premium_removed_at": datetime.datetime.now()
            }
        }
    )
    
    # Log premium removal
    await premium_logs_col.insert_one({
        "group_id": group_id,
        "action": "remove",
        "action_date": datetime.datetime.now()
    })
    
    return True

async def check_is_premium(group_id):
    """Check if group is premium and not expired"""
    group = await groups_col.find_one({"_id": group_id})
    if not group:
        return False
    
    if group.get("is_premium", False):
        expiry = group.get("premium_expiry")
        # Check if expired
        if expiry and expiry > datetime.datetime.now():
            return True
        else:
            # Expired, remove status automatically
            await remove_premium(group_id)
            return False
    return False

async def get_premium_expiry(group_id):
    """Get premium expiry date"""
    group = await groups_col.find_one({"_id": group_id})
    if group and group.get("is_premium", False):
        return group.get("premium_expiry")
    return None

async def get_expiring_premiums(days_before=7):
    """Get groups whose premium is expiring soon"""
    expiring_groups = []
    expiry_date = datetime.datetime.now() + timedelta(days=days_before)
    
    async for group in groups_col.find({
        "is_premium": True,
        "premium_expiry": {
            "$lte": expiry_date,
            "$gte": datetime.datetime.now()
        }
    }):
        expiring_groups.append({
            "group_id": group["_id"],
            "title": group.get("title", "Unknown"),
            "expiry_date": group.get("premium_expiry")
        })
    
    return expiring_groups

async def get_expired_premiums():
    """Get expired premium groups"""
    expired_groups = []
    
    async for group in groups_col.find({
        "is_premium": True,
        "premium_expiry": {"$lt": datetime.datetime.now()}
    }):
        expired_groups.append({
            "group_id": group["_id"],
            "title": group.get("title", "Unknown"),
            "expiry_date": group.get("premium_expiry")
        })
    
    return expired_groups

async def get_premium_stats():
    """Get premium statistics"""
    total_premium = 0
    active_premium = 0
    expired_premium = 0
    
    async for group in groups_col.find({"is_premium": True}):
        total_premium += 1
        if await check_is_premium(group["_id"]):
            active_premium += 1
        else:
            expired_premium += 1
    
    # Revenue calculation (assuming ₹100 per month)
    revenue = 0
    async for log in premium_logs_col.find({"action": "add"}):
        revenue += (log.get("months", 0) * 100)
    
    return {
        "total": total_premium,
        "active": active_premium,
        "expired": expired_premium,
        "revenue": f"₹{revenue}"
    }

# ================ SETTINGS FUNCTIONS ================
async def get_settings(chat_id):
    """Get or create default settings for chat"""
    settings = await settings_col.find_one({"_id": chat_id})
    
    if not settings:
        # Default settings
        default_settings = {
            "_id": chat_id,
            "spelling_on": True,
            "auto_delete_on": False,
            "delete_time": 0,
            "welcome_enabled": True,
            "force_sub_enabled": False,
            "ai_enabled": True,
            "link_protection": True,
            "abuse_protection": True,
            "max_warnings": 3,
            "created_at": datetime.datetime.now(),
            "updated_at": datetime.datetime.now()
        }
        
        await settings_col.insert_one(default_settings)
        return default_settings
    
    return settings

async def update_settings(chat_id, key, value):
    """Update specific setting"""
    await settings_col.update_one(
        {"_id": chat_id},
        {
            "$set": {
                key: value,
                "updated_at": datetime.datetime.now()
            }
        },
        upsert=True
    )
    
    # Update group's settings configured flag
    await groups_col.update_one(
        {"_id": chat_id},
        {"$set": {"settings_configured": True}}
    )
    
    return True

async def update_multiple_settings(chat_id, settings_dict):
    """Update multiple settings at once"""
    if not settings_dict:
        return False
    
    settings_dict["updated_at"] = datetime.datetime.now()
    
    await settings_col.update_one(
        {"_id": chat_id},
        {"$set": settings_dict},
        upsert=True
    )
    
    return True

async def reset_settings(chat_id):
    """Reset settings to default"""
    default_settings = {
        "spelling_on": True,
        "auto_delete_on": False,
        "delete_time": 0,
        "welcome_enabled": True,
        "force_sub_enabled": False,
        "ai_enabled": True,
        "link_protection": True,
        "abuse_protection": True,
        "max_warnings": 3,
        "updated_at": datetime.datetime.now()
    }
    
    await settings_col.update_one(
        {"_id": chat_id},
        {"$set": default_settings},
        upsert=True
    )
    
    return True

# ================ FORCE SUB FUNCTIONS ================
async def set_force_sub(chat_id, channel_id):
    """Set force subscribe channel"""
    await force_sub_col.update_one(
        {"_id": chat_id},
        {
            "$set": {
                "channel_id": channel_id,
                "enabled": True,
                "set_at": datetime.datetime.now()
            }
        },
        upsert=True
    )
    
    # Also update settings
    await update_settings(chat_id, "force_sub_enabled", True)
    
    return True

async def get_force_sub(chat_id):
    """Get force subscribe settings"""
    return await force_sub_col.find_one({"_id": chat_id})

async def remove_force_sub(chat_id):
    """Remove force subscribe"""
    result = await force_sub_col.delete_one({"_id": chat_id})
    
    # Also update settings
    await update_settings(chat_id, "force_sub_enabled", False)
    
    return result.deleted_count > 0

async def disable_force_sub(chat_id):
    """Disable force subscribe temporarily"""
    await force_sub_col.update_one(
        {"_id": chat_id},
        {"$set": {"enabled": False}}
    )
    
    await update_settings(chat_id, "force_sub_enabled", False)
    
    return True

async def enable_force_sub(chat_id):
    """Enable force subscribe"""
    force_sub = await get_force_sub(chat_id)
    if not force_sub:
        return False
    
    await force_sub_col.update_one(
        {"_id": chat_id},
        {"$set": {"enabled": True}}
    )
    
    await update_settings(chat_id, "force_sub_enabled", True)
    
    return True

# ================ WARNING SYSTEM ================
async def get_warnings(chat_id, user_id):
    """Get user's warning count"""
    data = await warnings_col.find_one({"chat_id": chat_id, "user_id": user_id})
    return data["count"] if data else 0

async def add_warning(chat_id, user_id):
    """Add warning to user"""
    data = await warnings_col.find_one({"chat_id": chat_id, "user_id": user_id})
    count = (data["count"] + 1) if data else 1
    
    await warnings_col.update_one(
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

async def reset_warnings(chat_id, user_id):
    """Reset user's warnings"""
    result = await warnings_col.delete_one({"chat_id": chat_id, "user_id": user_id})
    return result.deleted_count > 0

async def remove_warning(chat_id, user_id):
    """Remove one warning from user"""
    data = await warnings_col.find_one({"chat_id": chat_id, "user_id": user_id})
    if not data:
        return 0
    
    count = max(0, data["count"] - 1)
    
    if count == 0:
        await reset_warnings(chat_id, user_id)
    else:
        await warnings_col.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"$set": {"count": count}}
        )
    
    return count

async def get_all_warnings(chat_id=None, user_id=None):
    """Get all warnings with filters"""
    query = {}
    if chat_id:
        query["chat_id"] = chat_id
    if user_id:
        query["user_id"] = user_id
    
    warnings = []
    async for warning in warnings_col.find(query).sort("last_warning", -1):
        warnings.append(warning)
    
    return warnings

async def clear_all_warnings(chat_id=None):
    """Clear all warnings (optionally for a specific chat)"""
    query = {}
    if chat_id:
        query["chat_id"] = chat_id
    
    result = await warnings_col.delete_many(query)
    return result.deleted_count

# ================ AUTO ACCEPT SYSTEM ================
async def set_auto_accept(chat_id, status: bool):
    """Enable or disable auto accept"""
    await auto_accept_col.update_one(
        {"_id": chat_id},
        {
            "$set": {
                "enabled": status,
                "updated_at": datetime.datetime.now()
            }
        },
        upsert=True
    )
    return True

async def get_auto_accept(chat_id):
    """Get auto accept status"""
    data = await auto_accept_col.find_one({"_id": chat_id})
    return data.get("enabled", False) if data else False

async def get_all_auto_accept_groups():
    """Get all groups with auto accept enabled"""
    groups = []
    async for data in auto_accept_col.find({"enabled": True}):
        groups.append(data["_id"])
    return groups

async def toggle_auto_accept(chat_id):
    """Toggle auto accept status"""
    current = await get_auto_accept(chat_id)
    new_status = not current
    await set_auto_accept(chat_id, new_status)
    return new_status

# ================ MOVIE REQUESTS SYSTEM ================
async def add_movie_request(chat_id, user_id, movie_name, message_id=None):
    """Add movie request"""
    request_data = {
        "chat_id": chat_id,
        "user_id": user_id,
        "movie_name": movie_name,
        "status": "pending",
        "requested_at": datetime.datetime.now(),
        "message_id": message_id
    }
    
    result = await movie_requests_col.insert_one(request_data)
    return str(result.inserted_id)

async def get_pending_requests(chat_id=None):
    """Get pending movie requests"""
    query = {"status": "pending"}
    if chat_id:
        query["chat_id"] = chat_id
    
    requests = []
    async for req in movie_requests_col.find(query).sort("requested_at", -1).limit(100):
        requests.append(req)
    return requests

async def update_request_status(request_id, status, updated_by=None):
    """Update request status"""
    update_data = {
        "status": status,
        "updated_at": datetime.datetime.now()
    }
    
    if updated_by:
        update_data["updated_by"] = updated_by
    
    result = await movie_requests_col.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": update_data}
    )
    
    return result.modified_count > 0

async def get_user_requests(user_id, chat_id=None, limit=50):
    """Get user's movie requests"""
    query = {"user_id": user_id}
    if chat_id:
        query["chat_id"] = chat_id
    
    requests = []
    async for req in movie_requests_col.find(query).sort("requested_at", -1).limit(limit):
        requests.append(req)
    return requests

async def get_request_by_id(request_id):
    """Get request by ID"""
    try:
        return await movie_requests_col.find_one({"_id": ObjectId(request_id)})
    except:
        return None

async def store_request_message(chat_id, message_id, user_id, movie_name):
    """Store request message details for callback handling"""
    return await add_movie_request(chat_id, user_id, movie_name, message_id)

async def get_request_by_message(chat_id, message_id):
    """Get request by message ID"""
    return await movie_requests_col.find_one({
        "chat_id": chat_id,
        "message_id": message_id
    })

async def get_request_stats(chat_id=None, days=30):
    """Get movie request statistics"""
    date_filter = datetime.datetime.now() - timedelta(days=days)
    
    query = {"requested_at": {"$gte": date_filter}}
    if chat_id:
        query["chat_id"] = chat_id
    
    total = await movie_requests_col.count_documents(query)
    pending = await movie_requests_col.count_documents({**query, "status": "pending"})
    accepted = await movie_requests_col.count_documents({**query, "status": "accepted"})
    rejected = await movie_requests_col.count_documents({**query, "status": "rejected"})
    
    return {
        "total": total,
        "pending": pending,
        "accepted": accepted,
        "rejected": rejected,
        "period_days": days
    }

async def cleanup_old_requests(days=30):
    """Cleanup old requests"""
    cutoff_date = datetime.datetime.now() - timedelta(days=days)
    
    result = await movie_requests_col.delete_many({
        "requested_at": {"$lt": cutoff_date}
    })
    
    return result.deleted_count

# ================ ADMIN LOGS ================
async def add_admin_log(action, user_id, details=None):
    """Add admin action log"""
    log_data = {
        "action": action,
        "user_id": user_id,
        "action_date": datetime.datetime.now(),
        "details": details or {}
    }
    
    await admin_logs_col.insert_one(log_data)
    return True

async def get_admin_logs(user_id=None, action=None, limit=100):
    """Get admin logs"""
    query = {}
    if user_id:
        query["user_id"] = user_id
    if action:
        query["action"] = action
    
    logs = []
    async for log in admin_logs_col.find(query).sort("action_date", -1).limit(limit):
        logs.append(log)
    return logs

# ================ UTILITY FUNCTIONS ================
async def clear_junk():
    """Clear junk entries from database"""
    deleted_count = 0
    
    # Clean banned users older than 30 days
    cutoff_date = datetime.datetime.now() - timedelta(days=30)
    result1 = await users_col.delete_many({
        "banned": True,
        "banned_at": {"$lt": cutoff_date}
    })
    deleted_count += result1.deleted_count
    
    # Clean inactive groups older than 30 days
    result2 = await groups_col.delete_many({
        "active": False,
        "deactivated_at": {"$lt": cutoff_date}
    })
    deleted_count += result2.deleted_count
    
    # Clean old warnings (older than 90 days)
    cutoff_warnings = datetime.datetime.now() - timedelta(days=90)
    result3 = await warnings_col.delete_many({
        "last_warning": {"$lt": cutoff_warnings}
    })
    deleted_count += result3.deleted_count
    
    # Clean old admin logs (older than 60 days)
    cutoff_logs = datetime.datetime.now() - timedelta(days=60)
    result4 = await admin_logs_col.delete_many({
        "action_date": {"$lt": cutoff_logs}
    })
    deleted_count += result4.deleted_count
    
    return deleted_count

async def backup_database():
    """Create database backup info"""
    stats = {
        "timestamp": datetime.datetime.now(),
        "users": await get_user_count(),
        "groups": await get_group_count(),
        "premium_stats": await get_premium_stats(),
        "user_stats": await get_user_stats(),
        "group_stats": await get_group_stats(),
        "request_stats": await get_request_stats()
    }
    return stats

async def get_database_stats():
    """Get comprehensive database statistics"""
    stats = {
        "total_users": await users_col.count_documents({}),
        "active_users": await users_col.count_documents({"banned": False}),
        "total_groups": await groups_col.count_documents({}),
        "active_groups": await groups_col.count_documents({"active": True}),
        "premium_groups": await get_premium_stats(),
        "total_requests": await movie_requests_col.count_documents({}),
        "pending_requests": await movie_requests_col.count_documents({"status": "pending"}),
        "total_warnings": await warnings_col.count_documents({}),
        "auto_accept_enabled": len(await get_all_auto_accept_groups()),
        "force_sub_enabled": await force_sub_col.count_documents({}),
        "last_updated": datetime.datetime.now()
    }
    return stats

async def cleanup_all_old_data():
    """Cleanup all old data"""
    deleted = 0
    
    # Clean old movie requests
    deleted += await cleanup_old_requests(30)
    
    # Clean old warnings
    cutoff_warnings = datetime.datetime.now() - timedelta(days=90)
    result = await warnings_col.delete_many({
        "last_warning": {"$lt": cutoff_warnings}
    })
    deleted += result.deleted_count
    
    # Clean old premium logs
    cutoff_logs = datetime.datetime.now() - timedelta(days=180)
    result = await premium_logs_col.delete_many({
        "action_date": {"$lt": cutoff_logs}
    })
    deleted += result.deleted_count
    
    return deleted

# ================ INITIALIZATION ================
async def initialize_database():
    """Initialize database with indexes and default data"""
    try:
        await create_indexes()
        print("✅ Database initialized successfully!")
        
        # Create a system stats entry
        await db["system_stats"].update_one(
            {"_id": "initialization"},
            {"$set": {
                "initialized_at": datetime.datetime.now(),
                "version": "1.0.0",
                "total_calls": 0
            }},
            upsert=True
        )
        
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

# Run initialization when imported
asyncio.create_task(initialize_database())
