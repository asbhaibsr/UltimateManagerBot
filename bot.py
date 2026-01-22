import asyncio
import logging
import time
import re
import datetime
from pyrogram import Client, filters, idle
from pyrogram.enums import ChatMemberStatus, ChatType, ChatAction
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, ChatMemberUpdated, ChatPermissions, ChatJoinRequest,
    BotCommand, BotCommandScopeAllGroupChats
)
from pyrogram.errors import FloodWait, UserNotParticipant, ChatAdminRequired, PeerIdInvalid
from config import Config
from database import *
from utils import MovieBotUtils
from pyrogram.raw import functions

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
ai_typing_cache = {}  # For AI typing indicators

# ================ HELPER FUNCTIONS ================
async def is_admin(chat_id, user_id):
    """Check if user is admin in chat"""
    if user_id == Config.OWNER_ID:
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

async def get_channel_info(channel_id):
    """Get channel title and link"""
    try:
        chat = await app.get_chat(channel_id)
        link = chat.invite_link or f"https://t.me/{chat.username}" if chat.username else None
        return chat.title, link
    except:
        return "Unknown Channel", None

async def get_admins_mentions(chat_id, exclude_user_id=None):
    """Get list of admin mentions for tagging"""
    admins = []
    try:
        async for admin in app.get_chat_members(chat_id, filter="administrators"):
            if (not admin.user.is_bot and 
                admin.user.id != exclude_user_id and
                admin.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]):
                admins.append(f"👑 <a href='tg://user?id={admin.user.id}'>{admin.user.first_name}</a>")
    except Exception as e:
        logger.error(f"Get admins error: {e}")
    return admins

async def show_typing_indicator(chat_id):
    """Show typing indicator"""
    try:
        await app.send_chat_action(chat_id, ChatAction.TYPING)
    except:
        pass

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
                f"👤 **Name:** {user.mention}\n"
                f"🆔 **ID:** `{user.id}`\n"
                f"🔗 **Username:** @{user.username if user.username else 'N/A'}\n"
                f"📅 **Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            await client.send_message(Config.LOGS_CHANNEL, log_text)
        except Exception as e:
            logger.error(f"Log Error: {e}")

    welcome_text = f"""╔══════════════════════════╗
     🎬  MOVIE HELPER BOT  🎬
╚══════════════════════════╝

👋 **Namaste {user.first_name}!** 

🤖 **Premium Features:**
✅ Smart Spelling Correction
✅ Auto Delete Files  
✅ AI Movie Recommendations
⚡ Auto Accept Join Requests
🛡️ Advanced Abuse/Link Protection
💎 Force Subscribe System

📌 **Bot Commands:**
• /help - All commands
• /settings - Group settings
• /request - Movie request
• /ai - AI chat assistant

➡️ **Add me to groups for best experience!** 🚀"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [
            InlineKeyboardButton("💎 Premium", callback_data="premium_info"),
            InlineKeyboardButton("📋 Help", callback_data="help_main")
        ],
        [InlineKeyboardButton("⚡ Features", callback_data="features_list")],
        [InlineKeyboardButton("👑 Owner", url="https://t.me/asbhai_bsr")]
    ])
    
    msg = await message.reply_text(welcome_text, reply_markup=buttons)
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ HELP COMMAND (UPDATED) ================
@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    """Handle /help command"""
    help_text = """╔══════════════════════════╗
        🆘  HELP MENU  🆘  
╚══════════════════════════╝

📌 **Group Owners/Admins:**
1. Add me to group & make Admin
2. Use `/settings` - Configure bot
3. `/addfsub` - Force Subscribe (Premium)

🎯 **Main Features:**
• ✏️ **Spelling Checker** - Auto-corrects movie names
• 🗑️ **Auto Delete** - Auto deletes files
• ✅ **Auto Accept** - Auto approves join requests
• 🤖 **AI Chat** - Movie recommendations
• 🛡️ **Security** - Link & abuse protection

👤 **User Commands:**
• /start - Start bot
• /request <movie> - Request movie
• /ai <question> - Ask AI
• /ping - Check status
• /id - Get IDs

👑 **Premium Features:**
• 🔇 No Ads/Broadcasts
• 🔗 Force Subscribe System
• ⚡ Priority Support
• 🎯 Advanced Features

