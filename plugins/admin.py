# plugins/admin.py

import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from database import db
from config import Config
from datetime import datetime, timedelta

@Client.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats_command(client, message):
    """Show bot statistics - FIXED ASYNC ISSUE"""
    try:
        users, groups, requests, active_groups = await db.get_stats()
        
        # Get premium groups count
        premium_count = 0
        all_groups = await db.get_all_groups()
        for group in all_groups:
            if await db.is_premium(group['id']):
                premium_count += 1
        
        text = f"""
🤖 **Bot Statistics**

👥 **Users:** {users}
📢 **Groups:** {groups}
🌟 **Premium Groups:** {premium_count}
📥 **Requests:** {requests}
🎯 **Active Groups (7 days):** {active_groups}

📊 **Database Status:** ✅ Connected
⏰ **Uptime:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        buttons = [
            [
                InlineKeyboardButton("🗑 Clean Junk", callback_data="clean_junk"),
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")
            ],
            [
                InlineKeyboardButton("📊 Detailed Stats", callback_data="detailed_stats"),
                InlineKeyboardButton("📢 Broadcast", callback_data="broadcast_menu")
            ]
        ]
        
        await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        await message.reply(f"❌ Error getting stats: {str(e)}")

@Client.on_callback_query(filters.regex(r"^refresh_stats$") & filters.user(Config.OWNER_ID))
async def refresh_stats_callback(client, callback):
    """Refresh statistics"""
    await stats_command(client, callback.message)
    await callback.answer("Stats refreshed!")

@Client.on_message(filters.command("broadcast") & filters.user(Config.OWNER_ID) & filters.reply)
async def broadcast_handler(client, message):
    """Broadcast message to all users and groups - FIXED"""
    if not message.reply_to_message:
        await message.reply("Please reply to a message to broadcast!")
        return
    
    msg = message.reply_to_message
    
    # Get counts
    users_count = await db.users.count_documents({})
    groups_count = await db.groups.count_documents({})
    
    confirm_text = f"""
⚠️ **Broadcast Confirmation**

**Message Type:** {msg.media.value if msg.media else "Text"}
**Content:** {(msg.text or msg.caption or "Media")[:100]}...

**Targets:**
• All Users ({users_count})
• All Groups ({groups_count})

**Note:** This will send to everyone including premium groups.

**Proceed with broadcast?**
    """
    
    buttons = [
        [
            InlineKeyboardButton("✅ Yes, Broadcast", callback_data="confirm_broadcast"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")
        ]
    ]
    
    await message.reply(confirm_text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^confirm_broadcast$") & filters.user(Config.OWNER_ID))
async def confirm_broadcast(client, callback):
    """Confirm and start broadcast - FIXED"""
    await callback.message.edit_text("🚀 Starting broadcast...")
    
    msg = callback.message.reply_to_message
    total_users = 0
    success_users = 0
    failed_users = 0
    
    total_groups = 0
    success_groups = 0
    failed_groups = 0
    
    # Broadcast to users - FIXED ASYNC ITERATION
    all_users = await db.get_all_users()
    for user in all_users:
        total_users += 1
        try:
            await msg.copy(chat_id=user['id'])
            success_users += 1
        except Exception as e:
            failed_users += 1
            # Remove inactive users
            if "deactivated" in str(e).lower() or "blocked" in str(e).lower():
                await db.delete_user(user['id'])
        
        # Update progress every 10 users
        if total_users % 10 == 0:
            await callback.message.edit_text(
                f"📤 Broadcasting...\n\n"
                f"👥 Users: {success_users}/{total_users}\n"
                f"📢 Groups: {success_groups}/{total_groups}"
            )
    
    # Broadcast to all groups - FIXED ASYNC ITERATION
    all_groups = await db.get_all_groups()
    for group in all_groups:
        total_groups += 1
        try:
            await msg.copy(chat_id=group['id'])
            success_groups += 1
        except Exception:
            failed_groups += 1
    
    # Final report
    report = f"""
✅ **Broadcast Completed!**

👥 **Users:**
• Total: {total_users}
• Success: {success_users}
• Failed: {failed_users}

📢 **Groups:**
• Total: {total_groups}
• Success: {success_groups}
• Failed: {failed_groups}

💾 **Cleanup:**
• Inactive users removed: {failed_users}
    """
    
    await callback.message.edit_text(report)

# ... rest of admin functions ...
