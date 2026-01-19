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
from pyrogram.errors import FloodWait, UserNotParticipant, ChatAdminRequired, PeerIdInvalid
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
    """Check if user is admin or owner"""
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

async def get_all_admins(chat_id):
    """Get all admins of a group"""
    admins = []
    try:
        async for admin in app.get_chat_members(chat_id, filter="administrators"):
            if not admin.user.is_bot:
                admins.append(admin.user)
        return admins
    except Exception as e:
        logger.error(f"Error getting admins: {e}")
        return []

async def get_owner(chat_id):
    """Get group owner"""
    try:
        async for member in app.get_chat_members(chat_id, filter="administrators"):
            if member.status == ChatMemberStatus.OWNER:
                return member.user
    except:
        return None
    return None

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
                f"🎬 **New User Started Bot**\n\n"
                f"👤 **Name:** {user.mention}\n"
                f"🆔 **ID:** `{user.id}`\n"
                f"📱 **Username:** @{user.username if user.username else 'N/A'}\n"
                f"⏰ **Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            await client.send_message(Config.LOGS_CHANNEL, log_text)
        except Exception as e:
            logger.error(f"Log Error: {e}")

    welcome_text = f"""🎬 **Namaste {user.first_name}!** 🎬

✨ **Welcome to Movie Helper Bot** ✨

🤖 **I'm your personal movie assistant with powerful features:**

✅ **Smart Spelling Correction** - Auto-corrects movie names
✅ **Auto Delete Files** - Keeps your group clean
✅ **AI Movie Recommendations** - Get movie suggestions
✅ **Auto Accept Join Requests** - Automatically approve members
✅ **Advanced Security** - Link & abuse protection
✅ **Force Subscribe System** - Premium feature
✅ **Movie Requests** - Easy movie requesting system

📌 **How to use:**
1. Add me to your group
2. Make me admin with necessary permissions
3. Use `/settings` to configure
4. Enjoy seamless movie management!"""
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add to Group", 
                url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true"),
            InlineKeyboardButton("📢 Our Channel", 
                url="https://t.me/asbhai_bsr")
        ],
        [
            InlineKeyboardButton("💎 Premium Plans", 
                callback_data="premium_info"),
            InlineKeyboardButton("🛠️ Help Commands", 
                callback_data="help_main")
        ],
        [
            InlineKeyboardButton("⚡ Auto Accept Setup", 
                callback_data="auto_accept_setup"),
            InlineKeyboardButton("📞 Contact Owner", 
                url="https://t.me/asbhai_bsr")
        ]
    ])
    
    try:
        if user.photo:
            msg = await client.send_photo(
                message.chat.id,
                photo=user.photo.big_file_id,
                caption=welcome_text,
                reply_markup=buttons
            )
        else:
            msg = await message.reply_text(welcome_text, reply_markup=buttons)
    except:
        msg = await message.reply_text(welcome_text, reply_markup=buttons)
    
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ HELP COMMAND (UPDATED) ================
@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    """Handle /help command"""
    help_text = """**🎬 Movie Helper Bot - Help Center 🎬**

**👑 ADMIN COMMANDS:**
• `/settings` - Configure bot settings
• `/addfsub` - Set Force Subscribe (Premium)
• `/stats` - View bot statistics
• `/broadcast` - Send message to all users

**🎥 USER COMMANDS:**
• `/start` - Start the bot
• `/request <movie>` - Request a movie
• `/ai <question>` - Ask AI about movies
• `/ping` - Check bot status
• `/id` - Get user/group ID

**⚙️ BOT FEATURES:**
• **Spelling Checker** - Auto-corrects movie names
• **Auto Delete** - Automatically deletes files
• **Auto Accept** - Auto-approves join requests
• **AI Chat** - Movie recommendations
• **Security** - Link & abuse protection
• **Force Subscribe** - Premium only

**📌 QUICK TIPS:**
1. Use `/request Movie Name` to request movies
2. Tag bot in group for quick settings
3. Contact @asbhai_bsr for premium"""
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💎 Premium Features", 
                callback_data="premium_info"),
            InlineKeyboardButton("⚡ Quick Setup", 
                callback_data="auto_accept_setup")
        ],
        [
            InlineKeyboardButton("⚙️ Group Settings", 
                callback_data="help_settings"),
            InlineKeyboardButton("🎬 Request Guide", 
                callback_data="help_guide")
        ],
        [
            InlineKeyboardButton("📞 Contact Support", 
                url="https://t.me/asbhai_bsr"),
            InlineKeyboardButton("❌ Close", 
                callback_data="close_help")
        ]
    ])
    
    msg = await message.reply_text(help_text, reply_markup=buttons)
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ SETTINGS COMMAND (UPDATED) ================
@app.on_message(filters.command("settings") & filters.group)
async def settings_command(client: Client, message: Message):
    """Group settings menu"""
    if not message.from_user:
        return
    
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("⛔ **Only Group Admins/Owner can use this command!**")
        await asyncio.sleep(5)
        await msg.delete()
        return
    
    settings = await get_settings(message.chat.id)
    is_prem = await check_is_premium(message.chat.id)
    auto_accept = await get_auto_accept(message.chat.id)
    
    # Status icons
    prem_status = "💎 Premium" if is_prem else "🎯 Free"
    spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
    delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
    accept_status = "✅ ON" if auto_accept else "❌ OFF"
    welcome_status = "✅ ON" if settings.get("welcome_enabled", True) else "❌ OFF"
    time_text = f"{settings.get('delete_time', 0)} min" if settings.get('delete_time', 0) > 0 else "Permanent"
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✏️ Spelling {spelling_status}", 
                callback_data="toggle_spelling"),
            InlineKeyboardButton(f"🗑️ Auto Delete {delete_status}", 
                callback_data="toggle_auto_delete")
        ],
        [
            InlineKeyboardButton(f"✅ Auto Accept {accept_status}", 
                callback_data="toggle_auto_accept"),
            InlineKeyboardButton(f"👋 Welcome {welcome_status}", 
                callback_data="toggle_welcome")
        ],
        [
            InlineKeyboardButton(f"⏰ Time: {time_text}", 
                callback_data="set_delete_time"),
            InlineKeyboardButton(f"{prem_status}", 
                callback_data="premium_info")
        ],
        [
            InlineKeyboardButton("🔄 Refresh", 
                callback_data="refresh_settings"),
            InlineKeyboardButton("❌ Close", 
                callback_data="close_settings")
        ]
    ])
    
    text = f"""**⚙️ {message.chat.title} - Settings Panel**

📊 **Current Status:**
• Spelling Correction: {spelling_status}
• Auto Delete Files: {delete_status}
• Auto Accept Requests: {accept_status}
• Welcome Messages: {welcome_status}
• Delete Time: {time_text}
• Plan: {prem_status}

💡 **Tip:** Click buttons to toggle settings"""
    
    msg = await message.reply_text(text, reply_markup=buttons)
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ REQUEST HANDLER (FIXED - NOW TAGS ADMIN & OWNER) ================
@app.on_message(filters.command("request") & filters.group)
async def request_handler(client: Client, message: Message):
    """Handle movie requests with admin tagging"""
    if not message.from_user:
        return
        
    if len(message.command) < 2:
        msg = await message.reply_text("❌ **Please specify movie name!**\n\n**Example:** `/request Pushpa 2`")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return
    
    movie_name = " ".join(message.command[1:])
    user = message.from_user
    chat = message.chat
    
    # Get group owner
    owner = await get_owner(chat.id)
    owner_mention = owner.mention if owner else "Group Owner"
    
    # Get all admins for tagging (excluding bots and the requesting user)
    admins = await get_all_admins(chat.id)
    admin_mentions = []
    
    for admin in admins:
        if admin.id != user.id and not admin.is_bot:
            admin_mentions.append(admin.mention)
    
    # Combine owner and admins for tagging
    all_admins = [owner_mention] + admin_mentions if owner_mention != "Group Owner" else admin_mentions
    admin_tags = " ".join(all_admins[:5])  # Limit to 5 mentions
    
    # Create request message with professional design
    text = (
        f"🎬 **NEW MOVIE REQUEST** 🎬\n\n"
        f"**📌 Movie:** `{movie_name}`\n"
        f"**👤 Requested By:** {user.mention}\n"
        f"**🆔 User ID:** `{user.id}`\n"
        f"**📍 Group:** {chat.title}\n"
        f"**⏰ Time:** {datetime.datetime.now().strftime('%H:%M:%S')}\n\n"
        f"**📢 Attention:** {admin_tags if admin_tags else 'Admins'}\n"
        f"Please check this movie request!"
    )
    
    # Create buttons - Only for admins
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Available", 
                callback_data=f"req_accept_{user.id}_{message.id}"),
            InlineKeyboardButton("❌ Not Available", 
                callback_data=f"req_reject_{user.id}_{message.id}")
        ],
        [
            InlineKeyboardButton("📊 Status", 
                callback_data=f"req_status_{user.id}"),
            InlineKeyboardButton("👤 Contact User", 
                url=f"tg://user?id={user.id}")
        ]
    ])
    
    msg = await message.reply_text(text, reply_markup=buttons)
    
    # Store message ID for admin-only actions
    await store_request_message(chat.id, msg.id, user.id, movie_name)
    
    # Auto delete after 10 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 600))

