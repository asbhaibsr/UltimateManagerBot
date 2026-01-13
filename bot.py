import asyncio
import logging
import time
from pyrogram import Client, filters, idle
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, ChatMemberUpdated, ChatPermissions
)
from pyrogram.errors import UserNotParticipant, FloodWait, ChatAdminRequired
from config import Config
from database import *
from utils import MovieBotUtils

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MovieBot")

# Initialize Pyrogram Client
app = Client(
    name="movie_helper_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    in_memory=True
)

# ================ HELPER FUNCTIONS ================
async def is_admin(chat_id: int, user_id: int) -> bool:
    """Check if user is admin"""
    if user_id == Config.OWNER_ID:
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

# ================ START COMMAND ================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Handle /start command"""
    user = message.from_user
    await add_user(user.id, user.username, user.first_name)
    
    welcome_text = f"""🎬 Welcome {user.first_name}! 🎬

I'm your Movie Helper Bot! 🤖

Features:
✅ Spelling Correction in Groups
✅ Auto Delete Files
✅ AI Movie Recommendations
✅ Force Subscribe Channel
✅ Broadcast Messages

Add me to your groups and make me admin! 😊"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton("🤖 Help", callback_data="help_main")]
    ])
    
    await message.reply_text(welcome_text, reply_markup=buttons)

# ================ HELP COMMAND ================
@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    """Handle /help command"""
    help_text = """🆘 Help Guide 🆘

For Group Admins:
1. Add me to your group
2. Make me admin with delete message permission
3. Use /settings to configure

Group Features:
• Spelling Correction: Auto-corrects movie names
• Auto Delete Files: Remove unwanted media
• Force Subscribe: Force users to join channel
• AI Chat: Ask about movies/series

Commands List:
• /start - Start the bot
• /help - This message
• /settings - Group settings (admin only)
• /stats - Bot statistics
• /ai [question] - Ask AI
• /addfsub - Set force subscribe channel

Owner Commands:
• /broadcast - Broadcast to users
• /grp_broadcast - Broadcast to groups
• /ban [user_id] - Ban user
• /unban [user_id] - Unban user

Utility Commands:
• /ping - Check if bot is alive
• /id - Get user/group ID"""
    
    await message.reply_text(help_text)

# ================ SETTINGS COMMAND ================
@app.on_message(filters.command("settings") & filters.group)
async def settings_command(client: Client, message: Message):
    """Group settings menu"""
    # Check if user is admin
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ Only Group Admins/Owner can use settings!")
        await asyncio.sleep(5)
        await msg.delete()
        return
    
    settings = await get_settings(message.chat.id)
    
    # Create settings buttons
    spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
    delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
    delete_time = settings.get("delete_time", 0)
    time_text = f"{delete_time} min" if delete_time > 0 else "Permanent"
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Spelling Correction: {spelling_status}", callback_data="toggle_spelling")],
        [InlineKeyboardButton(f"Auto Delete Files: {delete_status}", callback_data="toggle_auto_delete")],
        [InlineKeyboardButton(f"Delete Time: {time_text}", callback_data="set_delete_time")],
        [InlineKeyboardButton("🔗 Force Subscribe", callback_data="force_sub_menu")],
        [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
    ])
    
    await message.reply_text(
        f"⚙️ Settings for {message.chat.title}\n\n"
        "Configure your group settings below:",
        reply_markup=buttons
    )

# ================ STATS COMMAND ================
@app.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats_command(client: Client, message: Message):
    """Bot statistics"""
    users = await get_user_count()
    groups = await get_group_count()
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Clear Junk", callback_data="clear_junk")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]
    ])
    
    stats_text = f"""📊 Bot Statistics

👥 Total Users: {users}
👥 Total Groups: {groups}
⚡ Bot Uptime: 24/7
🔄 Last Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    
    await message.reply_text(stats_text, reply_markup=buttons)

