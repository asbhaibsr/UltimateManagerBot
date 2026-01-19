import asyncio
import logging
import time
import re
import datetime
from pyrogram import Client, filters, idle
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, ChatMemberUpdated, ChatPermissions, ChatJoinRequest
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

# Cache for Force Sub to prevent double messages
fsub_cache = []
command_cache = {}  # For auto-deleting command messages

# ================ HELPER FUNCTIONS ================
async def is_admin(chat_id, user_id):
    if user_id == Config.OWNER_ID:
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

async def get_channel_info(channel_id):
    try:
        chat = await app.get_chat(channel_id)
        link = chat.invite_link or f"https://t.me/{chat.username}" if chat.username else None
        return chat.title, link
    except:
        return "Unknown Channel", None

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
                f"🧑‍💻 New User Started Bot\n\n"
                f"👤 Name: {user.mention}\n"
                f"🆔 ID: {user.id}\n"
                f"🔗 Username: @{user.username if user.username else 'N/A'}"
            )
            await client.send_message(Config.LOGS_CHANNEL, log_text)
        except Exception as e:
            logger.error(f"Log Error: {e}")

    welcome_text = f"""🎬 **Namaste {user.first_name}!** 🎬

Main hoon apka **Movie Helper Bot!** 🤖

✨ **Premium Features:**
✅ Smart Spelling Correction
✅ Auto Delete Files
✅ AI Movie Recommendations
⚡ Auto Accept Join Requests
🛡️ Advanced Abuse/Link Protection
💎 Force Subscribe System

➡️ **Add me to your groups and make me admin!** 😊"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add me to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton("💎 Premium Plans", callback_data="premium_info")],
        [InlineKeyboardButton("🤖 Help Commands", callback_data="help_main")],
        [InlineKeyboardButton("⚡ Auto Accept Setup", callback_data="auto_accept_setup")]
    ])
    
    msg = await message.reply_text(welcome_text, reply_markup=buttons)
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ HELP COMMAND (UPDATED) ================
@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    """Handle /help command"""
    help_text = """**🆘 Help Menu 🆘**

**📌 For Group Owners/Admins:**
1. Add me to group and make Admin
2. Use `/settings` - Change group settings
3. Use `/addfsub` - Set Force Subscribe (Premium Only)

**🛠 Bot Features:**
• **Spelling Checker** - Auto-corrects movie names
• **Auto Delete** - Automatically deletes media files
• **Auto Accept** - Auto-approves join requests
• **AI Chat** - Movie recommendations & chat
• **Security** - Link & abuse protection
• **Force Subscribe** - Premium feature

**👤 User Commands:**
• `/start` - Start the bot
• `/request <movie>` - Request a movie
• `/ai <question>` - Ask AI about movies
• `/ping` - Check bot status
• `/id` - Get user/group ID

**👑 Premium Commands:**
• `/addfsub <channel_id>` - Connect channel for Force Subscribe

**📞 Contact:** @asbhai_bsr"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 Premium Info", callback_data="premium_info")],
        [InlineKeyboardButton("⚡ Auto Accept Setup", callback_data="auto_accept_setup")],
        [InlineKeyboardButton("⚙️ Group Settings", callback_data="help_settings")],
        [InlineKeyboardButton("❌ Close", callback_data="close_help")]
    ])
    
    msg = await message.reply_text(help_text, reply_markup=buttons)
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ SETTINGS COMMAND (UPDATED) ================
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
    auto_accept = await get_auto_accept(message.chat.id)
    
    prem_status = "💎 Active" if is_prem else "❌ Free"
    spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
    delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
    accept_status = "✅ ON" if auto_accept else "❌ OFF"
    welcome_status = "✅ ON" if settings.get("welcome_enabled", True) else "❌ OFF"
    time_text = f"{settings.get('delete_time', 0)} min" if settings.get('delete_time', 0) > 0 else "Permanent"
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✏️ Spelling: {spelling_status}", callback_data="toggle_spelling")],
        [InlineKeyboardButton(f"🗑️ Auto Delete: {delete_status}", callback_data="toggle_auto_delete")],
        [InlineKeyboardButton(f"✅ Auto Accept: {accept_status}", callback_data="toggle_auto_accept")],
        [InlineKeyboardButton(f"👋 Welcome: {welcome_status}", callback_data="toggle_welcome")],
        [InlineKeyboardButton(f"⏰ Time: {time_text}", callback_data="set_delete_time")],
        [InlineKeyboardButton(f"{prem_status} Premium", callback_data="premium_info")],
        [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
    ])
    
    msg = await message.reply_text(f"**⚙️ Settings for {message.chat.title}**", reply_markup=buttons)
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ REQUEST HANDLER (UPDATED) ================
@app.on_message(filters.command("request") & filters.group)
async def request_handler(client: Client, message: Message):
    if len(message.command) < 2:
        msg = await message.reply_text("❌ Please specify movie name!\nExample: `/request Pushpa 2`")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return
    
    movie_name = " ".join(message.command[1:])
    user = message.from_user
    chat = message.chat
    
    # Get admins for tagging
    admins = []
    try:
        async for admin in client.get_chat_members(chat.id, filter="administrators"):
            if not admin.user.is_bot and admin.user.id != user.id:
                admins.append(admin.user.mention)
    except:
        pass
    
    admin_tags = " ".join(admins[:3]) if admins else "Admins"
    
    # Create request message
    text = (
        f"**🔔 NEW MOVIE REQUEST**\n\n"
        f"**👤 User:** {user.mention}\n"
        f"**🎬 Movie:** `{movie_name}`\n"
        f"**📍 Group:** {chat.title}\n\n"
        f"**{admin_tags}** - Please check this request!"
    )
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Available", callback_data=f"req_accept_{user.id}"),
            InlineKeyboardButton("❌ Not Available", callback_data=f"req_reject_{user.id}")
        ],
        [
            InlineKeyboardButton("📝 Status", callback_data=f"req_status_{user.id}")
        ]
    ])
    
    msg = await message.reply_text(text, reply_markup=buttons)
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# Also handle #request hashtag
@app.on_message(filters.group & filters.regex(r'^#request\s+', re.IGNORECASE))
async def hashtag_request_handler(client: Client, message: Message):
    movie_name = message.text.split('#request', 1)[1].strip()
    if not movie_name:
        return
    
    user = message.from_user
    chat = message.chat
    
    # Delete the original hashtag message
    try:
        await message.delete()
    except:
        pass
    
    # Get admins for tagging
    admins = []
    try:
        async for admin in client.get_chat_members(chat.id, filter="administrators"):
            if not admin.user.is_bot and admin.user.id != user.id:
                admins.append(admin.user.mention)
    except:
        pass
    
    admin_tags = " ".join(admins[:3]) if admins else "Admins"
    
    # Create request message
    text = (
        f"**🔔 NEW MOVIE REQUEST**\n\n"
        f"**👤 User:** {user.mention}\n"
        f"**🎬 Movie:** `{movie_name}`\n"
        f"**📍 Group:** {chat.title}\n\n"
        f"**{admin_tags}** - Please check this request!"
    )
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Available", callback_data=f"req_accept_{user.id}"),
            InlineKeyboardButton("❌ Not Available", callback_data=f"req_reject_{user.id}")
        ],
        [
            InlineKeyboardButton("📝 Status", callback_data=f"req_status_{user.id}")
        ]
    ])
    
    msg = await client.send_message(chat.id, text, reply_markup=buttons)
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

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
    
    stats_text = f"""**📊 Bot Statistics**

👥 **Total Users:** {users}
👥 **Total Groups:** {groups}
💎 **Premium Groups:** {premium_count}
⚡ **Bot Uptime:** 24/7
🔄 **Last Updated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Database Status:** ✅ Connected
**AI Status:** ✅ Active
**Server:** Koyeb Cloud
**Status:** ✅ Running"""
    
    await message.reply_text(stats_text, reply_markup=buttons)