📞 **Support:** @asbhai_bsr"""
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👑 Premium", callback_data="premium_info"),
            InlineKeyboardButton("⚡ Auto Accept", callback_data="auto_accept_setup")
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="help_settings"),
            InlineKeyboardButton("🎬 Examples", callback_data="help_example")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="close_help")]
    ])
    
    if message.chat.type == "private":
        msg = await message.reply_text(help_text, reply_markup=buttons)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))
    else:
        # Group mein command message auto delete
        msg = await message.reply_text(help_text, reply_markup=buttons)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 120))

# ================ SETTINGS COMMAND (UPDATED WITH AI CHAT TOGGLE) ================
@app.on_message(filters.command("settings") & filters.group)
async def settings_command(client: Client, message: Message):
    """Group settings menu"""
    if not message.from_user:
        return
    
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ **Only Group Admins/Owner can change settings!**")
        await asyncio.sleep(5)
        await msg.delete()
        return
    
    settings = await get_settings(message.chat.id)
    is_prem = await check_is_premium(message.chat.id)
    auto_accept = await get_auto_accept(message.chat.id)
    
    prem_status = "💎 Active" if is_prem else "🔓 Free"
    spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
    delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
    accept_status = "✅ ON" if auto_accept else "❌ OFF"
    welcome_status = "✅ ON" if settings.get("welcome_enabled", True) else "❌ OFF"
    ai_chat_status = "✅ ON" if settings.get("ai_chat_on", False) else "❌ OFF"
    time_text = f"{settings.get('delete_time', 0)} min" if settings.get('delete_time', 0) > 0 else "Permanent"
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✏️ Spell: {spelling_status}", callback_data="toggle_spelling"),
            InlineKeyboardButton(f"🗑️ Delete: {delete_status}", callback_data="toggle_auto_delete")
        ],
        [
            InlineKeyboardButton(f"🤖 AI Chat: {ai_chat_status}", callback_data="toggle_ai_chat"),
            InlineKeyboardButton(f"👋 Welcome: {welcome_status}", callback_data="toggle_welcome")
        ],
        [
            InlineKeyboardButton(f"✅ Auto Accept: {accept_status}", callback_data="toggle_auto_accept"),
            InlineKeyboardButton(f"⏰ Time: {time_text}", callback_data="set_delete_time")
        ],
        [
            InlineKeyboardButton(f"{prem_status} Premium", callback_data="premium_info"),
            InlineKeyboardButton("❌ Close", callback_data="close_settings")
        ]
    ])
    
    msg = await message.reply_text(
        f"╔══════════════════════════╗\n"
        f"      ⚙️  SETTINGS  ⚙️      \n"
        f"╚══════════════════════════╝\n\n"
        f"**Group:** {message.chat.title}\n"
        f"**Click buttons to toggle:**",
        reply_markup=buttons
    )
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ REQUEST HANDLER (FIXED - ADMIN TAGGING WITH EMOJI) ================
@app.on_message(filters.command("request") & filters.group)
async def request_handler(client: Client, message: Message):
    if not message.from_user:
        return
        
    if len(message.command) < 2:
        msg = await message.reply_text(
            "❌ **Please specify movie name!**\n"
            "**Example:** `/request Pushpa 2`\n"
            "**Or:** `#request Pushpa 2`"
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return
    
    movie_name = " ".join(message.command[1:])
    user = message.from_user
    chat = message.chat
    
    # Get admins for tagging (EXCLUDE THE USER WHO SENT REQUEST)
    admins = await get_admins_mentions(chat.id, exclude_user_id=user.id)
    
    # Format admin tags with emoji
    if admins:
        admin_tags = " ".join(admins[:3])  # Max 3 admins tag
    else:
        admin_tags = "👑 **Group Admins**"
    
    # Create request message with owner/admin tagging inside emoji
    text = (
        f"╔══════════════════════════╗\n"
        f"     🎬  MOVIE REQUEST  🎬    \n"
        f"╚══════════════════════════╝\n\n"
        f"👤 **User:** {user.mention}\n"
        f"🎬 **Movie:** `{movie_name}`\n"
        f"📅 **Time:** {datetime.datetime.now().strftime('%H:%M:%S')}\n\n"
        f"🔔 **Attention:** {admin_tags}\n"
        f"Please check this movie request! 📥"
    )
    
    # Buttons sirf admin/owner ke liye
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Available", callback_data=f"req_accept_{user.id}_{message.id}"),
            InlineKeyboardButton("❌ Not Available", callback_data=f"req_reject_{user.id}_{message.id}")
        ],
        [
            InlineKeyboardButton("📊 Request Stats", callback_data="request_stats"),
            InlineKeyboardButton("🔍 Search Movie", url=f"https://www.imdb.com/find?q={movie_name.replace(' ', '+')}")
        ]
    ])
    
    msg = await message.reply_text(text, reply_markup=buttons)
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# Also handle #request hashtag (FIXED VERSION)
@app.on_message(filters.group & filters.regex(r'^#request\s+', re.IGNORECASE))
async def hashtag_request_handler(client: Client, message: Message):
    if not message.from_user:
        return
        
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
    
    # Get admins for tagging (EXCLUDE THE USER WHO SENT REQUEST)
    admins = await get_admins_mentions(chat.id, exclude_user_id=user.id)
    
    # Format admin tags with emoji
    if admins:
        admin_tags = " ".join(admins[:3])  # Max 3 admins tag
    else:
        admin_tags = "👑 **Group Admins**"
    
    # Create request message
    text = (
        f"╔══════════════════════════╗\n"
        f"     🎬  MOVIE REQUEST  🎬    \n"
        f"╚══════════════════════════╝\n\n"
        f"👤 **User:** {user.mention}\n"
        f"🎬 **Movie:** `{movie_name}`\n"
        f"📅 **Time:** {datetime.datetime.now().strftime('%H:%M:%S')}\n\n"
        f"🔔 **Attention:** {admin_tags}\n"
        f"Please check this movie request! 📥"
    )
    
    # Buttons sirf admin/owner ke liye
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Available", callback_data=f"req_accept_{user.id}_{message.id}"),
            InlineKeyboardButton("❌ Not Available", callback_data=f"req_reject_{user.id}_{message.id}")
        ],
        [
            InlineKeyboardButton("📊 Request Stats", callback_data="request_stats"),
            InlineKeyboardButton("🔍 Search Movie", url=f"https://www.imdb.com/find?q={movie_name.replace(' ', '+')}")
        ]
    ])
    
    msg = await client.send_message(chat.id, text, reply_markup=buttons)
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ STATS COMMAND ================
@app.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats_command(client: Client, message: Message):
    """Bot statistics"""
    stats = await get_bot_stats()
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Clear Junk", callback_data="clear_junk")],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats"),
            InlineKeyboardButton("📊 Details", callback_data="detailed_stats")
        ]
    ])
    
    stats_text = f"""╔══════════════════════════╗
     📊  BOT STATISTICS  📊  
╚══════════════════════════╝

👥 **Users:** `{stats['total_users']}`
📁 **Groups:** `{stats['total_groups']}`
🚫 **Banned:** `{stats['banned_users']}`
💎 **Premium:** `{stats['premium_groups']}`
✅ **Active:** `{stats['active_groups']}`

📨 **Requests:**
├─ Pending: `{stats['pending_requests']}`
└─ Total: `{stats['total_requests']}`

