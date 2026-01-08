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
                "**How to get Group ID?**\n"
                "1. Add @userinfobot to your group\n"
                "2. Type /id in group\n"
                "3. Copy the Group ID (starts with -100)\n"
                "4. Use: `/connect -100xxxxxxx`\n\n"
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
            
            # Check bot admin status
            try:
                member = await client.get_chat_member(group_id, "me")
                if member.status != enums.ChatMemberStatus.ADMINISTRATOR:
                    await message.reply("❌ Bot is not admin in this group. Make me admin first!")
                    return
            except:
                await message.reply("❌ Can't check admin status. Make sure bot is admin!")
                return
            
            # Find owner
            owner_id = None
            async for m in client.get_chat_members(group_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
                if m.status == enums.ChatMemberStatus.OWNER:
                    owner_id = m.user.id
                    break
            
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
                    f"✅ **Successfully Connected!**\n\n"
                    f"**Group:** {chat.title}\n"
                    f"**Group ID:** `{group_id}`\n"
                    f"**Owner:** {owner_id}\n\n"
                    f"Now configure your group settings:",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                
                # Log to channel
                try:
                    await client.send_message(
                        Config.LOG_CHANNEL,
                        f"📥 **New Group Connected**\n\n"
                        f"**Group:** {chat.title}\n"
                        f"**ID:** `{group_id}`\n"
                        f"**Owner:** {owner_id}\n"
                        f"**Added by:** {message.from_user.mention}"
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
                member = await client.get_chat_member(group_id, "me")
                if member.status != enums.ChatMemberStatus.ADMINISTRATOR:
                    await message.reply("❌ I need to be admin to connect!")
                    return
            except:
                await message.reply("❌ Can't check admin status!")
                return
            
            # Find owner
            owner_id = None
            async for m in client.get_chat_members(group_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
                if m.status == enums.ChatMemberStatus.OWNER:
                    owner_id = m.user.id
                    break
            
            if not owner_id:
                owner_id = message.from_user.id
            
            # Add to database
            success = await db.add_group(group_id, message.chat.title, owner_id)
            
            if success:
                await message.reply(
                    f"✅ **Group Connected Successfully!**\n\n"
                    f"**Group:** {message.chat.title}\n"
                    f"**Owner ID:** `{owner_id}`\n\n"
                    f"Use /settings to configure the bot."
                )
            else:
                await message.reply("ℹ️ Group already connected!")
                
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")

@Client.on_message(filters.command("disconnect"))
async def disconnect_handler(client, message):
    """Disconnect bot from group"""
    if message.chat.type == "private":
        await message.reply("Use /disconnect in the group you want to disconnect from.")
        return
    
    group_id = message.chat.id
    
    # Check if user is admin
    try:
        user_status = await client.get_chat_member(group_id, message.from_user.id)
        if user_status.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            await message.reply("❌ Only admins can disconnect the bot!")
            return
    except:
        await message.reply("❌ Can't verify admin status!")
        return
    
    # Confirm disconnect
    buttons = [
        [
            InlineKeyboardButton("✅ Yes, Disconnect", callback_data=f"confirm_disc_{group_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_disc_{group_id}")
        ]
    ]
    
    await message.reply(
        "⚠️ **Are you sure you want to disconnect the bot?**\n\n"
        "This will:\n"
        "• Remove all settings\n"
        "• Delete group data\n"
        "• Stop all bot functions\n\n"
        "**This action cannot be undone!**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^confirm_disc_"))
async def confirm_disconnect(client, callback):
    """Confirm disconnect"""
    group_id = int(callback.data.split("_")[2])
    
    # Check permission
    try:
        user_status = await client.get_chat_member(group_id, callback.from_user.id)
        if user_status.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            await callback.answer("Only admins can disconnect!", show_alert=True)
            return
    except:
        await callback.answer("Error!", show_alert=True)
        return
    
    # Delete group from database
    await db.delete_group(group_id)
    
    await callback.message.edit_text(
        "✅ **Bot disconnected successfully!**\n\n"
        "All group data has been deleted.\n"
        "You can reconnect anytime using /connect."
    )
    
    # Leave group
    try:
        await client.leave_chat(group_id)
    except:
        pass

@Client.on_callback_query(filters.regex(r"^cancel_disc_"))
async def cancel_disconnect(client, callback):
    """Cancel disconnect"""
    await callback.message.delete()
    await callback.answer("Disconnect cancelled!")

@Client.on_callback_query(filters.regex(r"^manage_"))
async def manage_group(client, callback):
    """Manage group settings"""
    group_id = int(callback.data.split("_")[1])
    
    group = await db.get_group(group_id)
    if not group:
        await callback.answer("Group not found!", show_alert=True)
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
    premium = await db.is_premium(group_id)
    premium_status = "🌟 Premium" if premium else "🔓 Free"
    
    text = f"""
**⚙️ Group Settings**

**Group:** {group['title']}
**ID:** `{group_id}`
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
            InlineKeyboardButton(f"{welcome_icon} Welcome", callback_data=f"toggle_welcome_{group_id}"),
            InlineKeyboardButton(f"{spell_icon} Spell Check", callback_data=f"toggle_spell_{group_id}")
        ],
        [
            InlineKeyboardButton(f"{auto_delete_icon} Auto Delete", callback_data=f"toggle_autodel_{group_id}"),
            InlineKeyboardButton("⏰ Set Time", callback_data=f"set_time_{group_id}")
        ],
        [
            InlineKeyboardButton("📢 Force Join", callback_data=f"fsub_menu_{group_id}"),
            InlineKeyboardButton("📊 Stats", callback_data=f"stats_{group_id}")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="back_to_start"),
            InlineKeyboardButton("❌ Disconnect", callback_data=f"confirm_disc_{group_id}")
        ]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^toggle_"))
async def toggle_setting(client, callback):
    """Toggle group setting"""
    action, setting, group_id = callback.data.split("_")
    group_id = int(group_id)
    
    group = await db.get_group(group_id)
    if not group:
        await callback.answer("Error!", show_alert=True)
        return
    
    current = group["settings"].get(setting, False)
    await db.update_settings(group_id, setting, not current)
    
    # Refresh management menu
    await manage_group(client, callback)
    await callback.answer(f"{setting.replace('_', ' ').title()} {'enabled' if not current else 'disabled'}!")

@Client.on_callback_query(filters.regex(r"^set_time_"))
async def set_auto_delete_time(client, callback):
    """Set auto delete time"""
    group_id = int(callback.data.split("_")[2])
    
    buttons = [
        [
            InlineKeyboardButton("5 min", callback_data=f"time_5_{group_id}"),
            InlineKeyboardButton("10 min", callback_data=f"time_10_{group_id}")
        ],
        [
            InlineKeyboardButton("30 min", callback_data=f"time_30_{group_id}"),
            InlineKeyboardButton("1 hour", callback_data=f"time_60_{group_id}")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data=f"manage_{group_id}")]
    ]
    
    await callback.message.edit_text(
        "⏰ **Set Auto Delete Time**\n\n"
        "How long after sending should files be deleted?\n"
        "This applies to movie details, photos, etc.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^time_"))
async def save_auto_delete_time(client, callback):
    """Save auto delete time"""
    minutes, group_id = callback.data.split("_")[1], int(callback.data.split("_")[2])
    
    await db.update_settings(group_id, "delete_after_minutes", int(minutes))
    await db.update_settings(group_id, "auto_delete_files", True)
    
    await callback.answer(f"Auto delete set to {minutes} minutes!", show_alert=True)
    await manage_group(client, callback)

@Client.on_callback_query(filters.regex(r"^fsub_menu_"))
async def fsub_menu(client, callback):
    """Force join menu"""
    group_id = int(callback.data.split("_")[2])
    
    group = await db.get_group(group_id)
    channel_id = group["settings"].get("fsub")
    
    if channel_id:
        try:
            channel = await client.get_chat(channel_id)
            channel_info = f"✅ **Current Channel:** {channel.title}\n🆔 ID: `{channel_id}`"
        except:
            channel_info = "⚠️ **Channel not accessible**"
    else:
        channel_info = "❌ **Not set up**"
    
    buttons = [
        [InlineKeyboardButton("🔗 Link Channel", callback_data=f"link_fsub_{group_id}")],
        [InlineKeyboardButton("🚫 Remove", callback_data=f"remove_fsub_{group_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"manage_{group_id}")]
    ]
    
    await callback.message.edit_text(
        f"📢 **Force Join Setup**\n\n{channel_info}\n\n"
        "Setup steps:\n"
        "1. Add bot as admin in your channel\n"
        "2. Click 'Link Channel'\n"
        "3. Send channel ID\n\n"
        "Users will need to join your channel to send messages.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^link_fsub_"))
async def link_fsub_prompt(client, callback):
    """Prompt for channel linking"""
    group_id = int(callback.data.split("_")[2])
    
    await callback.message.edit_text(
        f"To link a channel:\n\n"
        f"1. Make sure bot is admin in your channel\n"
        f"2. Get your channel ID (starts with -100)\n"
        f"3. Use this command:\n\n"
        f"`/linkfsub {group_id} -100xxxxxxx`\n\n"
        f"Send this command in private chat with the bot.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=f"fsub_menu_{group_id}")]
        ])
    )

@Client.on_callback_query(filters.regex(r"^remove_fsub_"))
async def remove_fsub(client, callback):
    """Remove force join"""
    group_id = int(callback.data.split("_")[2])
    
    await db.update_settings(group_id, "fsub", None)
    await callback.answer("Force join removed!", show_alert=True)
    await fsub_menu(client, callback)

@Client.on_callback_query(filters.regex(r"^stats_"))
async def group_stats(client, callback):
    """Show group statistics"""
    group_id = int(callback.data.split("_")[1])
    
    group = await db.get_group(group_id)
    if not group:
        await callback.answer("Error!", show_alert=True)
        return
    
    stats = group.get("stats", {})
    
    text = f"""
**📊 Group Statistics**

**Group:** {group['title']}
**ID:** `{group_id}`

**📈 Activity:**
📝 Total Messages: {stats.get('total_messages', 0)}
👥 Total Users: {stats.get('total_users', 0)}
🔄 Last Updated: {stats.get('last_updated', 'Never')}

**⚙️ Settings Status:**
✅ Welcome: {'On' if group['settings'].get('welcome') else 'Off'}
✅ Spell Check: {'On' if group['settings'].get('spell_check') else 'Off'}
✅ Auto Delete: {'On' if group['settings'].get('auto_delete_files') else 'Off'}
✅ Force Join: {'Set' if group['settings'].get('fsub') else 'Not Set'}
    """
    
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data=f"manage_{group_id}")]]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