# ================ AI COMMAND ================
@app.on_message(filters.command("ai"))
async def ai_command(client: Client, message: Message):
    """AI chat feature"""
    if len(message.command) < 2:
        await message.reply_text("Usage: /ai your question\nExample: /ai Tell me about Inception movie")
        return
    
    query = ' '.join(message.command[1:])
    waiting_msg = await message.reply_text("🤔 Thinking... Please wait!")
    
    response = await MovieBotUtils.get_ai_response(query)
    
    await waiting_msg.delete()
    await message.reply_text(response)

# ================ BROADCAST COMMANDS ================
@app.on_message(filters.command(["broadcast", "grp_broadcast"]) & filters.user(Config.OWNER_ID))
async def broadcast_command(client: Client, message: Message):
    """Broadcast messages to users/groups"""
    if not message.reply_to_message:
        await message.reply_text("❌ Please reply to a message to broadcast!")
        return
    
    broadcast_type = "users" if "broadcast" in message.command else "groups"
    target_ids = await get_all_users() if broadcast_type == "users" else await get_all_groups()
    
    if not target_ids:
        await message.reply_text(f"❌ No {broadcast_type} found!")
        return
    
    progress_msg = await message.reply_text(f"📤 Broadcasting to {len(target_ids)} {broadcast_type}...\nProgress: 0/{len(target_ids)}")
    
    success = 0
    failed = 0
    
    for idx, target_id in enumerate(target_ids, 1):
        try:
            await message.reply_to_message.copy(target_id)
            success += 1
            if idx % 10 == 0:
                await progress_msg.edit_text(
                    f"📤 Broadcasting to {len(target_ids)} {broadcast_type}...\n"
                    f"Progress: {idx}/{len(target_ids)}\n"
                    f"✅ Success: {success} | ❌ Failed: {failed}"
                )
            await asyncio.sleep(Config.BROADCAST_DELAY)
        except Exception as e:
            failed += 1
            logger.error(f"Failed to send to {target_id}: {e}")
    
    await progress_msg.edit_text(
        f"✅ Broadcast Complete!\n\n"
        f"📊 Results:\n"
        f"• Total {broadcast_type.capitalize()}: {len(target_ids)}\n"
        f"• ✅ Successful: {success}\n"
        f"• ❌ Failed: {failed}\n"
        f"• 📈 Success Rate: {(success/len(target_ids)*100):.1f}%"
    )

# ================ ADDFSUB COMMAND ================
@app.on_message(filters.command("addfsub") & filters.group)
async def addfsub_command(client: Client, message: Message):
    """Set force subscribe channel"""
    # Check Admin
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ Only Admins can use this!")

    if not message.reply_to_message:
        return await message.reply_text("❌ Reply to a forwarded message from your channel!")

    # Logic: Check forwarded chat
    fwd_chat = message.reply_to_message.forward_from_chat
    
    if not fwd_chat or fwd_chat.type != "channel":
        return await message.reply_text("❌ I cannot see the channel ID. Make sure 'Forwarding' is enabled in channel settings OR bot is admin in channel.")

    channel_id = fwd_chat.id
    channel_title = fwd_chat.title

    # Verify Bot is Admin in that Channel
    try:
        await client.get_chat_member(channel_id, (await client.get_me()).id)
    except:
        return await message.reply_text("❌ <b>Error:</b> I am not an Admin in that Channel! Please add me there first.")

    # Save to DB
    await set_force_sub(message.chat.id, channel_id)
    await message.reply_text(f"✅ <b>Force Subscribe Connected!</b>\nLinked to: {channel_title}")

# ================ PING COMMAND ================
@app.on_message(filters.command("ping"))
async def ping_command(client: Client, message: Message):
    """Check if bot is alive"""
    start_time = time.time()
    msg = await message.reply_text("🏓 Pinging...")
    end_time = time.time()
    
    ping_time = round((end_time - start_time) * 1000, 2)
    
    await msg.edit_text(f"🏓 Pong!\n\n⏱ Response Time: {ping_time}ms\n🚀 Status: ✅ Alive")