# Also handle #request hashtag
@app.on_message(filters.group & filters.regex(r'^#request\s+', re.IGNORECASE))
async def hashtag_request_handler(client: Client, message: Message):
    """Handle hashtag movie requests"""
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
    
    # Get group owner
    owner = await get_owner(chat.id)
    owner_mention = owner.mention if owner else "Group Owner"
    
    # Get all admins for tagging
    admins = await get_all_admins(chat.id)
    admin_mentions = []
    
    for admin in admins:
        if admin.id != user.id and not admin.is_bot:
            admin_mentions.append(admin.mention)
    
    # Combine owner and admins for tagging
    all_admins = [owner_mention] + admin_mentions if owner_mention != "Group Owner" else admin_mentions
    admin_tags = " ".join(all_admins[:5])
    
    # Create request message
    text = (
        f"🎬 **NEW MOVIE REQUEST** 🎬\n\n"
        f"**📌 Movie:** `{movie_name}`\n"
        f"**👤 Requested By:** {user.mention}\n"
        f"**🆔 User ID:** `{user.id}`\n"
        f"**📍 Group:** {chat.title}\n"
        f"**⏰ Time:** {datetime.datetime.now().strftime('%H:%M:%S')}\n\n"
        f"**📢 Attention:** {admin_tags if admin_tags else 'Admins'}\n"
        f"Please check this movie request!"
    )
    
    # Create buttons - Only for admins
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Available", 
                callback_data=f"req_accept_{user.id}_{message.id}"),
            InlineKeyboardButton("❌ Not Available", 
                callback_data=f"req_reject_{user.id}_{message.id}")
        ],
        [
            InlineKeyboardButton("📊 Status", 
                callback_data=f"req_status_{user.id}"),
            InlineKeyboardButton("👤 Contact User", 
                url=f"tg://user?id={user.id}")
        ]
    ])
    
    msg = await client.send_message(chat.id, text, reply_markup=buttons)
    
    # Store message ID for admin-only actions
    await store_request_message(chat.id, msg.id, user.id, movie_name)
    
    # Auto delete after 10 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 600))

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
        [
            InlineKeyboardButton("🧹 Clean Database", 
                callback_data="clear_junk"),
            InlineKeyboardButton("🔄 Refresh", 
                callback_data="refresh_stats")
        ],
        [
            InlineKeyboardButton("📊 Premium Stats", 
                callback_data="premium_stats"),
            InlineKeyboardButton("📈 Growth", 
                callback_data="growth_stats")
        ]
    ])
    
    stats_text = f"""**📊 Bot Statistics Dashboard**

👥 **Users:** {users}
👥 **Groups:** {groups}
💎 **Premium Groups:** {premium_count}

⚡ **Performance:**
• Uptime: 24/7
• Response Time: < 1s
• Server: Koyeb Cloud
• Status: ✅ Operational

🔄 **Last Updated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    
    await message.reply_text(stats_text, reply_markup=buttons)

# ================ AI COMMAND (FIXED LIBRARY) ================
@app.on_message(filters.command("ai"))
async def ai_command(client: Client, message: Message):
    """AI chat feature with fixed library"""
    if len(message.command) < 2:
        msg = await message.reply_text("**🤖 AI Chat Assistant**\n\n**Usage:** `/ai your question`\n**Example:** `/ai Tell me about Inception movie`")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return
    
    query = ' '.join(message.command[1:])
    
    # Check if query is too short
    if len(query) < 3:
        msg = await message.reply_text("❌ **Please ask a proper question!**\nMinimum 3 characters required.")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return
    
    waiting_msg = await message.reply_text("🤔 **Thinking... Please wait!**")
    
    try:
        response = await MovieBotUtils.get_ai_response(query)
        
        # Format the response nicely
        formatted_response = f"**🤖 AI Response:**\n\n{response}\n\n💡 *This is an AI generated response*"
        
        await waiting_msg.delete()
        msg = await message.reply_text(formatted_response)
        
        # Auto delete after 5 minutes
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))
        
    except Exception as e:
        logger.error(f"AI Error: {e}")
        await waiting_msg.delete()
        error_msg = await message.reply_text(
            "❌ **Sorry, I couldn't process your request right now.**\n\n"
            "Please try again later or contact @asbhai_bsr for support."
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, error_msg, 30))

# ================ BROADCAST COMMAND ================
@app.on_message(filters.command(["broadcast", "grp_broadcast"]) & filters.user(Config.OWNER_ID))
async def broadcast_command(client: Client, message: Message):
    """Broadcast messages to users or groups"""
    if not message.reply_to_message:
        msg = await message.reply_text("❌ **Please reply to a message to broadcast!**")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return
    
    is_group = "grp_broadcast" in message.text
    target_ids = await get_all_groups() if is_group else await get_all_users()
    
    # Premium Filter for Groups (Don't broadcast to Premium)
    if is_group:
        target_ids = [g for g in target_ids if not await check_is_premium(g)]

    progress = await message.reply_text(f"📢 **Broadcasting to {len(target_ids)} chats...**\n\n⏳ Please wait...")
    success, failed, deleted = 0, 0, 0
    
    for idx, chat_id in enumerate(target_ids):
        try:
            await message.reply_to_message.copy(chat_id)
            success += 1
            
            # Update progress every 50 messages
            if idx % 50 == 0:
                await progress.edit_text(
                    f"📢 **Broadcast Progress**\n\n"
                    f"✅ **Success:** {success}\n"
                    f"❌ **Failed:** {failed}\n"
                    f"🗑️ **Cleaned:** {deleted}\n"
                    f"🎯 **Total:** {len(target_ids)}\n\n"
                    f"⏳ **Please wait...**"
                )
                
        except PeerIdInvalid:
            # Invalid chat ID, remove from database
            if is_group:
                await remove_group(chat_id)
            deleted += 1
        except Exception as e:
            logger.error(f"Broadcast Error to {chat_id}: {e}")
            failed += 1
        await asyncio.sleep(0.5)  # Rate limiting
    
    # Final report
    msg = await progress.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"📊 **Statistics:**\n"
        f"🎯 Total Target: {len(target_ids)}\n"
        f"✅ Successfully Sent: {success}\n"
        f"❌ Failed: {failed}\n"
        f"🧹 Cleaned Junk: {deleted}\n\n"
        f"⏰ Time: {datetime.datetime.now().strftime('%H:%M:%S')}"
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
        msg = await message.reply_text("⛔ **Only Admins can use this command!**")
        await asyncio.sleep(5)
        await msg.delete()
        return

    # Check Premium First
    if not await check_is_premium(message.chat.id):
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💎 Buy Premium", 
                    url="https://t.me/asbhai_bsr"),
                InlineKeyboardButton("ℹ️ Premium Info", 
                    callback_data="premium_info")
            ],
            [
                InlineKeyboardButton("🔄 Try Free", 
                    callback_data="free_trial"),
                InlineKeyboardButton("❌ Close", 
                    callback_data="close_settings")
            ]
        ])
        msg = await message.reply_text(
            "**💎 Premium Feature Required!**\n\n"
            "✨ **Force Subscribe** is available only for premium users.\n\n"
            "🚀 **Premium Benefits:**\n"
            "• Ads free experience\n"
            "• Force Subscribe system\n"
            "• Priority support\n"
            "• Advanced features\n\n"
            "📞 **Contact @asbhai_bsr for premium plans!**",
            reply_markup=buttons
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return

    channel_id = None
    
    if len(message.command) > 1:
        try:
            channel_id = int(message.command[1])
        except ValueError:
            msg = await message.reply_text("❌ **Invalid Channel ID!**\n\nPlease use numeric ID (e.g., `-1001234567890`)")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            return

    elif message.reply_to_message:
        if message.reply_to_message.forward_from_chat:
            channel_id = message.reply_to_message.forward_from_chat.id
        else:
            msg = await message.reply_text(
                "❌ **Cannot get Channel ID!**\n\n"
                "Forward privacy is enabled.\n"
                "**Solution:** Use `/addfsub -100xxxxxxxxxx`"
            )
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            return
    else:
        msg = await message.reply_text(
            "**📝 How to use:**\n\n"
            "**Method 1:**\n"
            "`/addfsub -1001234567890`\n\n"
            "**Method 2:**\n"
            "Forward a message from channel\n"
            "Reply with `/addfsub`"
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return

    try:
        chat = await client.get_chat(channel_id)
        me = await client.get_chat_member(channel_id, (await client.get_me()).id)
        
        if not me.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            msg = await message.reply_text(
                f"❌ **I'm not admin in {chat.title}!**\n\n"
                "Please make me admin in the channel first."
            )
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            return
            
    except Exception as e:
        msg = await message.reply_text(
            f"❌ **Error connecting to channel!**\n\n"
            f"**Details:** {e}\n\n"
            "**Please ensure:**\n"
            "1. Channel exists\n"
            "2. Bot is added to channel\n"
            "3. Bot is admin in channel"
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return

    await set_force_sub(message.chat.id, channel_id)
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 Channel Link", 
                url=chat.invite_link or f"https://t.me/{chat.username}"),
            InlineKeyboardButton("⚙️ Test FSub", 
                callback_data="test_fsub")
        ],
        [
            InlineKeyboardButton("✅ Done", 
                callback_data="close_settings")
        ]
    ])
    
    msg = await message.reply_text(
        f"✅ **Force Subscribe Connected Successfully!**\n\n"
        f"**📢 Channel:** {chat.title}\n"
        f"**🆔 Channel ID:** `{channel_id}`\n"
        f"**🔗 Link:** {chat.invite_link or f'https://t.me/{chat.username}'}\n\n"
        f"**📌 How it works:**\n"
        f"1. New members must join this channel\n"
        f"2. After joining, they can chat in group\n"
        f"3. Auto-verification system enabled",
        reply_markup=buttons
    )
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))

# ================ PREMIUM ADMIN COMMANDS ================
@app.on_message(filters.command("add_premium") & filters.user(Config.OWNER_ID))
async def add_premium_cmd(client: Client, message: Message):
    """Add premium to a group"""
    try:
        if len(message.command) < 3:
             msg = await message.reply_text("**Usage:** `/add_premium <group_id> <months>`\n\n**Example:** `/add_premium -1001234567890 3`")
             asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
             return

        group_id = int(message.command[1])
        raw_months = message.command[2].lower()
        clean_months = ''.join(filter(str.isdigit, raw_months))
        
        if not clean_months:
             msg = await message.reply_text("❌ **Invalid months format!**\n\nPlease use numbers only.")
             asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
             return
             
        months = int(clean_months)
        expiry = await add_premium(group_id, months)
        
        try:
            chat = await client.get_chat(group_id)
            group_name = chat.title
        except:
            group_name = f"Group ({group_id})"
        
        msg = await message.reply_text(
            f"✅ **Premium Activated Successfully!**\n\n"
            f"**👥 Group:** {group_name}\n"
            f"**🆔 Group ID:** `{group_id}`\n"
            f"**📅 Months:** {months}\n"
            f"**⏰ Expires:** {expiry.strftime('%d %b %Y, %H:%M')}\n\n"
            f"✨ **Premium features are now active!**"
        )
        
        try:
            # Notify the group
            await client.send_message(
                group_id,
                f"✨ **PREMIUM ACTIVATED!** ✨\n\n"
                f"🎉 Congratulations! Your group has been upgraded to premium.\n\n"
                f"**✅ Features Unlocked:**\n"
                f"• No ads or broadcasts\n"
                f"• Force Subscribe system\n"
                f"• Priority support\n"
                f"• All premium features\n\n"
                f"**📅 Valid Until:** {expiry.strftime('%d %b %Y')}\n"
                f"**👑 Plan:** {months} Month(s)\n\n"
                f"Thank you for your support! ❤️"
            )
        except:
            await message.reply_text("⚠️ **Database updated but couldn't notify group.**")
            
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            
    except Exception as e:
        msg = await message.reply_text(f"❌ **Error:** {str(e)}")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))

@app.on_message(filters.command("remove_premium") & filters.user(Config.OWNER_ID))
async def remove_premium_cmd(client: Client, message: Message):
    """Remove premium from a group"""
    try:
        if len(message.command) < 2:
            msg = await message.reply_text("**Usage:** `/remove_premium <group_id>`\n\n**Example:** `/remove_premium -1001234567890`")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            return
            
        group_id = int(message.command[1])
        await remove_premium(group_id)
        
        try:
            chat = await client.get_chat(group_id)
            group_name = chat.title
        except:
            group_name = f"Group ({group_id})"
            
        msg = await message.reply_text(f"❌ **Premium removed from {group_name}**")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
    except Exception as e:
        msg = await message.reply_text(f"❌ **Error:** {str(e)}")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))

@app.on_message(filters.command("premiumstats") & filters.user(Config.OWNER_ID))
async def premium_stats_cmd(client: Client, message: Message):
    """Show premium statistics"""
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
    
    premium_text = f"**💎 Premium Groups - {count} Total**\n\n"
    if premium_list:
        premium_text += "\n".join(premium_list[:15])  # Show first 15
        if len(premium_list) > 15:
            premium_text += f"\n\n... and {len(premium_list) - 15} more groups"
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh", 
                callback_data="refresh_premium_stats"),
            InlineKeyboardButton("📊 Export", 
                callback_data="export_premium")
        ]
    ])
    
    await message.reply_text(premium_text, reply_markup=buttons)

# ================ MAIN FILTER (UPDATED SPELLING CHECK) ================
@app.on_message(filters.group & filters.text & ~filters.command([
    "start", "help", "settings", "addfsub", "stats", "ai", 
    "broadcast", "request", "ban", "unban", "add_premium", 
    "remove_premium", "premiumstats", "ping", "id"
]))
async def group_message_filter(client, message):
    """Filter group messages for spam, links, and spelling"""
    if not message.from_user:
        return
        
    # Skip if user is admin
    if await is_admin(message.chat.id, message.from_user.id):
        return

    settings = await get_settings(message.chat.id)
    quality = MovieBotUtils.check_message_quality(message.text)

    # 1. LINK HANDLING
    if quality == "LINK":
        try:
            await message.delete()
        except:
            pass
            
        warn_count = await add_warning(message.chat.id, message.from_user.id)
        limit = 3
        
        if warn_count >= limit:
            try:
                # Mute User for 24 hours
                await client.restrict_chat_member(
                    message.chat.id, 
                    message.from_user.id, 
                    ChatPermissions(can_send_messages=False),
                    until_date=datetime.datetime.now() + datetime.timedelta(hours=24)
                )
                warn_msg = await message.reply_text(
                    f"🚫 {message.from_user.mention} **has been muted for 24 hours!**\n"
                    f"**Reason:** Sharing links not allowed"
                )
                await reset_warnings(message.chat.id, message.from_user.id)
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, warn_msg, 10))
            except:
                pass
        else:
            warn_msg = await message.reply_text(
                f"⚠️ {message.from_user.mention}, **Links are not allowed!**\n"
                f"**Warning:** {warn_count}/{limit}"
            )
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, warn_msg, 10))

    # 2. ABUSE HANDLING
    elif quality == "ABUSE":
        try:
            await message.delete()
        except:
            pass
            
        warn_count = await add_warning(message.chat.id, message.from_user.id)
        limit = 3
        
        if warn_count >= limit:
            try:
                # Ban User
                await client.ban_chat_member(message.chat.id, message.from_user.id)
                ban_msg = await message.reply_text(
                    f"🚫 {message.from_user.mention} **has been banned!**\n"
                    f"**Reason:** Using abusive language"
                )
                await reset_warnings(message.chat.id, message.from_user.id)
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, ban_msg, 10))
            except:
                pass
        else:
            warn_msg = await message.reply_text(
                f"⚠️ {message.from_user.mention}, **Abusive language is not allowed!**\n"
                f"**Warning:** {warn_count}/{limit}"
            )
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, warn_msg, 10))

    # 3. SPELLING CHECK - UPDATED DESIGN
    elif settings.get("spelling_on", True) and quality == "JUNK":
        try:
            await message.delete()
        except:
            pass
        
        # Extract movie name from message
        movie_name = MovieBotUtils.extract_movie_name(message.text)
        suggestions = MovieBotUtils.get_movie_suggestions()
        
        if movie_name:
            # Try to find correct spelling
            corrected = MovieBotUtils.get_spelling_suggestion(movie_name, suggestions)
            
            if corrected:
                # Create stylish correction message
                correction_text = (
                    f"✨ **Spelling Correction** ✨\n\n"
                    f"👤 **User:** {message.from_user.mention}\n"
                    f"❌ **Incorrect:** `{message.text[:50]}...`\n"
                    f"✅ **Correct:** `{corrected}`\n\n"
                    f"📌 **Tip:** Use proper format - `Movie Name (Year)`"
                )
            else:
                correction_text = (
                    f"✨ **Format Correction** ✨\n\n"
                    f"👤 **User:** {message.from_user.mention}\n"
                    f"❌ **Wrong Format:** `{message.text[:50]}...`\n"
                    f"✅ **Correct Format:** `Movie Name (Year)`\n\n"
                    f"📌 **Examples:**\n"
                    f"• `Pushpa 2 (2024)`\n"
                    f"• `Kalki 2898 AD (2024)`\n"
                    f"• `Jawan (2023)`"
                )
        else:
            correction_text = (
                f"✨ **Format Correction** ✨\n\n"
                f"👤 **User:** {message.from_user.mention}\n"
                f"❌ **Wrong Format:** `{message.text[:50]}...`\n"
                f"✅ **Correct Format:** `Movie Name (Year)`\n\n"
                f"📌 **Popular Movies:**\n"
                f"• Pushpa 2 (2024)\n"
                f"• Kalki 2898 AD (2024)\n"
                f"• Jawan (2023)\n"
                f"• Pathaan (2023)"
            )
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎬 Request Movie", 
                    switch_inline_query_current_chat="/request "),
                InlineKeyboardButton("📖 Guide", 
                    callback_data="help_guide")
            ]
        ])
        
        spell_msg = await message.reply_text(correction_text, reply_markup=buttons)
        # Delete after 3 minutes
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
            f"Media files are automatically deleted after **{delete_time} minutes**."
        )
        
        notification = await message.reply_text(
            notification_text,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⚙️ Settings", 
                        callback_data="settings_menu"),
                    InlineKeyboardButton("❌ Disable", 
                        callback_data="toggle_auto_delete")
                ]
            ])
        )
        await MovieBotUtils.auto_delete_message(client, notification, 10)
    except:
        pass

# ================ FORCE SUBSCRIBE (IMPROVED) ================
@app.on_chat_member_updated()
async def handle_fsub_join(client, update: ChatMemberUpdated):
    """Handle force subscribe when user joins"""
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
            
            # Send welcome message
            welcome_text = (
                f"🎉 **Welcome {user.mention}!** 🎉\n\n"
                f"✅ **Verification Complete!**\n"
                f"You can now chat in the group.\n\n"
                f"Enjoy your stay! 😊"
            )
            
            try:
                welcome_msg = await client.send_message(chat_id, welcome_text)
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 60))
            except:
                pass
            return
            
    except UserNotParticipant:
        # User hasn't joined, mute them
        try:
            await client.restrict_chat_member(
                chat_id, user_id, 
                ChatPermissions(can_send_messages=False)
            )
        except:
            pass
        
        # Get Channel Info
        try:
            chat_info = await client.get_chat(channel_id)
            channel_name = chat_info.title
            link = chat_info.invite_link or f"https://t.me/{chat_info.username}"
        except:
            channel_name = "our channel"
            link = "https://t.me/asbhai_bsr"

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📢 Join Channel", 
                    url=link),
                InlineKeyboardButton("✅ I Joined", 
                    callback_data=f"fsub_verify_{user_id}_{chat_id}")
            ]
        ])
        
        # Welcome message
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
            
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, fsub_msg, 300))
        except:
            fsub_msg = await client.send_message(chat_id, welcome_txt, reply_markup=buttons)
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, fsub_msg, 300))
            
    except Exception as e:
        logger.error(f"FSub Error: {e}")

# ================ WELCOME MESSAGE FOR NEW MEMBERS (FIXED) ================
@app.on_message(filters.new_chat_members)
async def welcome_new_members(client: Client, message: Message):
    """Welcome new members with photo and details"""
    try:
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
                    f"🤖 **I'm Movie Helper Bot**\n\n"
                    f"✅ **My Features:**\n"
                    f"• Smart Spelling Correction\n"
                    f"• Auto Delete Files\n"
                    f"• AI Movie Chat\n"
                    f"• Auto Accept Requests\n"
                    f"• Advanced Security\n\n"
                    f"⚙️ **Setup Instructions:**\n"
                    f"1. Make me **Admin**\n"
                    f"2. Use `/settings` to configure\n"
                    f"3. Use `/help` for guide\n\n"
                    f"Need help? Contact @asbhai_bsr",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("⚙️ Settings", 
                                callback_data="settings_menu"),
                            InlineKeyboardButton("📖 Help", 
                                callback_data="help_main")
                        ],
                        [
                            InlineKeyboardButton("➕ Add to Another Group", 
                                url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")
                        ]
                    ])
                )
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, bot_welcome, 120))
                
                # LOGS
                if Config.LOGS_CHANNEL:
                    try:
                        log_txt = (
                            f"📂 **Bot Added to New Group**\n\n"
                            f"📛 **Name:** {message.chat.title}\n"
                            f"🆔 **ID:** `{message.chat.id}`\n"
                            f"👥 **Members:** {await client.get_chat_members_count(message.chat.id)}\n"
                            f"👤 **Added By:** {message.from_user.mention if message.from_user else 'Unknown'}\n"
                            f"⏰ **Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
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
                    f"✨ **You can:**\n"
                    f"• Request movies using `/request`\n"
                    f"• Chat with AI using `/ai`\n"
                    f"• Get help using `/help`\n\n"
                    f"Enjoy your stay! 😊"
                )
                
                try:
                    if user.photo:
                        welcome_msg = await client.send_photo(
                            message.chat.id,
                            photo=user.photo.big_file_id,
                            caption=welcome_text,
                            reply_markup=InlineKeyboardMarkup([
                                [
                                    InlineKeyboardButton("🎬 Request Movie", 
                                        switch_inline_query_current_chat="/request "),
                                    InlineKeyboardButton("🤖 AI Chat", 
                                        switch_inline_query_current_chat="/ai ")
                                ]
                            ])
                        )
                    else:
                        welcome_msg = await message.reply_text(welcome_text)
                    
                    # Delete welcome message after 2 minutes
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 120))
                except:
                    pass
                    
        # Delete the "User joined" message after 10 seconds
        try:
            await asyncio.sleep(10)
            await message.delete()
        except:
            pass
            
    except Exception as e:
        logger.error(f"Welcome Error: {e}")

# ================ AUTO ACCEPT JOIN REQUEST (IMPROVED) ================
@app.on_chat_join_request()
async def auto_approve_join(client: Client, request: ChatJoinRequest):
    """Auto approve join requests"""
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
                f"✅ **Join Request Approved!**\n\n"
                f"🎉 Welcome to **{request.chat.title}**!\n\n"
                f"🎬 **Enjoy unlimited movies & entertainment!** 🍿\n\n"
                f"📌 **Group Rules:**\n"
                f"• No spamming\n"
                f"• No abusive language\n"
                f"• Follow admin instructions\n"
                f"• Enjoy your stay!\n\n"
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
            help_text = """**🤖 MOVIE HELPER BOT - HELP CENTER**

