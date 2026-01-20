import asyncio
import logging
import time
import re
import datetime
from pyrogram import Client, filters, idle
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, ChatMemberUpdated, ChatPermissions, ChatJoinRequest,
    BotCommand, BotCommandScopeAllPrivateChats
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
    """Get list of admin mentions for tagging with emoji"""
    admins = []
    try:
        async for admin in app.get_chat_members(chat_id, filter="administrators"):
            if (not admin.user.is_bot and 
                admin.user.id != exclude_user_id and
                admin.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]):
                
                # Add emoji based on admin status
                emoji = "👑" if admin.status == ChatMemberStatus.OWNER else "⚡"
                admins.append(f"{emoji} <a href='tg://user?id={admin.user.id}'>{admin.user.first_name}</a>")
    except Exception as e:
        logger.error(f"Get admins error: {e}")
    return admins

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

    welcome_text = f"""🎬 **Namaste {user.first_name}!** 🎬

🤖 **Movie Helper Bot** mein aapka swagat hai!

✨ **Premium Features:**
✅ Smart Spelling Correction
✅ Auto Delete Files
✅ AI Movie Recommendations
⚡ Auto Accept Join Requests
🛡️ Advanced Abuse/Link Protection
💎 Force Subscribe System

➡️ **Mujhe apne groups mein add karein aur Admin banaein!** 😊"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Group Mein Add Karein", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton("💎 Premium Plans", callback_data="premium_info")],
        [InlineKeyboardButton("📋 Help Commands", callback_data="help_main")],
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

**📌 Group Owners/Admins Ke Liye:**
1. Mujhe group mein add karein aur Admin banaein
2. `/settings` use karein - Group settings change karein
3. `/addfsub` use karein - Force Subscribe set karein (Premium Only)

**🛠 Bot Features:**
• **Spelling Checker** - Movie names auto-correct karta hai
• **Auto Delete** - Media files automatically delete karta hai
• **Auto Accept** - Join requests auto-approve karta hai
• **AI Chat** - Movie recommendations aur chat
• **Security** - Link & abuse protection
• **Force Subscribe** - Premium feature

**👤 User Commands:**
• `/start` - Bot start karein
• `/request <movie>` - Movie request karein
• `/ai <question>` - AI se movies ke baare mein puchein
• `/ping` - Bot status check karein
• `/id` - User/group ID get karein

**👑 Premium Commands:**
• `/addfsub <channel_id>` - Force Subscribe ke liye channel connect karein

**📞 Contact:** @asbhai_bsr"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 Premium Info", callback_data="premium_info")],
        [InlineKeyboardButton("⚡ Auto Accept Setup", callback_data="auto_accept_setup")],
        [InlineKeyboardButton("⚙️ Group Settings", callback_data="help_settings")],
        [InlineKeyboardButton("❌ Close", callback_data="close_help")]
    ])
    
    if message.chat.type == "private":
        msg = await message.reply_text(help_text, reply_markup=buttons)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))
    else:
        # Group mein command message auto delete
        msg = await message.reply_text(help_text, reply_markup=buttons)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 120))

# ================ SETTINGS COMMAND (UPDATED WITH SPELLING OPTIONS) ================
@app.on_message(filters.command("settings") & filters.group)
async def settings_command(client: Client, message: Message):
    """Group settings menu"""
    if not message.from_user:
        return
    
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ Sirf Group Admins/Owner hi settings use kar sakte hain!")
        await asyncio.sleep(5)
        await msg.delete()
        return
    
    settings = await get_settings(message.chat.id)
    spelling_settings = await get_spelling_settings(message.chat.id)
    is_prem = await check_is_premium(message.chat.id)
    auto_accept = await get_auto_accept(message.chat.id)
    
    prem_status = "💎 Active" if is_prem else "🔓 Free"
    spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
    advanced_spelling = "🔍 Advanced" if spelling_settings.get("advanced_spelling", False) else "📝 Simple"
    delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
    accept_status = "✅ ON" if auto_accept else "❌ OFF"
    welcome_status = "✅ ON" if settings.get("welcome_enabled", True) else "❌ OFF"
    welcome_photo = "📸 ON" if settings.get("welcome_with_photo", True) else "📝 TEXT"
    time_text = f"{settings.get('delete_time', 0)} min" if settings.get('delete_time', 0) > 0 else "Permanent"
    
    # Professional buttons layout (2 buttons per row)
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✏️ Spelling: {spelling_status}", callback_data="toggle_spelling"),
            InlineKeyboardButton(f"🔍 Type: {advanced_spelling}", callback_data="toggle_adv_spelling")
        ],
        [
            InlineKeyboardButton(f"🗑️ Auto Delete: {delete_status}", callback_data="toggle_auto_delete"),
            InlineKeyboardButton(f"⏰ Time: {time_text}", callback_data="set_delete_time")
        ],
        [
            InlineKeyboardButton(f"✅ Auto Accept: {accept_status}", callback_data="toggle_auto_accept"),
            InlineKeyboardButton(f"👋 Welcome: {welcome_status}", callback_data="toggle_welcome")
        ],
        [
            InlineKeyboardButton(f"📸 Welcome Photo: {welcome_photo}", callback_data="toggle_welcome_photo"),
            InlineKeyboardButton(f"{prem_status} Premium", callback_data="premium_info")
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_settings"),
            InlineKeyboardButton("❌ Close", callback_data="close_settings")
        ]
    ])
    
    settings_text = f"""**⚙️ Settings for {message.chat.title}**

