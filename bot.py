import asyncio
import logging
import time
from pyrogram import Client, filters, idle
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, ChatMemberUpdated, ChatPermissions
)
from pyrogram.errors import FloodWait, UserNotParticipant, ChatAdminRequired
from config import Config
from database import *
from utils import MovieBotUtils

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Pyrogram Client
app = Client(
    name="movie_helper_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    in_memory=True
)

# ================ HELPER FUNCTIONS ================
async def is_admin(chat_id, user_id):
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
    
    # Database me add karo
    await add_user(user.id, user.username, user.first_name)
    
    # Log Channel me bhejo
    if Config.LOGS_CHANNEL:
        try:
            log_text = (
                f"🧑‍💻 **New User Started Bot**\n\n"
                f"👤 Name: {user.mention}\n"
                f"🆔 ID: `{user.id}`\n"
                f"🔗 Username: @{user.username if user.username else 'N/A'}"
            )
            await client.send_message(Config.LOGS_CHANNEL, log_text)
        except Exception as e:
            logger.error(f"Log Error: {e}")

    welcome_text = f"""🎬 Namaste {user.first_name}! 🎬

Main hoon apka Movie Helper Bot! 🤖

**Features:**
✅ Spelling Correction
✅ Auto Delete Files
✅ AI Movie Recommendations
💎 Premium Force Subscribe

Add me to your groups and make me admin! 😊"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton("💎 Premium Plans", callback_data="premium_info")],
        [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/asbhai_bsr")],
        [InlineKeyboardButton("🤖 Help", callback_data="help_main")]
    ])
    
    await message.reply_text(welcome_text, reply_markup=buttons)
    await MovieBotUtils.auto_delete_message(client, message)

# ================ HELP COMMAND ================
@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    """Handle /help command"""
    help_text = """🆘 **Help Menu** 🆘

**Group Admins ke liye:**
1. Group me add karke Admin banao.
2. /settings - Settings change karne ke liye.
3. /addfsub - Force Subscribe set karne ke liye (Premium Only).

**Commands:**
• /start - Start Bot
• /ai [query] - Movie pucho
• /ping - Check Status
• /id - Get ID

**Premium Commands:**
• /addfsub <channel_id> - Connect Channel

Contact Owner: @asbhai_bsr"""
    
    await message.reply_text(help_text)
    await MovieBotUtils.auto_delete_message(client, message)

# ================ SETTINGS COMMAND ================
@app.on_message(filters.command("settings") & filters.group)
async def settings_command(client: Client, message: Message):
    """Group settings menu"""
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ Only Group Admins/Owner can use settings!")
        await asyncio.sleep(5)
        await msg.delete()
        return
    
    settings = await get_settings(message.chat.id)
    is_prem = await check_is_premium(message.chat.id)
    prem_status = "💎 Active" if is_prem else "❌ Free"
    
    spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
    delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
    time_text = f"{settings.get('delete_time', 0)} min" if settings.get('delete_time', 0) > 0 else "Permanent"
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Spelling: {spelling_status}", callback_data="toggle_spelling")],
        [InlineKeyboardButton(f"Auto Delete: {delete_status}", callback_data="toggle_auto_delete")],
        [InlineKeyboardButton(f"Time: {time_text}", callback_data="set_delete_time")],
        [InlineKeyboardButton(f"Premium: {prem_status}", callback_data="premium_info")],
        [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
    ])
    
    await message.reply_text(f"⚙️ Settings for **{message.chat.title}**", reply_markup=buttons)

# ================ STATS COMMAND ================
@app.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats_command(client: Client, message: Message):
    """Bot statistics"""
    users = await get_user_count()
    groups = await get_group_count()
    
    # Premium groups count
    premium_count = 0
    all_grps = await get_all_groups()
    for g in all_grps:
        if await check_is_premium(g):
            premium_count += 1
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Clear Junk", callback_data="clear_junk")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]
    ])
    
    stats_text = f"""📊 Bot Statistics