# ================ AI COMMAND ================
@app.on_message(filters.command("ai"))
async def ai_command(client: Client, message: Message):
    """AI chat feature"""
    if len(message.command) < 2:
        msg = await message.reply_text("**Usage:** `/ai your question`\n**Example:** `/ai Tell me about Inception movie`")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return
    
    query = ' '.join(message.command[1:])
    waiting_msg = await message.reply_text("🤔 **Soch raha hu...**")
    
    response = await MovieBotUtils.get_ai_response(query)
    
    await waiting_msg.delete()
    msg = await message.reply_text(response)
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ BROADCAST COMMAND ================
@app.on_message(filters.command(["broadcast", "grp_broadcast"]) & filters.user(Config.OWNER_ID))
async def broadcast_command(client: Client, message: Message):
    if not message.reply_to_message:
        msg = await message.reply_text("❌ Please reply to a message to broadcast!")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return
    
    is_group = "grp_broadcast" in message.text
    target_ids = await get_all_groups() if is_group else await get_all_users()
    
    # Premium Filter for Groups (Don't broadcast to Premium)
    if is_group:
        target_ids = [g for g in target_ids if not await check_is_premium(g)]

    progress = await message.reply_text(f"🚀 **Broadcasting to {len(target_ids)} chats...**")
    success, failed, deleted = 0, 0, 0
    
    for id in target_ids:
        try:
            await message.reply_to_message.copy(id)
            success += 1
        except Exception as e:
            # Agar bot block hai ya kick hai to DB se hata do
            if "PeerIdInvalid" in str(e) or "UserDeactivated" in str(e) or "ChannelPrivate" in str(e) or "ChatWriteForbidden" in str(e):
                if is_group:
                    await remove_group(id)
                deleted += 1
            failed += 1
        await asyncio.sleep(0.5)
        
    msg = await progress.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"🎯 **Total:** {len(target_ids)}\n"
        f"✅ **Success:** {success}\n"
        f"❌ **Failed:** {failed}\n"
        f"🗑️ **Cleaned Junk:** {deleted}"
    )
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ ADDFSUB COMMAND ================
@app.on_message(filters.command("addfsub") & filters.group)
async def addfsub_command(client: Client, message: Message):
    """Set force subscribe channel"""
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ Only Admins can use this command!")
        await asyncio.sleep(5)
        await msg.delete()
        return

    # Check Premium First
    if not await check_is_premium(message.chat.id):
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Buy Premium", url="https://t.me/asbhai_bsr")],
            [InlineKeyboardButton("ℹ️ Premium Info", callback_data="premium_info")]
        ])
        msg = await message.reply_text(
            "**💎 Premium Feature!**\n\n"
            "Force Subscribe use karne ke liye Premium lena padega.\n"
            "Premium se aapko ads free experience milega aur Force Subscribe feature milega.",
            reply_markup=buttons
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return

    channel_id = None
    
    if len(message.command) > 1:
        try:
            channel_id = int(message.command[1])
        except ValueError:
            msg = await message.reply_text("❌ Invalid ID! Numeric ID daalo (e.g. -100xxxxxxx)")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            return

    elif message.reply_to_message:
        if message.reply_to_message.forward_from_chat:
            channel_id = message.reply_to_message.forward_from_chat.id
        else:
            msg = await message.reply_text("❌ Channel ID nahi mili. Forward privacy on hai. \n**Try:** `/addfsub -100xxxxxxx`")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            return
    else:
        msg = await message.reply_text(
            "**❌ Usage:**\n"
            "1. `/addfsub -100xxxxxxx`\n"
            "2. Reply to channel message with `/addfsub`"
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return

    try:
        chat = await client.get_chat(channel_id)
        me = await client.get_chat_member(channel_id, (await client.get_me()).id)
        if not me.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
             msg = await message.reply_text("❌ Main us channel me Admin nahi hu! Pehle mujhe admin banao.")
             asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
             return
    except Exception as e:
        msg = await message.reply_text(f"❌ Error: Bot ko Channel me add karo aur Admin banao!\n**Error:** {e}")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return

    await set_force_sub(message.chat.id, channel_id)
    msg = await message.reply_text(
        f"✅ **Force Subscribe Connected!**\n\n"
        f"**Linked to:** {chat.title}\n"
        f"**Channel ID:** `{channel_id}`\n\n"
        f"Ab naye users ko channel join karna hoga group me baat karne ke liye."
    )
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))