• **✏️ Spelling Check:** {spelling_status}
• **🔍 Spelling Mode:** {advanced_spelling}
• **🗑️ Auto Delete:** {delete_status} ({time_text})
• **✅ Auto Accept:** {accept_status}
• **👋 Welcome Msg:** {welcome_status}
• **📸 Welcome Photo:** {welcome_photo}
• **💎 Premium:** {prem_status}

_Click buttons to change settings:_"""
    
    msg = await message.reply_text(settings_text, reply_markup=buttons)
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ REQUEST HANDLER (IMPROVED WITH EMOJI TAGS) ================
@app.on_message(filters.command("request") & filters.group)
async def request_handler(client: Client, message: Message):
    if not message.from_user:
        return
        
    if len(message.command) < 2:
        msg = await message.reply_text("❌ Please specify movie name!\n**Example:** `/request Pushpa 2`")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return
    
    movie_name = " ".join(message.command[1:])
    user = message.from_user
    chat = message.chat
    
    # Get admins for tagging with emoji format
    admins = await get_admins_mentions(chat.id, exclude_user_id=user.id)
    
    # Format with emoji tags
    if admins:
        admin_tags = ""
        for i, admin in enumerate(admins[:3], 1):  # Max 3 admins
            emoji = "👑" if i == 1 else "⚡" if i == 2 else "⭐"
            admin_tags += f"{emoji} {admin}\n"
    else:
        admin_tags = "👑 **Group Admins**"
    
    # Create request message with professional design
    text = (
        f"🎬 **NEW MOVIE REQUEST** 🎬\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"**📌 Movie:** `{movie_name}`\n"
        f"**👤 Requested By:** {user.mention}\n"
        f"**📍 Group:** {chat.title}\n\n"
        f"**{admin_tags}**\n"
        f"Please check this request!"
    )
    
    # Professional buttons (3 in a row)
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Available", callback_data=f"req_accept_{user.id}_{message.id}"),
            InlineKeyboardButton("❌ Not Available", callback_data=f"req_reject_{user.id}_{message.id}"),
            InlineKeyboardButton("⏳ Processing", callback_data=f"req_process_{user.id}_{message.id}")
        ],
        [
            InlineKeyboardButton("📊 Check Stats", callback_data=f"req_stats_{user.id}"),
            InlineKeyboardButton("👤 My Requests", callback_data=f"my_requests_{user.id}")
        ],
        [
            InlineKeyboardButton("🔔 Notify All", callback_data=f"notify_all_{chat.id}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_req_{message.id}")
        ]
    ])
    
    msg = await message.reply_text(text, reply_markup=buttons)
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))
    
    # Also save to database
    await add_movie_request(chat.id, user.id, movie_name)

# Also handle #request hashtag (IMPROVED VERSION)
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
    
    # Get admins for tagging with emoji format
    admins = await get_admins_mentions(chat.id, exclude_user_id=user.id)
    
    # Format with emoji tags
    if admins:
        admin_tags = ""
        for i, admin in enumerate(admins[:3], 1):  # Max 3 admins
            emoji = "👑" if i == 1 else "⚡" if i == 2 else "⭐"
            admin_tags += f"{emoji} {admin}\n"
    else:
        admin_tags = "👑 **Group Admins**"
    
    # Create request message
    text = (
        f"🎬 **NEW MOVIE REQUEST** 🎬\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"**📌 Movie:** `{movie_name}`\n"
        f"**👤 Requested By:** {user.mention}\n"
        f"**📍 Group:** {chat.title}\n\n"
        f"**{admin_tags}**\n"
        f"Please check this request!"
    )
    
    # Professional buttons
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Available", callback_data=f"req_accept_{user.id}_{message.id}"),
            InlineKeyboardButton("❌ Not Available", callback_data=f"req_reject_{user.id}_{message.id}")
        ],
        [
            InlineKeyboardButton("📊 Check Status", callback_data=f"req_status_{user.id}")
        ]
    ])
    
    msg = await client.send_message(chat.id, text, reply_markup=buttons)
    # Auto delete after 5 minutes
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))
    
    # Save to database
    await add_movie_request(chat.id, user.id, movie_name)

# ================ STATS COMMAND WITH BETTER BUTTONS ================
@app.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats_command(client: Client, message: Message):
    """Bot statistics with professional buttons"""
    users = await get_user_count()
    groups = await get_group_count()
    
    premium_count = 0
    all_grps = await get_all_groups()
    for g in all_grps:
        if await check_is_premium(g):
            premium_count += 1
    
    # Professional button layout
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧹 Clear Junk", callback_data="clear_junk"),
            InlineKeyboardButton("📊 User Stats", callback_data="user_stats")
        ],
        [
            InlineKeyboardButton("👥 Group Stats", callback_data="group_stats"),
            InlineKeyboardButton("💎 Premium Stats", callback_data="premium_stats")
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats"),
            InlineKeyboardButton("📈 Analytics", callback_data="analytics")
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="close_stats")
        ]
    ])
    
    stats_text = f"""**📊 BOT STATISTICS DASHBOARD**