👥 Total Users: {users}
👥 Total Groups: {groups}
💎 Premium Groups: {premium_count}
⚡ Bot Uptime: 24/7
🔄 Last Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Database Status: ✅ Connected
AI Status: ✅ Active
Server: Koyeb Cloud
Status: ✅ Running"""
    
    await message.reply_text(stats_text, reply_markup=buttons)

# ================ AI COMMAND ================
@app.on_message(filters.command("ai"))
async def ai_command(client: Client, message: Message):
    """AI chat feature"""
    if len(message.command) < 2:
        await message.reply_text("Usage: /ai your question\nExample: /ai Tell me about Inception movie")
        return
    
    query = ' '.join(message.command[1:])
    waiting_msg = await message.reply_text("🤔 Soch raha hu...")
    
    response = await MovieBotUtils.get_ai_response(query)
    
    await waiting_msg.delete()
    await message.reply_text(response)
    await MovieBotUtils.auto_delete_message(client, message)

# ================ BROADCAST COMMANDS (UPDATED WITH PREMIUM FILTER) ================
@app.on_message(filters.command(["broadcast", "grp_broadcast"]) & filters.user(Config.OWNER_ID))
async def broadcast_command(client: Client, message: Message):
    """Broadcast messages to users/groups"""
    if not message.reply_to_message:
        await message.reply_text("❌ Please reply to a message to broadcast!")
        return
    
    if "grp_broadcast" in message.text:
        # Groups broadcast (Only to non-premium groups)
        all_groups = await get_all_groups()
        target_ids = []
        # Filter: Don't send to Premium Groups
        for grp_id in all_groups:
            if not await check_is_premium(grp_id):
                target_ids.append(grp_id)
        broadcast_type = "groups"
    else:
        # Users broadcast
        target_ids = await get_all_users()
        broadcast_type = "users"
    
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
            if idx % 10 == 0:  # Update progress every 10 sends
                await progress_msg.edit_text(
                    f"📤 Broadcasting to {len(target_ids)} {broadcast_type}...\n"
                    f"Progress: {idx}/{len(target_ids)}\n"
                    f"✅ Success: {success} | ❌ Failed: {failed}"
                )
            await asyncio.sleep(Config.BROADCAST_DELAY)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await message.reply_to_message.copy(target_id)
                success += 1
            except:
                failed += 1
        except Exception as e:
            failed += 1
            logger.error(f"Failed to send to {target_id}: {e}")
    
    await progress_msg.edit_text(
        f"✅ **Broadcast Done!**\n\n"
        f"Total {broadcast_type.capitalize()}: {len(target_ids)}\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}\n"
        f"📈 Success Rate: {(success/len(target_ids)*100):.1f}%"
    )

# ================ ADDFSUB COMMAND (FIXED WITH PREMIUM CHECK) ================
@app.on_message(filters.command("addfsub") & filters.group)
async def addfsub_command(client: Client, message: Message):
    """Set force subscribe channel"""
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ Only Admins can use this!")
        await asyncio.sleep(5)
        await msg.delete()
        return

    # Check Premium First
    if not await check_is_premium(message.chat.id):
        return await message.reply_text(
            "💎 **Premium Feature!**\n\n"
            "Force Subscribe use karne ke liye Premium lena padega.\n"
            "Buy Premium: @asbhai_bsr",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Buy Premium", url="https://t.me/asbhai_bsr")]])
        )

    channel_id = None
    
    # 1. Check commands arguments (e.g., /addfsub -100123456)
    if len(message.command) > 1:
        try:
            channel_id = int(message.command[1])
        except ValueError:
            return await message.reply_text("❌ Invalid ID! Numeric ID daalo (e.g. -100...)")

    # 2. Check reply forwarded message
    elif message.reply_to_message:
        if message.reply_to_message.forward_from_chat:
            channel_id = message.reply_to_message.forward_from_chat.id
        else:
            return await message.reply_text("❌ Channel ID nahi mili. Forward privacy on hai. \nTry command: `/addfsub <channel_id>`")
    else:
        return await message.reply_text("❌ Usage:\n1. `/addfsub -100xxxx`\n2. Reply to channel message with `/addfsub`")

    # Verify Bot Admin in Channel
    try:
        chat = await client.get_chat(channel_id)
        me = await client.get_chat_member(channel_id, (await client.get_me()).id)
        if not me.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
             return await message.reply_text("❌ Main us channel me Admin nahi hu!")
    except Exception as e:
        return await message.reply_text(f"❌ Error: Bot ko Channel me add karo aur Admin banao!\nError: {e}")

    await set_force_sub(message.chat.id, channel_id)
    await message.reply_text(f"✅ **Force Subscribe Connected!**\n\nLinked to: {chat.title}")

# ================ PREMIUM ADMIN COMMANDS ================
@app.on_message(filters.command("add_premium") & filters.user(Config.OWNER_ID))
async def add_premium_cmd(client: Client, message: Message):
    try:
        # /add_premium -100xxxx 1
        _, group_id, months = message.text.split()
        expiry = await add_premium(int(group_id), int(months))
        
        # Notify Admin
        await message.reply_text(f"✅ **Premium Added!**\nGroup: `{group_id}`\nMonths: {months}\nExpires: {expiry}")
        
        # Notify Group
        try:
            await client.send_message(
                int(group_id),
                f"💎 **Premium Activated!** 💎\n\n✅ Ads Removed (No Broadcasts)\n✅ Force Subscribe Enabled (/addfsub)\n\nThank you for support! ❤️"
            )
        except:
            await message.reply_text("⚠️ Database update hua par Group me msg nahi gaya (Bot kicked?)")
            
    except Exception as e:
        await message.reply_text(f"❌ Usage: `/add_premium <group_id> <months>`\nError: {e}")

@app.on_message(filters.command("remove_premium") & filters.user(Config.OWNER_ID))
async def remove_premium_cmd(client: Client, message: Message):
    try:
        group_id = int(message.command[1])
        await remove_premium(group_id)
        await message.reply_text(f"❌ Premium removed for `{group_id}`")
    except:
        await message.reply_text("Usage: `/remove_premium <group_id>`")

@app.on_message(filters.command("premiumstats") & filters.user(Config.OWNER_ID))
async def premium_stats_cmd(client: Client, message: Message):
    count = 0
    all_grps = await get_all_groups()
    for g in all_grps:
        if await check_is_premium(g):
            count += 1
    await message.reply_text(f"💎 **Total Premium Groups:** {count}")

# ================ MAIN FILTER (JUNK REMOVER) ================
@app.on_message(filters.group & filters.text & ~filters.command(["start", "help", "settings", "addfsub", "stats", "ai", "broadcast", "grp_broadcast", "setcommands", "ping", "id", "ban", "unban", "add_premium", "remove_premium", "premiumstats"]))
async def group_message_filter(client, message):
    # 1. Ignore Admins/Owner (Unko kuch bhi likhne do)
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
            # Optional: Warn user (Self destructing message)
            warn = await message.reply_text(
                f"🚫 {message.from_user.mention}, extra words allowed nahi hain!\n"
                f"Sahi tarika: `The Raja Saab` ya `Stranger Things S01`"
            )
            await MovieBotUtils.auto_delete_message(client, warn, 5)
        except Exception as e:
            print(f"Delete Error: {e}")
            
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
        await asyncio.sleep(delete_time * 60)  # Convert minutes to seconds
    
    try:
        await client.delete_messages(message.chat.id, message.id)
        
        # Send notification if enabled
        notification = await message.reply_text(
            f"🗑️ File Auto-Deleted\n"
            f"Files are automatically deleted after {delete_time} minutes in this group.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu")]
            ])
        )
        await MovieBotUtils.auto_delete_message(client, notification)
    except:
        pass

# ================ FORCE SUBSCRIBE ENFORCEMENT ================
@app.on_chat_member_updated()
async def handle_fsub_join(client, update: ChatMemberUpdated):
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
            await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
            
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
            
            await client.send_message(
                chat_id,
                f"👋 Welcome {update.new_chat_member.user.mention}!\n\n"
                f"🔒 **Group Message Karne ke liye Channel Join karein.**",
                reply_markup=buttons
            )
        except Exception as e:
            logger.error(f"Fsub Error: {e}")
    except Exception as e:
        # Bot might not be admin in channel
        logger.error(f"Fsub Admin Check Error: {e}")

# ================ CALLBACK QUERY HANDLERS ================
@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    """Handle all callback queries"""
    data = query.data
    chat_id = query.message.chat.id if query.message else query.from_user.id
    user_id = query.from_user.id
    
    if data == "premium_info":
        text = """💎 **Premium Plans** 💎