# ================ ID COMMAND ================
@app.on_message(filters.command("id"))
async def id_command(client: Client, message: Message):
    """Get user/group ID"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    text = f"👤 Your ID: {user_id}\n"
    
    if message.chat.type != "private":
        text += f"👥 Group ID: {chat_id}\n"
        text += f"📝 Group Title: {message.chat.title}\n"
    
    await message.reply_text(text)

# ================ BAN/UNBAN COMMANDS ================
@app.on_message(filters.command("ban") & filters.user(Config.OWNER_ID))
async def ban_command(client: Client, message: Message):
    """Ban a user"""
    if len(message.command) < 2:
        await message.reply_text("Usage: /ban <user_id>")
        return
    
    try:
        user_id = int(message.command[1])
        await ban_user(user_id)
        await message.reply_text(f"✅ User {user_id} banned successfully!")
    except ValueError:
        await message.reply_text("❌ Invalid user ID!")

@app.on_message(filters.command("unban") & filters.user(Config.OWNER_ID))
async def unban_command(client: Client, message: Message):
    """Unban a user"""
    if len(message.command) < 2:
        await message.reply_text("Usage: /unban <user_id>")
        return
    
    try:
        user_id = int(message.command[1])
        await unban_user(user_id)
        await message.reply_text(f"✅ User {user_id} unbanned successfully!")
    except ValueError:
        await message.reply_text("❌ Invalid user ID!")

# ================ MAIN FILTER (JUNK REMOVER) ================
@app.on_message(filters.group & filters.text & ~filters.command(["start", "help", "settings", "stats", "ai", "broadcast", "grp_broadcast", "addfsub", "ping", "id", "ban", "unban"]))
async def group_message_filter(client: Client, message: Message):
    # Ignore Admins/Owner
    if await is_admin(message.chat.id, message.from_user.id):
        return

    settings = await get_settings(message.chat.id)
    if not settings.get("spelling_on", True):
        return

    text = message.text
    quality = MovieBotUtils.check_message_quality(text)

    if quality == "JUNK":
        # Delete IMMEDIATELY
        try:
            await message.delete()
            # Optional: Warn user
            warn = await message.reply_text(
                f"🚫 {message.from_user.mention}, extra words allowed nahi hain!\n"
                f"Sahi tarika: `The Raja Saab` ya `Stranger Things S01`"
            )
            await MovieBotUtils.auto_delete_message(client, warn, 5)
        except Exception as e:
            logger.error(f"Delete Error: {e}")
            
    elif quality == "CLEAN":
        # Message is clean. Let it stay.
        pass

# ================ AUTO DELETE FILES ================
@app.on_message(filters.group & (filters.document | filters.video | filters.audio | filters.photo))
async def auto_delete_files(client: Client, message: Message):
    """Auto delete media files"""
    settings = await get_settings(message.chat.id)
    if not settings.get("auto_delete_on", False):
        return
    
    delete_time = settings.get("delete_time", 0)
    
    if delete_time > 0:
        await asyncio.sleep(delete_time * 60)
    
    try:
        await client.delete_messages(message.chat.id, message.id)
    except:
        pass

# ================ FORCE SUBSCRIBE ENFORCEMENT ================
@app.on_chat_member_updated()
async def handle_fsub_join(client: Client, update: ChatMemberUpdated):
    # Only check if new member joins
    if not update.new_chat_member:
        return
        
    # Ignore if user is bot or already left
    if update.new_chat_member.user.is_bot:
        return

    chat_id = update.chat.id
    user_id = update.new_chat_member.user.id
    
    # Check DB for Force Sub Channel
    fsub_data = await get_force_sub(chat_id)
    if not fsub_data:
        return

    channel_id = fsub_data["channel_id"]
    
    try:
        # Check if user is in channel
        await client.get_chat_member(channel_id, user_id)
        # User is present, do nothing
    except UserNotParticipant:
        # User NOT in channel -> Mute them & Send Alert
        try:
            await client.restrict_chat_member(
                chat_id, user_id, 
                ChatPermissions(can_send_messages=False)
            )
            
            # Get Invite Link
            try:
                chat_info = await client.get_chat(channel_id)
                link = chat_info.invite_link or f"https://t.me/{chat_info.username}"
            except:
                link = "#"

            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url=link)],
                [InlineKeyboardButton("✅ I Joined", callback_data=f"unmute_{user_id}")]
            ])
            
            welcome_msg = await client.send_message(
                chat_id,
                f"👋 Welcome {update.new_chat_member.user.mention}!\n\n"
                f"🔒 **Group Message Karne ke liye Channel Join karein.**",
                reply_markup=buttons
            )
            
            # Auto delete welcome message after 5 minutes
            await asyncio.sleep(300)
            try:
                await welcome_msg.delete()
            except:
                pass
                
        except Exception as e:
            logger.error(f"Fsub Error: {e}")
    except Exception as e:
        logger.error(f"Fsub Admin Check Error: {e}")

# ================ GROUP EVENTS ================
@app.on_message(filters.new_chat_members)
async def welcome_new_members(client: Client, message: Message):
    """Welcome new members and add group to database"""
    for member in message.new_chat_members:
        if member.is_self:  # Bot added to group
            await add_group(
                message.chat.id,
                message.chat.title,
                message.chat.username
            )
            
            welcome_text = f"""🎬 Thanks for adding me! 🎬