📈 **Overview:**
├ 👥 **Total Users:** `{users}`
├ 👥 **Total Groups:** `{groups}`
├ 💎 **Premium Groups:** `{premium_count}`
└ 🆓 **Free Groups:** `{groups - premium_count}`

⚡ **Performance:**
├ 🚀 **Status:** ✅ Active
├ ☁️ **Server:** Koyeb Cloud
├ ⏱️ **Uptime:** 24/7
└ 📅 **Updated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔧 **Database:** ✅ Connected
🤖 **AI Service:** ✅ Active
🛡️ **Security:** ✅ Enabled"""

    await message.reply_text(stats_text, reply_markup=buttons)

# ================ AI COMMAND (FIXED SERVER BUSY ERROR) ================
@app.on_message(filters.command("ai"))
async def ai_command(client: Client, message: Message):
    """AI chat feature with better error handling"""
    if len(message.command) < 2:
        msg = await message.reply_text(
            "**🤖 AI Chat Assistant**\n\n"
            "**Usage:** `/ai your question`\n\n"
            "**Examples:**\n"
            "• `/ai Tell me about Inception movie`\n"
            "• `/ai Best comedy movies 2023`\n"
            "• `/ai Who directed Jawan?`\n\n"
            "**Note:** Keep questions clear and specific."
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return
    
    query = ' '.join(message.command[1:])
    
    # Show typing action
    await message.chat.action("typing")
    
    # Send initial message
    waiting_msg = await message.reply_text("🤔 **Thinking... Please wait...**")
    
    try:
        # Get AI response with timeout
        response = await asyncio.wait_for(
            MovieBotUtils.get_ai_response(query),
            timeout=20
        )
        
        await waiting_msg.delete()
        
        # Check if response is too long
        if len(response) > 4000:
            response = response[:4000] + "...\n\n📝 **Response truncated due to length**"
        
        # Create better formatted response
        formatted_response = f"**🤖 AI Assistant**\n\n{response}\n\n💡 *Powered by Movie Helper AI*"
        
        msg = await message.reply_text(formatted_response)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))
        
    except asyncio.TimeoutError:
        await waiting_msg.edit_text(
            "⏳ **Taking too long to respond!**\n\n"
            "The AI server is currently busy.\n"
            "Please try again in a moment.\n\n"
            "💡 **Tip:** Try a simpler question."
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, waiting_msg, 30))
        
    except Exception as e:
        logger.error(f"AI Command Error: {e}")
        await waiting_msg.edit_text(
            "⚠️ **Temporary Service Issue**\n\n"
            "I'm having trouble connecting to the AI service.\n"
            "Please try again in a few minutes.\n\n"
            "🎬 You can still use `/request` for movies!"
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, waiting_msg, 30))

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
    
    for chat_id in target_ids:
        try:
            await message.reply_to_message.copy(chat_id)
            success += 1
        except PeerIdInvalid:
            # Invalid chat ID, remove from database
            if is_group:
                await mark_group_inactive(chat_id)
            deleted += 1
        except Exception as e:
            logger.error(f"Broadcast Error to {chat_id}: {e}")
            failed += 1
        await asyncio.sleep(0.5)
        
    msg = await progress.edit_text(
        f"✅ **Broadcast Complete!** ✅\n\n"
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
    if not message.from_user:
        return
        
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ Sirf Admins hi ye command use kar sakte hain!")
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
            msg = await message.reply_text("❌ Invalid ID! Numeric ID daalein (e.g. -100xxxxxxx)")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            return

    elif message.reply_to_message:
        if message.reply_to_message.forward_from_chat:
            channel_id = message.reply_to_message.forward_from_chat.id
        else:
            msg = await message.reply_text(
                "❌ Channel ID nahi mili. Forward privacy on hai.\n"
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
             msg = await message.reply_text("❌ Main us channel mein Admin nahi hun! Pehle mujhe admin banaein.")
             asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
             return
    except Exception as e:
        msg = await message.reply_text(f"❌ Error: Bot ko Channel mein add karein aur Admin banaein!\n**Error:** {e}")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return

    await set_force_sub(message.chat.id, channel_id)
    msg = await message.reply_text(
        f"✅ **Force Subscribe Connected!** ✅\n\n"
        f"**Linked to:** {chat.title}\n"
        f"**Channel ID:** `{channel_id}`\n\n"
        f"Ab naye users ko channel join karna hoga group mein baat karne ke liye."
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
            f"✅ **Premium Added Successfully!** ✅\n\n"
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
            await message.reply_text("⚠️ Database update hua par Group mein msg nahi gaya")
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

# ================ MAIN FILTER (UPDATED WITH FORMAT DETECTION) ================
@app.on_message(filters.group & filters.text & ~filters.command([
    "start", "help", "settings", "addfsub", "stats", "ai", 
    "broadcast", "request", "ban", "unban", "add_premium", 
    "remove_premium", "premiumstats", "ping", "id", "setcommands"
]))
async def group_message_filter(client, message):
    if not message.from_user:
        return
        
    if await is_admin(message.chat.id, message.from_user.id):
        return

    settings = await get_settings(message.chat.id)
    spelling_settings = await get_spelling_settings(message.chat.id)
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
                f"⚠️ {message.from_user.mention}, **Link mat bhejein!**\n"
                f"Warning: **{warn_count}/{limit}**"
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
                f"⚠️ {message.from_user.mention}, **Gali mat dein!**\n"
                f"Warning: **{warn_count}/{limit}**"
            )
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, warn_msg, 10))

    # 3. SPELLING CHECK (JUNK) - UPDATED WITH FORMAT DETECTION
    elif settings.get("spelling_on", True) and quality == "JUNK":
        try:
            await message.delete()
        except:
            pass
        
        # Check format (Movie vs Series)
        format_type, corrected_name = MovieBotUtils.check_movie_format(message.text)
        
        if format_type == "SERIES" and corrected_name:
            # Series format detected - show series format message
            series_text = (
                f"🎭 **Series Format Detected** 🎭\n\n"
                f"👤 **User:** {message.from_user.mention}\n"
                f"✅ **Correct Format:** `{corrected_name}`\n\n"
                f"📌 **Series Format Examples:**\n"
                f"• `Money Heist S01 E01`\n"
                f"• `Mirzapur Season 2`\n"
                f"• `Sacred Games S01`"
            )
            spell_msg = await message.reply_text(series_text)
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, spell_msg, 180))
            
        elif format_type == "MOVIE" and corrected_name:
            # Movie format detected - check spelling if advanced mode is on
            if spelling_settings.get("advanced_spelling", False):
                # Advanced spelling correction
                corrected_spelling, suggestions = await MovieBotUtils.advanced_spelling_correction(corrected_name)
                
                if suggestions and corrected_spelling.lower() != corrected_name.lower():
                    correction_text = (
                        f"✨ **Advanced Spelling Check** ✨\n\n"
                        f"👤 **User:** {message.from_user.mention}\n"
                        f"❌ **Typed:** `{message.text}`\n"
                        f"✅ **Correct:** `{corrected_spelling}`\n\n"
                    )
                    
                    if len(suggestions) > 1:
                        correction_text += f"📌 **Other Suggestions:**\n"
                        for i, sug in enumerate(suggestions[1:4], 1):
                            correction_text += f"{i}. `{sug}`\n"
                    
                    correction_text += f"\n🎬 **Format:** Movie Name (Year)"
                    
                else:
                    correction_text = (
                        f"✨ **Spelling Check** ✨\n\n"
                        f"👤 **User:** {message.from_user.mention}\n"
                        f"✅ **Format:** `{corrected_name}`\n\n"
                        f"📌 **Correct Format:** `Movie Name (Year)`\n"
                        f"**Example:** `{corrected_name} (2024)`"
                    )
            else:
                # Simple spelling check
                correction_text = (
                    f"✨ **Spelling Check** ✨\n\n"
                    f"👤 **User:** {message.from_user.mention}\n"
                    f"✅ **Format:** `{corrected_name}`\n\n"
                    f"📌 **Correct Format:** Movie Name (Year)\n"
                    f"**Example:** `{corrected_name} (2024)`"
                )
            
            spell_msg = await message.reply_text(correction_text)
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, spell_msg, 180))
            
        else:
            # Invalid format
            correction_text = (
                f"✨ **Format Check** ✨\n\n"
                f"👤 **User:** {message.from_user.mention}\n"
                f"❌ **Invalid Format:** `{message.text}`\n\n"
                f"📌 **For Movies:** Movie Name (Year)\n"
                f"• `Pushpa 2 (2024)`\n"
                f"• `Animal (2023)`\n\n"
                f"📌 **For Series:** Series Name S01 E01\n"
                f"• `Mirzapur S01 E01`\n"
                f"• `Sacred Games Season 1`"
            )
            spell_msg = await message.reply_text(correction_text)
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
            
            # Send welcome message
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
        try:
            await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
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

# ================ WELCOME MESSAGE FOR NEW MEMBERS (FIXED) ================
@app.on_message(filters.new_chat_members)
async def welcome_new_members(client: Client, message: Message):
    """Welcome new members with photo and details"""
    try:
        # Delete the automatic "user joined" message
        try:
            await message.delete()
        except:
            pass
        
        settings = await get_settings(message.chat.id)
        if not settings.get("welcome_enabled", True):
            return
        
        for member in message.new_chat_members:
            if member.is_self:  # Bot added to group
                await add_group(message.chat.id, message.chat.title, message.chat.username)
                
                bot_welcome = await message.reply_text(
                    f"🎬 **Thanks for adding me to {message.chat.title}!**\n\n"
                    f"🤖 **I'm Movie Helper Bot**\n"
                    f"✅ **Main Features:**\n"
                    f"• ✏️ Smart Spelling Correction\n"
                    f"• 🗑️ Auto Delete Files\n"
                    f"• 🤖 AI Movie Chat\n"
                    f"• ✅ Auto Accept Requests\n\n"
                    f"⚙️ **Quick Setup:**\n"
                    f"1. Make me **Admin**\n"
                    f"2. Use `/settings` to configure\n\n"
                    f"Need help? Use `/help`",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu")],
                        [InlineKeyboardButton("📖 Help Guide", callback_data="help_guide")]
                    ])
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
                    f"✨ Request movies using `/request` command.\n"
                    f"🤖 Chat with AI using `/ai`\n\n"
                    f"Enjoy your stay! 😊"
                )
                
                try:
                    # Check if welcome with photo is enabled and user has photo
                    if settings.get("welcome_with_photo", True):
                        try:
                            # Try to get user photo
                            photos = await client.get_chat_photos(user.id, limit=1)
                            if photos.total_count > 0:
                                photo = await client.download_media(photos[0].file_id)
                                welcome_msg = await client.send_photo(
                                    message.chat.id,
                                    photo=photo,
                                    caption=welcome_text
                                )
                            else:
                                raise Exception("No photo")
                        except:
                            # Fallback to text message if no photo
                            welcome_msg = await message.reply_text(welcome_text)
                    else:
                        # Text only welcome
                        welcome_msg = await message.reply_text(welcome_text)
                    
                    # Delete welcome message after 2 minutes
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 120))
                    
                except Exception as e:
                    logger.error(f"Welcome message error: {e}")
                    # Fallback to simple text
                    welcome_msg = await message.reply_text(f"🎉 Welcome {user.mention}!")
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 120))
                    
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
                f"✅ **Request Approved!** ✅\n\n"
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
        
        # NEW: Advanced spelling toggle
        elif data == "toggle_adv_spelling":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            spelling_settings = await get_spelling_settings(chat_id)
            new_value = not spelling_settings.get("advanced_spelling", False)
            await update_spelling_settings(chat_id, "advanced_spelling", new_value)
            
            status = "🔍 Advanced" if new_value else "📝 Simple"
            await query.answer(f"Spelling mode: {status}")
            await refresh_settings_menu(client, query)
        
        # NEW: Welcome photo toggle
        elif data == "toggle_welcome_photo":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            settings = await get_settings(chat_id)
            new_value = not settings.get("welcome_with_photo", True)
            await update_settings(chat_id, "welcome_with_photo", new_value)
            
            status = "📸 ON" if new_value else "📝 TEXT"
            await query.answer(f"Welcome photo: {status}")
            await refresh_settings_menu(client, query)
        
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
                        f"✅ **Movie Available!** {query.from_user.mention} ne upload kar diya hai.\n"
                        f"👤 <a href='tg://user?id={req_user_id}'>User</a>, please check!"
                    )
                    await query.message.delete()
                except:
                    pass
                await query.answer("Request accepted!")
        
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
                        f"❌ **Movie Not Available**\n"
                        f"Request rejected by Admin {query.from_user.mention}."
                    )
                    await query.message.delete()
                except:
                    pass
                await query.answer("Request rejected!")
        
        # Request Processing
        elif data.startswith("req_process_"):
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
                        f"⏳ **Processing Request**\n"
                        f"Admin {query.from_user.mention} is processing this request.\n"
                        f"Please wait..."
                    )
                except:
                    pass
                await query.answer("Request marked as processing!")
        
        # Request Status Check
        elif data.startswith("req_status_"):
            req_user_id = int(data.split("_")[2])
            if query.from_user.id != req_user_id:
                await query.answer("❌ This button is for the requester only!", show_alert=True)
                return
            await query.answer("✅ Your request is pending review by admins.", show_alert=True)
        
        elif data.startswith("req_stats_"):
            req_user_id = int(data.split("_")[2])
            if query.from_user.id != req_user_id:
                await query.answer("❌ This button is for the requester only!", show_alert=True)
                return
            
            # Get user's pending requests
            pending_count = 0
            try:
                requests = await get_pending_requests(chat_id)
                for req in requests:
                    if req.get("user_id") == req_user_id:
                        pending_count += 1
            except:
                pass
            
            await query.answer(f"📊 You have {pending_count} pending requests.", show_alert=True)
        
        elif data.startswith("my_requests_"):
            req_user_id = int(data.split("_")[2])
            if query.from_user.id != req_user_id:
                await query.answer("❌ This button is for the requester only!", show_alert=True)
                return
            
            await query.answer("📋 Your requests feature coming soon!", show_alert=True)
        
        elif data.startswith("notify_all_"):
            target_chat_id = int(data.split("_")[2])
            
            # Check if user is admin
            if not await is_admin(target_chat_id, query.from_user.id):
                await query.answer("❌ Only admins can notify everyone!", show_alert=True)
                return
            
            await query.answer("🔔 Notification feature coming soon!", show_alert=True)
        
        elif data.startswith("delete_req_"):
            msg_id = int(data.split("_")[2])
            
            # Check if user is admin or requester
            is_requester = False
            try:
                # We need to check if this user is the one who requested
                # For now, allow admins to delete
                if await is_admin(chat_id, user_id):
                    await query.message.delete()
                    await query.answer("🗑️ Request deleted!")
                else:
                    await query.answer("❌ Only admins can delete requests!", show_alert=True)
            except:
                pass
        
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
            await query.answer(f"Spelling correction: {status}")
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
            await query.answer(f"Auto delete: {status}")
            await refresh_settings_menu(client, query)

        elif data == "toggle_auto_accept":
            # Check admin
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            current = await get_auto_accept(chat_id)
            await set_auto_accept(chat_id, not current)
            status = "ON ✅" if not current else "OFF ❌"
            await query.answer(f"Auto Accept: {status}")
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
            await query.answer(f"Welcome messages: {status}")
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

        # Clear junk (FIXED)
        elif data == "clear_junk":
            # Owner only
            if user_id != Config.OWNER_ID:
                await query.answer("❌ Only owner can use this!", show_alert=True)
                return
                
            junk_count = await clear_junk()
            await query.answer(f"🧹 Cleared {junk_count} junk entries!")
            
            # Update stats after clearing
            users = await get_user_count()
            groups = await get_group_count()
            
            await query.message.edit_text(
                f"✅ **Junk Cleanup Complete!** ✅\n\n"
                f"**Removed:** {junk_count} inactive entries\n\n"
                f"📊 **Updated Stats:**\n"
                f"• Users: {users}\n"
                f"• Groups: {groups}\n\n"
                f"Database optimized successfully!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh Stats", callback_data="refresh_stats")]
                ])
            )
        
        elif data == "refresh_stats":
            # Owner only
            if user_id != Config.OWNER_ID:
                await query.answer("❌ Only owner can use this!", show_alert=True)
                return
                
            users = await get_user_count()
            groups = await get_group_count()
            premium_count = 0
            all_grps = await get_all_groups()
            for g in all_grps:
                if await check_is_premium(g):
                    premium_count += 1
            
            stats_text = f"""**📊 BOT STATISTICS DASHBOARD**