💸 **Pricing:**
• 1 Month: ₹100
• 2 Months: ₹200
• Lifetime: ₹500

🔥 **Benefits:**
1. 🔇 No Broadcast Messages (Ads Free)
2. 🔗 Force Subscribe Feature Access
3. ⚡ Priority Support

Buy karne ke liye owner se contact karein: @asbhai_bsr"""
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await query.answer()
    
    elif data == "help_main":
        await query.message.delete()
        await help_command(client, query.message)
        await query.answer()
    
    elif data == "toggle_spelling":
        settings = await get_settings(chat_id)
        new_value = not settings.get("spelling_on", True)
        await update_settings(chat_id, "spelling_on", new_value)
        
        status = "✅ ON" if new_value else "❌ OFF"
        is_prem = await check_is_premium(chat_id)
        prem_status = "💎 Active" if is_prem else "❌ Free"
        
        await query.message.edit_reply_markup(
            InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Spelling: {status}", callback_data="toggle_spelling")],
                [InlineKeyboardButton(f"Auto Delete: {'✅ ON' if settings.get('auto_delete_on', False) else '❌ OFF'}", callback_data="toggle_auto_delete")],
                [InlineKeyboardButton(f"Time: {settings.get('delete_time', 0)} min", callback_data="set_delete_time")],
                [InlineKeyboardButton(f"Premium: {prem_status}", callback_data="premium_info")],
                [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
            ])
        )
        await query.answer(f"Spelling correction turned {status}")
    
    elif data == "toggle_auto_delete":
        settings = await get_settings(chat_id)
        new_value = not settings.get("auto_delete_on", False)
        await update_settings(chat_id, "auto_delete_on", new_value)
        
        status = "✅ ON" if new_value else "❌ OFF"
        is_prem = await check_is_premium(chat_id)
        prem_status = "💎 Active" if is_prem else "❌ Free"
        
        await query.message.edit_reply_markup(
            InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Spelling: {'✅ ON' if settings.get('spelling_on', True) else '❌ OFF'}", callback_data="toggle_spelling")],
                [InlineKeyboardButton(f"Auto Delete: {status}", callback_data="toggle_auto_delete")],
                [InlineKeyboardButton(f"Time: {settings.get('delete_time', 0)} min", callback_data="set_delete_time")],
                [InlineKeyboardButton(f"Premium: {prem_status}", callback_data="premium_info")],
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
        is_prem = await check_is_premium(chat_id)
        prem_status = "💎 Active" if is_prem else "❌ Free"
        
        spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
        delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
        delete_time = minutes
        time_text = f"{delete_time} min" if delete_time > 0 else "Permanent"
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Spelling: {spelling_status}", callback_data="toggle_spelling")],
            [InlineKeyboardButton(f"Auto Delete: {delete_status}", callback_data="toggle_auto_delete")],
            [InlineKeyboardButton(f"Time: {time_text}", callback_data="set_delete_time")],
            [InlineKeyboardButton(f"Premium: {prem_status}", callback_data="premium_info")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ])
        
        await query.message.edit_text(
            f"⚙️ Settings for {query.message.chat.title}",
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
        
        # Premium groups count
        premium_count = 0
        all_grps = await get_all_groups()
        for g in all_grps:
            if await check_is_premium(g):
                premium_count += 1
        
        stats_text = f"""📊 Bot Statistics