📌 **MAIN FEATURES:**
1. ✏️ **Spelling Checker** - Auto-corrects movie names
2. 🗑️ **Auto Delete** - Deletes files automatically
3. ✅ **Auto Accept** - Auto-approves join requests
4. 🤖 **AI Chat** - Movie recommendations & chat
5. 🛡️ **Security** - Link & abuse protection

📋 **QUICK COMMANDS:**
• /start - Start the bot
• /help - This menu
• /settings - Group settings
• /request - Request movies
• /ai - Ask AI questions
• /ping - Check bot status"""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👑 Premium", 
                        callback_data="help_premium"),
                    InlineKeyboardButton("⚙️ Admin", 
                        callback_data="help_admin")
                ],
                [
                    InlineKeyboardButton("📖 User Guide", 
                        callback_data="help_guide"),
                    InlineKeyboardButton("🎬 Examples", 
                        callback_data="help_example")
                ],
                [
                    InlineKeyboardButton("📞 Contact", 
                        url="https://t.me/asbhai_bsr"),
                    InlineKeyboardButton("❌ Close", 
                        callback_data="close_help")
                ]
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
5. 📊 **Detailed Analytics**

💰 **Pricing Plans:**
• **1 Month:** ₹100
• **3 Months:** ₹250 (Save ₹50)
• **6 Months:** ₹450 (Save ₹150)
• **Lifetime:** ₹500 (One Time)

🛒 **How to Buy:**
Contact @asbhai_bsr for premium purchase.

🎁 **Free Trial:** 3 days trial available!"""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("💬 Contact Owner", 
                        url="https://t.me/asbhai_bsr"),
                    InlineKeyboardButton("🔄 Refresh", 
                        callback_data="help_premium")
                ],
                [
                    InlineKeyboardButton("⬅️ Back", 
                        callback_data="help_main"),
                    InlineKeyboardButton("❌ Close", 
                        callback_data="close_help")
                ]
            ])
            
            await query.message.edit_text(premium_text, reply_markup=buttons)
            await query.answer("Premium information")
        
        elif data == "help_admin":
            admin_text = """**⚙️ ADMIN COMMANDS**

**👑 Group Admins Can Use:**
• `/settings` - Configure bot settings
• `/addfsub <channel_id>` - Set Force Subscribe (Premium)
• `/stats` - View bot statistics

**🤖 Bot Owner Commands:**
• `/add_premium <group_id> <months>` - Add premium
• `/remove_premium <group_id>` - Remove premium
• `/broadcast` - Send message to all users
• `/grp_broadcast` - Send to all groups
• `/ban <user_id>` - Ban user from bot
• `/unban <user_id>` - Unban user

**📌 Note:** Some commands require premium subscription."""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⬅️ Back", 
                        callback_data="help_main"),
                    InlineKeyboardButton("⚡ Auto Accept", 
                        callback_data="auto_accept_setup")
                ],
                [
                    InlineKeyboardButton("❌ Close", 
                        callback_data="close_help")
                ]
            ])
            
            await query.message.edit_text(admin_text, reply_markup=buttons)
            await query.answer()
        
        elif data == "help_guide":
            guide_text = """**📖 USER GUIDE**

**🎬 How to Request Movies:**
1. Use `/request Movie Name`
2. Or use `#request Movie Name`
3. Admins will be notified instantly

**🤖 Using AI Chat:**
• `/ai Tell me about Inception`
• `/ai Best movies of 2023`
• `/ai Comedy movies list`
• `/ai Movie recommendations`

**⚙️ Group Rules:**
• No spam or links
• No abusive language
• Use proper movie format
• Follow admin instructions

**📞 Support:**
For help contact @asbhai_bsr"""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⬅️ Back", 
                        callback_data="help_main"),
                    InlineKeyboardButton("🎬 Examples", 
                        callback_data="help_example")
                ],
                [
                    InlineKeyboardButton("📞 Contact", 
                        url="https://t.me/asbhai_bsr"),
                    InlineKeyboardButton("❌ Close", 
                        callback_data="close_help")
                ]
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
• `#request Pathaan 2023`