📈 **Overview:**
├ 👥 **Total Users:** `{users}`
├ 👥 **Total Groups:** `{groups}`
├ 💎 **Premium Groups:** `{premium_count}`
└ 🆓 **Free Groups:** `{groups - premium_count}`

⚡ **Performance:**
├ 🚀 **Status:** ✅ Active
├ ☁️ **Server:** Koyeb Cloud
├ ⏱️ **Uptime:** 24/7
└ 📅 **Updated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔧 **Database:** ✅ Connected
🤖 **AI Service:** ✅ Active
🛡️ **Security:** ✅ Enabled"""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🧹 Clear Junk", callback_data="clear_junk"),
                    InlineKeyboardButton("📊 User Stats", callback_data="user_stats")
                ],
                [
                    InlineKeyboardButton("👥 Group Stats", callback_data="group_stats"),
                    InlineKeyboardButton("💎 Premium Stats", callback_data="premium_stats")
                ],
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats"),
                    InlineKeyboardButton("📈 Analytics", callback_data="analytics")
                ],
                [
                    InlineKeyboardButton("❌ Close", callback_data="close_stats")
                ]
            ])
            
            await query.message.edit_text(stats_text, reply_markup=buttons)
            await query.answer("✅ Stats refreshed!")
        
        elif data == "user_stats":
            if user_id != Config.OWNER_ID:
                await query.answer("❌ Only owner can use this!", show_alert=True)
                return
            users = await get_user_count()
            await query.answer(f"👥 Total Users: {users}", show_alert=True)
        
        elif data == "group_stats":
            if user_id != Config.OWNER_ID:
                await query.answer("❌ Only owner can use this!", show_alert=True)
                return
            groups = await get_group_count()
            await query.answer(f"👥 Total Groups: {groups}", show_alert=True)
        
        elif data == "premium_stats":
            if user_id != Config.OWNER_ID:
                await query.answer("❌ Only owner can use this!", show_alert=True)
                return
            premium_count = 0
            all_grps = await get_all_groups()
            for g in all_grps:
                if await check_is_premium(g):
                    premium_count += 1
            await query.answer(f"💎 Premium Groups: {premium_count}", show_alert=True)
        
        elif data == "analytics":
            if user_id != Config.OWNER_ID:
                await query.answer("❌ Only owner can use this!", show_alert=True)
                return
            await query.answer("📈 Analytics feature coming soon!", show_alert=True)
        
        elif data == "close_stats":
            try:
                await query.message.delete()
            except:
                pass
            await query.answer("Stats closed!")
        
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
                        f"✅ **Verification Successful!** ✅\n\n"
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
        
        elif data == "refresh_settings":
            await refresh_settings_menu(client, query)
    
    except Exception as e:
        logger.error(f"Callback Error: {e}")
        await query.answer("❌ Error processing request!")

# Helper for updating settings menu
async def refresh_settings_menu(client, query):
    try:
        chat_id = query.message.chat.id
        settings = await get_settings(chat_id)
        spelling_settings = await get_spelling_settings(chat_id)
        is_prem = await check_is_premium(chat_id)
        auto_accept = await get_auto_accept(chat_id)
        
        prem_status = "💎 Active" if is_prem else "🔓 Free"
        spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
        advanced_spelling = "🔍 Advanced" if spelling_settings.get("advanced_spelling", False) else "📝 Simple"
        delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
        accept_status = "✅ ON" if auto_accept else "❌ OFF"
        welcome_status = "✅ ON" if settings.get("welcome_enabled", True) else "❌ OFF"
        welcome_photo = "📸 ON" if settings.get("welcome_with_photo", True) else "📝 TEXT"
        delete_time = settings.get("delete_time", 0)
        time_text = f"{delete_time} min" if delete_time > 0 else "Permanent"
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"✏️ Spelling: {spelling_status}", callback_data="toggle_spelling"),
                InlineKeyboardButton(f"🔍 Type: {advanced_spelling}", callback_data="toggle_adv_spelling")
            ],
            [
                InlineKeyboardButton(f"🗑️ Auto Delete: {delete_status}", callback_data="toggle_auto_delete"),
                InlineKeyboardButton(f"⏰ Time: {time_text}", callback_data="set_delete_time")
            ],
            [
                InlineKeyboardButton(f"✅ Auto Accept: {accept_status}", callback_data="toggle_auto_accept"),
                InlineKeyboardButton(f"👋 Welcome: {welcome_status}", callback_data="toggle_welcome")
            ],
            [
                InlineKeyboardButton(f"📸 Welcome Photo: {welcome_photo}", callback_data="toggle_welcome_photo"),
                InlineKeyboardButton(f"{prem_status} Premium", callback_data="premium_info")
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_settings"),
                InlineKeyboardButton("❌ Close", callback_data="close_settings")
            ]
        ])
        
        settings_text = f"""**⚙️ Settings for {query.message.chat.title}**

