# plugins/connect.py

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from database import db
from config import Config

@Client.on_message(filters.command("connect"))
async def connect_handler(client, message: Message):
    """Connect bot to group - ANYONE CAN USE THIS"""
    if message.chat.type == "private":
        # If in PM, ask for group ID
        if len(message.command) < 2:
            await message.reply(
                "🔗 **Connect Bot to Group**\n\n"
                "**Usage:** `/connect -1001234567890`\n\n"
                "**How to get Group ID?**\n"
                "1. Add @userinfobot to your group\n"
                "2. Type `/id` in group\n"
                "3. Copy the **Group ID** (starts with -100)\n"
                "4. Use: `/connect -100xxxxxxxxxx`\n\n"
                "**Note:** Bot must be admin in the group!"
            )
            return
        
        try:
            group_id = int(message.command[1])
            
            # Check if bot is in group
            try:
                chat = await client.get_chat(group_id)
            except:
                await message.reply("❌ Bot is not in this group. Add me first!")
                return
            
            # Check bot admin status - FIXED ERROR HERE
            try:
                me = await client.get_me()
                member = await client.get_chat_member(group_id, me.id)
                if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                    await message.reply("❌ Bot is not admin in this group. Make me admin first!")
                    return
            except Exception as e:
                await message.reply(f"❌ Can't check admin status: {str(e)}")
                return
            
            # Find owner - simplified
            owner_id = message.from_user.id
            
            # Add to database
            success = await db.add_group(group_id, chat.title, owner_id)
            
            if success:
                buttons = [
                    [InlineKeyboardButton("⚙️ Manage Group", callback_data=f"manage_{group_id}")],
                    [InlineKeyboardButton("📊 View Stats", callback_data=f"stats_{group_id}")]
                ]
                
                await message.reply(
                    f"✅ **Successfully Connected!**\n\n"
                    f"**Group:** {chat.title}\n"
                    f"**Group ID:** {group_id}\n"
                    f"**Connected by:** {message.from_user.mention}\n\n"
                    f"Now configure your group settings:",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                
                # Log to channel
                try:
                    await client.send_message(
                        Config.LOG_CHANNEL,
                        f"📥 **New Group Connected**\n\n"
                        f"**Group:** {chat.title}\n"
                        f"**ID:** {group_id}\n"
                        f"**Connected by:** {message.from_user.mention}\n"
                        f"**User ID:** {message.from_user.id}"
                    )
                except:
                    pass
            else:
                await message.reply("ℹ️ Group already connected!")
                
        except ValueError:
            await message.reply("❌ Invalid Group ID! ID should be a number starting with -100")
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
    
    else:
        # If in group, connect directly
        try:
            group_id = message.chat.id
            
            # Check bot admin status - FIXED ERROR HERE
            try:
                me = await client.get_me()
                member = await client.get_chat_member(group_id, me.id)
                if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                    await message.reply("❌ I need to be admin to connect!")
                    return
            except Exception as e:
                await message.reply(f"❌ Can't check admin status: {str(e)}")
                return
            
            # Find owner
            owner_id = message.from_user.id
            
            # Add to database
            success = await db.add_group(group_id, message.chat.title, owner_id)
            
            if success:
                await message.reply(
                    f"✅ **Group Connected Successfully!**\n\n"
                    f"**Group:** {message.chat.title}\n"
                    f"**Connected by:** {message.from_user.mention}\n\n"
                    f"Use `/settings` to configure the bot."
                )
            else:
                await message.reply("ℹ️ Group already connected!")
                
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")

# ... rest of the settings command remains same ...