# ================ PREMIUM ADMIN COMMANDS ================
@app.on_message(filters.command("add_premium") & filters.user(Config.OWNER_ID))
async def add_premium_cmd(client: Client, message: Message):
    try:
        if len(message.command) < 3:
             msg = await message.reply_text("❌ Usage: `/add_premium <group_id> <months>`")
             asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
             return

        group_id = int(message.command[1])
        raw_months = message.command[2].lower()
        clean_months = ''.join(filter(str.isdigit, raw_months))
        
        if not clean_months:
             msg = await message.reply_text("❌ Error: Invalid month format. Use numbers only.")
             asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
             return
             
        months = int(clean_months)
        expiry = await add_premium(group_id, months)
        
        msg = await message.reply_text(
            f"✅ **Premium Added!**\n\n"
            f"**Group:** `{group_id}`\n"
            f"**Months:** {months}\n"
            f"**Expires:** {expiry.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        try:
            await client.send_message(
                group_id,
                f"**💎 Premium Activated! 💎**\n\n"
                f"✅ Ads Removed\n"
                f"✅ Force Subscribe Enabled\n"
                f"✅ Priority Support\n\n"
                f"Thank you for your support! ❤️"
            )
        except:
            await message.reply_text("⚠️ Database update hua par Group me msg nahi gaya")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            
    except Exception as e:
        msg = await message.reply_text(f"❌ Error: {e}")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))

@app.on_message(filters.command("remove_premium") & filters.user(Config.OWNER_ID))
async def remove_premium_cmd(client: Client, message: Message):
    try:
        if len(message.command) < 2:
            msg = await message.reply_text("❌ Usage: `/remove_premium <group_id>`")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            return
            
        group_id = int(message.command[1])
        await remove_premium(group_id)
        msg = await message.reply_text(f"❌ Premium removed for `{group_id}`")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
    except Exception as e:
        msg = await message.reply_text(f"❌ Error: {e}")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))

@app.on_message(filters.command("premiumstats") & filters.user(Config.OWNER_ID))
async def premium_stats_cmd(client: Client, message: Message):
    count = 0
    premium_list = []
    all_grps = await get_all_groups()
    for g in all_grps:
        if await check_is_premium(g):
            count += 1
            try:
                chat = await client.get_chat(g)
                premium_list.append(f"• {chat.title} (`{g}`)")
            except:
                premium_list.append(f"• Unknown (`{g}`)")
    
    premium_text = f"**💎 Total Premium Groups: {count}**\n\n"
    if premium_list:
        premium_text += "\n".join(premium_list[:10])
        if len(premium_list) > 10:
            premium_text += f"\n\n...and {len(premium_list) - 10} more"
    
    await message.reply_text(premium_text)

# ================ MAIN FILTER (UPDATED SPELLING CHECK) ================
@app.on_message(filters.group & filters.text & ~filters.command([
    "start", "help", "settings", "addfsub", "stats", "ai", 
    "broadcast", "request", "ban", "unban", "add_premium", 
    "remove_premium", "premiumstats", "ping", "id"
]))
async def group_message_filter(client, message):
    if await is_admin(message.chat.id, message.from_user.id):
        return

    settings = await get_settings(message.chat.id)
    quality = MovieBotUtils.check_message_quality(message.text)

    # 1. LINK HANDLING
    if quality == "LINK":
        await message.delete()
        warn_count = await add_warning(message.chat.id, message.from_user.id)
        limit = 3
        
        if warn_count >= limit:
            try:
                # Ban/Mute User (Muting for 24 hours)
                await client.restrict_chat_member(
                    message.chat.id, 
                    message.from_user.id, 
                    ChatPermissions(can_send_messages=False),
                    until_date=datetime.datetime.now() + datetime.timedelta(hours=24)
                )
                warn_msg = await message.reply_text(
                    f"🚫 {message.from_user.mention} ko **Mute** kar diya gaya hai (Links not allowed)!"
                )
                await reset_warnings(message.chat.id, message.from_user.id)
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, warn_msg, 10))
            except:
                pass
        else:
            warn_msg = await message.reply_text(
                f"⚠️ {message.from_user.mention}, **Link mat bhejo!**\n"
                f"Warning: **{warn_count}/{limit}**"
            )
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, warn_msg, 10))

    # 2. ABUSE HANDLING
    elif quality == "ABUSE":
        await message.delete()
        warn_count = await add_warning(message.chat.id, message.from_user.id)
        limit = 3
        
        if warn_count >= limit:
            try:
                # Ban User
                await client.ban_chat_member(message.chat.id, message.from_user.id)
                ban_msg = await message.reply_text(
                    f"🚫 {message.from_user.mention} ko **Ban** kar diya gaya hai (Abusive Language)!"
                )
                await reset_warnings(message.chat.id, message.from_user.id)
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, ban_msg, 10))
            except:
                pass
        else:
            warn_msg = await message.reply_text(
                f"⚠️ {message.from_user.mention}, **Gali mat do!**\n"
                f"Warning: **{warn_count}/{limit}**"
            )
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, warn_msg, 10))

    # 3. SPELLING CHECK (JUNK) - UPDATED DESIGN
    elif settings.get("spelling_on", True) and quality == "JUNK":
        await message.delete()
        
        # Extract movie name from message
        movie_name = MovieBotUtils.extract_movie_name(message.text)
        suggestions = MovieBotUtils.get_movie_suggestions()
        
        if movie_name:
            # Try to find correct spelling
            corrected = MovieBotUtils.get_spelling_suggestion(movie_name, suggestions)
            
            if corrected:
                # Create stylish correction message
                correction_text = (
                    f"✨ **Spelling Check** ✨\n\n"
                    f"👤 **User:** {message.from_user.mention}\n"
                    f"❌ **Galat:** `{message.text}`\n"
                    f"✅ **Sahi:** `{corrected}`\n\n"
                    f"📌 **Suggested Format:** Movie Name (Year)"
                )
            else:
                correction_text = (
                    f"✨ **Spelling Check** ✨\n\n"
                    f"👤 **User:** {message.from_user.mention}\n"
                    f"❌ **Galat Format:** `{message.text}`\n"
                    f"✅ **Sahi Format:** Movie Name (Year)\n\n"
                    f"📌 **Example:** `Pushpa 2 (2024)`"
                )
        else:
            correction_text = (
                f"✨ **Spelling Check** ✨\n\n"
                f"👤 **User:** {message.from_user.mention}\n"
                f"❌ **Galat Format:** `{message.text}`\n"
                f"✅ **Sahi Format:** Movie Name (Year)\n\n"
                f"📌 **Example:** `Pushpa 2 (2024)`\n"
                f"📌 **Popular Movies:** Pushpa 2, Kalki 2898 AD, Jawan, Pathaan"
            )
        
        spell_msg = await message.reply_text(correction_text)
        # Delete after 3 minutes (180 seconds)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, spell_msg, 180))

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
        notification_text = (
            f"🗑️ **File Auto-Deleted**\n"
            f"Files are automatically deleted after **{delete_time} minutes**."
        )
        
        notification = await message.reply_text(
            notification_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu")]
            ])
        )
        await MovieBotUtils.auto_delete_message(client, notification, 10)
    except:
        pass