⚡ **Status:** ✅ Running
☁️ **Server:** Koyeb Cloud
🕐 **Updated:** {datetime.datetime.now().strftime('%H:%M:%S')}"""
    
    await message.reply_text(stats_text, reply_markup=buttons)

# ================ AI COMMAND (WITH TYPING INDICATOR) ================
@app.on_message(filters.command("ai"))
async def ai_command(client: Client, message: Message):
    """AI chat feature with typing indicator"""
    if len(message.command) < 2:
        msg = await message.reply_text(
            "**Usage:** `/ai your question`\n"
            "**Examples:**\n"
            "• `/ai Tell me about Inception`\n"
            "• `/ai Best movies of 2023`\n"
            "• `/ai Comedy movies list`"
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return
    
    query = ' '.join(message.command[1:])
    
    # Show typing indicator
    await show_typing_indicator(message.chat.id)
    waiting_msg = await message.reply_text("💭 **Thinking... Please wait...**")
    
    response = await MovieBotUtils.get_ai_response(query)
    
    await waiting_msg.delete()
    msg = await message.reply_text(response)
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ BROADCAST COMMAND ================
@app.on_message(filters.command(["broadcast", "grp_broadcast"]) & filters.user(Config.OWNER_ID))
async def broadcast_command(client: Client, message: Message):
    if not message.reply_to_message:
        msg = await message.reply_text("❌ **Reply to a message to broadcast!**")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return
    
    is_group = "grp_broadcast" in message.text
    target_ids = await get_all_groups() if is_group else await get_all_users()
    
    # Premium Filter for Groups (Don't broadcast to Premium)
    if is_group:
        target_ids = [g for g in target_ids if not await check_is_premium(g)]

    progress = await message.reply_text(f"📤 **Broadcasting to {len(target_ids)} chats...**")
    success, failed, deleted = 0, 0, 0
    
    for chat_id in target_ids:
        try:
            await message.reply_to_message.copy(chat_id)
            success += 1
        except PeerIdInvalid:
            # Invalid chat ID, remove from database
            if is_group:
                await remove_group(chat_id)
            deleted += 1
        except Exception as e:
            logger.error(f"Broadcast Error to {chat_id}: {e}")
            failed += 1
        await asyncio.sleep(0.5)
        
    msg = await progress.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"🎯 **Total:** {len(target_ids)}\n"
        f"✅ **Success:** {success}\n"
        f"❌ **Failed:** {failed}\n"
        f"🗑️ **Cleaned:** {deleted}"
    )
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ ADDFSUB COMMAND ================
@app.on_message(filters.command("addfsub") & filters.group)
async def addfsub_command(client: Client, message: Message):
    """Set force subscribe channel"""
    if not message.from_user:
        return
        
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ **Only Admins can use this command!**")
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
            "╔══════════════════════════╗\n"
            "      💎  PREMIUM  💎      \n"
            "╚══════════════════════════╝\n\n"
            "**Force Subscribe is a Premium Feature!**\n\n"
            "✨ **Premium Benefits:**\n"
            "✅ No Ads/Broadcasts\n"
            "✅ Force Subscribe System\n"
            "✅ Priority Support\n"
            "✅ Advanced Features\n\n"
            "Contact @asbhai_bsr for premium.",
            reply_markup=buttons
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return

    channel_id = None
    
    if len(message.command) > 1:
        try:
            channel_id = int(message.command[1])
        except ValueError:
            msg = await message.reply_text("❌ **Invalid ID!** Use numeric ID (e.g. -100xxxxxxx)")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            return

    elif message.reply_to_message:
        if message.reply_to_message.forward_from_chat:
            channel_id = message.reply_to_message.forward_from_chat.id
        else:
            msg = await message.reply_text(
                "❌ **Channel ID not found.** Forward privacy is on.\n"
                "**Try:** `/addfsub -100xxxxxxx`"
            )
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
             msg = await message.reply_text("❌ **I'm not Admin in that channel!** Add me as Admin first.")
             asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
             return
    except Exception as e:
        msg = await message.reply_text(f"❌ **Error:** Add me to channel and make Admin!\n`{e}`")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return

    await set_force_sub(message.chat.id, channel_id)
    msg = await message.reply_text(
        f"✅ **Force Subscribe Connected!**\n\n"
        f"**Channel:** {chat.title}\n"
        f"**ID:** `{channel_id}`\n\n"
        f"New users must join channel to chat in group."
    )
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))

# ================ PREMIUM ADMIN COMMANDS ================
@app.on_message(filters.command("add_premium") & filters.user(Config.OWNER_ID))
async def add_premium_cmd(client: Client, message: Message):
    try:
        if len(message.command) < 3:
             msg = await message.reply_text("❌ **Usage:** `/add_premium <group_id> <months>`")
             asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
             return

        group_id = int(message.command[1])
        raw_months = message.command[2].lower()
        clean_months = ''.join(filter(str.isdigit, raw_months))
        
        if not clean_months:
             msg = await message.reply_text("❌ **Invalid month format.** Use numbers only.")
             asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
             return
             
        months = int(clean_months)
        expiry = await add_premium(group_id, months)
        
        msg = await message.reply_text(
            f"✅ **Premium Added Successfully!**\n\n"
            f"**Group:** `{group_id}`\n"
            f"**Months:** {months}\n"
            f"**Expires:** {expiry.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        try:
            await client.send_message(
                group_id,
                f"╔══════════════════════════╗\n"
                f"      💎  PREMIUM  💎      \n"
                f"╚══════════════════════════╝\n\n"
                f"✅ **Premium Activated!**\n\n"
                f"✨ **Benefits:**\n"
                f"• No Ads/Broadcasts\n"
                f"• Force Subscribe Enabled\n"
                f"• Priority Support\n"
                f"• Advanced Features\n\n"
                f"Thank you for your support! ❤️"
            )
        except:
            await message.reply_text("⚠️ **Database updated but message not sent to group.**")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            
    except Exception as e:
        msg = await message.reply_text(f"❌ **Error:** {e}")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))

@app.on_message(filters.command("remove_premium") & filters.user(Config.OWNER_ID))
async def remove_premium_cmd(client: Client, message: Message):
    try:
        if len(message.command) < 2:
            msg = await message.reply_text("❌ **Usage:** `/remove_premium <group_id>`")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            return
            
        group_id = int(message.command[1])
        await remove_premium(group_id)
        msg = await message.reply_text(f"❌ **Premium removed for** `{group_id}`")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
    except Exception as e:
        msg = await message.reply_text(f"❌ **Error:** {e}")
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
    
    premium_text = f"╔══════════════════════════╗\n"
    premium_text += f"     💎  PREMIUM STATS  💎    \n"
    premium_text += f"╚══════════════════════════╝\n\n"
    premium_text += f"**Total Premium Groups:** {count}\n\n"
    
    if premium_list:
        premium_text += "\n".join(premium_list[:10])
        if len(premium_list) > 10:
            premium_text += f"\n\n...and {len(premium_list) - 10} more"
    
    await message.reply_text(premium_text)

# ================ UPDATED MAIN MESSAGE HANDLER ================
@app.on_message(filters.group & filters.text & ~filters.command([
    "start", "help", "settings", "addfsub", "stats", "ai", 
    "broadcast", "request", "ban", "unban", "add_premium", 
    "remove_premium", "premiumstats", "ping", "id", "clean",
    "cleangroup", "pinmovie", "feature", "movieoftheday",
    "motd", "poll", "moviepoll", "purge", "clearchat",
    "groupstats", "ginfo"
]))
async def group_message_filter(client, message):
    if not message.from_user:
        return
        
    if await is_admin(message.chat.id, message.from_user.id):
        return

    settings = await get_settings(message.chat.id)
    
    # 1. Check if AI chat is enabled and respond to direct messages
    if settings.get("ai_chat_on", False) and not message.reply_to_message:
        # Check if message is a direct question to bot
        if message.text.lower().startswith(('bot', 'hey bot', 'hi bot', 'hello bot', '@bot')) or '?' in message.text:
            # Show typing indicator
            await show_typing_indicator(message.chat.id)
            
            # Send typing message
            typing_msg = await message.reply_text("💭 **Typing...**")
            
            # Get AI response
            ai_response = await MovieBotUtils.get_ai_response(message.text)
            
            # Delete typing message and send response
            await typing_msg.delete()
            response_msg = await message.reply_text(ai_response)
            
            # Auto delete after 3 minutes
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, response_msg, 180))
            return

    # Check message quality
    quality = MovieBotUtils.check_message_quality(message.text)

    # 2. LINK HANDLING
    if quality == "LINK":
        try:
            await message.delete()
        except:
            pass
        warn_count = await add_warning(message.chat.id, message.from_user.id)
        limit = Config.MAX_WARNINGS
        
        if warn_count >= limit:
            try:
                await client.restrict_chat_member(
                    message.chat.id, 
                    message.from_user.id, 
                    ChatPermissions(can_send_messages=False),
                    until_date=datetime.datetime.now() + datetime.timedelta(hours=24)
                )
                warn_msg = await message.reply_text(
                    f"🚫 **{message.from_user.mention} has been muted for 24 hours!**\n"
                    f"Reason: Links not allowed in this group."
                )
                await reset_warnings(message.chat.id, message.from_user.id)
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, warn_msg, 10))
            except:
                pass
        else:
            warn_msg = await message.reply_text(
                f"⚠️ **Warning {warn_count}/{limit}**\n"
                f"User: {message.from_user.mention}\n"
                f"Reason: Links are not allowed!\n\n"
                f"Next violation: 24 hour mute"
            )
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, warn_msg, 10))

    # 3. ABUSE HANDLING
    elif quality == "ABUSE":
        try:
            await message.delete()
        except:
            pass
        warn_count = await add_warning(message.chat.id, message.from_user.id)
        limit = Config.MAX_WARNINGS
        
        if warn_count >= limit:
            try:
                await client.ban_chat_member(message.chat.id, message.from_user.id)
                ban_msg = await message.reply_text(
                    f"🚫 **{message.from_user.mention} has been banned!**\n"
                    f"Reason: Abusive language not tolerated."
                )
                await reset_warnings(message.chat.id, message.from_user.id)
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, ban_msg, 10))
            except:
                pass
        else:
            warn_msg = await message.reply_text(
                f"⚠️ **Warning {warn_count}/{limit}**\n"
                f"User: {message.from_user.mention}\n"
                f"Reason: Abusive language detected!\n\n"
                f"Next violation: Permanent ban"
            )
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, warn_msg, 10))

    # 4. FORMAT CORRECTION (MAIN FEATURE - UPDATED)
    elif settings.get("spelling_on", True) and quality == "JUNK":
        try:
            await message.delete()
        except:
            pass
        
        # Validate format using new function
        validation = MovieBotUtils.validate_movie_format(message.text)
        
        if not validation['is_valid']:
            # Invalid format - send correction message
            group_username = message.chat.username or ""
            
            message_text, buttons = MovieBotUtils.create_format_message(
                user_name=message.from_user.mention,
                original_text=message.text,
                validation_result=validation,
                group_username=group_username
            )
            
            # Add header to message
            formatted_message = (
                f"╔══════════════════════════╗\n"
                f"     ✨  FORMAT GUIDE  ✨     \n"
                f"╚══════════════════════════╝\n\n"
                f"{message_text}"
            )
            
            correction_msg = await message.reply_text(
                formatted_message,
                reply_markup=buttons,
                disable_web_page_preview=True
            )
            
            # Delete after 3 minutes
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, correction_msg, 180))
            
        else:
            # Valid format detected - send confirmation
            confirm_msg = await message.reply_text(
                f"✅ **Perfect Format!**\n\n"
                f"👤 **User:** {message.from_user.mention}\n"
                f"🎬 **Search:** {validation['correct_format']}\n\n"
                f"🔄 **Processing your request...**"
            )
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, confirm_msg, 60))

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
            f"Files auto-delete after **{delete_time} minutes**."
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

# ================ FORCE SUBSCRIBE (FIXED NO LOOP) ================
@app.on_chat_member_updated()
async def handle_fsub_join(client, update: ChatMemberUpdated):
    # 1. Stop Loop: Ignore updates caused by the Bot itself
    if update.from_user and update.from_user.id == (await client.get_me()).id:
        return

    # 2. Stop Loop: Ignore if it's not a new join (e.g., just a permission change)
    if update.old_chat_member and update.old_chat_member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
        return

    if not update.new_chat_member or update.new_chat_member.user.is_bot:
        return

    # Double Message Fix (Debounce)
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
            
            # Send welcome message
            welcome_text = (
                f"╔══════════════════════════╗\n"
                f"     🎉  WELCOME  🎉       \n"
                f"╚══════════════════════════╝\n\n"
                f"👤 **User:** {user.mention}\n"
                f"✅ **Verification Complete!**\n\n"
                f"✨ You can now chat in the group.\n"
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
        pass # Proceed to mute logic below
    except Exception as e:
        logger.error(f"FSub Check Error: {e}")
        return

    # If user hasn't joined:
    try:
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
            [InlineKeyboardButton("✅ I've Joined", callback_data=f"fsub_verify_{user_id}")]
        ])
        
        # Welcome message with strong wording
        welcome_txt = (
            f"╔══════════════════════════╗\n"
            f"     🔒  GROUP LOCKED  🔒   \n"
            f"╚══════════════════════════╝\n\n"
            f"👋 **Hello {user.mention}!**\n\n"
            f"⚠️ **To unlock chatting:**\n"
            f"1. **Join:** {channel_name}\n"
            f"2. **Click 'I've Joined' button**\n\n"
            f"❌ **Without joining, you cannot send messages!**\n"
            f"✅ **After joining, you'll be auto-unmuted.**"
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
            
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, fsub_msg, 300))
        except FloodWait as e:
            # If flood wait happens, wait and retry text only
            await asyncio.sleep(e.value)
            fsub_msg = await client.send_message(chat_id, welcome_txt, reply_markup=buttons)
        except Exception as e:
            logger.error(f"FSub Send Error: {e}")

    except Exception as e:
        logger.error(f"FSub Action Error: {e}")

# ================ WELCOME MESSAGE FOR NEW MEMBERS (FIXED) ================
@app.on_message(filters.new_chat_members)
async def welcome_new_members(client: Client, message: Message):
    """Welcome new members with photo and details"""
    try:
        # Delete the automatic "user joined" message immediately
        try:
            await message.delete()
        except:
            pass
        
        settings = await get_settings(message.chat.id)
        if not settings.get("welcome_enabled", True):
            return
        
        for member in message.new_chat_members:
            if member.is_self:  # Bot added to group
                # Bot added to group
                await add_group(message.chat.id, message.chat.title, message.chat.username)
                
                # Send Welcome
                bot_welcome = await message.reply_text(
                    f"╔══════════════════════════╗\n"
                    f"     🤖  BOT ADDED  🤖     \n"
                    f"╚══════════════════════════╝\n\n"
                    f"🎬 **Thanks for adding me to {message.chat.title}!**\n\n"
                    f"✨ **My Features:**\n"
                    f"✅ Spelling Correction\n"
                    f"✅ Auto Delete Files\n"
                    f"✅ AI Movie Chat\n"
                    f"✅ Auto Accept Requests\n\n"
                    f"⚙️ **Setup Instructions:**\n"
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
                    f"╔══════════════════════════╗\n"
                    f"     🎉  WELCOME  🎉       \n"
                    f"╚══════════════════════════╝\n\n"
                    f"👤 **User:** {user.mention}\n"
                    f"🆔 **ID:** `{user.id}`\n"
                    f"📅 **Joined:** {datetime.datetime.now().strftime('%d %B %Y %H:%M:%S')}\n\n"
                    f"🎬 **Welcome to our movie community!**\n"
                    f"Request movies using `/request` command.\n\n"
                    f"✨ **Enjoy your stay!** 😊"
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
                    
    except Exception as e:
        logger.error(f"Welcome Error: {e}")

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
                f"╔══════════════════════════╗\n"
                f"     ✅  APPROVED  ✅       \n"
                f"╚══════════════════════════╝\n\n"
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

# ================ CALLBACK QUERY HANDLERS (UPDATED) ================
@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    """Handle all callback queries"""
    try:
        data = query.data
        chat_id = query.message.chat.id if query.message else query.from_user.id
        user_id = query.from_user.id
        
        # Auto delete callback messages after 5 minutes
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, query.message, 300))
        
        # HELP SYSTEM WITH PAGES
        if data == "help_main":
            help_text = """╔══════════════════════════╗
        🤖  BOT FEATURES  🤖  