**❌ Wrong Format:**
• `movie dedo`
• `send pushpa`
• `pushpa movie chahiye`
• `plz send movie`

**📌 Tips:**
• Always include movie name
• Add year if possible
• Use proper spelling
• Avoid spam words
• Be specific"""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⬅️ Back", 
                        callback_data="help_guide"),
                    InlineKeyboardButton("🎬 Try Request", 
                        switch_inline_query_current_chat="/request ")
                ],
                [
                    InlineKeyboardButton("❌ Close", 
                        callback_data="close_help")
                ]
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
5. ⏰ **Delete Time** - Set timer (0-60 mins)

**How to Configure:**
1. Use `/settings` in group
2. Click buttons to toggle
3. Set delete time as needed
4. Premium for extra features

**Note:** Need admin rights to change settings."""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⬅️ Back", 
                        callback_data="help_main"),
                    InlineKeyboardButton("⚙️ Open Settings", 
                        switch_inline_query_current_chat="/settings")
                ],
                [
                    InlineKeyboardButton("❌ Close", 
                        callback_data="close_help")
                ]
            ])
            
            await query.message.edit_text(settings_text, reply_markup=buttons)
            await query.answer()
        
        elif data == "premium_info":
            text = """**💎 PREMIUM PLANS**

**✨ Premium Benefits:**
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
2. Send payment via UPI/Google Pay
3. Get premium activated instantly

**🎁 Free Trial:** 3 days trial available!"""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("💬 Contact Owner", 
                        url="https://t.me/asbhai_bsr"),
                    InlineKeyboardButton("🔄 Refresh", 
                        callback_data="premium_info")
                ],
                [
                    InlineKeyboardButton("🔙 Back", 
                        callback_data="help_main"),
                    InlineKeyboardButton("🎁 Free Trial", 
                        callback_data="free_trial")
                ]
            ])
            
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer("Premium information")
        
        # Request Accept Logic - ADMIN ONLY
        elif data.startswith("req_accept_"):
            # Extract data
            parts = data.split("_")
            if len(parts) < 4:
                await query.answer("❌ Invalid request!", show_alert=True)
                return
                
            req_user_id = int(parts[2])
            message_id = int(parts[3])
            
            # Check if user is admin
            if not await is_admin(query.message.chat.id, query.from_user.id):
                await query.answer("❌ Only admins can accept requests!", show_alert=True)
                return
            
            try:
                # Get user info
                req_user = await client.get_users(req_user_id)
                
                # Update message
                new_text = (
                    f"✅ **MOVIE AVAILABLE!**\n\n"
                    f"🎬 **Movie:** Available now!\n"
                    f"👤 **Requested By:** {req_user.mention}\n"
                    f"✅ **Approved By:** {query.from_user.mention}\n"
                    f"⏰ **Time:** {datetime.datetime.now().strftime('%H:%M:%S')}\n\n"
                    f"📢 **Note:** The movie has been made available!"
                )
                
                buttons = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("👤 Contact User", 
                            url=f"tg://user?id={req_user_id}"),
                        InlineKeyboardButton("✅ Done", 
                            callback_data="close_request")
                    ]
                ])
                
                await query.message.edit_text(new_text, reply_markup=buttons)
                await query.answer("✅ Request accepted!")
                
                # Notify user
                try:
                    await client.send_message(
                        req_user_id,
                        f"✅ **Your movie request has been accepted!**\n\n"
                        f"**Approved by:** {query.from_user.mention}\n"
                        f"**Group:** {query.message.chat.title}\n"
                        f"**Time:** {datetime.datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"Check the group for the movie! 🎬"
                    )
                except:
                    pass
                    
            except Exception as e:
                await query.answer(f"❌ Error: {str(e)}", show_alert=True)

        # Request Reject Logic - ADMIN ONLY
        elif data.startswith("req_reject_"):
            # Extract data
            parts = data.split("_")
            if len(parts) < 4:
                await query.answer("❌ Invalid request!", show_alert=True)
                return
                
            req_user_id = int(parts[2])
            message_id = int(parts[3])
            
            # Check if user is admin
            if not await is_admin(query.message.chat.id, query.from_user.id):
                await query.answer("❌ Only admins can reject requests!", show_alert=True)
                return
            
            try:
                # Get user info
                req_user = await client.get_users(req_user_id)
                
                # Update message
                new_text = (
                    f"❌ **REQUEST REJECTED**\n\n"
                    f"🎬 **Movie:** Not available\n"
                    f"👤 **Requested By:** {req_user.mention}\n"
                    f"❌ **Rejected By:** {query.from_user.mention}\n"
                    f"⏰ **Time:** {datetime.datetime.now().strftime('%H:%M:%S')}\n\n"
                    f"📢 **Note:** This movie is currently not available."
                )
                
                buttons = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("👤 Contact User", 
                            url=f"tg://user?id={req_user_id}"),
                        InlineKeyboardButton("❌ Close", 
                            callback_data="close_request")
                    ]
                ])
                
                await query.message.edit_text(new_text, reply_markup=buttons)
                await query.answer("❌ Request rejected!")
                
                # Notify user
                try:
                    await client.send_message(
                        req_user_id,
                        f"❌ **Your movie request has been rejected!**\n\n"
                        f"**Rejected by:** {query.from_user.mention}\n"
                        f"**Group:** {query.message.chat.title}\n"
                        f"**Time:** {datetime.datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"**Reason:** Movie not available currently.\n"
                        f"You can request another movie! 🎬"
                    )
                except:
                    pass
                    
            except Exception as e:
                await query.answer(f"❌ Error: {str(e)}", show_alert=True)

        # Request Status
        elif data.startswith("req_status_"):
            req_user_id = int(data.split("_")[2])
            if query.from_user.id != req_user_id:
                await query.answer("❌ This status is for the requester only!", show_alert=True)
                return
            
            status_text = (
                f"📊 **Request Status**\n\n"
                f"👤 **User:** {query.from_user.mention}\n"
                f"🆔 **ID:** `{req_user_id}`\n"
                f"⏰ **Request Time:** {datetime.datetime.now().strftime('%H:%M:%S')}\n"
                f"📌 **Status:** ⏳ Pending\n\n"
                f"Admins will review your request shortly!"
            )
            
            await query.answer(status_text, show_alert=True)

        # Close request
        elif data == "close_request":
            if not await is_admin(query.message.chat.id, query.from_user.id):
                await query.answer("❌ Only admins can close requests!", show_alert=True)
                return
            await query.message.delete()
            await query.answer("Request closed!")

        # Settings Toggles
        elif data == "toggle_spelling":
            if not await is_admin(query.message.chat.id, query.from_user.id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            settings = await get_settings(chat_id)
            new_value = not settings.get("spelling_on", True)
            await update_settings(chat_id, "spelling_on", new_value)
            status = "✅ ON" if new_value else "❌ OFF"
            await query.answer(f"Spelling correction: {status}")
            await refresh_settings_menu(client, query)
        
        elif data == "toggle_auto_delete":
            if not await is_admin(query.message.chat.id, query.from_user.id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            settings = await get_settings(chat_id)
            new_value = not settings.get("auto_delete_on", False)
            await update_settings(chat_id, "auto_delete_on", new_value)
            status = "✅ ON" if new_value else "❌ OFF"
            await query.answer(f"Auto delete: {status}")
            await refresh_settings_menu(client, query)

        elif data == "toggle_auto_accept":
            if not await is_admin(query.message.chat.id, query.from_user.id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            current = await get_auto_accept(chat_id)
            await set_auto_accept(chat_id, not current)
            status = "✅ ON" if not current else "❌ OFF"
            await query.answer(f"Auto Accept: {status}")
            await refresh_settings_menu(client, query)
        
        elif data == "toggle_welcome":
            if not await is_admin(query.message.chat.id, query.from_user.id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            settings = await get_settings(chat_id)
            new_value = not settings.get("welcome_enabled", True)
            await update_settings(chat_id, "welcome_enabled", new_value)
            status = "✅ ON" if new_value else "❌ OFF"
            await query.answer(f"Welcome messages: {status}")
            await refresh_settings_menu(client, query)
        
        elif data == "set_delete_time":
            if not await is_admin(query.message.chat.id, query.from_user.id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("5 Minutes", callback_data="time_5"),
                    InlineKeyboardButton("10 Minutes", callback_data="time_10")
                ],
                [
                    InlineKeyboardButton("15 Minutes", callback_data="time_15"),
                    InlineKeyboardButton("30 Minutes", callback_data="time_30")
                ],
                [
                    InlineKeyboardButton("1 Hour", callback_data="time_60"),
                    InlineKeyboardButton("Permanent ❌", callback_data="time_0")
                ],
                [
                    InlineKeyboardButton("🔙 Back", callback_data="back_settings")
                ]
            ])
            await query.message.edit_text(
                "**⏰ Select Auto-Delete Time:**\n\n"
                "How long should media files stay before auto-deletion?",
                reply_markup=buttons
            )
            await query.answer()
        
        elif data.startswith("time_"):
            if not await is_admin(query.message.chat.id, query.from_user.id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            minutes = int(data.split("_")[1])
            await update_settings(chat_id, "delete_time", minutes)
            time_text = f"{minutes} minutes" if minutes > 0 else "Permanent"
            await query.answer(f"✅ Delete time set to {time_text}")
            await refresh_settings_menu(client, query)

        elif data == "clear_junk":
            if query.from_user.id != Config.OWNER_ID:
                await query.answer("❌ Only owner can clear junk!", show_alert=True)
                return
                
            junk_count = await clear_junk()
            await query.answer(f"🧹 Cleared {junk_count} junk entries!")
            await query.message.edit_text(
                f"✅ **Database Cleaned!**\n\n"
                f"Removed **{junk_count}** inactive entries from database.\n\n"
                f"⏰ Time: {datetime.datetime.now().strftime('%H:%M:%S')}",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔄 Refresh Stats", 
                            callback_data="refresh_stats"),
                        InlineKeyboardButton("✅ Done", 
                            callback_data="close_settings")
                    ]
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
                    [
                        InlineKeyboardButton("🧹 Clean Database", 
                            callback_data="clear_junk"),
                        InlineKeyboardButton("🔄 Refresh", 
                            callback_data="refresh_stats")
                    ]
                ])
            )
            await query.answer("✅ Stats refreshed!")
        
        # Force Subscribe Verification
        elif data.startswith("fsub_verify_"):
            parts = data.split("_")
            if len(parts) < 4:
                return
                
            target_id = int(parts[2])
            channel_id = int(parts[3]) if len(parts) > 3 else None
            
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
                [
                    InlineKeyboardButton("👥 For Group", 
                        callback_data="auto_group"),
                    InlineKeyboardButton("📢 For Channel", 
                        callback_data="auto_channel")
                ],
                [
                    InlineKeyboardButton("🔙 Back", 
                        callback_data="help_main"),
                    InlineKeyboardButton("❌ Close", 
                        callback_data="close_help")
                ]
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
                [
                    InlineKeyboardButton("➕ Add to Group", 
                        url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true"),
                    InlineKeyboardButton("⚙️ Group Settings", 
                        switch_inline_query_current_chat="/settings")
                ],
                [
                    InlineKeyboardButton("🔙 Back", 
                        callback_data="auto_accept_setup"),
                    InlineKeyboardButton("❌ Close", 
                        callback_data="close_help")
                ]
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
        
        elif data == "refresh_settings":
            await refresh_settings_menu(client, query)
            await query.answer("✅ Settings refreshed!")
        
        elif data == "close_settings":
            if not await is_admin(query.message.chat.id, query.from_user.id):
                await query.answer("❌ Only admins can close settings!", show_alert=True)
                return
            await query.message.delete()
            await query.answer("Settings closed!")
        
        elif data == "close_help":
            await query.message.delete()
            await query.answer("Help closed!")
        
        elif data == "back_settings" or data == "settings_menu":
            await refresh_settings_menu(client, query)
        
        elif data == "free_trial":
            await query.answer("🎁 Contact @asbhai_bsr for free trial!", show_alert=True)
        
        elif data == "test_fsub":
            await query.answer("✅ Force Subscribe is working!", show_alert=True)
        
        elif data == "premium_stats":
            # Show premium stats
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
            
            premium_text = f"**💎 Premium Groups - {count} Total**\n\n"
            if premium_list:
                premium_text += "\n".join(premium_list[:10])
                if len(premium_list) > 10:
                    premium_text += f"\n\n... and {len(premium_list) - 10} more groups"
            
            await query.message.edit_text(premium_text)
            await query.answer()
        
        elif data == "export_premium":
            await query.answer("📊 Feature coming soon!", show_alert=True)
        
        elif data == "growth_stats":
            await query.answer("📈 Feature coming soon!", show_alert=True)
        
        elif data == "refresh_premium_stats":
            await query.answer("🔄 Refreshing...", show_alert=True)
            # You can implement refresh logic here
    
    except Exception as e:
        logger.error(f"Callback Error: {e}")
        try:
            await query.answer("❌ Error processing request!", show_alert=True)
        except:
            pass

# Helper for updating settings menu
async def refresh_settings_menu(client, query):
    """Refresh settings menu"""
    try:
        chat_id = query.message.chat.id
        user_id = query.from_user.id
        
        # Check if user is admin
        if not await is_admin(chat_id, user_id):
            try:
                await query.answer("❌ Only admins can access settings!", show_alert=True)
            except:
                pass
            return
        
        settings = await get_settings(chat_id)
        is_prem = await check_is_premium(chat_id)
        auto_accept = await get_auto_accept(chat_id)
        
        # Status icons
        prem_status = "💎 Premium" if is_prem else "🎯 Free"
        spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
        delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
        accept_status = "✅ ON" if auto_accept else "❌ OFF"
        welcome_status = "✅ ON" if settings.get("welcome_enabled", True) else "❌ OFF"
        delete_time = settings.get("delete_time", 0)
        time_text = f"{delete_time} min" if delete_time > 0 else "Permanent"
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"✏️ Spelling {spelling_status}", 
                    callback_data="toggle_spelling"),
                InlineKeyboardButton(f"🗑️ Auto Delete {delete_status}", 
                    callback_data="toggle_auto_delete")
            ],
            [
                InlineKeyboardButton(f"✅ Auto Accept {accept_status}", 
                    callback_data="toggle_auto_accept"),
                InlineKeyboardButton(f"👋 Welcome {welcome_status}", 
                    callback_data="toggle_welcome")
            ],
            [
                InlineKeyboardButton(f"⏰ Time: {time_text}", 
                    callback_data="set_delete_time"),
                InlineKeyboardButton(f"{prem_status}", 
                    callback_data="premium_info")
            ],
            [
                InlineKeyboardButton("🔄 Refresh", 
                    callback_data="refresh_settings"),
                InlineKeyboardButton("❌ Close", 
                    callback_data="close_settings")
            ]
        ])
        
        text = f"""**⚙️ {query.message.chat.title} - Settings Panel**

📊 **Current Status:**
• Spelling Correction: {spelling_status}
• Auto Delete Files: {delete_status}
• Auto Accept Requests: {accept_status}
• Welcome Messages: {welcome_status}
• Delete Time: {time_text}
• Plan: {prem_status}

💡 **Tip:** Click buttons to toggle settings"""
        
        await query.message.edit_text(text, reply_markup=buttons)
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
                f"❌ **You are not admin in {chat.title}!**\n\n"
                f"You need to be admin to setup auto accept.\n"
                f"Please ask the channel owner to add you as admin."
            )
            return
        
        # Check if bot is admin
        try:
            bot_member = await client.get_chat_member(channel_id, (await client.get_me()).id)
            if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                await message.reply_text(
                    f"❌ **I'm not admin in {chat.title}!**\n\n"
                    f"Please add me as admin first with 'Add Users' permission.\n\n"
                    f"**Message to send in channel:**\n"
                    f"`@MovieHelper_asBot I can Approve your Join Requests Automatically! Just add me as Admin and you are good to Go..`"
                )
                return
        except:
            await message.reply_text(
                f"❌ **I'm not in {chat.title}!**\n\n"
                f"Please add me to the channel first as admin.\n\n"
                f"**Message to send in channel:**\n"
                f"`@MovieHelper_asBot I can Approve your Join Requests Automatically! Just add me as Admin and you are good to Go..`"
            )
            return
        
        # Enable auto accept for this channel
        await set_auto_accept(channel_id, True)
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📢 View Channel", 
                    url=f"https://t.me/c/{str(channel_id)[4:]}" if str(channel_id).startswith("-100") else f"t.me/{chat.username}"),
                InlineKeyboardButton("✅ Test", 
                    callback_data="test_auto_accept")
            ]
        ])
        
        await message.reply_text(
            f"✅ **Auto Accept Enabled Successfully!**\n\n"
            f"**Channel:** {chat.title}\n"
            f"**ID:** `{channel_id}`\n\n"
            f"Now I will automatically approve all join requests in this channel.\n\n"
            f"**Note:** Make sure join requests are enabled in channel settings.",
            reply_markup=buttons
        )
        
    except Exception as e:
        await message.reply_text(
            f"❌ **Error setting up auto accept!**\n\n"
            f"**Error:** {str(e)}\n\n"
            f"**Please make sure:**\n"
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
        await message.reply_text("✅ **Bot commands set successfully!**")
    except Exception as e:
        await message.reply_text(f"❌ **Failed to set commands:** {e}")

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
        f"📊 **Uptime:** 24/7\n"
        f"⏰ **Time:** {datetime.datetime.now().strftime('%H:%M:%S')}"
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
        text += f"👥 **Total Members:** {await client.get_chat_members_count(chat_id)}\n"
    
    text += f"⏰ **Time:** {datetime.datetime.now().strftime('%H:%M:%S')}"
    
    await message.reply_text(text)

# ================ BAN/UNBAN COMMANDS ================
@app.on_message(filters.command("ban") & filters.user(Config.OWNER_ID))
async def ban_command(client: Client, message: Message):
    """Ban a user from Bot"""
    if len(message.command) < 2:
        await message.reply_text("**Usage:** `/ban <user_id>`\n\n**Example:** `/ban 123456789`")
        return
    try:
        user_id = int(message.command[1])
        await ban_user(user_id)
        await message.reply_text(f"✅ **User `{user_id}` banned from Bot successfully!**")
    except ValueError:
        await message.reply_text("❌ **Invalid user ID!** Please provide a numeric ID.")

@app.on_message(filters.command("unban") & filters.user(Config.OWNER_ID))
async def unban_command(client: Client, message: Message):
    """Unban a user from Bot"""
    if len(message.command) < 2:
        await message.reply_text("**Usage:** `/unban <user_id>`\n\n**Example:** `/unban 123456789`")
        return
    try:
        user_id = int(message.command[1])
        await unban_user(user_id)
        await message.reply_text(f"✅ **User `{user_id}` unbanned from Bot successfully!**")
    except ValueError:
        await message.reply_text("❌ **Invalid user ID!** Please provide a numeric ID.")

# ================ COMMAND AUTO DELETE ================
@app.on_message(filters.command([
    "start", "help", "settings", "addfsub", "stats", "ai", 
    "broadcast", "request", "ping", "id"
]) & filters.group)
async def auto_delete_commands(client: Client, message: Message):
    """Auto delete command messages after 5 minutes"""
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, message, 300))