# ================ FORCE SUBSCRIBE (IMPROVED) ================
@app.on_chat_member_updated()
async def handle_fsub_join(client, update: ChatMemberUpdated):
    if not update.new_chat_member or update.new_chat_member.user.is_bot:
        return

    # Double Message Fix
    user_id = update.new_chat_member.user.id
    chat_id = update.chat.id
    cache_key = f"{user_id}_{chat_id}"
    
    if cache_key in fsub_cache:
        return
    fsub_cache.append(cache_key)
    asyncio.get_event_loop().call_later(5, lambda: fsub_cache.remove(cache_key))

    fsub_data = await get_force_sub(chat_id)
    if not fsub_data:
        return

    channel_id = fsub_data["channel_id"]
    user = update.new_chat_member.user
    
    try:
        # Check if user has joined the channel
        member = await client.get_chat_member(channel_id, user_id)
        if member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
            # User has already joined, unmute them
            await client.restrict_chat_member(
                chat_id, user_id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True
                )
            )
            
            # Send welcome message with user's photo
            welcome_text = (
                f"🎉 **Welcome {user.mention}!** 🎉\n\n"
                f"✅ **Verification Complete!**\n"
                f"You can now chat in the group.\n\n"
                f"Enjoy your stay! 😊"
            )
            
            try:
                if user.photo:
                    welcome_msg = await client.send_photo(
                        chat_id, 
                        photo=user.photo.big_file_id, 
                        caption=welcome_text
                    )
                else:
                    welcome_msg = await client.send_message(chat_id, welcome_text)
                
                # Delete welcome message after 1 minute
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 60))
            except:
                pass
            return
            
    except UserNotParticipant:
        # User hasn't joined, mute them
        await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
        
        # Get Channel Info
        try:
            chat_info = await client.get_chat(channel_id)
            channel_name = chat_info.title
            link = chat_info.invite_link or f"https://t.me/{chat_info.username}"
        except:
            channel_name = "our channel"
            link = "https://t.me/asbhai_bsr"

        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=link)],
            [InlineKeyboardButton("✅ I Joined", callback_data=f"fsub_verify_{user_id}")]
        ])
        
        # Welcome message with strong wording
        welcome_txt = (
            f"🔒 **GROUP LOCKED** 🔒\n\n"
            f"👋 **Hello {user.mention}!**\n\n"
            f"⚠️ **To unlock chatting privileges:**\n"
            f"1. **Join our channel:** {channel_name}\n"
            f"2. **Click 'I Joined' button below**\n\n"
            f"❌ **Without joining, you cannot send messages!**\n"
            f"✅ **After joining, you'll be automatically unmuted.**"
        )
        
        try:
            if user.photo:
                fsub_msg = await client.send_photo(
                    chat_id, 
                    photo=user.photo.big_file_id, 
                    caption=welcome_txt, 
                    reply_markup=buttons
                )
            else:
                fsub_msg = await client.send_message(chat_id, welcome_txt, reply_markup=buttons)
            
            # Store message ID for auto-delete
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, fsub_msg, 300))
        except:
            fsub_msg = await client.send_message(chat_id, welcome_txt, reply_markup=buttons)
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, fsub_msg, 300))
    except Exception as e:
        logger.error(f"FSub Error: {e}")

# ================ AUTO ACCEPT JOIN REQUEST (IMPROVED) ================
@app.on_chat_join_request()
async def auto_approve_join(client: Client, request: ChatJoinRequest):
    chat_id = request.chat.id
    user_id = request.from_user.id
    
    if await get_auto_accept(chat_id):
        try:
            # Check if bot is admin
            try:
                bot_member = await client.get_chat_member(chat_id, (await client.get_me()).id)
                if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                    return
            except:
                return
            
            # Approve the request
            await client.approve_chat_join_request(chat_id, user_id)
            
            # Send welcome message to user
            welcome_msg = (
                f"✅ **Request Approved!**\n\n"
                f"Welcome to **{request.chat.title}**!\n\n"
                f"🎬 **Enjoy unlimited movies & entertainment!** 🍿\n\n"
                f"📌 **Group Rules:**\n"
                f"• No spamming\n"
                f"• No abusive language\n"
                f"• Follow admin instructions\n\n"
                f"Have a great time! 😊"
            )
            
            try:
                await client.send_message(user_id, welcome_msg)
            except:
                pass
                
        except Exception as e:
            logger.error(f"Auto Accept Error: {e}")