╚══════════════════════════╝

📌 **Main Functions:**
✅ ✏️ Spelling Checker
✅ 🗑️ Auto Delete Files  
✅ ✅ Auto Accept Requests
✅ 🤖 AI Movie Recommendations
✅ 🛡️ Advanced Security

📋 **Commands Available:**
• /start - Start bot
• /help - This menu  
• /settings - Group settings
• /request - Request movies
• /ai - Ask AI questions
• /ping - Check status
• /id - Get IDs

✨ **Premium Features:**
• 🔇 No Ads/Broadcasts
• 🔗 Force Subscribe System
• ⚡ Priority Support
• 🎯 Advanced Tools"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Premium Features", callback_data="help_premium")],
                [InlineKeyboardButton("⚙️ Admin Commands", callback_data="help_admin")],
                [InlineKeyboardButton("📖 User Guide", callback_data="help_guide")],
                [InlineKeyboardButton("❌ Close", callback_data="close_help")]
            ])
            
            await query.message.edit_text(help_text, reply_markup=buttons)
            await query.answer()
        
        elif data == "help_premium":
            premium_text = """╔══════════════════════════╗
     👑  PREMIUM FEATURES  👑  
╚══════════════════════════╝

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
Contact @asbhai_bsr for premium purchase.

🎁 **Free Trial:** 3 days trial available!"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="help_main")],
                [InlineKeyboardButton("💎 Buy Now", url="https://t.me/asbhai_bsr")],
                [InlineKeyboardButton("❌ Close", callback_data="close_help")]
            ])
            
            await query.message.edit_text(premium_text, reply_markup=buttons)
            await query.answer()
        
        elif data == "help_admin":
            admin_text = """╔══════════════════════════╗
     ⚙️  ADMIN COMMANDS  ⚙️  