I'm Movie Helper Bot! Here's what I can do:

✅ Auto-correct movie names (remove extra words)
✅ Auto-delete files after set time
✅ Force subscribe to your channel
✅ AI movie recommendations

Setup Instructions:
1. Make me admin with delete permissions
2. Use /settings to configure
3. Set up force subscribe with /addfsub

Need help? Use /help 😊"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu")],
                [InlineKeyboardButton("📚 Help", callback_data="help_main")]
            ])
            
            await message.reply_text(welcome_text, reply_markup=buttons)
            
            # Notify owner
            if Config.OWNER_ID:
                owner_msg = (
                    f"🤖 Bot Added to New Group!\n\n"
                    f"Group: {message.chat.title}\n"
                    f"ID: {message.chat.id}\n"
                    f"Username: @{message.chat.username or 'N/A'}\n"
                    f"Added by: {message.from_user.mention if message.from_user else 'Unknown'}"
                )
                try:
                    await client.send_message(Config.OWNER_ID, owner_msg)
                except:
                    pass
            
            break

# ================ CALLBACK QUERY HANDLERS ================
@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    """Handle all callback queries"""
    data = query.data
    chat_id = query.message.chat.id if query.message else query.from_user.id
    user_id = query.from_user.id
    
    if data == "help_main":
        help_text = """🆘 Help Menu 🆘

Main Features:
• 🎬 Movie recommendations
• ✨ Spelling correction
• 🗑️ Auto delete files
• 🔗 Force subscribe
• 🤖 AI chat

Quick Commands:
/start - Start bot
/help - Detailed help
/settings - Group settings
/ai - Ask AI anything"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Start", callback_data="back_to_start")],
            [InlineKeyboardButton("⚙️ Group Settings", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")]
        ])
        
        await query.message.edit_text(help_text, reply_markup=buttons)
        await query.answer()
    
    elif data == "back_to_start":
        welcome_text = f"""🎬 Welcome! 🎬

I'm your Movie Helper Bot! 🤖

Features:
✅ Spelling Correction in Groups
✅ Auto Delete Files
✅ AI Movie Recommendations
✅ Force Subscribe Channel

