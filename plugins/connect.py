# plugins/connect.py

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from database import db
from config import Config

@Client.on_message(filters.command("connect"))
async def connect_handler(client, message: Message):
    """Connect bot to group"""
    if message.chat.type == "private":
        # If in PM, ask for group ID
        if len(message.command) < 2:
            await message.reply(
                "Please provide Group ID!\n\n"
                "How to get Group ID?\n"
                "1. Add @userinfobot to your group\n"
                "2. Type /id in group\n"
                "3. Copy the Group ID (starts with -100)\n"
                "4. Use: /connect -100xxxxxxx\n\n"
                "Note: Bot must be admin in the group!"
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
            
            # Check bot admin status
            try:
                member = await client.get_chat_member(group_id, (await client.get_me()).id)
                if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                    await message.reply("❌ Bot is not admin in this group. Make me admin first!")
                    return
            except Exception as e:
                await message.reply(f"❌ Can't check admin status: {str(e)}")
                return
            
            # Find owner
            owner_id = None
            try:
                async for m in client.get_chat_members(group_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
                    if m.status == enums.ChatMemberStatus.OWNER:
                        owner_id = m.user.id
                        break
            except:
                pass
            
            if not owner_id:
                owner_id = message.from_user.id
            
            # Add to database
            success = await db.add_group(group_id, chat.title, owner_id)
            
            if success:
                buttons = [
                    [InlineKeyboardButton("⚙️ Manage Group", callback_data=f"manage_{group_id}")],
                    [InlineKeyboardButton("📊 View Stats", callback_data=f"stats_{group_id}")]
                ]
                
                await message.reply(
                    f"✅ Successfully Connected!\n\n"
                    f"Group: {chat.title}\n"
                    f"Group ID: {group_id}\n"
                    f"Owner: {owner_id}\n\n"
                    f"Now configure your group settings:",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                
                # Log to channel
                try:
                    await client.send_message(
                        Config.LOG_CHANNEL,
                        f"📥 New Group Connected\n\n"
                        f"Group: {chat.title}\n"
                        f"ID: {group_id}\n"
                        f"Owner: {owner_id}\n"
                        f"Added by: {message.from_user.mention}"
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
            
            # Check bot admin status
            try:
                member = await client.get_chat_member(group_id, (await client.get_me()).id)
                if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                    await message.reply("❌ I need to be admin to connect!")
                    return
            except Exception as e:
                await message.reply(f"❌ Can't check admin status: {str(e)}")
                return
            
            # Find owner
            owner_id = None
            try:
                async for m in client.get_chat_members(group_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
                    if m.status == enums.ChatMemberStatus.OWNER:
                        owner_id = m.user.id
                        break
            except:
                pass
            
            if not owner_id:
                owner_id = message.from_user.id
            
            # Add to database
            success = await db.add_group(group_id, message.chat.title, owner_id)
            
            if success:
                await message.reply(
                    f"✅ Group Connected Successfully!\n\n"
                    f"Group: {message.chat.title}\n"
                    f"Owner ID: {owner_id}\n\n"
                    f"Use /settings to configure the bot."
                )
            else:
                await message.reply("ℹ️ Group already connected!")
                
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")

@Client.on_message(filters.command("settings"))
async def settings_command(client, message):
    """Show group settings"""
    if message.chat.type == "private":
        await message.reply("This command works only in groups!")
        return
    
    group = await db.get_group(message.chat.id)
    if not group:
        await message.reply("Group not connected! Use /connect first.")
        return
    
    settings = group.get("settings", {})
    
    # Status icons
    welcome_icon = "✅" if settings.get("welcome") else "❌"
    spell_icon = "✅" if settings.get("spell_check") else "❌"
    auto_delete_icon = "✅" if settings.get("auto_delete_files") else "❌"
    
    # FSub status
    fsub_status = "❌ Not Set"
    if settings.get("fsub"):
        try:
            channel = await client.get_chat(settings["fsub"])
            fsub_status = f"✅ {channel.title}"
        except:
            fsub_status = "✅ Set (Channel)"
    
    # Premium status
    premium = await db.is_premium(message.chat.id)
    premium_status = "🌟 Premium" if premium else "🔓 Free"
    
    text = f"""
⚙️ **Group Settings**

**Group:** {group['title']}
**ID:** {message.chat.id}
**Status:** {premium_status}

**Settings:**
{welcome_icon} Welcome Messages
{spell_icon} Spell Check
{auto_delete_icon} Auto Delete Files
{fsub_status} Force Join

**Stats:**
📊 Total Messages: {group.get('stats', {}).get('total_messages', 0)}
👥 Total Users: {group.get('stats', {}).get('total_users', 0)}
    """
    
    buttons = [
        [
            InlineKeyboardButton(f"{welcome_icon} Welcome", callback_data=f"toggle_welcome_{message.chat.id}"),
            InlineKeyboardButton(f"{spell_icon} Spell Check", callback_data=f"toggle_spell_{message.chat.id}")
        ],
        [
            InlineKeyboardButton(f"{auto_delete_icon} Auto Delete", callback_data=f"toggle_autodel_{message.chat.id}"),
            InlineKeyboardButton("⏰ Set Time", callback_data=f"set_time_{message.chat.id}")
        ],
        [
            InlineKeyboardButton("📢 Force Join", callback_data=f"fsub_menu_{message.chat.id}"),
            InlineKeyboardButton("📊 Stats", callback_data=f"stats_{message.chat.id}")
        ]
    ]
    
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))

# ... rest of the code same as before ...
