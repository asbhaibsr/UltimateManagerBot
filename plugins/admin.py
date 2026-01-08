#  plugins/admin.py

import asyncio
import time
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
from database import db
from config import Config
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- Stats ---
@Client.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats_handler(client, message):
    users, groups = await db.get_stats()
    
    text = (
        f"📊 **Bot Stats**\n\n"
        f"👥 Users: {users}\n"
        f"📢 Groups: {groups}\n"
    )
    
    buttons = [[InlineKeyboardButton("🗑 Clear Junk", callback_data="clear_junk")]]
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))

# --- Broadcast ---
@Client.on_message(filters.command("broadcast") & filters.user(Config.OWNER_ID) & filters.reply)
async def broadcast_handler(client, message):
    msg_to_send = message.reply_to_message
    
    status_msg = await message.reply("🚀 Broadcast Started...")
    
    # Get all targets
    all_users = await db.get_all_users()
    all_groups = await db.get_all_groups()
    
    success_u, fail_u = 0, 0
    success_g, fail_g = 0, 0
    
    # Users Broadcast
    async for user in all_users:
        try:
            await msg_to_send.copy(chat_id=user['id'])
            success_u += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await msg_to_send.copy(chat_id=user['id'])
            success_u += 1
        except (InputUserDeactivated, UserIsBlocked, PeerIdInvalid):
            await db.delete_user(user['id'])
            fail_u += 1
        except Exception:
            fail_u += 1
            
        if (success_u + fail_u) % 20 == 0:
            await status_msg.edit_text(f"Broadcasting Users...\nSent: {success_u}\nFailed: {fail_u}")

    # Groups Broadcast
    async for group in all_groups:
        # Check Premium
        if await db.is_premium(group['id']):
            continue # Skip Premium Groups
            
        try:
            await msg_to_send.copy(chat_id=group['id'])
            success_g += 1
        except Exception:
            # Assuming bot removed or no permission
            fail_g += 1
    
    await status_msg.edit_text(
        f"✅ **Broadcast Completed**\n\n"
        f"👥 Users: {success_u} (Failed/Deleted: {fail_u})\n"
        f"📢 Groups: {success_g} (Failed: {fail_g})"
    )

# --- Clear Junk ---
@Client.on_callback_query(filters.regex("clear_junk") & filters.user(Config.OWNER_ID))
async def clear_junk(client, callback):
    await callback.message.edit_text("♻️ Cleaning Junk Groups... This may take time.")
    removed = 0
    async for group in await db.get_all_groups():
        try:
            chat = await client.get_chat(group['id'])
            # Check if bot is member
            await client.get_chat_member(group['id'], "me")
        except Exception:
            # If error (kicked, chat not found), delete from DB
            await db.delete_group(group['id'])
            removed += 1
            
    await callback.message.edit_text(f"✅ Cleanup Done!\n🗑 Removed {removed} dead groups.")

# --- Premium ---
@Client.on_message(filters.command("addpremium") & filters.user(Config.OWNER_ID))
async def add_premium(client, message):
    try:
        # /addpremium -100xxxx 30
        args = message.command
        group_id = int(args[1])
        days = int(args[2])
        
        import datetime
        expiry = datetime.datetime.now() + datetime.timedelta(days=days)
        
        await db.add_premium(group_id, expiry)
        await message.reply(f"🌟 Premium added to `{group_id}` for {days} days.")
    except:
        await message.reply("Use: `/addpremium <group_id> <days>`")