Add me to groups and use /settings to configure! 😊"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
            [InlineKeyboardButton("🤖 Help", callback_data="help_main")]
        ])
        
        await query.message.edit_text(welcome_text, reply_markup=buttons)
        await query.answer()
    
    elif data == "toggle_spelling":
        settings = await get_settings(chat_id)
        new_value = not settings.get("spelling_on", True)
        await update_settings(chat_id, "spelling_on", new_value)
        
        status = "✅ ON" if new_value else "❌ OFF"
        await query.message.edit_reply_markup(
            InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Spelling Correction: {status}", callback_data="toggle_spelling")],
                [InlineKeyboardButton(f"Auto Delete Files: {'✅ ON' if settings.get('auto_delete_on', False) else '❌ OFF'}", callback_data="toggle_auto_delete")],
                [InlineKeyboardButton(f"Delete Time: {settings.get('delete_time', 0)} min", callback_data="set_delete_time")],
                [InlineKeyboardButton("🔗 Force Subscribe", callback_data="force_sub_menu")],
                [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
            ])
        )
        await query.answer(f"Spelling correction turned {status}")
    
    elif data == "toggle_auto_delete":
        settings = await get_settings(chat_id)
        new_value = not settings.get("auto_delete_on", False)
        await update_settings(chat_id, "auto_delete_on", new_value)
        
        status = "✅ ON" if new_value else "❌ OFF"
        await query.message.edit_reply_markup(
            InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Spelling Correction: {'✅ ON' if settings.get('spelling_on', True) else '❌ OFF'}", callback_data="toggle_spelling")],
                [InlineKeyboardButton(f"Auto Delete Files: {status}", callback_data="toggle_auto_delete")],
                [InlineKeyboardButton(f"Delete Time: {settings.get('delete_time', 0)} min", callback_data="set_delete_time")],
                [InlineKeyboardButton("🔗 Force Subscribe", callback_data="force_sub_menu")],
                [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
            ])
        )
        await query.answer(f"Auto delete turned {status}")
    
    elif data == "set_delete_time":
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("5 Minutes", callback_data="time_5")],
            [InlineKeyboardButton("10 Minutes", callback_data="time_10")],
            [InlineKeyboardButton("15 Minutes", callback_data="time_15")],
            [InlineKeyboardButton("30 Minutes", callback_data="time_30")],
            [InlineKeyboardButton("Permanent", callback_data="time_0")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_settings")]
        ])
        await query.message.edit_text("⏰ Select Auto-Delete Time:", reply_markup=buttons)
        await query.answer()
    
    elif data.startswith("time_"):
        minutes = int(data.split("_")[1])
        await update_settings(chat_id, "delete_time", minutes)
        
        time_text = f"{minutes} minutes" if minutes > 0 else "Permanent"
        await query.answer(f"Delete time set to {time_text}")
        
        # Go back to settings
        settings = await get_settings(chat_id)
        spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
        delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
        delete_time = minutes
        time_text = f"{delete_time} min" if delete_time > 0 else "Permanent"
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Spelling Correction: {spelling_status}", callback_data="toggle_spelling")],
            [InlineKeyboardButton(f"Auto Delete Files: {delete_status}", callback_data="toggle_auto_delete")],
            [InlineKeyboardButton(f"Delete Time: {time_text}", callback_data="set_delete_time")],
            [InlineKeyboardButton("🔗 Force Subscribe", callback_data="force_sub_menu")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ])
        
        await query.message.edit_text(
            f"⚙️ Settings for {query.message.chat.title}\n\n"
            "Configure your group settings below:",
            reply_markup=buttons
        )
    
    elif data == "force_sub_menu":
        force_sub = await get_force_sub(chat_id)
        if force_sub:
            channel_id = force_sub.get("channel_id")
            try:
                channel = await client.get_chat(channel_id)
                channel_link = f"https://t.me/{channel.username}" if channel.username else ""
                
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Visit Channel", url=channel_link)],
                    [InlineKeyboardButton("❌ Disconnect", callback_data="disconnect_fsub")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_settings")]
                ])
                await query.message.edit_text(
                    f"🔗 Force Subscribe Channel:\n\n"
                    f"Channel: {channel.title}\n"
                    f"Status: ✅ Connected\n\n"
                    f"New members must join this channel.",
                    reply_markup=buttons
                )
            except:
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back_settings")]
                ])
                await query.message.edit_text(
                    "❌ Channel Not Found!\n\n"
                    "The channel is no longer accessible or bot was removed.",
                    reply_markup=buttons
                )
        else:
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Set Channel", callback_data="set_fsub")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_settings")]
            ])
            await query.message.edit_text(
                "🔗 Force Subscribe\n\n"
                "No channel set yet. Set a channel that new members must join.",
                reply_markup=buttons
            )
        await query.answer()
    
    elif data == "disconnect_fsub":
        await remove_force_sub(chat_id)
        await query.answer("✅ Force subscribe disconnected!")
        await query.message.delete()
    
    elif data == "clear_junk":
        junk_count = await clear_junk()
        await query.answer(f"🧹 Cleared {junk_count} junk entries!")
        await query.message.edit_text(
            f"✅ Junk Cleared!\n\n"
            f"Removed {junk_count} inactive entries from database.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh Stats", callback_data="refresh_stats")]
            ])
        )
    
    elif data == "refresh_stats":
        users = await get_user_count()
        groups = await get_group_count()
        
        stats_text = f"""📊 Bot Statistics

👥 Total Users: {users}
👥 Total Groups: {groups}
⚡ Bot Uptime: 24/7
🔄 Last Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        await query.message.edit_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🧹 Clear Junk", callback_data="clear_junk")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]
            ])
        )
        await query.answer("✅ Stats refreshed!")
    
    elif data.startswith("unmute_"):
        target_id = int(data.split("_")[1])
        if user_id != target_id:
            return await query.answer("Ye button apke liye nahi hai!", show_alert=True)
            
        # Re-check join status
        fsub_data = await get_force_sub(chat_id)
        channel_id = fsub_data["channel_id"]
        try:
            await client.get_chat_member(channel_id, user_id)
            # Unmute user
            await client.restrict_chat_member(
                chat_id, user_id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            await query.message.delete()
            await query.answer("✅ Verified! You can chat now.")
        except UserNotParticipant:
            await query.answer("❌ Abhi bhi join nahi kiya!", show_alert=True)
    
    elif data == "ok_correction":
        await query.message.delete()
        await query.answer()
    
    elif data == "close_settings":
        await query.message.delete()
        await query.answer("Settings closed!")
    
    elif data == "back_settings":
        settings = await get_settings(chat_id)
        spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
        delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
        delete_time = settings.get("delete_time", 0)
        time_text = f"{delete_time} min" if delete_time > 0 else "Permanent"
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Spelling Correction: {spelling_status}", callback_data="toggle_spelling")],
            [InlineKeyboardButton(f"Auto Delete Files: {delete_status}", callback_data="toggle_auto_delete")],
            [InlineKeyboardButton(f"Delete Time: {time_text}", callback_data="set_delete_time")],
            [InlineKeyboardButton("🔗 Force Subscribe", callback_data="force_sub_menu")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ])
        
        await query.message.edit_text(
            f"⚙️ Settings for {query.message.chat.title}\n\n"
            "Configure your group settings below:",
            reply_markup=buttons
        )
        await query.answer()
    
    elif data == "set_fsub":
        await query.message.edit_text(
            "🔗 Set Force Subscribe Channel\n\n"
            "To set force subscribe channel:\n"
            "1. Forward any message from your channel\n"
            "2. Reply to it with command: /addfsub\n\n"
            "Make sure I'm admin in that channel!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="force_sub_menu")]
            ])
        )
        await query.answer()

# ================ MAIN FUNCTION ================
if __name__ == "__main__":
    print("🚀 Starting Movie Helper Bot...")
    app.run()
