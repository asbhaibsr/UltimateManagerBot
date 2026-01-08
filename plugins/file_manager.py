# plugins/file_manager.py

import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from database import db
from config import Config

@Client.on_message(filters.group & (filters.document | filters.video | filters.audio))
async def auto_delete_files(client, message):
    """Auto delete files after specified time"""
    group = await db.get_group(message.chat.id)
    if not group or not group["settings"].get("auto_delete_files"):
        return
    
    # Check if user has permission to bypass
    try:
        user_status = await client.get_chat_member(message.chat.id, message.from_user.id)
        if user_status.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return
    except:
        pass
    
    # Get delete time
    delete_after = group["settings"].get("delete_after_minutes", Config.AUTO_DELETE_MINUTES)
    
    # Create delete button
    buttons = []
    if group["settings"].get("fsub"):
        # Premium feature: Delete now button
        if await db.is_premium(message.chat.id):
            buttons.append([InlineKeyboardButton("🗑 Delete Now", callback_data=f"delete_now_{message.id}")])
    
    # Send warning message
    warning = await message.reply(
        f"⚠️ **This file will be deleted in {delete_after} minutes.**\n\n"
        f"To keep files longer, upgrade to Premium!",
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
    )
    
    # Schedule deletion
    await asyncio.sleep(delete_after * 60)
    
    try:
        await message.delete()
        await warning.delete()
    except:
        pass

@Client.on_callback_query(filters.regex(r"^delete_now_"))
async def delete_now_callback(client, callback):
    """Delete file immediately"""
    message_id = int(callback.data.split("_")[2])
    
    # Check if user is admin
    try:
        user_status = await client.get_chat_member(callback.message.chat.id, callback.from_user.id)
        if user_status.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            await callback.answer("Only admins can delete immediately!", show_alert=True)
            return
    except:
        await callback.answer("Error!", show_alert=True)
        return
    
    try:
        await client.delete_messages(callback.message.chat.id, message_id)
        await callback.message.edit_text("✅ File deleted!")
        await callback.answer()
    except Exception as e:
        await callback.answer(f"Error: {str(e)}", show_alert=True)

@Client.on_message(filters.group & filters.command("autodelete"))
async def auto_delete_command(client, message):
    """Configure auto delete settings"""
    group = await db.get_group(message.chat.id)
    if not group:
        return
    
    # Check admin
    try:
        user_status = await client.get_chat_member(message.chat.id, message.from_user.id)
        if user_status.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            await message.reply("Only admins can configure auto delete!")
            return
    except:
        await message.reply("Error checking admin status!")
        return
    
    if len(message.command) < 2:
        current_status = "✅ Enabled" if group["settings"].get("auto_delete_files") else "❌ Disabled"
        current_time = group["settings"].get("delete_after_minutes", Config.AUTO_DELETE_MINUTES)
        
        await message.reply(
            f"⏰ **Auto Delete Settings**\n\n"
            f"Status: {current_status}\n"
            f"Delete after: {current_time} minutes\n\n"
            f"**Usage:**\n"
            f"`/autodelete on` - Enable auto delete\n"
            f"`/autodelete off` - Disable auto delete\n"
            f"`/autodelete 10` - Set to 10 minutes\n\n"
            f"**Note:** Premium groups get extra features!"
        )
        return
    
    arg = message.command[1].lower()
    
    if arg == "on":
        await db.update_settings(message.chat.id, "auto_delete_files", True)
        await message.reply("✅ Auto delete enabled!")
    
    elif arg == "off":
        await db.update_settings(message.chat.id, "auto_delete_files", False)
        await message.reply("✅ Auto delete disabled!")
    
    elif arg.isdigit():
        minutes = int(arg)
        if minutes < 1 or minutes > 1440:
            await message.reply("Please enter minutes between 1 and 1440 (24 hours)")
            return
        
        await db.update_settings(message.chat.id, "delete_after_minutes", minutes)
        await db.update_settings(message.chat.id, "auto_delete_files", True)
        await message.reply(f"✅ Auto delete set to {minutes} minutes!")
    
    else:
        await message.reply("Invalid argument! Use on/off or a number.")