╚══════════════════════════╝

**Group Admins Can Use:**
• `/settings` - Configure bot
• `/addfsub <channel_id>` - Force Subscribe (Premium)
• `/stats` - View statistics

**Bot Owner Commands:**
• `/add_premium <group_id> <months>` - Add premium
• `/remove_premium <group_id>` - Remove premium  
• `/broadcast` - Send to all users
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
            guide_text = """╔══════════════════════════╗
     📖  USER GUIDE  📖  
╚══════════════════════════╝

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

**📞 Support:** @asbhai_bsr"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="help_main")],
                [InlineKeyboardButton("🎬 Request Example", callback_data="help_example")],
                [InlineKeyboardButton("❌ Close", callback_data="close_help")]
            ])
            
            await query.message.edit_text(guide_text, reply_markup=buttons)
            await query.answer()
        
        elif data == "help_example":
            example_text = """╔══════════════════════════╗
     🎬  EXAMPLES  🎬  
╚══════════════════════════╝

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
            settings_text = """╔══════════════════════════╗
     ⚙️  SETTINGS GUIDE  ⚙️  
╚══════════════════════════╝

**Available Settings:**
1. ✏️ **Spelling Check** - ON/OFF
2. 🗑️ **Auto Delete** - ON/OFF  
3. ✅ **Auto Accept** - ON/OFF
4. 👋 **Welcome Message** - ON/OFF
5. 🤖 **AI Chat** - ON/OFF
6. ⏰ **Delete Time** - Set timer

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
            text = """╔══════════════════════════╗
     💎  PREMIUM PLANS  💎  
╚══════════════════════════╝

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
            text = """╔══════════════════════════╗
     ⚡  AUTO ACCEPT SETUP  ⚡  
╚══════════════════════════╝

**I can Approve Join Requests Automatically!**

**How to Setup:**
1. Add me as **Admin** in group/channel
2. Enable **Auto Accept** in settings
3. That's it! I'll auto-approve all requests

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
            text = """╔══════════════════════════╗
     👥  GROUP AUTO ACCEPT  👥  
╚══════════════════════════╝

**Setup Steps:**
1. Add me to your **Group**
2. Make me **Admin** with join request permission
3. Use `/settings` in group
4. Enable **Auto Accept** option
5. Done! I'll auto-approve all requests

**Requirements:**
• Bot must be admin
• Join requests must be enabled
• Auto accept must be ON in settings

**Note:** Works for private groups with join requests."""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
                [InlineKeyboardButton("⚙️ Group Settings", switch_inline_query_current_chat="/settings")],
                [InlineKeyboardButton("🔙 Back", callback_data="auto_accept_setup")]
            ])
            
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
        
        elif data == "auto_channel":
            text = """╔══════════════════════════╗
     📢  CHANNEL AUTO ACCEPT  📢  
