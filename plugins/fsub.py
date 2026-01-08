# plugins/fsub.py

import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from pyrogram.errors import UserNotParticipant, ChatAdminRequired
from database import db
from config import Config

@Client.on_message(filters.command("linkfsub"))
async def link_fsub_command(client, message: Message):
    """Link force subscribe channel - WORKS IN PRIVATE & GROUP"""
    try:
        if len(message.command) < 2:
            await message.reply(
                "📢 **Setup Force Join**\n\n"
                "**Usage:** `/linkfsub channel_id`\n\n"
                "**Example:**\n"
                "`/linkfsub -1001234567890`\n\n"
                "**How to get Channel ID?**\n"
                "1. Add bot to your channel as admin\n"
                "2. Type `/id` in channel (if bot supports)\n"
                "3. Or copy from channel invite link\n\n"
                "**Note:** Bot must be admin in the channel!"
            )
            return
        
        channel_id = int(message.command[1])
        
        # Get group ID from message
        group_id = message.chat.id
        
        # Check if it's a group
        if message.chat.type == "private":
            await message.reply("❌ This command works only in groups!\n\n"
                              "Add me to your group and use this command there.")
            return
        
        # Check bot admin in group
        try:
            me = await client.get_me()
            member = await client.get_chat_member(group_id, me.id)
            if member.status != enums.ChatMemberStatus.ADMINISTRATOR:
                await message.reply("❌ I need to be admin in this group!")
                return
        except Exception as e:
            await message.reply(f"❌ Can't check admin status: {str(e)}")
            return
        
        # Check user is admin
        try:
            user_status = await client.get_chat_member(group_id, message.from_user.id)
            if user_status.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                await message.reply("❌ Only admins can set up force join!")
                return
        except:
            await message.reply("❌ Error checking admin status!")
            return
        
        # Check bot admin in channel
        try:
            channel_member = await client.get_chat_member(channel_id, me.id)
            if channel_member.status != enums.ChatMemberStatus.ADMINISTRATOR:
                await message.reply("❌ Bot is not admin in the channel!")
                return
        except Exception as e:
            await message.reply(f"❌ Can't access channel: {str(e)}\n\n"
                              "Make sure:\n"
                              "1. Bot is added to channel\n"
                              "2. Bot is admin in channel\n"
                              "3. Channel ID is correct")
            return
        
        # Get channel info
        try:
            channel = await client.get_chat(channel_id)
        except:
            await message.reply("❌ Can't get channel info!")
            return
        
        # Update database
        await db.update_settings(group_id, "fsub", channel_id)
        
        # Get invite link
        try:
            invite = await client.create_chat_invite_link(channel_id, member_limit=1)
            invite_link = invite.invite_link
        except:
            invite_link = f"https://t.me/c/{str(channel_id)[4:]}"
        
        await message.reply(
            f"✅ **Force Join Linked Successfully!**\n\n"
            f"**Channel:** {channel.title}\n"
            f"**Channel ID:** {channel_id}\n"
            f"**Group:** {message.chat.title}\n\n"
            f"**Join Link:** {invite_link}\n\n"
            f"Users will now need to join the channel to send messages.\n\n"
            f"Use `/fsubstatus` to check status."
        )
        
    except ValueError:
        await message.reply("❌ Invalid Channel ID! ID should be a number starting with -100")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ... rest of the fsub functions remain same ...