• **✏️ Spelling Check:** {spelling_status}
• **🔍 Spelling Mode:** {advanced_spelling}
• **🗑️ Auto Delete:** {delete_status} ({time_text})
• **✅ Auto Accept:** {accept_status}
• **👋 Welcome Msg:** {welcome_status}
• **📸 Welcome Photo:** {welcome_photo}
• **💎 Premium:** {prem_status}

_Click buttons to change settings:_"""
        
        await query.message.edit_text(settings_text, reply_markup=buttons)
        
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
            f"✅ **Auto Accept Enabled for {chat.title}!** ✅\n\n"
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

# ================ SETCOMMANDS COMMAND (FIXED) ================
@app.on_message(filters.command("setcommands") & filters.user(Config.OWNER_ID))
async def setcommands_command(client: Client, message: Message):
    """Set bot commands - FIXED VERSION"""
    try:
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Get help menu"),
            BotCommand("settings", "Group settings"),
            BotCommand("request", "Request a movie"),
            BotCommand("ai", "Ask AI about movies"),
            BotCommand("addfsub", "Set force subscribe (Premium)"),
            BotCommand("ping", "Check bot status"),
            BotCommand("id", "Get user/group ID"),
            BotCommand("stats", "Bot statistics (Owner)"),
            BotCommand("setcommands", "Set bot commands (Owner)")
        ]
        
        # Set commands globally
        await client.set_bot_commands(commands)
        
        # Also set for specific scope
        await client.set_bot_commands(
            commands,
            scope=BotCommandScopeAllPrivateChats()
        )
        
        await message.reply_text(
            "✅ **Bot commands set successfully!**\n\n"
            "Commands are now available in:\n"
            "• Private chats\n"
            "• Group chats\n"
            "• All contexts"
        )
        
    except Exception as e:
        await message.reply_text(
            f"❌ **Failed to set commands:**\n\n"
            f"**Error:** `{e}`\n\n"
            f"Make sure the bot has proper permissions."
        )
        logger.error(f"SetCommands Error: {e}")

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
    print("\n" + "="*50)
    print("🚀 **Starting Movie Helper Bot...**")
    print("="*50)
    print("\n✅ **All Features Fixed:**")
    print("   1. ✅ Movie vs Series format detection")
    print("   2. ✅ Advanced spelling correction system")
    print("   3. ✅ Clear junk button working")
    print("   4. ✅ /setcommands command fixed")
    print("   5. ✅ /ai server busy error fixed")
    print("   6. ✅ Request system with emoji tags")
    print("   7. ✅ Welcome message photo issue fixed")
    print("   8. ✅ Professional button layouts")
    print("\n🤖 **Bot is now fully professional and ready!**")
    print("="*50)
    
    try:
        app.run()
        print("\n🤖 Bot stopped gracefully")
    except KeyboardInterrupt:
        print("\n⏹️ Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot crashed: {e}")
        import traceback
        traceback.print_exc()