╚══════════════════════════╝

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
        
        # Request Accept Logic (ADMIN ONLY)
        elif data.startswith("req_accept_"):
            parts = data.split("_")
            if len(parts) >= 4:
                req_user_id = int(parts[2])
                original_msg_id = int(parts[3])
                
                # Check if user is admin
                if not await is_admin(query.message.chat.id, query.from_user.id):
                    await query.answer("❌ Only admins can use this button!", show_alert=True)
                    return
                
                try:
                    await client.send_message(
                        query.message.chat.id, 
                        f"✅ **Movie Available!**\n"
                        f"{query.from_user.mention} has uploaded it.\n\n"
                        f"👤 <a href='tg://user?id={req_user_id}'>User</a>, please check!"
                    )
                    await query.message.delete()
                except:
                    pass
                await query.answer("✅ Request accepted!")
        
        # Request Reject Logic (ADMIN ONLY)
        elif data.startswith("req_reject_"):
            parts = data.split("_")
            if len(parts) >= 4:
                req_user_id = int(parts[2])
                original_msg_id = int(parts[3])
                
                # Check if user is admin
                if not await is_admin(query.message.chat.id, query.from_user.id):
                    await query.answer("❌ Only admins can use this button!", show_alert=True)
                    return
                
                try:
                    await client.send_message(
                        query.message.chat.id, 
                        f"❌ **Movie Not Available**\n\n"
                        f"Request rejected by Admin {query.from_user.mention}."
                    )
                    await query.message.delete()
                except:
                    pass
                await query.answer("❌ Request rejected!")
        
        # Request Status Check
        elif data.startswith("req_status_"):
            req_user_id = int(data.split("_")[2])
            if query.from_user.id != req_user_id:
                await query.answer("❌ This button is for the requester only!", show_alert=True)
                return
            await query.answer("✅ Your request is pending review by admins.", show_alert=True)
        
        # Settings Toggles
        elif data == "toggle_spelling":
            # Check admin
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            settings = await get_settings(chat_id)
            new_value = not settings.get("spelling_on", True)
            await update_settings(chat_id, "spelling_on", new_value)
            status = "ON ✅" if new_value else "OFF ❌"
            await query.answer(f"✏️ Spelling: {status}")
            await refresh_settings_menu(client, query)
        
        elif data == "toggle_auto_delete":
            # Check admin
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            settings = await get_settings(chat_id)
            new_value = not settings.get("auto_delete_on", False)
            await update_settings(chat_id, "auto_delete_on", new_value)
            status = "ON ✅" if new_value else "OFF ❌"
            await query.answer(f"🗑️ Auto Delete: {status}")
            await refresh_settings_menu(client, query)

        elif data == "toggle_auto_accept":
            # Check admin
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            current = await get_auto_accept(chat_id)
            await set_auto_accept(chat_id, not current)
            status = "ON ✅" if not current else "OFF ❌"
            await query.answer(f"✅ Auto Accept: {status}")
            await refresh_settings_menu(client, query)
        
        elif data == "toggle_welcome":
            # Check admin
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            settings = await get_settings(chat_id)
            new_value = not settings.get("welcome_enabled", True)
            await update_settings(chat_id, "welcome_enabled", new_value)
            status = "ON ✅" if new_value else "OFF ❌"
            await query.answer(f"👋 Welcome: {status}")
            await refresh_settings_menu(client, query)
        
        elif data == "toggle_ai_chat":
            # Check admin
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            settings = await get_settings(chat_id)
            new_value = not settings.get("ai_chat_on", False)
            await update_settings(chat_id, "ai_chat_on", new_value)
            status = "ON ✅" if new_value else "OFF ❌"
            await query.answer(f"🤖 AI Chat: {status}")
            await refresh_settings_menu(client, query)
        
        elif data == "set_delete_time":
            # Check admin
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
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
            # Check admin
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            minutes = int(data.split("_")[1])
            await update_settings(chat_id, "delete_time", minutes)
            time_text = f"{minutes} minutes" if minutes > 0 else "Permanent"
            await query.answer(f"✅ Delete time set to {time_text}")
            await refresh_settings_menu(client, query)

        elif data == "clear_junk":
            # Owner only
            if user_id != Config.OWNER_ID:
                await query.answer("❌ Only owner can use this!", show_alert=True)
                return
                
            junk_count = await clear_junk()
            total_cleaned = sum(junk_count.values())
            await query.answer(f"🧹 Cleared {total_cleaned} items!")
            await query.message.edit_text(
                f"✅ **Junk Cleared Successfully!**\n\n"
                f"🗑️ **Cleaned Items:**\n"
                f"• Banned Users: {junk_count.get('banned_users', 0)}\n"
                f"• Inactive Groups: {junk_count.get('inactive_groups', 0)}\n\n"
                f"🔄 **Total:** {total_cleaned} items removed",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh Stats", callback_data="refresh_stats")]
                ])
            )
        
        elif data == "refresh_stats":
            stats = await get_bot_stats()
            
            stats_text = f"""╔══════════════════════════╗
     📊  BOT STATISTICS  📊  
╚══════════════════════════╝

👥 **Users:** `{stats['total_users']}`
📁 **Groups:** `{stats['total_groups']}`
🚫 **Banned:** `{stats['banned_users']}`
💎 **Premium:** `{stats['premium_groups']}`
✅ **Active:** `{stats['active_groups']}`

📨 **Requests:**
├─ Pending: `{stats['pending_requests']}`
└─ Total: `{stats['total_requests']}`

⚡ **Status:** ✅ Running
🕐 **Updated:** {datetime.datetime.now().strftime('%H:%M:%S')}"""
            
            await query.message.edit_text(
                stats_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🧹 Clear Junk", callback_data="clear_junk")],
                    [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]
                ])
            )
            await query.answer("✅ Stats refreshed!")
        
        elif data == "detailed_stats":
            stats = await get_bot_stats()
            detailed_text = f"""📊 **Detailed Statistics**

👥 **User Statistics:**
├─ Total Users: {stats['total_users']}
├─ Banned Users: {stats['banned_users']}
└─ Active Users: {stats['total_users'] - stats['banned_users']}

📁 **Group Statistics:**
├─ Total Groups: {stats['total_groups']}
├─ Premium Groups: {stats['premium_groups']}
├─ Active Groups: {stats['active_groups']}
└─ Inactive Groups: {stats['total_groups'] - stats['active_groups']}

📨 **Request Statistics:**
├─ Total Requests: {stats['total_requests']}
├─ Pending Requests: {stats['pending_requests']}
└─ Completed: {stats['total_requests'] - stats['pending_requests']}

🔄 **Last Cleanup:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            
            await query.message.reply_text(detailed_text)
            await query.answer("📊 Detailed stats shown!")
        
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
            await query.answer("⚙️ Settings closed!")
        
        elif data == "close_help":
            await query.message.delete()
            await query.answer("🆘 Help closed!")
        
        elif data == "back_settings" or data == "settings_menu":
            await refresh_settings_menu(client, query)
        
        elif data == "features_list":
            features_text = """╔══════════════════════════╗
     ✨  BOT FEATURES  ✨  
╚══════════════════════════╝

🎬 **Movie Features:**
✅ Smart Format Correction
✅ Movie Request System
✅ AI Movie Recommendations
✅ Auto Spelling Check

🛡️ **Security Features:**
✅ Link Protection
✅ Abuse Filter
✅ Warning System
✅ Auto Mute/Ban

⚙️ **Group Management:**
✅ Auto Accept Requests
✅ Force Subscribe System
✅ Welcome Messages
✅ File Auto Delete

🤖 **AI Features:**
✅ Chat Assistant
✅ Movie Information
✅ Recommendations
✅ Quick Responses

💎 **Premium Features:**
✅ No Ads
✅ Priority Support
✅ Advanced Tools
✅ Force Subscribe"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Premium Info", callback_data="premium_info")],
                [InlineKeyboardButton("📋 Commands", callback_data="help_main")],
                [InlineKeyboardButton("❌ Close", callback_data="close_help")]
            ])
            
            await query.message.edit_text(features_text, reply_markup=buttons)
            await query.answer()
    
    except Exception as e:
        logger.error(f"Callback Error: {e}")
        await query.answer("❌ Error processing request!")