👥 Total Users: {users}
👥 Total Groups: {groups}
💎 Premium Groups: {premium_count}
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
            # Unmute
            await client.restrict_chat_member(
                chat_id, user_id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True
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
        is_prem = await check_is_premium(chat_id)
        prem_status = "💎 Active" if is_prem else "❌ Free"
        
        spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
        delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
        delete_time = settings.get("delete_time", 0)
        time_text = f"{delete_time} min" if delete_time > 0 else "Permanent"
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Spelling: {spelling_status}", callback_data="toggle_spelling")],
            [InlineKeyboardButton(f"Auto Delete: {delete_status}", callback_data="toggle_auto_delete")],
            [InlineKeyboardButton(f"Time: {time_text}", callback_data="set_delete_time")],
            [InlineKeyboardButton(f"Premium: {prem_status}", callback_data="premium_info")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ])
        
        await query.message.edit_text(
            f"⚙️ Settings for {query.message.chat.title}",
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

# ================ GROUP EVENTS ================
@app.on_message(filters.new_chat_members)
async def welcome_new_members(client: Client, message: Message):
    """Welcome new members and add group to database"""
    for member in message.new_chat_members:
        if member.is_self:  # Bot added to group
            # Bot added to group
            await add_group(message.chat.id, message.chat.title, message.chat.username)
            
            # Send Welcome
            await message.reply_text(
                f"🎬 Thanks for adding me to **{message.chat.title}**!\n\nUse /settings to setup.\nMake me Admin first!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu")]])
            )
            
            # LOGS + INVITE LINK
            if Config.LOGS_CHANNEL:
                invite_link = "N/A"
                try:
                    link_obj = await client.export_chat_invite_link(message.chat.id)
                    invite_link = link_obj
                except:
                    invite_link = "Bot needs Admin to generate link"
                
                log_txt = (
                    f"📂 **Bot Added to Group**\n\n"
                    f"📛 Name: {message.chat.title}\n"
                    f"🆔 ID: `{message.chat.id}`\n"
                    f"👥 Members: {await client.get_chat_members_count(message.chat.id)}\n"
                    f"🔗 Link: {invite_link}\n"
                    f"👤 Added By: {message.from_user.mention if message.from_user else 'Unknown'}"
                )
                try:
                    await client.send_message(Config.LOGS_CHANNEL, log_txt)
                except Exception as e:
                    logger.error(f"Log Error: {e}")
            
            break  # Only need to handle bot addition once