# ================ WELCOME MESSAGE FOR NEW MEMBERS ================
@app.on_message(filters.new_chat_members)
async def welcome_new_members(client: Client, message: Message):
    """Welcome new members with photo and details"""
    settings = await get_settings(message.chat.id)
    if not settings.get("welcome_enabled", True):
        return
    
    for member in message.new_chat_members:
        if member.is_self:  # Bot added to group
            # Bot added to group
            await add_group(message.chat.id, message.chat.title, message.chat.username)
            
            # Send Welcome
            bot_welcome = await message.reply_text(
                f"🎬 **Thanks for adding me to {message.chat.title}!**\n\n"
                f"🤖 **I'm Movie Helper Bot**\n"
                f"✅ **Features:**\n"
                f"• Spelling Correction\n"
                f"• Auto Delete Files\n"
                f"• AI Movie Chat\n"
                f"• Auto Accept Requests\n\n"
                f"⚙️ **Setup:**\n"
                f"1. Make me **Admin**\n"
                f"2. Use `/settings` to configure\n\n"
                f"Need help? Use `/help`",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu")]])
            )
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, bot_welcome, 120))
            
            # LOGS
            if Config.LOGS_CHANNEL:
                try:
                    log_txt = (
                        f"📂 **Bot Added to Group**\n\n"
                        f"📛 **Name:** {message.chat.title}\n"
                        f"🆔 **ID:** `{message.chat.id}`\n"
                        f"👥 **Members:** {await client.get_chat_members_count(message.chat.id)}\n"
                        f"👤 **Added By:** {message.from_user.mention if message.from_user else 'Unknown'}"
                    )
                    await client.send_message(Config.LOGS_CHANNEL, log_txt)
                except Exception as e:
                    logger.error(f"Log Error: {e}")
            break
        else:
            # Regular user joined
            user = member
            welcome_text = (
                f"🎉 **Welcome {user.mention}!** 🎉\n\n"
                f"👤 **Name:** {user.first_name or ''} {user.last_name or ''}\n"
                f"🆔 **ID:** `{user.id}`\n"
                f"📅 **Joined:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"🎬 **Welcome to our movie community!**\n"
                f"Request movies using `/request` command.\n\n"
                f"Enjoy your stay! 😊"
            )
            
            try:
                if user.photo:
                    welcome_msg = await client.send_photo(
                        message.chat.id,
                        photo=user.photo.big_file_id,
                        caption=welcome_text
                    )
                else:
                    welcome_msg = await message.reply_text(welcome_text)
                
                # Delete welcome message after 2 minutes
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 120))
            except:
                pass

# ================ CALLBACK QUERY HANDLERS (UPDATED) ================
@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    """Handle all callback queries"""
    data = query.data
    chat_id = query.message.chat.id if query.message else query.from_user.id
    user_id = query.from_user.id
    
    # Auto delete callback messages after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, query.message, 300))
    
    # HELP SYSTEM WITH PAGES
    if data == "help_main":
        help_text = """**🤖 BOT FEATURES**

📌 **Main Functions:**
1. ✏️ **Spelling Checker** - Auto-corrects movie names
2. 🗑️ **Auto Delete** - Deletes files after time
3. ✅ **Auto Accept** - Auto-approves join requests
4. 🤖 **AI Chat** - Movie recommendations
5. 🛡️ **Security** - Link & abuse protection

📋 **Commands Available:**
• /start - Start bot
• /help - This menu
• /settings - Group settings
• /request - Request movies
• /ai - Ask AI questions"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("👑 Premium Features", callback_data="help_premium")],
            [InlineKeyboardButton("⚙️ Admin Commands", callback_data="help_admin")],
            [InlineKeyboardButton("📖 User Guide", callback_data="help_guide")],
            [InlineKeyboardButton("❌ Close", callback_data="close_help")]
        ])
        
        await query.message.edit_text(help_text, reply_markup=buttons)
        await query.answer()
    
    elif data == "help_premium":
        premium_text = """**👑 PREMIUM FEATURES**

💎 **Premium Benefits:**
1. 🔇 **No Ads/Broadcasts**
2. 🔗 **Force Subscribe System**
3. ⚡ **Priority Support**
4. 🎯 **Advanced Features**

💰 **Pricing:**
• 1 Month: ₹100
• 3 Months: ₹250
• Lifetime: ₹500

🛒 **Buy Premium:**
Contact @asbhai_bsr for premium purchase."""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="help_main")],
            [InlineKeyboardButton("💎 Buy Now", url="https://t.me/asbhai_bsr")],
            [InlineKeyboardButton("❌ Close", callback_data="close_help")]
        ])
        
        await query.message.edit_text(premium_text, reply_markup=buttons)
        await query.answer()
    
    elif data == "help_admin":
        admin_text = """**⚙️ ADMIN COMMANDS**

**Group Admins Can Use:**
• `/settings` - Configure bot settings
• `/addfsub <channel_id>` - Set Force Subscribe (Premium)
• `/stats` - View bot statistics

**Bot Owner Commands:**
• `/add_premium <group_id> <months>` - Add premium
• `/remove_premium <group_id>` - Remove premium
• `/broadcast` - Send message to all users
• `/grp_broadcast` - Send to all groups
• `/ban <user_id>` - Ban user from bot
• `/unban <user_id>` - Unban user

**Note:** Some commands require premium."""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="help_main")],
            [InlineKeyboardButton("⚡ Auto Accept", callback_data="auto_accept_setup")],
            [InlineKeyboardButton("❌ Close", callback_data="close_help")]
        ])
        
        await query.message.edit_text(admin_text, reply_markup=buttons)
        await query.answer()
    
    elif data == "help_guide":
        guide_text = """**📖 USER GUIDE**

**🎬 How to Request Movies:**
1. Use `/request Movie Name`
2. Or use `#request Movie Name`
3. Admins will be notified

**🤖 Using AI Chat:**
• `/ai Tell me about Inception`
• `/ai Best movies of 2023`
• `/ai Comedy movies list`

