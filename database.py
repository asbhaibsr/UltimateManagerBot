async def store_request_message(chat_id, message_id, user_id, movie_name):
    """Store request message details"""
    try:
        await movie_requests_col.update_one(
            {
                "chat_id": chat_id,
                "user_id": user_id,
                "movie_name": movie_name,
                "status": "pending"
            },
            {
                "$set": {
                    "request_message_id": message_id,
                    "updated_at": datetime.datetime.now()
                }
            },
            upsert=False  # Only update existing pending requests
        )
        return True
    except Exception as e:
        print(f"Error storing request message: {e}")
        return False

async def get_request_message(chat_id, message_id):
    """Get request message details"""
    try:
        # Search by chat_id and request_message_id
        request = await movie_requests_col.find_one({
            "chat_id": chat_id,
            "request_message_id": message_id
        })
        
        if request:
            return {
                "request_id": request.get("_id"),
                "chat_id": request.get("chat_id"),
                "user_id": request.get("user_id"),
                "movie_name": request.get("movie_name"),
                "message_id": request.get("request_message_id"),
                "status": request.get("status", "pending"),
                "requested_at": request.get("requested_at")
            }
        
        # Alternative search by regular message_id (if you stored it differently)
        request = await movie_requests_col.find_one({
            "chat_id": chat_id,
            "_id": message_id  # Assuming message_id might be used as _id
        })
        
        if request:
            return {
                "request_id": request.get("_id"),
                "chat_id": request.get("chat_id"),
                "user_id": request.get("user_id"),
                "movie_name": request.get("movie_name"),
                "message_id": request.get("request_message_id"),
                "status": request.get("status", "pending"),
                "requested_at": request.get("requested_at")
            }
            
        return None
    except Exception as e:
        print(f"Error getting request message: {e}")
        return None

async def clear_junk():
    """Clear junk entries from database"""
    deleted_count = 0
    
    try:
        # 1. Delete old pending requests (older than 7 days)
        week_ago = datetime.datetime.now() - timedelta(days=7)
        result = await movie_requests_col.delete_many({
            "status": "pending",
            "requested_at": {"$lt": week_ago}
        })
        deleted_count += result.deleted_count
        
        # 2. Delete old completed/rejected requests (older than 30 days)
        month_ago = datetime.datetime.now() - timedelta(days=30)
        result = await movie_requests_col.delete_many({
            "status": {"$in": ["completed", "rejected"]},
            "updated_at": {"$lt": month_ago}
        })
        deleted_count += result.deleted_count
        
        # 3. Delete banned users (your existing logic)
        result = await users_col.delete_many({"banned": True})
        deleted_count += result.deleted_count
        
        # 4. Delete expired premium groups
        result = await groups_col.update_many(
            {
                "is_premium": True,
                "premium_expiry": {"$lt": datetime.datetime.now()}
            },
            {
                "$set": {
                    "is_premium": False,
                    "premium_expiry": None
                }
            }
        )
        # Note: This doesn't delete, only updates, so not counted
        
        # 5. Delete orphaned warnings (where user/group no longer exists)
        # Get all existing users
        existing_users = set()
        async for user in users_col.find({}, {"_id": 1}):
            existing_users.add(user["_id"])
        
        # Get all existing groups
        existing_groups = set()
        async for group in groups_col.find({}, {"_id": 1}):
            existing_groups.add(group["_id"])
        
        # Delete warnings for non-existent users/groups
        async for warning in warnings_col.find({}):
            if warning.get("user_id") not in existing_users or warning.get("chat_id") not in existing_groups:
                await warnings_col.delete_one({"_id": warning["_id"]})
                deleted_count += 1
        
        # 6. Clean up old auto_accept entries for non-existent groups
        async for auto_accept in auto_accept_col.find({}):
            if auto_accept.get("_id") not in existing_groups:
                await auto_accept_col.delete_one({"_id": auto_accept["_id"]})
                deleted_count += 1
        
        # 7. Clean up old force_sub entries for non-existent groups
        async for force_sub in force_sub_col.find({}):
            if force_sub.get("_id") not in existing_groups:
                await force_sub_col.delete_one({"_id": force_sub["_id"]})
                deleted_count += 1
        
        # 8. Clean up old settings for non-existent groups
        async for setting in settings_col.find({"_id": {"$lt": 0}}):  # Only groups (negative IDs)
            if setting.get("_id") not in existing_groups:
                await settings_col.delete_one({"_id": setting["_id"]})
                deleted_count += 1
        
        return deleted_count
        
    except Exception as e:
        print(f"Error clearing junk: {e}")
        return deleted_count