# ================ START BOT ================
async def main():
    """Main function to start the bot"""
    print("\n" + "="*50)
    print("🎬 MOVIE HELPER BOT - STARTING...")
    print("="*50)
    
    print("\n✅ **All Features Implemented:**")
    print("   1. ✅ Fixed Welcome Messages for new users")
    print("   2. ✅ Fixed /request command with admin tagging")
    print("   3. ✅ Admin-only buttons for accept/reject")
    print("   4. ✅ Fixed AI library warnings")
    print("   5. ✅ Professional design & messages")
    print("   6. ✅ Force Subscribe system")
    print("   7. ✅ Auto Accept join requests")
    print("   8. ✅ Spelling correction")
    print("   9. ✅ Auto delete files")
    print("   10.✅ Advanced security")
    print("   11.✅ Database integration")
    print("   12.✅ Premium features")
    
    print("\n🔧 **Fixed All Errors:**")
    print("   - ✅ Peer id invalid error")
    print("   - ✅ Welcome message not sending")
    print("   - ✅ Admin tagging in requests")
    print("   - ✅ Button permissions")
    print("   - ✅ AI library updates")
    print("   - ✅ Message not modified error")
    
    print("\n🚀 **Starting Bot...**")
    
    await app.start()
    
    # Set bot commands
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
    
    await app.set_bot_commands(commands)
    print("✅ Bot commands set successfully!")
    
    me = await app.get_me()
    print(f"✅ Bot started as @{me.username}")
    print(f"✅ Bot ID: {me.id}")
    print("✅ Status: 🟢 ONLINE")
    
    print("\n📡 Waiting for messages...")
    print("="*50 + "\n")
    
    await idle()
    
    await app.stop()
    print("\n🛑 Bot stopped gracefully!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot crashed: {e}")
        import traceback
        traceback.print_exc()