**⚙️ Group Rules:**
• No spam or links
• No abusive language
• Use proper movie format
• Follow admin instructions

**📞 Support:**
For help contact @asbhai_bsr"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="help_main")],
            [InlineKeyboardButton("🎬 Request Example", callback_data="help_example")],
            [InlineKeyboardButton("❌ Close", callback_data="close_help")]
        ])
        
        await query.message.edit_text(guide_text, reply_markup=buttons)
        await query.answer()
    
    elif data == "help_example":
        example_text = """**🎬 REQUEST EXAMPLES**

**✅ Correct Format:**
• `/request Pushpa 2 2024`
• `/request Kalki 2898 AD`
• `/request Animal 2023`
• `#request Jawan 2023`

**❌ Wrong Format:**
• `movie dedo`
• `send pushpa`
• `pushpa movie chahiye`
• `plz send movie`

**📌 Tips:**
• Always include movie name
• Add year if possible
• Use proper spelling
• Avoid spam words"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="help_guide")],
            [InlineKeyboardButton("🎬 Try Request", switch_inline_query_current_chat="/request ")]
        ])
        
        await query.message.edit_text(example_text, reply_markup=buttons)
        await query.answer()
    
    elif data == "help_settings":
        settings_text = """**⚙️ SETTINGS GUIDE**

**Available Settings:**
1. ✏️ **Spelling Check** - ON/OFF
2. 🗑️ **Auto Delete** - ON/OFF
3. ✅ **Auto Accept** - ON/OFF
4. 👋 **Welcome Message** - ON/OFF
5. ⏰ **Delete Time** - Set timer

**How to Configure:**
1. Use `/settings` in group
2. Click buttons to toggle
3. Set delete time as needed
4. Premium for extra features

**Note:** Need admin rights to change settings."""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="help_main")],
            [InlineKeyboardButton("⚙️ Open Settings", switch_inline_query_current_chat="/settings")]
        ])
        
        await query.message.edit_text(settings_text, reply_markup=buttons)
        await query.answer()
    
    elif data == "premium_info":
        text = """**💎 PREMIUM PLANS**

**✨ Benefits:**
1. 🔇 **Ads Free Experience**
2. 🔗 **Force Subscribe Feature**
3. ⚡ **Priority Support**
4. 🎯 **Advanced Features**
5. 📊 **Detailed Statistics**

**💰 Pricing:**
• **1 Month:** ₹100
• **3 Months:** ₹250 (Save ₹50)
• **6 Months:** ₹450 (Save ₹150)
• **Lifetime:** ₹500 (One Time)

**🛒 How to Buy:**
1. Contact @asbhai_bsr
2. Send payment via UPI
3. Get premium activated instantly

**🎁 Free Trial:** 3 days trial available!"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Contact Owner", url="https://t.me/asbhai_bsr")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="premium_info")],
            [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
        ])
        
        await query.message.edit_text(text, reply_markup=buttons)
        await query.answer("Premium information")
    
    # AUTO ACCEPT SETUP
    elif data == "auto_accept_setup":
        text = """**⚡ AUTO ACCEPT SETUP**

**I can Approve your Join Requests Automatically!**

**How to Setup:**
1. Add me as **Admin** in your group/channel
2. Enable **Auto Accept** in settings
3. That's it! I'll auto-approve all join requests

**Features:**
✅ Auto approve join requests
✅ Welcome new members
✅ No manual approval needed
✅ Works for groups & channels

**Setup for:**"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 For Group", callback_data="auto_group")],
            [InlineKeyboardButton("📢 For Channel", callback_data="auto_channel")],
            [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
        ])
        
        await query.message.edit_text(text, reply_markup=buttons)
        await query.answer()
    
    elif data == "auto_group":
        text = """**👥 GROUP AUTO ACCEPT**

**Setup Steps:**
1. Add me to your **Group**
2. Make me **Admin** with join request permission
3. Use `/settings` in group
4. Enable **Auto Accept** option
5. Done! I'll auto-approve all requests

**Requirements:**
• Bot must be admin
• Join requests must be enabled in group
• Auto accept must be ON in settings

**Note:** This works for private groups with join requests enabled."""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
            [InlineKeyboardButton("⚙️ Group Settings", switch_inline_query_current_chat="/settings")],
            [InlineKeyboardButton("🔙 Back", callback_data="auto_accept_setup")]
        ])
        
        await query.message.edit_text(text, reply_markup=buttons)
        await query.answer()
    
    elif data == "auto_channel":
        text = """**📢 CHANNEL AUTO ACCEPT**

**Setup Steps:**
1. Add me to your **Channel**
2. Make me **Admin** with add users permission
3. Send me your **Channel ID**
4. I'll enable auto accept for your channel

**Channel ID Format:** `-100xxxxxxxxx`

**How to get Channel ID:**
1. Forward any message from channel to @userinfobot
2. Or add @getidsbot to channel
3. Copy the numeric ID starting with -100