# ================ SETCOMMANDS COMMAND ================
@app.on_message(filters.command("setcommands") & filters.user(Config.OWNER_ID))
async def setcommands_command(client: Client, message: Message):
    """Set bot commands"""
    commands = [
        {"command": "start", "description": "Start the bot"},
        {"command": "help", "description": "Get help"},
        {"command": "settings", "description": "Group settings"},
        {"command": "stats", "description": "Bot statistics"},
        {"command": "ai", "description": "Ask AI about movies"},
        {"command": "addfsub", "description": "Set force subscribe (Premium)"},
        {"command": "ping", "description": "Check bot status"},
        {"command": "id", "description": "Get user/group ID"}
    ]
    
    try:
        await client.set_bot_commands(commands)
        await message.reply_text("✅ Bot commands set successfully!")
    except Exception as e:
        await message.reply_text(f"❌ Failed to set commands: {e}")

# ================ PING COMMAND ================
@app.on_message(filters.command("ping"))
async def ping_command(client: Client, message: Message):
    """Check if bot is alive"""
    start_time = time.time()
    msg = await message.reply_text("🏓 Pinging...")
    end_time = time.time()
    
    ping_time = round((end_time - start_time) * 1000, 2)
    
    await msg.edit_text(f"🏓 Pong!\n\n⏱ Response Time: {ping_time}ms\n🚀 Status: ✅ Alive\n☁️ Server: Koyeb Cloud")

# ================ ID COMMAND ================
@app.on_message(filters.command("id"))
async def id_command(client: Client, message: Message):
    """Get user/group ID"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    text = f"👤 Your ID: `{user_id}`\n"
    
    if message.chat.type != "private":
        text += f"👥 Group ID: `{chat_id}`\n"
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
        await message.reply_text(f"✅ User `{user_id}` banned successfully!")
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
        await message.reply_text(f"✅ User `{user_id}` unbanned successfully!")
    except ValueError:
        await message.reply_text("❌ Invalid user ID!")

if __name__ == "__main__":
    print("🚀 Starting Movie Helper Bot...")
    
    # Simple run without idle
    try:
        app.run()
    except KeyboardInterrupt:
        print("⏹️ Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
        import traceback
        traceback.print_exc()
