import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from pyrogram.errors import UserNotParticipant, ChatAdminRequired
from database import db
from config import Config

@Client.on_message(filters.command("linkfsub"))
async def link_fsub_command(client, message):
    """Link force subscribe channel"""
    if message.chat.type != "private":
        await message.reply("This command works only in private chat!")
        return
    
    if len(message.command) < 3:
        await message.reply(
            "Usage: `/linkfsub <group_id> <channel_id>`\n\n"
            "Example: `/linkfsub -100123456789 -100987654321`\n\n"
            "Note: Make sure:\n"
            "1. Bot is admin in both group and channel\n"
            "2. Channel ID should start with -100"
        )
        return
    
    try:
        group_id = int(message.command[1])
        channel_id = int(message.command[2])
        
        # Check if user owns the group
        group = await db.get_group(group_id)
        if not group:
            await message.reply("Group not found in database! Use /connect first.")
            return
        
        if group["owner_id"] != message.from_user.id:
            await message.reply("You are not the owner of this group!")
            return
        
        # Check bot admin in channel
        try:
            member = await client.get_chat_member(channel_id, "me")
            if member.status != enums.ChatMemberStatus.ADMINISTRATOR:
                await message.reply("❌ Bot is not admin in the channel!")
                return
        except Exception as e:
            await message.reply(f"❌ Can't access channel: {str(e)}")
            return
        
        # Check bot admin in group
        try:
            member = await client.get_chat_member(group_id, "me")
            if member.status != enums.ChatMemberStatus.ADMINISTRATOR:
                await message.reply("❌ Bot is not admin in the group!")
                return
        except Exception as e:
            await message.reply(f"❌ Can't access group: {str(e)}")
            return
        
        # Update database
        await db.update_settings(group_id, "fsub", channel_id)
        
        # Get channel info
        channel = await client.get_chat(channel_id)
        
        await message.reply(
            f"✅ **Force Join Linked Successfully!**\n\n"
            f"📢 **Channel:** {channel.title}\n"
            f"🆔 **Channel ID:** `{channel_id}`\n"
            f"👥 **Group:** `{group_id}`\n\n"
            f"Users will now need to join the channel to send messages."
        )
        
    except ValueError:
        await message.reply("Invalid ID format! IDs should be numbers.")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

@Client.on_message(filters.command("fsubstatus"))
async def fsub_status(client, message):
    """Check force subscribe status"""
    group = await db.get_group(message.chat.id)
    if not group:
        return
    
    channel_id = group["settings"].get("fsub")
    
    if not channel_id:
        await message.reply("❌ Force Join is not set up for this group.")
        return
    
    try:
        channel = await client.get_chat(channel_id)
        
        # Check bot admin status
        try:
            member = await client.get_chat_member(channel_id, "me")
            admin_status = "✅ Admin" if member.status == enums.ChatMemberStatus.ADMINISTRATOR else "❌ Not Admin"
        except:
            admin_status = "❌ Not Admin"
        
        await message.reply(
            f"📢 **Force Join Status**\n\n"
            f"**Channel:** {channel.title}\n"
            f"**Channel ID:** `{channel_id}`\n"
            f"**Bot Status:** {admin_status}\n\n"
            f"Users must join this channel to send messages."
        )
    except Exception as e:
        await message.reply(f"❌ Error accessing channel: {str(e)}")

@Client.on_message(filters.group & ~filters.service, group=2)
async def enforce_fsub(client, message):
    """Enforce force subscribe"""
    if not message.from_user:
        return
    
    group = await db.get_group(message.chat.id)
    if not group:
        return
    
    channel_id = group["settings"].get("fsub")
    if not channel_id:
        return
    
    # Ignore admins
    try:
        user_status = await client.get_chat_member(message.chat.id, message.from_user.id)
        if user_status.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return
    except:
        pass
    
    # Check if user joined channel
    try:
        await client.get_chat_member(channel_id, message.from_user.id)
        # User is member, allow message
        return
    except UserNotParticipant:
        # User not joined, restrict
        try:
            # Delete user's message
            await message.delete()
        except:
            pass
        
        # Get channel invite link
        try:
            invite = await client.create_chat_invite_link(channel_id, member_limit=1)
            invite_link = invite.invite_link
        except:
            invite_link = f"https://t.me/c/{str(channel_id)[4:]}"
        
        # Send warning message
        warning = await message.reply(
            f"👋 {message.from_user.mention},\n\n"
            f"📢 **You must join our channel to send messages here!**\n\n"
            f"👉 Join: {invite_link}\n\n"
            f"After joining, click **Unmute Me** below.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Join Channel", url=invite_link)],
                [InlineKeyboardButton("🔓 Unmute Me", callback_data=f"fsub_unmute_{message.from_user.id}")]
            ])
        )
        
        # Restrict user
        try:
            await client.restrict_chat_member(
                message.chat.id,
                message.from_user.id,
                ChatPermissions(can_send_messages=False)
            )
        except:
            pass
        
        # Auto delete warning after 60 seconds
        await asyncio.sleep(60)
        try:
            await warning.delete()
        except:
            pass

@Client.on_callback_query(filters.regex(r"^fsub_unmute_"))
async def fsub_unmute_callback(client, callback):
    """Unmute user after joining channel"""
    user_id = int(callback.data.split("_")[2])
    
    if callback.from_user.id != user_id:
        await callback.answer("This button is not for you!", show_alert=True)
        return
    
    group = await db.get_group(callback.message.chat.id)
    if not group:
        await callback.answer("Error!", show_alert=True)
        return
    
    channel_id = group["settings"].get("fsub")
    if not channel_id:
        await callback.answer("Force join not set up!", show_alert=True)
        return
    
    # Check if user joined
    try:
        await client.get_chat_member(channel_id, user_id)
        # User joined, unmute them
        try:
            await client.restrict_chat_member(
                callback.message.chat.id,
                user_id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            
            await callback.answer("✅ You have been unmuted! You can now send messages.", show_alert=True)
            await callback.message.delete()
            
        except Exception as e:
            await callback.answer(f"❌ Failed to unmute: {str(e)}", show_alert=True)
            
    except UserNotParticipant:
        await callback.answer("❌ You haven't joined the channel yet!", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)