**Send your Channel ID now:**"""
        
        await query.message.edit_text(text)
        await query.answer("Send your channel ID in reply")
    
    # Request Accept Logic
    elif data.startswith("req_accept_"):
        req_user_id = int(data.split("_")[2])
        try:
            await client.send_message(
                query.message.chat.id, 
                f"✅ **Movie Available!** {query.from_user.mention} ne upload kar di hai.\n"
                f"👤 <a href='tg://user?id={req_user_id}'>User</a>, check karo!"
            )
            await query.message.delete()
        except:
            pass
        await query.answer("Request accepted!")

    # Request Reject Logic
    elif data.startswith("req_reject_"):
        req_user_id = int(data.split("_")[2])
        try:
            await client.send_message(
                query.message.chat.id, 
                f"❌ **Movie Not Available**\n"
                f"Request rejected by Admin."
            )
            await query.message.delete()
        except:
            pass
        await query.answer("Request rejected!")

    # Settings Toggles
    elif data == "toggle_spelling":
        settings = await get_settings(chat_id)
        new_value = not settings.get("spelling_on", True)
        await update_settings(chat_id, "spelling_on", new_value)
        status = "ON ✅" if new_value else "OFF ❌"
        await query.answer(f"Spelling correction: {status}")
        await refresh_settings_menu(client, query)
    
    elif data == "toggle_auto_delete":
        settings = await get_settings(chat_id)
        new_value = not settings.get("auto_delete_on", False)
        await update_settings(chat_id, "auto_delete_on", new_value)
        status = "ON ✅" if new_value else "OFF ❌"
        await query.answer(f"Auto delete: {status}")
        await refresh_settings_menu(client, query)

    elif data == "toggle_auto_accept":
        current = await get_auto_accept(chat_id)
        await set_auto_accept(chat_id, not current)
        status = "ON ✅" if not current else "OFF ❌"
        await query.answer(f"Auto Accept: {status}")
        await refresh_settings_menu(client, query)
    
    elif data == "toggle_welcome":
        settings = await get_settings(chat_id)
        new_value = not settings.get("welcome_enabled", True)
        await update_settings(chat_id, "welcome_enabled", new_value)
        status = "ON ✅" if new_value else "OFF ❌"
        await query.answer(f"Welcome messages: {status}")
        await refresh_settings_menu(client, query)
    
    elif data == "set_delete_time":
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("5 Minutes", callback_data="time_5")],
            [InlineKeyboardButton("10 Minutes", callback_data="time_10")],
            [InlineKeyboardButton("15 Minutes", callback_data="time_15")],
            [InlineKeyboardButton("30 Minutes", callback_data="time_30")],
            [InlineKeyboardButton("1 Hour", callback_data="time_60")],
            [InlineKeyboardButton("Permanent ❌", callback_data="time_0")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_settings")]
        ])
        await query.message.edit_text("**⏰ Select Auto-Delete Time:**", reply_markup=buttons)
        await query.answer()
    
    elif data.startswith("time_"):
        minutes = int(data.split("_")[1])
        await update_settings(chat_id, "delete_time", minutes)
        time_text = f"{minutes} minutes" if minutes > 0 else "Permanent"
        await query.answer(f"✅ Delete time set to {time_text}")
        await refresh_settings_menu(client, query)

    elif data == "clear_junk":
        junk_count = await clear_junk()
        await query.answer(f"🧹 Cleared {junk_count} junk entries!")
        await query.message.edit_text(
            f"✅ **Junk Cleared!**\n\n"
            f"Removed **{junk_count}** inactive entries from database.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh Stats", callback_data="refresh_stats")]
            ])
        )
    
    elif data == "refresh_stats":
        users = await get_user_count()
        groups = await get_group_count()
        premium_count = 0
        all_grps = await get_all_groups()
        for g in all_grps:
            if await check_is_premium(g):
                premium_count += 1
        
        stats_text = f"""**📊 Bot Statistics**

👥 **Total Users:** {users}
👥 **Total Groups:** {groups}
💎 **Premium Groups:** {premium_count}
⚡ **Bot Uptime:** 24/7
🔄 **Last Updated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        await query.message.edit_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🧹 Clear Junk", callback_data="clear_junk")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]
            ])
        )
        await query.answer("✅ Stats refreshed!")
    
    elif data.startswith("fsub_verify_"):
        target_id = int(data.split("_")[2])
        if user_id != target_id:
            return await query.answer("❌ This button is not for you!", show_alert=True)
            
        fsub_data = await get_force_sub(chat_id)
        if not fsub_data:
             return await query.message.delete()

        channel_id = fsub_data["channel_id"]
        try:
            # Check if user joined channel
            member = await client.get_chat_member(channel_id, user_id)
            if member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                # Unmute user
                await client.restrict_chat_member(
                    chat_id, user_id,
                    ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_other_messages=True
                    )
                )
                await query.message.delete()
                
                # Send welcome message
                welcome_text = (
                    f"✅ **Verification Successful!**\n\n"
                    f"Welcome {query.from_user.mention}!\n"
                    f"You can now chat in the group.\n\n"
                    f"Enjoy your stay! 😊"
                )
                welcome_msg = await client.send_message(chat_id, welcome_text)
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 60))
                
                await query.answer("✅ Verified! You can chat now.")
            else:
                await query.answer("❌ You haven't joined the channel yet!", show_alert=True)
        except UserNotParticipant:
            await query.answer("❌ You haven't joined the channel!", show_alert=True)
        except Exception as e:
            await query.answer("❌ Error verifying, try again!", show_alert=True)
    
    elif data == "close_settings":
        await query.message.delete()
        await query.answer("Settings closed!")
    
    elif data == "close_help":
        await query.message.delete()
        await query.answer("Help closed!")
    
    elif data == "back_settings" or data == "settings_menu":
        await refresh_settings_menu(client, query)

# Helper for updating settings menu
async def refresh_settings_menu(client, query):
    chat_id = query.message.chat.id
    settings = await get_settings(chat_id)
    is_prem = await check_is_premium(chat_id)
    auto_accept = await get_auto_accept(chat_id)
    
    prem_status = "💎 Active" if is_prem else "❌ Free"
    spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
    delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
    accept_status = "✅ ON" if auto_accept else "❌ OFF"
    welcome_status = "✅ ON" if settings.get("welcome_enabled", True) else "❌ OFF"
    delete_time = settings.get("delete_time", 0)
    time_text = f"{delete_time} min" if delete_time > 0 else "Permanent"
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✏️ Spelling: {spelling_status}", callback_data="toggle_spelling")],
        [InlineKeyboardButton(f"🗑️ Auto Delete: {delete_status}", callback_data="toggle_auto_delete")],
        [InlineKeyboardButton(f"✅ Auto Accept: {accept_status}", callback_data="toggle_auto_accept")],
        [InlineKeyboardButton(f"👋 Welcome: {welcome_status}", callback_data="toggle_welcome")],
        [InlineKeyboardButton(f"⏰ Time: {time_text}", callback_data="set_delete_time")],
        [InlineKeyboardButton(f"{prem_status} Premium", callback_data="premium_info")],
        [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
    ])
    
    await query.message.edit_text(
        f"**⚙️ Settings for {query.message.chat.title}**",
        reply_markup=buttons
    )