# Helper for updating settings menu
async def refresh_settings_menu(client, query):
    try:
        chat_id = query.message.chat.id
        settings = await get_settings(chat_id)
        is_prem = await check_is_premium(chat_id)
        auto_accept = await get_auto_accept(chat_id)
        
        prem_status = "💎 Active" if is_prem else "🔓 Free"
        spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
        delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
        accept_status = "✅ ON" if auto_accept else "❌ OFF"
        welcome_status = "✅ ON" if settings.get("welcome_enabled", True) else "❌ OFF"
        ai_chat_status = "✅ ON" if settings.get("ai_chat_on", False) else "❌ OFF"
        delete_time = settings.get("delete_time", 0)
        time_text = f"{delete_time} min" if delete_time > 0 else "Permanent"
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"✏️ Spell: {spelling_status}", callback_data="toggle_spelling"),
                InlineKeyboardButton(f"🗑️ Delete: {delete_status}", callback_data="toggle_auto_delete")
            ],
            [
                InlineKeyboardButton(f"🤖 AI Chat: {ai_chat_status}", callback_data="toggle_ai_chat"),
                InlineKeyboardButton(f"👋 Welcome: {welcome_status}", callback_data="toggle_welcome")
            ],
            [
                InlineKeyboardButton(f"✅ Auto Accept: {accept_status}", callback_data="toggle_auto_accept"),
                InlineKeyboardButton(f"⏰ Time: {time_text}", callback_data="set_delete_time")
            ],
            [
                InlineKeyboardButton(f"{prem_status} Premium", callback_data="premium_info"),
                InlineKeyboardButton("❌ Close", callback_data="close_settings")
            ]
        ])
        
        # Check if message needs to be edited
        await query.message.edit_text(
            f"╔══════════════════════════╗\n"
            f"      ⚙️  SETTINGS  ⚙️      \n"
            f"╚══════════════════════════╝\n\n"
            f"**Group:** {query.message.chat.title}\n"
            f"**Click buttons to toggle:**",
            reply_markup=buttons
        )
    except Exception as e:
        logger.error(f"Refresh Settings Error: {e}")

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
                    f"Please add me as admin first with 'Add Users' permission."
                )
                return
        except:
            await message.reply_text(
                f"❌ **I'm not in {chat.title}!**\n"
                f"Please add me to the channel first as admin."
            )
            return
        
        # Enable auto accept for this channel
        await set_auto_accept(channel_id, True)
        
        await message.reply_text(
            f"✅ **Auto Accept Enabled for {chat.title}!**\n\n"
            f"**Channel:** {chat.title}\n"
            f"**ID:** `{channel_id}`\n\n"
            f"Now I will automatically approve all join requests.\n\n"
            f"**Note:** Make sure join requests are enabled in settings."
        )
        
    except Exception as e:
        await message.reply_text(
            f"❌ **Error setting up auto accept!**\n\n"
            f"**Error:** {e}\n\n"
            f"Please make sure:\n"
            f"1. Channel ID is correct\n"
            f"2. You are admin in channel\n"
            f"3. Bot is added as admin"
        )

# ================ SETCOMMANDS COMMAND (FIXED) ================
@app.on_message(filters.command("setcommands") & filters.user(Config.OWNER_ID))
async def setcommands_command(client: Client, message: Message):
    """Set bot commands - FIXED"""
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Get help menu"),
        BotCommand("settings", "Group settings"),
        BotCommand("request", "Request a movie"),
        BotCommand("ai", "Ask AI about movies"),
        BotCommand("addfsub", "Set force subscribe (Premium)"),
        BotCommand("ping", "Check bot status"),
        BotCommand("id", "Get user/group ID"),
        BotCommand("clean", "Clean group (Admin only)"),
        BotCommand("groupstats", "Group statistics"),
        BotCommand("movieoftheday", "Featured movie")
    ]
    
    try:
        await client.set_bot_commands(commands)
        await message.reply_text("✅ **Bot commands set successfully!**")
        
        # Also set for groups
        group_commands = [
            BotCommand("request", "Request movie"),
            BotCommand("help", "Help menu"),
            BotCommand("settings", "Group settings"),
            BotCommand("ai", "Ask AI"),
            BotCommand("movieoftheday", "Featured movie"),
            BotCommand("id", "Get ID")
        ]
        
        await client.set_bot_commands(group_commands, scope=BotCommandScopeAllGroupChats())
        await message.reply_text("✅ **Group commands also set!**")
        
    except Exception as e:
        await message.reply_text(f"❌ **Failed to set commands:** {str(e)}")

# ================ PING COMMAND ================
@app.on_message(filters.command("ping"))
async def ping_command(client: Client, message: Message):
    """Check if bot is alive"""
    start_time = time.time()
    msg = await message.reply_text("🏓 **Pinging...**")
    end_time = time.time()
    ping_time = round((end_time - start_time) * 1000, 2)
    await msg.edit_text(
        f"╔══════════════════════════╗\n"
        f"      🏓  PONG  🏓         \n"
        f"╚══════════════════════════╝\n\n"
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
    user_id = message.from_user.id if message.from_user else "Unknown"
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
        await message.reply_text(f"✅ **User `{user_id}` banned from Bot successfully!**")
    except ValueError:
        await message.reply_text("❌ **Invalid user ID!**")

@app.on_message(filters.command("unban") & filters.user(Config.OWNER_ID))
async def unban_command(client: Client, message: Message):
    """Unban a user from Bot"""
    if len(message.command) < 2:
        await message.reply_text("**Usage:** `/unban <user_id>`")
        return
    try:
        user_id = int(message.command[1])
        await unban_user(user_id)
        await message.reply_text(f"✅ **User `{user_id}` unbanned from Bot successfully!**")
    except ValueError:
        await message.reply_text("❌ **Invalid user ID!**")

# ================ COMMAND AUTO DELETE ================
@app.on_message(filters.command([
    "start", "help", "settings", "addfsub", "stats", "ai", 
    "broadcast", "request", "ping", "id"
]) & filters.group)
async def auto_delete_commands(client: Client, message: Message):
    """Auto delete command messages after 5 minutes"""
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, message, 300))

# ================ ADDITIONAL FEATURES FROM OTHER.PY ================
# Note: These functions are now integrated into bot.py

@app.on_message(filters.command(["clean", "cleangroup"]) & filters.group)
async def clean_group_command(client: Client, message: Message):
    """Clean group from inactive members"""
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ **Only admins can use this command!**")
        await asyncio.sleep(5)
        await msg.delete()
        return
    
    processing_msg = await message.reply_text("🔄 **Scanning group members...**")
    
    try:
        deleted_count = 0
        total_count = 0
        
        async for member in client.get_chat_members(message.chat.id):
            total_count += 1
            if member.user.is_deleted:
                try:
                    await client.ban_chat_member(message.chat.id, member.user.id)
                    deleted_count += 1
                    await asyncio.sleep(0.5)
                except:
                    pass
        
        await processing_msg.edit_text(
            f"✅ **Group Cleanup Complete!**\n\n"
            f"👥 **Total Members:** {total_count}\n"
            f"🗑️ **Deleted Accounts:** {deleted_count}\n"
            f"👤 **Active Members:** {total_count - deleted_count}\n\n"
            f"_Group is now clean!_ ✨"
        )
        
    except Exception as e:
        await processing_msg.edit_text(f"❌ **Error:** {str(e)}")

@app.on_message(filters.command(["groupstats", "ginfo"]) & filters.group)
async def group_statistics(client: Client, message: Message):
    """Show group statistics"""
    try:
        chat = await client.get_chat(message.chat.id)
        member_count = await client.get_chat_members_count(message.chat.id)
        
        admin_count = 0
        async for member in client.get_chat_members(message.chat.id, filter="administrators"):
            admin_count += 1
        
        bot_count = 0
        async for member in client.get_chat_members(message.chat.id):
            if member.user.is_bot:
                bot_count += 1
        
        stats_text = f"""
╔══════════════════════════╗
     📊  GROUP STATS  📊  
╚══════════════════════════╝

🏷️ **Name:** {chat.title}
👥 **Members:** {member_count}
👑 **Admins:** {admin_count}
🤖 **Bots:** {bot_count}
👤 **Users:** {member_count - bot_count}

📅 **Created:** {chat.date.strftime('%d %b %Y') if chat.date else 'N/A'}
🔗 **Username:** @{chat.username if chat.username else 'Private'}

📈 **Activity:** High
⚡ **Status:** Active
"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_group_stats")],
            [InlineKeyboardButton("📋 Export Data", callback_data="export_group_data")]
        ])
        
        await message.reply_text(stats_text, reply_markup=buttons)
        
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")

@app.on_message(filters.command(["movieoftheday", "motd"]) & filters.group)
async def movie_of_the_day(client: Client, message: Message):
    """Feature a movie of the day"""
    import random
    popular_movies = [
        {"title": "Kalki 2898 AD", "year": "2024", "genre": "Sci-Fi/Action", "rating": "8.5/10"},
        {"title": "Pushpa 2: The Rule", "year": "2024", "genre": "Action/Drama", "rating": "8.7/10"},
        {"title": "Jawan", "year": "2023", "genre": "Action/Thriller", "rating": "8.2/10"},
        {"title": "Animal", "year": "2023", "genre": "Action/Drama", "rating": "7.8/10"},
        {"title": "Gadar 2", "year": "2023", "genre": "Action/Drama", "rating": "7.5/10"},
        {"title": "OMG 2", "year": "2023", "genre": "Drama/Comedy", "rating": "8.0/10"},
    ]
    
    movie = random.choice(popular_movies)
    
    motd_text = f"""
╔══════════════════════════╗
     🎬  MOVIE OF THE DAY  🎬  
╚══════════════════════════╝

🌟 **{movie['title']} ({movie['year']})**
⭐ **Rating:** {movie['rating']}
🎭 **Genre:** {movie['genre']}
📅 **Featured:** {datetime.datetime.now().strftime('%d %B %Y')}

📌 **Why Watch Today?**
This movie is trending with excellent reviews!

🎯 **Available in:** HD | 720p | 1080p
🔊 **Audio:** Hindi Dual Audio
📝 **Subtitles:** English

💬 **Share your reviews below!**
"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎥 Watch Trailer", url="https://youtube.com")],
        [InlineKeyboardButton("⭐ Rate This Movie", callback_data="rate_movie")],
        [InlineKeyboardButton("📋 Request Similar", callback_data="request_similar")]
    ])
    
    await message.reply_text(motd_text, reply_markup=buttons)

# ================ SCHEDULED CLEANUP TASK ================
async def scheduled_cleanup():
    """Automatically clean junk data"""
    while True:
        try:
            # Wait for cleanup interval
            await asyncio.sleep(Config.CLEANUP_INTERVAL)
            
            # Perform cleanup
            junk_count = await clear_junk()
            if sum(junk_count.values()) > 0:
                logger.info(f"Scheduled cleanup: {junk_count}")
                
                # Notify owner
                try:
                    cleanup_text = (
                        f"🔄 **Scheduled Cleanup Complete**\n\n"
                        f"🗑️ **Items Cleaned:**\n"
                        f"• Banned Users: {junk_count.get('banned_users', 0)}\n"
                        f"• Inactive Groups: {junk_count.get('inactive_groups', 0)}\n\n"
                        f"🔄 **Total:** {sum(junk_count.values())} items"
                    )
                    await app.send_message(Config.OWNER_ID, cleanup_text)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Scheduled cleanup error: {e}")
            await asyncio.sleep(3600)  # Wait 1 hour on error

# ================ START BOT WITH SCHEDULED TASKS ================
async def start_bot():
    """Start bot with scheduled tasks"""
    # Start scheduled cleanup
    asyncio.create_task(scheduled_cleanup())
    
    # Start the bot
    await app.start()
    
    # Get bot info
    bot_info = await app.get_me()
    logger.info(f"✅ Bot started as @{bot_info.username}")
    
    # Set bot commands
    try:
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Get help"),
            BotCommand("settings", "Group settings"),
            BotCommand("stats", "Bot statistics"),
            BotCommand("ai", "Ask AI about movies"),
            BotCommand("addfsub", "Set force subscribe"),
            BotCommand("ping", "Check bot status"),
            BotCommand("id", "Get user/group ID")
        ]
        
        await app.set_bot_commands(commands)
        logger.info("✅ Bot commands set successfully")
    except Exception as e:
        logger.warning(f"⚠️ Could not set bot commands: {e}")
    
    # Send startup message to owner
    try:
        await app.send_message(
            Config.OWNER_ID,
            f"╔══════════════════════════╗\n"
            f"     🤖  BOT STARTED  🤖    \n"
            f"╚══════════════════════════╝\n\n"
            f"🎬 **Bot:** @{bot_info.username}\n"
            f"🕐 **Time:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"☁️ **Server:** Koyeb Cloud\n"
            f"⚡ **Status:** ✅ Running\n\n"
            f"✨ **All systems operational!**"
        )
    except:
        pass
    
    logger.info("🤖 Bot is now running and ready!")
    logger.info("📡 Waiting for messages...")
    
    # Keep bot running
    await idle()

# ================ START BOT ================
if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 **Starting Movie Helper Bot...**")
    print("="*50)
    print("\n✅ **All Features Implemented:**")
    print("   1. ✅ Professional Format Correction System")
    print("   2. ✅ Fixed Clear Junk Button")
    print("   3. ✅ Fixed /setcommands Command")
    print("   4. ✅ Improved AI with Typing Indicator")
    print("   5. ✅ Enhanced Request System with Admin Tagging")
    print("   6. ✅ Fixed Welcome Messages with Photos")
    print("   7. ✅ Professional Design with Emojis & Symbols")
    print("   8. ✅ New Group Management Features")
    print("\n🤖 **Bot is now professional and ready!**")
    print("="*50)
    
    try:
        app.run(start_bot())
        print("\n🤖 Bot stopped gracefully")
    except KeyboardInterrupt:
        print("\n⏹️ Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot crashed: {e}")
        import traceback
        traceback.print_exc()