# ================ CHANNEL ID HANDLER ================
@app.on_message(filters.private & filters.regex(r'^-100\d+$'))
async def handle_channel_id(client: Client, message: Message):
    """Handle channel ID for auto accept setup"""
    channel_id = int(message.text.strip())
    user_id = message.from_user.id
    
    try:
        # Check if user is admin in channel
        chat = await client.get_chat(channel_id)
        member = await client.get_chat_member(channel_id, user_id)
        
        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await message.reply_text(
                f"❌ **You are not admin in {chat.title}!**\n"
                f"You need to be admin to setup auto accept."
            )
            return
        
        # Check if bot is admin
        try:
            bot_member = await client.get_chat_member(channel_id, (await client.get_me()).id)
            if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                await message.reply_text(
                    f"❌ **I'm not admin in {chat.title}!**\n"
                    f"Please add me as admin first with 'Add Users' permission.\n\n"
                    f"**Message to send in channel:**\n"
                    f"`I can Approve your Join Requests Automatically! Just add me as Admin and you are good to Go..`"
                )
                return
        except:
            await message.reply_text(
                f"❌ **I'm not in {chat.title}!**\n"
                f"Please add me to the channel first as admin.\n\n"
                f"**Message to send in channel:**\n"
                f"`I can Approve your Join Requests Automatically! Just add me as Admin and you are good to Go..`"
            )
            return
        
        # Enable auto accept for this channel
        await set_auto_accept(channel_id, True)
        
        await message.reply_text(
            f"✅ **Auto Accept Enabled for {chat.title}!**\n\n"
            f"**Channel:** {chat.title}\n"
            f"**ID:** `{channel_id}`\n\n"
            f"Now I will automatically approve all join requests in this channel.\n\n"
            f"**Note:** Make sure join requests are enabled in channel settings."
        )
        
    except Exception as e:
        await message.reply_text(
            f"❌ **Error setting up auto accept!**\n\n"
            f"**Error:** {e}\n\n"
            f"Please make sure:\n"
            f"1. Channel ID is correct\n"
            f"2. You are admin in channel\n"
            f"3. Bot is added as admin\n"
            f"4. Channel is not private"
        )

# ================ SETCOMMANDS COMMAND ================
@app.on_message(filters.command("setcommands") & filters.user(Config.OWNER_ID))
async def setcommands_command(client: Client, message: Message):
    """Set bot commands"""
    commands = [
        {"command": "start", "description": "Start the bot"},
        {"command": "help", "description": "Get help menu"},
        {"command": "settings", "description": "Group settings"},
        {"command": "request", "description": "Request a movie"},
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
    msg = await message.reply_text("🏓 **Pinging...**")
    end_time = time.time()
    ping_time = round((end_time - start_time) * 1000, 2)
    await msg.edit_text(
        f"🏓 **Pong!**\n\n"
        f"⏱ **Response Time:** {ping_time}ms\n"
        f"🚀 **Status:** ✅ Alive\n"
        f"☁️ **Server:** Koyeb Cloud\n"
        f"📊 **Uptime:** 24/7"
    )

# ================ ID COMMAND ================
@app.on_message(filters.command("id"))
async def id_command(client: Client, message: Message):
    """Get user/group ID"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = f"👤 **Your ID:** `{user_id}`\n"
    if message.chat.type != "private":
        text += f"👥 **Group ID:** `{chat_id}`\n"
        text += f"📝 **Group Title:** {message.chat.title}\n"
        if message.chat.username:
            text += f"🔗 **Group Link:** https://t.me/{message.chat.username}\n"
    
    await message.reply_text(text)

# ================ BAN/UNBAN COMMANDS ================
@app.on_message(filters.command("ban") & filters.user(Config.OWNER_ID))
async def ban_command(client: Client, message: Message):
    """Ban a user from Bot"""
    if len(message.command) < 2:
        await message.reply_text("**Usage:** `/ban <user_id>`")
        return
    try:
        user_id = int(message.command[1])
        await ban_user(user_id)
        await message.reply_text(f"✅ User `{user_id}` banned from Bot successfully!")
    except ValueError:
        await message.reply_text("❌ Invalid user ID!")

@app.on_message(filters.command("unban") & filters.user(Config.OWNER_ID))
async def unban_command(client: Client, message: Message):
    """Unban a user from Bot"""
    if len(message.command) < 2:
        await message.reply_text("**Usage:** `/unban <user_id>`")
        return
    try:
        user_id = int(message.command[1])
        await unban_user(user_id)
        await message.reply_text(f"✅ User `{user_id}` unbanned from Bot successfully!")
    except ValueError:
        await message.reply_text("❌ Invalid user ID!")

# ================ COMMAND AUTO DELETE ================
@app.on_message(filters.command([
    "start", "help", "settings", "addfsub", "stats", "ai", 
    "broadcast", "request", "ping", "id"
]) & filters.group)
async def auto_delete_commands(client: Client, message: Message):
    """Auto delete command messages after 5 minutes"""
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, message, 300))

# ================ START BOT ================
if __name__ == "__main__":
    print("🚀 Starting Movie Helper Bot...")
    print("✅ All features implemented:")
    print("   1. Fixed Force Subscribe with welcome message")
    print("   2. Improved Spelling Check with movie database")
    print("   3. Auto delete command messages (5 minutes)")
    print("   4. Enhanced Auto Accept setup")
    print("   5. Better Help system with pages")
    print("   6. Welcome messages with user photos")
    print("   7. #request hashtag support")
    print("   8. Enhanced settings menu")
    
    try:
        app.run()
        print("🤖 Bot stopped gracefully")
    except KeyboardInterrupt:
        print("⏹️ Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
        import traceback
        traceback.print_exc()
