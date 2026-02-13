import asyncio
import logging
import re
import datetime
import time
import sys
import traceback
from typing import Optional, Dict, List

from pyrogram import Client, filters, idle
from pyrogram.enums import ChatMemberStatus, ChatType, ChatAction
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, ChatMemberUpdated, ChatPermissions, ChatJoinRequest,
    BotCommand, BotCommandScopeAllGroupChats
)
from pyrogram.errors import (
    FloodWait, UserNotParticipant, ChatAdminRequired, 
    PeerIdInvalid, UserIsBlocked, InputUserDeactivated
)

from config import Config
from database import *
from utils import MovieBotUtils

# ================ SETUP ================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Pyrogram Client
app = Client(
    name="movie_helper_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    in_memory=True,
    workers=20,
    plugins=dict(root="plugins")  # Optional: for modular structure
)

# Global caches
fsub_cache = {}
admin_cache = {}
user_cache = {}
spam_cache = {}

# ================ HELPER FUNCTIONS ================
async def is_admin(chat_id: int, user_id: int) -> bool:
    """Check if user is admin (with caching)"""
    if user_id == Config.OWNER_ID:
        return True
    
    cache_key = f"{chat_id}_{user_id}"
    if cache_key in admin_cache:
        is_admin_val, expiry = admin_cache[cache_key]
        if expiry > datetime.datetime.now():
            return is_admin_val
    
    try:
        member = await app.get_chat_member(chat_id, user_id)
        is_admin_val = member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
        admin_cache[cache_key] = (is_admin_val, datetime.datetime.now() + datetime.timedelta(minutes=5))
        return is_admin_val
    except Exception as e:
        logger.error(f"Admin check error: {e}")
        return False

async def is_banned(user_id: int) -> bool:
    """Check if user is banned"""
    user = await get_user(user_id)
    return user and user.get("banned", False)

async def is_blacklisted_global(user_id: int) -> bool:
    """Check if user is globally blacklisted"""
    return await is_blacklisted(user_id)

async def show_typing(chat_id: int, duration: int = 1):
    """Show typing action"""
    try:
        await app.send_chat_action(chat_id, ChatAction.TYPING)
        await asyncio.sleep(duration)
    except:
        pass

async def safe_send_message(chat_id: int, text: str, **kwargs):
    """Send message with error handling"""
    try:
        return await app.send_message(chat_id, text, **kwargs)
    except FloodWait as e:
        logger.warning(f"Flood wait: {e.value}s")
        await asyncio.sleep(e.value)
        return await app.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logger.error(f"Error sending message to {chat_id}: {e}")
        return None

# ================ INIT DATABASE ================
@app.on_startup()
async def startup_tasks():
    """Run on bot startup"""
    logger.info("Running startup tasks...")
    
    # Create database indexes
    await init_db()
    
    # Set bot commands
    await set_bot_commands()
    
    # Clear old caches
    MovieBotUtils.clean_cache()
    MovieBotUtils.clean_rate_limits()
    
    logger.info("Startup tasks completed!")

async def set_bot_commands():
    """Set bot commands"""
    commands = [
        BotCommand("start", "🤖 Bot start karo"),
        BotCommand("help", "📚 Help aur commands"),
        BotCommand("request", "🎬 Movie request karo"),
        BotCommand("ai", "🤖 AI se movie pucho"),
        BotCommand("google", "🔍 Google search"),
        BotCommand("anime", "🇯🇵 Anime search"),
        BotCommand("motd", "🎥 Aaj ki movie"),
        BotCommand("ping", "🏓 Bot check"),
        BotCommand("id", "🆔 ID dekho"),
        BotCommand("settings", "⚙️ Group settings (Admin)"),
        BotCommand("addfsub", "📢 Force subscribe (Premium)"),
        BotCommand("cleanjoin", "🧹 Join message delete"),
        BotCommand("setwelcome", "👋 Welcome set karo"),
        BotCommand("rules", "📜 Group rules dekho"),
        BotCommand("notes", "📝 Saved notes"),
        BotCommand("filters", "🔍 Custom filters"),
        BotCommand("stats", "📊 Bot statistics"),
    ]
    
    try:
        await app.set_bot_commands(commands, scope=BotCommandScopeAllGroupChats())
        logger.info("Bot commands set successfully")
    except Exception as e:
        logger.error(f"Error setting commands: {e}")

# ================ 1. START COMMAND ================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    user = message.from_user
    
    # Add user to database
    await add_user(user.id, user.username, user.first_name, user.last_name)
    
    # Check if user is banned
    if await is_banned(user.id):
        await message.reply_text("❌ **You are banned!** Contact @asbhai_bsr for more info.")
        return
    
    # Check for deep linking
    if len(message.command) > 1:
        deep_link = message.command[1]
        
        if deep_link.startswith("req_"):
            # Handle request deep link
            await message.reply_text(
                "🎬 **Movie Request**\n\n"
                "Please send me the movie name you want to request.\n"
                "Example: `Inception` or `3 Idiots`"
            )
            return
    
    # Welcome message
    text = f"""🎬 **Namaste {user.first_name}!** 🙏

Main hoon aapka **personal movie assistant**! 
Groups ke liye bana hoon, movies dhundhne mein help karta hoon.

✨ **Kya kya kar sakta hoon?**

✅ Movie requests handle karna
✅ Spelling check + OMDb search
✅ Bio mein link ho to action
✅ Auto accept join requests
✅ Force subscribe (premium)
✅ AI se movie baat cheet
✅ Custom filters & notes
✅ Anti-spam protection

👇 **Group mein add karo aur enjoy karo!** 🚀"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Group Mein Add Karo", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [
            InlineKeyboardButton("📚 Commands", callback_data="help_menu"),
            InlineKeyboardButton("👑 Owner", url=f"https://t.me/{Config.OWNER_USERNAME}")
        ],
        [InlineKeyboardButton("💎 Premium Features", callback_data="premium_info")]
    ])
    
    await message.reply_text(text, reply_markup=buttons, disable_web_page_preview=True)

# ================ 2. HELP COMMAND ================
@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    text = """╔══════════════════════════╗
          🆘  HELP MENU  🆘  
╚══════════════════════════╝

**👤 SAB KE LIYE:**
• /start - Bot start
• /help - Yeh menu
• /request <movie> - Movie mango
• /ai <question> - AI se pucho
• /google <query> - Google search
• /anime <name> - Anime search
• /motd - Aaj ki movie
• /ping - Bot status
• /id - ID dekho
• /rules - Group rules

**👑 ADMIN KE LIYE:**
• /settings - Bot settings
• /addfsub - Force subscribe
• /cleanjoin - Join msg delete
• /setwelcome - Welcome set
• /filter - Add custom filter
• /notes - Manage notes
• /stats - Group stats

**💎 PREMIUM:**
Force Subscribe, No Ads, Priority Support

❓ **Koi problem?** @asbhai_bsr ko msg karo!"""
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 Examples", callback_data="help_examples"),
            InlineKeyboardButton("⚙️ Settings Guide", callback_data="help_settings")
        ],
        [
            InlineKeyboardButton("💎 Premium", callback_data="premium_info"),
            InlineKeyboardButton("📊 Stats", callback_data="bot_stats")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])
    
    await message.reply_text(text, reply_markup=buttons, disable_web_page_preview=True)

# ================ 3. SETTINGS COMMAND ================
@app.on_message(filters.command("settings") & filters.group)
async def settings_command(client: Client, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ **Sorry!** Sirf admin hi settings change kar sakte hain.")
        await MovieBotUtils.auto_delete_message(client, msg, 5)
        return
    
    await show_settings_menu(client, message, is_new=True)

async def show_settings_menu(client, message_or_query, is_new=False):
    """Display settings panel"""
    if is_new:
        message = message_or_query
        chat_id = message.chat.id
    else:
        message = message_or_query.message
        chat_id = message.chat.id
    
    settings = await get_settings(chat_id)
    auto_acc = await get_auto_accept(chat_id)
    is_premium = await check_is_premium(chat_id)
    
    # Status emojis
    def status_emoji(val): return "✅" if val else "❌"
    
    s_spell = status_emoji(settings.get("spelling_on", True))
    s_bio = status_emoji(settings.get("bio_check", True))
    s_clean = status_emoji(settings.get("clean_join", True))
    s_auto = status_emoji(auto_acc)
    s_ai = status_emoji(settings.get("ai_chat_on", False))
    s_antispam = status_emoji(settings.get("antispam", True))
    s_linkfilter = status_emoji(settings.get("link_filter", True))
    s_abusefilter = status_emoji(settings.get("bad_words_filter", True))
    
    mode = "📊 Advanced" if settings.get("spelling_mode") == "advanced" else "📝 Simple"
    
    premium_badge = "⭐ PREMIUM" if is_premium else "FREE"
    
    text = f"""╔══════════════════════════╗
        ⚙️  SETTINGS  ⚙️  
╚══════════════════════════╝

**Group:** {message.chat.title}
**Status:** {premium_badge}

📝 **Spelling Check:** {s_spell} ({mode})
🛡️ **Bio Protection:** {s_bio}
🔗 **Link Filter:** {s_linkfilter}
🚫 **Abuse Filter:** {s_abusefilter}
⚡ **Anti-Spam:** {s_antispam}
🧹 **Clean Join:** {s_clean}
🤖 **AI Chat:** {s_ai}
⚡ **Auto Accept:** {s_auto}

⬇️ **Option select karo:**"""
    
    buttons = [
        [InlineKeyboardButton(f"📝 Spelling ({s_spell})", callback_data="spelling_menu")],
        [InlineKeyboardButton(f"🛡️ Bio Protection ({s_bio})", callback_data="bio_menu")],
        [
            InlineKeyboardButton(f"⚡ Auto Accept", callback_data="toggle_auto_accept"),
            InlineKeyboardButton(f"🧹 Clean Join", callback_data="toggle_cleanjoin")
        ],
        [
            InlineKeyboardButton(f"🤖 AI Chat ({s_ai})", callback_data="toggle_ai"),
            InlineKeyboardButton(f"🔗 Links ({s_linkfilter})", callback_data="toggle_linkfilter")
        ],
        [
            InlineKeyboardButton(f"🚫 Abuse ({s_abusefilter})", callback_data="toggle_abusefilter"),
            InlineKeyboardButton(f"⚡ AntiSpam ({s_antispam})", callback_data="toggle_antispam")
        ],
        [InlineKeyboardButton("📊 Advanced Settings", callback_data="advanced_settings")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ]
    
    reply_markup = InlineKeyboardMarkup(buttons)

    if is_new:
        msg = await message.reply_text(text, reply_markup=reply_markup)
        await MovieBotUtils.auto_delete_message(client, msg, 300)
    else:
        await message.edit_text(text, reply_markup=reply_markup)

# ================ 4. REQUEST HANDLER ================
@app.on_message((filters.command("request") | filters.regex(r'^#request\s+', re.IGNORECASE)) & filters.group)
async def request_handler(client: Client, message: Message):
    """Handle movie requests with admin tagging"""
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Check if user is banned
    if await is_banned(user_id):
        await message.delete()
        return
    
    # Rate limiting
    if not MovieBotUtils.check_rate_limit(user_id, "request", limit=3, period=60):
        msg = await message.reply_text("⏳ **Slow down!** 1 minute mein sirf 3 requests kar sakte ho.")
        await MovieBotUtils.auto_delete_message(client, msg, 5)
        return
    
    # Extract movie name
    if message.text.startswith("/"):
        if len(message.command) < 2:
            msg = await message.reply_text(
                "❌ **Usage:** `/request Movie Name`\n\n"
                "✅ Example: `/request Kalki 2898 AD`"
            )
            await MovieBotUtils.auto_delete_message(client, msg, 5)
            return
        movie_name = " ".join(message.command[1:])
    else:
        movie_name = message.text.split('#request', 1)[1].strip()
    
    if not movie_name:
        return
    
    # Validate movie format
    validation = MovieBotUtils.validate_movie_format_advanced(movie_name)
    movie_display = validation['correct_format'] or validation['clean_name']
    
    # Add request to database
    request_id = await add_movie_request(chat_id, user_id, validation['clean_name'])
    
    # Get admin mentions
    admin_tags = await MovieBotUtils.get_admin_mentions(client, chat_id)
    
    # Request message
    text = f"""╔══════════════════════════╗
        🎬  MOVIE REQUEST  🎬  
╚══════════════════════════╝

**📽️ Movie:** `{movie_display}`

**👤 Requester:** {message.from_user.mention}
**🆔 ID:** `{user_id}`

**📊 Details:**
• Year: {validation['year'] or 'N/A'}
• Quality: {validation['quality'] or 'N/A'}
• Language: {validation['language'] or 'N/A'}

**👑 Admins:**
{admin_tags}

━━━━━━━━━━━━━━━━━━━━━
_Admins please check karo aur action lo! 🙏_"""
    
    # Action buttons
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Upload Ho Gayi", callback_data=f"req_accept_{request_id}_{user_id}")],
        [InlineKeyboardButton("❌ Available Nahi Hai", callback_data=f"req_reject_{request_id}_{user_id}")],
        [InlineKeyboardButton("🔍 OMDb Search", callback_data=f"omdb_{validation['clean_name']}")]
    ])
    
    await client.send_message(chat_id, text, reply_markup=buttons)
    
    # Delete user's message
    try:
        await message.delete()
    except:
        pass
    
    # Log to channel
    if Config.LOG_CHANNEL:
        try:
            await client.send_message(
                Config.LOG_CHANNEL,
                f"📨 **New Request**\n"
                f"Group: {message.chat.title} (`{chat_id}`)\n"
                f"Movie: {movie_display}\n"
                f"User: {message.from_user.mention} (`{user_id}`)"
            )
        except Exception as e:
            logger.error(f"Log channel error: {e}")

# ================ 5. AI COMMAND ================
@app.on_message(filters.command("ai"))
async def ai_command(client: Client, message: Message):
    if len(message.command) < 2:
        msg = await message.reply_text(
            "❌ **Usage:** `/ai your question`\n\n"
            "✅ **Examples:**\n"
            "• `/ai Inception movie ka story kya hai?`\n"
            "• `/ai Best action movies 2024`\n"
            "• `/ai Suggest me a comedy movie`"
        )
        await MovieBotUtils.auto_delete_message(client, msg, 30)
        return
    
    query = ' '.join(message.command[1:])
    
    # Rate limiting
    if not MovieBotUtils.check_rate_limit(message.from_user.id, "ai", limit=5, period=60):
        msg = await message.reply_text("⏳ **Slow down!** Thoda休息 karo!")
        await MovieBotUtils.auto_delete_message(client, msg, 5)
        return
    
    await show_typing(message.chat.id)
    waiting_msg = await message.reply_text("💭 **Soch raha hoon...**")
    
    # Get context if in group
    context = ""
    if message.chat.type != ChatType.PRIVATE:
        context = f"Group: {message.chat.title}"
    
    response = await MovieBotUtils.get_ai_response(query, context)
    
    await waiting_msg.delete()
    msg = await message.reply_text(response)
    await MovieBotUtils.auto_delete_message(client, msg, 300)

# ================ 6. GOOGLE SEARCH ================
@app.on_message(filters.command("google"))
async def google_search_cmd(client, message):
    if len(message.command) < 2:
        await message.reply_text("❌ **Usage:** /google search query")
        return
    
    query = " ".join(message.command[1:])
    
    # Rate limiting
    if not MovieBotUtils.check_rate_limit(message.from_user.id, "google", limit=5, period=60):
        msg = await message.reply_text("⏳ **Slow down!** Thoda休息 karo!")
        await MovieBotUtils.auto_delete_message(client, msg, 5)
        return
    
    msg = await message.reply_text("🔍 **Google search ho raha hai...**")
    
    results = await MovieBotUtils.get_google_search(query)
    
    if not results:
        await msg.edit_text(
            "❌ **Koi result nahi mila!**\n\n"
            "🔍 Different keywords try karo ya spelling check karo."
        )
        return
    
    text = f"🔍 **Search Results for:** {query}\n\n"
    for i, (href, title) in enumerate(results[:5], 1):
        text += f"{i}. [{title}]({href})\n"
    
    await msg.edit_text(text, disable_web_page_preview=True)

# ================ 7. ANIME SEARCH ================
@app.on_message(filters.command("anime"))
async def anime_search_cmd(client, message):
    if len(message.command) < 2:
        await message.reply_text("❌ **Usage:** /anime Anime Name")
        return
    
    query = " ".join(message.command[1:])
    
    # Rate limiting
    if not MovieBotUtils.check_rate_limit(message.from_user.id, "anime", limit=10, period=60):
        msg = await message.reply_text("⏳ **Slow down!** Thoda休息 karo!")
        await MovieBotUtils.auto_delete_message(client, msg, 5)
        return
    
    msg = await message.reply_text("🇯🇵 **Anime search ho raha hai...**")
    
    data = await MovieBotUtils.get_anime_info(query)
    
    if data:
        # Format genres
        genres = ", ".join(data['genres'][:3]) if data['genres'] else "N/A"
        
        text = (
            f"🎬 **{data['title']}**\n\n"
            f"⭐ **Rating:** {data['score']}/10 ({MovieBotUtils.format_number(data['scored_by'])} votes)\n"
            f"📊 **Rank:** #{data['rank']} | **Popularity:** #{data['popularity']}\n"
            f"📺 **Episodes:** {data['episodes']}\n"
            f"🎭 **Genres:** {genres}\n"
            f"🏢 **Studio:** {', '.join(data['studios'][:2]) if data['studios'] else 'N/A'}\n"
            f"📅 **Aired:** {data['aired']}\n"
            f"📝 **Story:** {data['synopsis']}"
        )
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 More Info on MyAnimeList", url=data['url'])]
        ])
        
        await msg.edit_text(text, reply_markup=buttons, disable_web_page_preview=True)
    else:
        await msg.edit_text("❌ **Anime nahi mila!** Spelling check karo ya full name likho.")

# ================ 8. MOVIE OF THE DAY ================
@app.on_message(filters.command(["movieoftheday", "motd"]))
async def movie_of_the_day(client: Client, message: Message):
    msg = await message.reply_text("🎬 **Aaj ki movie dhundh raha hoon...**")
    
    movie = await MovieBotUtils.get_random_movie()
    
    if movie:
        text = (
            f"🎬 **MOVIE OF THE DAY** 🎬\n\n"
            f"📽️ **{movie['title']}** ({movie['year']})\n"
            f"🎭 **Genre:** {movie['genre']}\n"
            f"⭐ **IMDb:** {movie['rating']}/10\n\n"
            f"📝 **Plot:** {movie['plot']}\n\n"
            f"📅 **Date:** {datetime.datetime.now().strftime('%d %B %Y')}\n\n"
            f"💡 **Request karo:** `/request {movie['title']}`\n\n"
            f"**Happy Watching!** 🍿"
        )
        
        await msg.edit_text(text)
    else:
        await msg.edit_text(
            "❌ **Aaj ki movie nahi mil sakti!**\n\n"
            "Thodi der baad try karo ya /request use karo."
        )

# ================ 9. PING COMMAND ================
@app.on_message(filters.command("ping"))
async def ping_command(client: Client, message: Message):
    start = time.time()
    msg = await message.reply_text("🏓 **Pinging...**")
    end = time.time()
    ping = round((end - start) * 1000, 2)
    
    # Get MongoDB ping
    db_start = time.time()
    await get_user_count()
    db_end = time.time()
    db_ping = round((db_end - db_start) * 1000, 2)
    
    await msg.edit_text(
        f"🏓 **Pong!**\n\n"
        f"📡 **Bot:** `{ping}ms`\n"
        f"🗄️ **Database:** `{db_ping}ms`"
    )

# ================ 10. ID COMMAND ================
@app.on_message(filters.command("id"))
async def id_command(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else "Unknown"
    text = f"👤 **Your ID:** `{user_id}`\n"
    
    if message.reply_to_message:
        replied_user = message.reply_to_message.from_user
        if replied_user:
            text += f"👤 **Replied User ID:** `{replied_user.id}`\n"
    
    if message.chat.type != ChatType.PRIVATE:
        text += f"👥 **Group ID:** `{message.chat.id}`\n"
    
    await message.reply_text(text)

# ================ 11. RULES COMMAND ================
@app.on_message(filters.command("rules") & filters.group)
async def rules_command(client: Client, message: Message):
    chat_id = message.chat.id
    rules = await get_rules(chat_id)
    
    if rules:
        text = f"📜 **Group Rules:**\n\n{rules}"
    else:
        text = "❌ **Koi rules set nahi hain!**\n\nAdmin /setrules use karke rules set kar sakte hain."
    
    await message.reply_text(text)

# ================ 12. SET RULES COMMAND ================
@app.on_message(filters.command("setrules") & filters.group)
async def set_rules_command(client: Client, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ Sirf admins!")
        return
    
    if len(message.command) < 2 and not message.reply_to_message:
        await message.reply_text(
            "❌ **Usage:**\n"
            "`/setrules Rule 1, Rule 2, ...`\n"
            "Ya kisi message ko reply karo `/setrules` se"
        )
        return
    
    if message.reply_to_message:
        rules_text = message.reply_to_message.text or message.reply_to_message.caption
    else:
        rules_text = message.text.split(None, 1)[1]
    
    await set_rules(message.chat.id, rules_text)
    await message.reply_text("✅ **Group rules set ho gaye!**")

# ================ 13. BIO PROTECTION HANDLER ================
@app.on_chat_member_updated(filters.group)
async def check_new_member_bio(client: Client, update: ChatMemberUpdated):
    """Check new member's bio for security issues"""
    if not update.new_chat_member:
        return
    
    # Only for new members joining
    if update.new_chat_member.status == ChatMemberStatus.MEMBER:
        # Check if it's a new join (not an update)
        if update.old_chat_member and update.old_chat_member.status in [ChatMemberStatus.RESTRICTED, ChatMemberStatus.MEMBER]:
            return
        
        user = update.new_chat_member.user
        chat_id = update.chat.id
        
        # Skip bots and self
        if user.is_bot or user.is_self:
            return
        
        # Get settings
        settings = await get_settings(chat_id)
        if not settings.get("bio_check", True):
            return
        
        try:
            # Get full user info with bio
            full_user = await client.get_chat(user.id)
            bio = full_user.bio or ""
            
            # Deep scan bio
            bio_check = MovieBotUtils.check_bio_safety_deep(bio)
            
            if not bio_check["safe"]:
                # Add warning
                warnings = await add_bio_warning(chat_id, user.id)
                bio_action = settings.get("bio_action", "mute")
                
                # Determine action based on warnings and settings
                action_msg = None
                
                if warnings >= 3 and bio_action == "ban":
                    try:
                        await client.ban_chat_member(chat_id, user.id)
                        action_msg = f"🚫 **{user.first_name}** ko ban kar diya!\nReason: Bio mein {', '.join(bio_check['issues'])}"
                    except:
                        pass
                
                elif warnings >= 2 or bio_action == "mute":
                    try:
                        mute_time = datetime.datetime.now() + datetime.timedelta(hours=1)
                        await client.restrict_chat_member(
                            chat_id, user.id,
                            ChatPermissions(can_send_messages=False),
                            until_date=mute_time
                        )
                        action_msg = f"🔇 **{user.first_name}** ko 1 hour mute!\nReason: Bio mein {', '.join(bio_check['issues'])}"
                    except:
                        pass
                
                else:
                    action_msg = f"⚠️ **{user.first_name}**, aapki bio mein {', '.join(bio_check['issues'])} hai.\nPlease remove karo!"
                
                if action_msg:
                    warn_msg = await client.send_message(chat_id, action_msg)
                    await MovieBotUtils.auto_delete_message(client, warn_msg, 30)
                    
        except Exception as e:
            logger.error(f"Bio Check Error: {e}")

# ================ 14. FORCE SUBSCRIBE HANDLER ================
@app.on_chat_member_updated(filters.group)
async def handle_fsub_join(client: Client, update: ChatMemberUpdated):
    """Handle force subscribe for new members"""
    if not update.new_chat_member:
        return
    
    # Only for new joins
    if update.old_chat_member and update.old_chat_member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
        return
    
    user = update.new_chat_member.user
    chat_id = update.chat.id
    
    if user.is_bot or user.is_self:
        return
    
    # Check force subscribe
    fsub_data = await get_force_sub(chat_id)
    if not fsub_data:
        return
    
    channel_id = fsub_data["channel_id"]
    channel_title = fsub_data.get("channel_title", "Channel")
    
    # Check if already joined
    cache_key = f"fsub_{user.id}_{channel_id}"
    if cache_key in fsub_cache:
        return
    
    is_joined = await MovieBotUtils.check_fsub_member(client, channel_id, user.id)
    
    if is_joined:
        fsub_cache[cache_key] = datetime.datetime.now()
        return
    
    # Mute user
    try:
        await client.restrict_chat_member(
            chat_id, user.id,
            ChatPermissions(can_send_messages=False)
        )
        
        # Get channel invite link
        try:
            chat_info = await client.get_chat(channel_id)
            channel_name = chat_info.title
            link = chat_info.invite_link or f"https://t.me/{chat_info.username}"
        except:
            channel_name = channel_title
            link = f"https://t.me/{Config.OWNER_USERNAME}"
        
        # Send force sub message
        text = f"""🔒 **Group Locked!**

Hello **{user.first_name}**! 👋

Is group mein message karne ke liye 
pehle hamara **channel join karna hoga**:

📢 **{channel_name}**

✅ Channel join karo
✅ "✅ Verified" button dabao
✅ Phir message kar sakoge

_Join karne ke baad auto-unmute ho jaoge!_ 🎉"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=link)],
            [InlineKeyboardButton("✅ Verified", callback_data=f"fsub_verify_{user.id}")]
        ])
        
        msg = await client.send_message(chat_id, text, reply_markup=buttons)
        await MovieBotUtils.auto_delete_message(client, msg, 300)
        
    except Exception as e:
        logger.error(f"FSub Error: {e}")

# ================ 15. AUTO ACCEPT JOIN REQUESTS ================
@app.on_chat_join_request()
async def auto_approve_join(client: Client, request: ChatJoinRequest):
    """Auto accept join requests"""
    chat_id = request.chat.id
    user_id = request.from_user.id
    
    # Check if user is banned
    if await is_banned(user_id) or await is_blacklisted_global(user_id):
        try:
            await client.decline_chat_join_request(chat_id, user_id)
        except:
            pass
        return
    
    should_approve = False
    
    # Channel always approve
    if request.chat.type == ChatType.CHANNEL:
        should_approve = True
    else:
        # Group check settings
        if await get_auto_accept(chat_id):
            should_approve = True
    
    if should_approve:
        try:
            await client.approve_chat_join_request(chat_id, user_id)
            
            # Send welcome PM
            text = f"""🎉 **Request Approved!**

Hello **{request.from_user.first_name}**! 🙏

Aapki join request **{request.chat.title}** 
approve ho gayi hai.

✅ Ab aap chat kar sakte ho!
🎬 Enjoy aur rules follow karo!

_Thank you for joining!_ ❤️"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 Open Chat", url=request.chat.invite_link or f"https://t.me/{request.chat.username}")]
            ])
            
            try:
                await client.send_message(user_id, text, reply_markup=buttons)
            except:
                pass
            
            # Log
            if Config.LOG_CHANNEL:
                await client.send_message(
                    Config.LOG_CHANNEL,
                    f"⚡ **Auto Accept**\n"
                    f"User: {request.from_user.mention} (`{user_id}`)\n"
                    f"Chat: {request.chat.title} (`{chat_id}`)"
                )
                
        except Exception as e:
            logger.error(f"Auto Accept Error: {e}")

# ================ 16. WELCOME NEW MEMBERS ================
@app.on_message(filters.new_chat_members)
async def welcome_new_members(client, message):
    """Welcome new members with custom message and sticker"""
    try:
        await message.delete()
    except:
        pass
    
    chat_id = message.chat.id
    settings = await get_settings(chat_id)
    
    if not settings.get("welcome_enabled", True):
        return
    
    custom_welcome = await get_welcome_message(chat_id)
    is_premium = await check_is_premium(chat_id)
    
    for member in message.new_chat_members:
        if member.is_self:
            continue
        
        # Skip bots
        if member.is_bot:
            continue
        
        # Get user photo
        user_photo_bytes = None
        if member.photo:
            try:
                photo = await client.download_media(member.photo.big_file_id, in_memory=True)
                user_photo_bytes = photo.getvalue()
            except:
                pass
        
        # Prepare welcome text
        if custom_welcome and custom_welcome.get('text'):
            welcome_text = custom_welcome['text']
            welcome_text = welcome_text.replace("{name}", member.first_name)
            welcome_text = welcome_text.replace("{chat}", message.chat.title)
            welcome_text = welcome_text.replace("{mention}", member.mention)
        else:
            welcome_text = f"""👋 **Welcome {member.first_name}!** 🎉

Aap **{message.chat.title}** mein add hue ho!

📌 **Rules yaad rakho:**
• No spam/abuse
• No links without permission
• Movie request: /request Movie Name

**Enjoy your stay!** ❤️"""
        
        # Try to send welcome sticker with photo
        sent = False
        
        if user_photo_bytes and settings.get("welcome_photo", True):
            sticker = await MovieBotUtils.create_welcome_sticker(
                user_photo_bytes, 
                message.chat.title, 
                Config.BOT_USERNAME,
                member.first_name,
                is_premium
            )
            
            if sticker:
                try:
                    await client.send_photo(chat_id, photo=sticker, caption=welcome_text)
                    sent = True
                except:
                    pass
        
        # Fallback
        if not sent:
            if custom_welcome and custom_welcome.get('photo_id'):
                try:
                    await client.send_photo(chat_id, photo=custom_welcome['photo_id'], caption=welcome_text)
                    sent = True
                except:
                    pass
            
            if not sent:
                await client.send_message(chat_id, welcome_text)

# ================ 17. GROUP MESSAGE FILTER ================
@app.on_message(filters.group & filters.text & ~filters.command([
    "start", "help", "settings", "request", "setwelcome", "addfsub", "stats", 
    "ai", "google", "anime", "cleanjoin", "ping", "id", "motd", "rules",
    "setrules", "filter", "filters", "note", "notes", "warn", "unwarn"
]))
async def group_message_filter(client, message):
    """Filter group messages for security and spam"""
    if not message.from_user:
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text
    
    # Check if user is banned
    if await is_banned(user_id) or await is_blacklisted_global(user_id):
        await message.delete()
        return
    
    # Admin bypass
    if await is_admin(chat_id, user_id):
        return
    
    settings = await get_settings(chat_id)
    
    # 1. ANTI-SPAM CHECK
    if settings.get("antispam", True):
        spam_count = await add_spam_count(user_id)
        
        if spam_count > 10:  # Too many messages
            try:
                await client.restrict_chat_member(
                    chat_id, user_id,
                    ChatPermissions(can_send_messages=False),
                    until_date=datetime.datetime.now() + datetime.timedelta(hours=1)
                )
                msg = await message.reply_text(f"🚫 **{message.from_user.first_name}** ko spam ke liye mute kiya!")
                await MovieBotUtils.auto_delete_message(client, msg, 10)
                await message.delete()
            except:
                pass
            return
    
    # 2. FORCE SUBSCRIBE CHECK (for existing members)
    fsub_data = await get_force_sub(chat_id)
    if fsub_data:
        channel_id = fsub_data["channel_id"]
        cache_key = f"fsub_{user_id}_{channel_id}"
        
        # Check cache first
        if cache_key not in fsub_cache:
            try:
                member = await client.get_chat_member(channel_id, user_id)
                if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                    await message.delete()
                    
                    # Get channel info
                    try:
                        chat_info = await client.get_chat(channel_id)
                        link = chat_info.invite_link or f"https://t.me/{chat_info.username}"
                        channel_name = chat_info.title
                    except:
                        link = f"https://t.me/{Config.OWNER_USERNAME}"
                        channel_name = "Channel"
                    
                    text = f"""🔒 **Arey {message.from_user.first_name}!**

Aapne hamara **channel leave kar diya**? 🤔

Group mein message karne ke liye 
wapis channel join karo!

📢 **{channel_name}**

✅ Join karo
✅ "✅ Verified" dabao
✅ Phir message karo"""
                    
                    buttons = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📢 Join Channel", url=link)],
                        [InlineKeyboardButton("✅ Verified", callback_data=f"fsub_verify_{user_id}")]
                    ])
                    
                    msg = await message.reply_text(text, reply_markup=buttons)
                    await MovieBotUtils.auto_delete_message(client, msg, 60)
                    return
                else:
                    fsub_cache[cache_key] = datetime.datetime.now()
                    
            except UserNotParticipant:
                await message.delete()
                # Similar message as above
                return
            except Exception as e:
                logger.error(f"FSub check error: {e}")
    
    # 3. CHECK CUSTOM FILTERS
    words = text.lower().split()
    for word in words:
        filter_data = await get_filter(chat_id, word)
        if filter_data:
            response = filter_data.get("response", "")
            file_id = filter_data.get("file_id")
            
            if file_id:
                await client.send_cached_media(chat_id, file_id, caption=response)
            else:
                await message.reply_text(response)
            
            try:
                await message.delete()
            except:
                pass
            return
    
    # 4. MESSAGE QUALITY CHECK
    quality = MovieBotUtils.check_message_quality(text)
    
    # Link filter
    if quality == "LINK" and settings.get("link_filter", True):
        try:
            await message.delete()
            warn_count = await add_warning(chat_id, user_id, "Link sharing")
            
            if warn_count >= Config.MAX_WARNINGS:
                try:
                    await client.restrict_chat_member(
                        chat_id, user_id,
                        ChatPermissions(can_send_messages=False),
                        until_date=datetime.datetime.now() + datetime.timedelta(hours=24)
                    )
                    msg = await message.reply_text(f"🚫 **{message.from_user.first_name}**, aapko 24 hour mute!\nReason: Links share kiye")
                    await reset_warnings(chat_id, user_id)
                    await MovieBotUtils.auto_delete_message(client, msg, 10)
                except:
                    pass
            else:
                msg = await message.reply_text(
                    f"⚠️ **Warning {warn_count}/{Config.MAX_WARNINGS}**\n\n"
                    f"{message.from_user.mention}, group mein **links allowed nahi hain!**\n"
                    f"Next warning par action hoga!"
                )
                await MovieBotUtils.auto_delete_message(client, msg, 10)
        except:
            pass
        return
    
    # Abuse filter
    elif quality == "ABUSE" and settings.get("bad_words_filter", True):
        try:
            await message.delete()
            warn_count = await add_warning(chat_id, user_id, "Abusive language")
            
            if warn_count >= Config.MAX_WARNINGS:
                try:
                    await client.ban_chat_member(chat_id, user_id)
                    msg = await message.reply_text(f"🚫 **{message.from_user.first_name}** banned!\nReason: Abuse/Gali")
                    await reset_warnings(chat_id, user_id)
                    await MovieBotUtils.auto_delete_message(client, msg, 10)
                except:
                    pass
            else:
                msg = await message.reply_text(
                    f"⚠️ **Warning {warn_count}/{Config.MAX_WARNINGS}**\n\n"
                    f"{message.from_user.mention}, **abusive language use mat karo!**\n"
                    f"Group culture maintain karo! 🤝"
                )
                await MovieBotUtils.auto_delete_message(client, msg, 10)
        except:
            pass
        return
    
    # Spam filter
    elif quality == "SPAM" and settings.get("antispam", True):
        try:
            await message.delete()
            msg = await message.reply_text(f"⚠️ **{message.from_user.first_name}**, spam mat karo!")
            await MovieBotUtils.auto_delete_message(client, msg, 5)
        except:
            pass
        return
    
    # 5. SPELLING CHECK
    if settings.get("spelling_on", True):
        validation = MovieBotUtils.validate_movie_format_advanced(text)
        
        if not validation['is_valid'] and validation['clean_name'] and len(validation['clean_name']) > 2:
            try:
                await message.delete()
                
                if validation['found_junk']:
                    junk_text = ", ".join(validation['found_junk'])
                    extra = f"\n❌ Extra words: `{junk_text}`\n✅ Sirf movie naam likho!"
                else:
                    extra = ""
                
                mode = settings.get("spelling_mode", "simple")
                
                if mode == "simple":
                    msg = await message.reply_text(
                        f"❌ **Wrong Format!** {message.from_user.mention}\n\n"
                        f"✅ **Sahi hai:** `{validation['correct_format']}`{extra}\n\n"
                        f"💡 Example: `/request {validation['clean_name']}`"
                    )
                    await MovieBotUtils.auto_delete_message(client, msg, 20)
                    
                elif mode == "advanced" and Config.OMDB_API_KEY:
                    waiting = await message.reply_text(f"🔍 `{validation['clean_name']}` search ho raha hai...")
                    omdb_info = await MovieBotUtils.get_omdb_info(validation['clean_name'])
                    await waiting.delete()
                    
                    if "not found" in omdb_info.lower():
                        msg = await message.reply_text(
                            f"❌ **Movie Not Found!** {message.from_user.mention}\n\n"
                            f"✅ **Try this:** `{validation['correct_format']}`\n\n"
                            f"OMDb mein ye movie nahi mili, spelling check karo!"
                        )
                    else:
                        msg = await message.reply_text(
                            f"❌ **Wrong Format!** {message.from_user.mention}\n\n"
                            f"✅ **Sahi naam:** `{validation['clean_name']}`\n\n"
                            f"{omdb_info}"
                        )
                    await MovieBotUtils.auto_delete_message(client, msg, 30)
            except Exception as e:
                logger.error(f"Spelling check error: {e}")
    
    # 6. AI CHAT
    if settings.get("ai_chat_on", False):
        bot_id = (await client.get_me()).id
        
        should_reply = False
        if message.reply_to_message and message.reply_to_message.from_user.id == bot_id:
            should_reply = True
        elif not message.reply_to_message and random.random() < 0.1:  # 10% chance
            should_reply = True
        
        if should_reply and MovieBotUtils.check_rate_limit(chat_id, "ai_chat", limit=10, period=60):
            await show_typing(chat_id)
            await asyncio.sleep(0.5)
            
            response = await MovieBotUtils.get_ai_response(text, f"Group: {message.chat.title}")
            msg = await message.reply_text(response)
            await MovieBotUtils.auto_delete_message(client, msg, 300)

# ================ 18. CALLBACK HANDLER ================
@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    try:
        data = query.data
        chat_id = query.message.chat.id if query.message else query.from_user.id
        user_id = query.from_user.id
        
        # === FSUB VERIFY ===
        if data.startswith("fsub_verify_"):
            target_id = int(data.split("_")[2])
            if user_id != target_id:
                await query.answer("❌ Ye button sirf aapke liye hai!", show_alert=True)
                return
            
            fsub_data = await get_force_sub(chat_id)
            if not fsub_data:
                await query.message.delete()
                return
            
            channel_id = fsub_data["channel_id"]
            
            is_joined = await MovieBotUtils.check_fsub_member(client, channel_id, user_id)
            
            if is_joined:
                try:
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
                    
                    msg = await client.send_message(
                        chat_id,
                        f"✅ **{query.from_user.first_name} verified!**\n\nAb aap group mein chat kar sakte ho! 🎉"
                    )
                    await MovieBotUtils.auto_delete_message(client, msg, 60)
                    await query.answer("✅ Verified!")
                    
                    # Add to cache
                    cache_key = f"fsub_{user_id}_{channel_id}"
                    fsub_cache[cache_key] = datetime.datetime.now()
                    
                except Exception as e:
                    await query.answer("❌ Verification failed!", show_alert=True)
            else:
                await query.answer("❌ Aapne channel join nahi kiya!", show_alert=True)
        
        # === REQUEST ACCEPT ===
        elif data.startswith("req_accept_"):
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            parts = data.split("_")
            if len(parts) >= 4:
                request_id = parts[2]
                req_user_id = int(parts[3])
                
                # Update request status
                await update_request_status(request_id, "completed", user_id)
                
                # Send confirmation
                await client.send_message(
                    chat_id,
                    f"✅ **Movie Upload Ho Gayi!** 🎉\n\n"
                    f"{query.from_user.mention} ne movie upload kar di hai!\n"
                    f"<a href='tg://user?id={req_user_id}'>Requester</a>, please check karo!"
                )
                
                # Notify requester in PM
                try:
                    await client.send_message(
                        req_user_id,
                        f"✅ **Good News!**\n\n"
                        f"Aapki requested movie **upload ho gayi** in **{query.message.chat.title}**!\n"
                        f"Please check karo! 🎬"
                    )
                except:
                    pass
                
                await query.message.delete()
                await query.answer("✅ Request accepted!")
        
        # === REQUEST REJECT ===
        elif data.startswith("req_reject_"):
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            parts = data.split("_")
            if len(parts) >= 4:
                request_id = parts[2]
                req_user_id = int(parts[3])
                
                # Update request status
                await update_request_status(request_id, "rejected", user_id)
                
                # Send rejection message
                await client.send_message(
                    chat_id,
                    f"❌ **Movie Available Nahi Hai!**\n\n"
                    f"Request rejected by {query.from_user.mention}.\n"
                    f"Sorry, ye movie abhi available nahi hai! 😔"
                )
                
                # Notify requester
                try:
                    await client.send_message(
                        req_user_id,
                        f"❌ **Sorry!**\n\n"
                        f"Aapki requested movie **{query.message.chat.title}** mein available nahi hai.\n"
                        f"Koi aur movie request karo! 🎬"
                    )
                except:
                    pass
                
                await query.message.delete()
                await query.answer("❌ Request rejected!")
        
        # === OMDb SEARCH ===
        elif data.startswith("omdb_"):
            movie_name = data[5:]
            await query.answer("🔍 Searching OMDb...")
            
            omdb_info = await MovieBotUtils.get_omdb_info(movie_name, detailed=True)
            
            await query.message.edit_text(omdb_info)
        
        # === SPELLING MENU ===
        elif data == "spelling_menu":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            settings = await get_settings(chat_id)
            current_mode = settings.get("spelling_mode", "simple")
            spelling_on = settings.get("spelling_on", True)
            
            status = "✅ ON" if spelling_on else "❌ OFF"
            
            text = f"""📝 **Spelling Check Settings**

**Status:** {status}
**Current Mode:** {'📊 Advanced' if current_mode == 'advanced' else '📝 Simple'}

**Simple Mode:** 
• Extra words hata ke correct format batayega
• Movie naam saaf karega
• Fast and efficient

**Advanced Mode:** 
• OMDb se movie info search karega
• Correct spelling suggest karega
• IMDb rating + Genre batayega
• More detailed information

Select mode:"""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📝 Simple", callback_data="set_spelling_simple"),
                    InlineKeyboardButton("📊 Advanced", callback_data="set_spelling_advanced")
                ],
                [
                    InlineKeyboardButton(f"{'✅' if spelling_on else '❌'} Toggle Spelling", callback_data="toggle_spelling")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="settings_menu")]
            ])
            
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
        
        # === TOGGLE SPELLING ===
        elif data == "toggle_spelling":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("spelling_on", True)
            await update_settings(chat_id, "spelling_on", new_val)
            
            await query.answer(f"Spelling Check: {'ON' if new_val else 'OFF'}")
            
            # Refresh menu
            await callback_handler(client, CallbackQuery(
                id=query.id,
                from_user=query.from_user,
                message=query.message,
                data="spelling_menu",
                chat_instance=query.chat_instance
            ))
        
        # === SET SPELLING MODE ===
        elif data == "set_spelling_simple":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            await update_settings(chat_id, "spelling_mode", "simple")
            await update_settings(chat_id, "spelling_on", True)
            await query.answer("✅ Simple Mode ON")
            await show_settings_menu(client, query, is_new=False)
        
        elif data == "set_spelling_advanced":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            if not Config.OMDB_API_KEY:
                await query.answer("❌ OMDb API key missing! Owner se contact karo.", show_alert=True)
                return
            
            await update_settings(chat_id, "spelling_mode", "advanced")
            await update_settings(chat_id, "spelling_on", True)
            await query.answer("✅ Advanced Mode ON")
            await show_settings_menu(client, query, is_new=False)
        
        # === BIO MENU ===
        elif data == "bio_menu":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            settings = await get_settings(chat_id)
            bio_status = "✅ ON" if settings.get("bio_check", True) else "❌ OFF"
            bio_action = settings.get("bio_action", "mute")
            action_text = "🔇 Mute" if bio_action == "mute" else "🚫 Ban"
            
            text = f"""🛡️ **Bio Protection Settings**

**Status:** {bio_status}
**Action:** {action_text}

**Kya karta hai?**
• Naye members ki bio scan
• Links/usernames detect
• Promotion content detect
• Warning → Mute → Ban

**Rules:**
• 1st time: Warning
• 2nd time: 1 hour Mute
• 3rd time: Ban

Select action:"""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔇 Mute", callback_data="bio_action_mute"),
                    InlineKeyboardButton("🚫 Ban", callback_data="bio_action_ban")
                ],
                [
                    InlineKeyboardButton(f"{'✅' if settings.get('bio_check', True) else '❌'} Toggle Bio Check", 
                                       callback_data="toggle_bio")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="settings_menu")]
            ])
            
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
        
        # === TOGGLE BIO ===
        elif data == "toggle_bio":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("bio_check", True)
            await update_settings(chat_id, "bio_check", new_val)
            
            await query.answer(f"Bio Check: {'ON' if new_val else 'OFF'}")
            
            # Refresh menu
            await callback_handler(client, CallbackQuery(
                id=query.id,
                from_user=query.from_user,
                message=query.message,
                data="bio_menu",
                chat_instance=query.chat_instance
            ))
        
        # === BIO ACTION ===
        elif data == "bio_action_mute":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            await update_settings(chat_id, "bio_action", "mute")
            await query.answer("✅ Action: Mute")
            
            # Refresh menu
            await callback_handler(client, CallbackQuery(
                id=query.id,
                from_user=query.from_user,
                message=query.message,
                data="bio_menu",
                chat_instance=query.chat_instance
            ))
        
        elif data == "bio_action_ban":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            await update_settings(chat_id, "bio_action", "ban")
            await query.answer("✅ Action: Ban")
            
            # Refresh menu
            await callback_handler(client, CallbackQuery(
                id=query.id,
                from_user=query.from_user,
                message=query.message,
                data="bio_menu",
                chat_instance=query.chat_instance
            ))
        
        # === TOGGLE SETTINGS ===
        elif data == "toggle_ai":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("ai_chat_on", False)
            await update_settings(chat_id, "ai_chat_on", new_val)
            await query.answer(f"AI Chat: {'ON' if new_val else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
        
        elif data == "toggle_cleanjoin":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("clean_join", True)
            await update_settings(chat_id, "clean_join", new_val)
            await query.answer(f"Clean Join: {'ON' if new_val else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
        
        elif data == "toggle_auto_accept":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            current = await get_auto_accept(chat_id)
            await set_auto_accept(chat_id, not current)
            await query.answer(f"Auto Accept: {'ON' if not current else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
        
        elif data == "toggle_linkfilter":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("link_filter", True)
            await update_settings(chat_id, "link_filter", new_val)
            await query.answer(f"Link Filter: {'ON' if new_val else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
        
        elif data == "toggle_abusefilter":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("bad_words_filter", True)
            await update_settings(chat_id, "bad_words_filter", new_val)
            await query.answer(f"Abuse Filter: {'ON' if new_val else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
        
        elif data == "toggle_antispam":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("antispam", True)
            await update_settings(chat_id, "antispam", new_val)
            await query.answer(f"Anti-Spam: {'ON' if new_val else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
        
        # === ADVANCED SETTINGS ===
        elif data == "advanced_settings":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            settings = await get_settings(chat_id)
            delete_time = settings.get("delete_time", 0)
            copyright_mode = settings.get("copyright_mode", False)
            
            text = f"""📊 **Advanced Settings**

**Delete Time:** {delete_time}s (0 = disable)
**Copyright Mode:** {'✅ ON' if copyright_mode else '❌ OFF'}

**Warning Limits:**
• Max Warnings: {Config.MAX_WARNINGS}
• Action: Mute/Ban after limit

**Premium Features:**
• Force Subscribe
• Priority Support
• No Ads

Configure advanced options:"""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⏱️ Set Delete Time", callback_data="set_deletetime"),
                    InlineKeyboardButton("©️ Toggle Copyright", callback_data="toggle_copyright")
                ],
                [InlineKeyboardButton("💎 Premium Info", callback_data="premium_info")],
                [InlineKeyboardButton("🔙 Back", callback_data="settings_menu")]
            ])
            
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
        
        # === TOGGLE COPYRIGHT ===
        elif data == "toggle_copyright":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("copyright_mode", False)
            await update_settings(chat_id, "copyright_mode", new_val)
            await query.answer(f"Copyright Mode: {'ON' if new_val else 'OFF'}")
            
            # Refresh advanced menu
            await callback_handler(client, CallbackQuery(
                id=query.id,
                from_user=query.from_user,
                message=query.message,
                data="advanced_settings",
                chat_instance=query.chat_instance
            ))
        
        # === SET DELETE TIME ===
        elif data == "set_deletetime":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            text = """⏱️ **Set Auto-Delete Time**

Choose delete time for bot messages:

• 0s - Disable auto-delete
• 5s - Very short
• 10s - Short
• 30s - Medium
• 60s - Long
• 300s - Very long

Select time:"""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("0s", callback_data="deletetime_0"),
                    InlineKeyboardButton("5s", callback_data="deletetime_5"),
                    InlineKeyboardButton("10s", callback_data="deletetime_10")
                ],
                [
                    InlineKeyboardButton("30s", callback_data="deletetime_30"),
                    InlineKeyboardButton("60s", callback_data="deletetime_60"),
                    InlineKeyboardButton("300s", callback_data="deletetime_300")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="advanced_settings")]
            ])
            
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
        
        # === DELETE TIME CALLBACKS ===
        elif data.startswith("deletetime_"):
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            seconds = int(data.split("_")[1])
            await update_settings(chat_id, "delete_time", seconds)
            await query.answer(f"✅ Delete time set to {seconds}s")
            
            # Back to advanced settings
            await callback_handler(client, CallbackQuery(
                id=query.id,
                from_user=query.from_user,
                message=query.message,
                data="advanced_settings",
                chat_instance=query.chat_instance
            ))
        
        # === SETTINGS MENU ===
        elif data == "settings_menu":
            await show_settings_menu(client, query, is_new=False)
            await query.answer()
        
        # === HELP MENUS ===
        elif data == "help_menu":
            text = """📚 **COMMANDS & FEATURES**

**👤 Sab ke liye:**
• /request - Movie mango
• /ai - AI se pucho
• /google - Google search
• /anime - Anime search
• /motd - Aaj ki movie
• /ping - Status check
• /id - ID dekho
• /rules - Group rules

**👑 Admin ke liye:**
• /settings - Bot settings
• /addfsub - Force subscribe
• /cleanjoin - Join msg delete
• /setwelcome - Welcome set
• /filter - Add custom filter
• /note - Add note
• /warn - Warn user
• /stats - Group stats

**💎 Premium:**
Contact @asbhai_bsr"""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📖 Examples", callback_data="help_examples"),
                    InlineKeyboardButton("⚙️ Settings Guide", callback_data="help_settings")
                ],
                [
                    InlineKeyboardButton("💎 Premium", callback_data="premium_info"),
                    InlineKeyboardButton("📊 Bot Stats", callback_data="bot_stats")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="help_back")]
            ])
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
        
        elif data == "help_examples":
            text = """📖 **EXAMPLES**

✅ **Sahi tarika:**
• `/request Inception 2010`
• `/request Kalki 2898 AD`
• `#request Jawan`

❌ **Galat tarika:**
• `movie dedo`
• `inception movie chahiye`
• `send jawan link`

🤖 **AI Examples:**
• `/ai Inception ka story kya hai?`
• `/ai Best movies 2024`
• `/ai Comedy movie suggest karo`

🔍 **Search:**
• `/google Avengers cast`
• `/anime Demon Slayer`

📝 **Filters:**
• `/filter hello Welcome!` - Add filter
• `/filters` - List filters
• `/note rules Group rules here` - Add note"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_menu")]
            ])
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
        
        elif data == "help_settings":
            text = """⚙️ **SETTINGS GUIDE**

**1. 📝 Spelling Check**
   • Simple: Extra words hatao
   • Advanced: OMDb se info

**2. 🛡️ Bio Protect**
   • Bio mein link/username detect
   • Warning → Mute → Ban

**3. ⚡ Auto Accept**
   • Join requests auto approve

**4. 🧹 Clean Join**
   • Service messages delete

**5. 🤖 AI Chat**
   • Bot auto-reply on mention

**6. 🔗 Link Filter**
   • Block all links
   • Warning system

**7. 🚫 Abuse Filter**
   • Block bad words
   • Auto warn/ban

**8. ⚡ Anti-Spam**
   • Rate limiting
   • Flood control

**How to use:**
/settings - Admin rights required!"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_menu")]
            ])
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
        
        elif data == "bot_stats":
            await query.answer("📊 Fetching stats...")
            
            stats = await get_bot_stats()
            
            text = f"""📊 **BOT STATISTICS**

**👥 Users:**
• Total: {stats.get('total_users', 0)}
• Banned: {stats.get('banned_users', 0)}
• Active Today: {stats.get('active_today', 0)}
• New Today: {stats.get('new_users_today', 0)}

**👥 Groups:**
• Total: {stats.get('total_groups', 0)}
• Active: {stats.get('active_groups', 0)}
• Premium: {stats.get('premium_groups', 0)}
• New Today: {stats.get('new_groups_today', 0)}

**🎬 Requests:**
• Total: {stats.get('total_requests', 0)}
• Pending: {stats.get('pending_requests', 0)}

**🔧 Other:**
• Filters: {stats.get('total_filters', 0)}
• Notes: {stats.get('total_notes', 0)}
• Blacklisted: {stats.get('blacklisted_users', 0)}

**⏰ Updated:** {datetime.datetime.now().strftime('%H:%M:%S')}"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="bot_stats"),
                 InlineKeyboardButton("🔙 Back", callback_data="help_menu")]
            ])
            
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
        
        elif data == "help_back":
            await start_command(client, query.message)
            await query.answer()
        
        # === PREMIUM INFO ===
        elif data == "premium_info":
            text = """💎 **PREMIUM FEATURES**

**✨ Benefits:**
✅ Force Subscribe System
✅ No Ads/Broadcasts
✅ Priority Support
✅ Early Access
✅ More Features Coming Soon

**💰 Pricing:**
• 1 Month: ₹100
• 3 Months: ₹250 (Save ₹50)
• 6 Months: ₹450 (Save ₹150)
• 1 Year: ₹800 (Save ₹400)

**🎁 Group Offers:**
• 5+ Groups: 20% Discount
• 10+ Groups: 30% Discount

**🛒 Buy Premium:**
Contact @asbhai_bsr

🎉 **3 Days Trial Available!**"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Contact Owner", url=f"https://t.me/{Config.OWNER_USERNAME}")],
                [InlineKeyboardButton("🔙 Back", callback_data="help_menu")]
            ])
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
        
        # === CLOSE ===
        elif data == "close":
            await query.message.delete()
            await query.answer()
    
    except Exception as e:
        logger.error(f"Callback Error: {e}")
        await query.answer("❌ Error!", show_alert=True)

# ================ 19. SET WELCOME COMMAND ================
@app.on_message(filters.command("setwelcome") & filters.group)
async def set_welcome_command(client, message):
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("❌ Sirf admins!")
        return
    
    reply = message.reply_to_message
    photo_id = None
    welcome_text = ""
    
    if reply:
        welcome_text = reply.caption or reply.text or ""
        if reply.photo:
            photo_id = reply.photo.file_id
    elif len(message.command) > 1:
        welcome_text = message.text.split(None, 1)[1]
    else:
        await message.reply(
            "❌ **Usage:**\n"
            "1. Kisi photo ya text ko reply karo /setwelcome se\n"
            "2. `/setwelcome Welcome {name} to {chat}!`\n\n"
            "**Variables:**\n"
            "• {name} - User's name\n"
            "• {chat} - Group name\n"
            "• {mention} - User mention"
        )
        return
    
    await set_welcome_message(message.chat.id, welcome_text, photo_id)
    await message.reply("✅ **Custom Welcome Set!** ✅")

# ================ 20. CLEAN JOIN COMMAND ================
@app.on_message(filters.command("cleanjoin") & filters.group)
async def cleanjoin_toggle(client, message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    
    settings = await get_settings(message.chat.id)
    new_val = not settings.get("clean_join", True)
    await update_settings(message.chat.id, "clean_join", new_val)
    
    status = "✅ ON" if new_val else "❌ OFF"
    msg = await message.reply(f"🧹 **Clean Join:** {status}")
    await MovieBotUtils.auto_delete_message(client, msg, 10)

# ================ 21. FORCE SUBSCRIBE COMMAND ================
@app.on_message(filters.command("addfsub") & filters.group)
async def addfsub_command(client: Client, message: Message):
    if not message.from_user:
        return
    
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ Sirf admins!")
        await MovieBotUtils.auto_delete_message(client, msg, 5)
        return

    if not await check_is_premium(message.chat.id):
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Buy Premium", url=f"https://t.me/{Config.OWNER_USERNAME}")]
        ])
        msg = await message.reply_text(
            "💎 **Force Subscribe is Premium Feature!**\n\n"
            "Contact @asbhai_bsr for premium.",
            reply_markup=buttons
        )
        await MovieBotUtils.auto_delete_message(client, msg, 30)
        return

    channel_id = None
    channel_title = None
    
    if len(message.command) > 1:
        try:
            channel_id = int(message.command[1])
        except ValueError:
            msg = await message.reply_text("❌ Invalid Channel ID!\nNumeric ID do: -100xxxxxxx")
            await MovieBotUtils.auto_delete_message(client, msg, 5)
            return

    elif message.reply_to_message and message.reply_to_message.forward_from_chat:
        channel = message.reply_to_message.forward_from_chat
        channel_id = channel.id
        channel_title = channel.title
    else:
        msg = await message.reply_text(
            "❌ **Usage:**\n"
            "1. `/addfsub -100xxxxxxx`\n"
            "2. Channel ki kisi post ko reply karo `/addfsub` se"
        )
        await MovieBotUtils.auto_delete_message(client, msg, 10)
        return

    try:
        # Verify bot is admin in channel
        chat = await client.get_chat(channel_id)
        bot_member = await client.get_chat_member(channel_id, (await client.get_me()).id)
        
        if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            msg = await message.reply_text("❌ Main uss channel mein admin nahi hoon!")
            await MovieBotUtils.auto_delete_message(client, msg, 5)
            return
        
        channel_title = chat.title
        
    except Exception as e:
        msg = await message.reply_text("❌ Error: Mujhe channel mein admin banao pehle!")
        await MovieBotUtils.auto_delete_message(client, msg, 5)
        return

    await set_force_sub(message.chat.id, channel_id, channel_title)
    
    msg = await message.reply_text(
        f"✅ **Force Subscribe Enabled!**\n\n"
        f"📢 **Channel:** {channel_title}\n\n"
        f"Ab naye members ko channel join karna hoga group mein chat karne ke liye!\n\n"
        f"**Existing members already checked!**"
    )
    await MovieBotUtils.auto_delete_message(client, msg, 30)

# ================ 22. REMOVE FORCE SUBSCRIBE ================
@app.on_message(filters.command("removefsub") & filters.group)
async def removefsub_command(client: Client, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ Sirf admins!")
        await MovieBotUtils.auto_delete_message(client, msg, 5)
        return
    
    await remove_force_sub(message.chat.id)
    
    msg = await message.reply_text("✅ **Force Subscribe Disabled!**")
    await MovieBotUtils.auto_delete_message(client, msg, 10)

# ================ 23. FILTER COMMANDS ================
@app.on_message(filters.command("filter") & filters.group)
async def add_filter_command(client, message):
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ Sirf admins!")
        return
    
    if len(message.command) < 3 and not message.reply_to_message:
        await message.reply_text(
            "❌ **Usage:**\n"
            "`/filter trigger response`\n"
            "Ya kisi message ko reply karo `/filter trigger` se"
        )
        return
    
    if message.reply_to_message:
        trigger = message.command[1].lower()
        response = message.reply_to_message.text or message.reply_to_message.caption
        file_id = None
        
        # Check for media
        media_info = MovieBotUtils.extract_media_info(message.reply_to_message)
        if media_info["file_id"]:
            file_id = media_info["file_id"]
    else:
        parts = message.text.split(None, 2)
        trigger = parts[1].lower()
        response = parts[2]
        file_id = None
    
    await add_filter(message.chat.id, trigger, response, file_id)
    await message.reply_text(f"✅ **Filter added!**\nTrigger: `{trigger}`")

@app.on_message(filters.command("filters") & filters.group)
async def list_filters_command(client, message):
    filters_list = await get_all_filters(message.chat.id)
    
    if not filters_list:
        await message.reply_text("❌ **Koi filter nahi hai!**\n/filter use karke add karo.")
        return
    
    text = "**📋 Filters in this group:**\n\n"
    for f in filters_list:
        text += f"• `{f['trigger']}`\n"
    
    await message.reply_text(text)

@app.on_message(filters.command("stop") & filters.group)
async def remove_filter_command(client, message):
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ Sirf admins!")
        return
    
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/stop trigger`")
        return
    
    trigger = message.command[1].lower()
    await remove_filter(message.chat.id, trigger)
    await message.reply_text(f"✅ **Filter removed:** `{trigger}`")

# ================ 24. NOTE COMMANDS ================
@app.on_message(filters.command("save") & filters.group)
async def save_note_command(client, message):
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ Sirf admins!")
        return
    
    if len(message.command) < 3 and not message.reply_to_message:
        await message.reply_text(
            "❌ **Usage:**\n"
            "`/save note_name content`\n"
            "Ya kisi message ko reply karo `/save note_name` se"
        )
        return
    
    if message.reply_to_message:
        name = message.command[1].lower()
        content = message.reply_to_message.text or message.reply_to_message.caption
        file_id = None
        
        media_info = MovieBotUtils.extract_media_info(message.reply_to_message)
        if media_info["file_id"]:
            file_id = media_info["file_id"]
    else:
        parts = message.text.split(None, 2)
        name = parts[1].lower()
        content = parts[2]
        file_id = None
    
    await add_note(message.chat.id, name, content, file_id)
    await message.reply_text(f"✅ **Note saved!**\nName: `{name}`\nUse `#{name}` to get it.")

@app.on_message(filters.command("notes") & filters.group)
async def list_notes_command(client, message):
    notes_list = await get_all_notes(message.chat.id)
    
    if not notes_list:
        await message.reply_text("❌ **Koi note nahi hai!**\n/save use karke add karo.")
        return
    
    text = "**📝 Notes in this group:**\n\n"
    for note in notes_list:
        text += f"• `#{note['name']}`\n"
    
    await message.reply_text(text)

@app.on_message(filters.command("delete") & filters.group)
async def delete_note_command(client, message):
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ Sirf admins!")
        return
    
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/delete note_name`")
        return
    
    name = message.command[1].lower()
    await remove_note(message.chat.id, name)
    await message.reply_text(f"✅ **Note deleted:** `{name}`")

# ================ 25. NOTE GETTER (HASHTAG) ================
@app.on_message(filters.group & filters.text & filters.regex(r'^#\w+'))
async def get_note_handler(client, message):
    text = message.text
    match = re.match(r'^#(\w+)', text)
    if not match:
        return
    
    note_name = match.group(1).lower()
    note = await get_note(message.chat.id, note_name)
    
    if note:
        content = note.get("content", "")
        file_id = note.get("file_id")
        
        if file_id:
            await client.send_cached_media(message.chat.id, file_id, caption=content)
        else:
            await message.reply_text(content)
        
        try:
            await message.delete()
        except:
            pass

# ================ 26. WARN COMMANDS ================
@app.on_message(filters.command("warn") & filters.group)
async def warn_user_command(client, message):
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ Sirf admins!")
        return
    
    if not message.reply_to_message:
        await message.reply_text("❌ Kisi user ke message ko reply karo /warn se")
        return
    
    user = message.reply_to_message.from_user
    if not user:
        return
    
    reason = "No reason"
    if len(message.command) > 1:
        reason = " ".join(message.command[1:])
    
    warn_count = await add_warning(message.chat.id, user.id, reason)
    
    text = f"⚠️ **{user.first_name}** ko warning di gayi!\n"
    text += f"📊 **Total Warnings:** {warn_count}/{Config.MAX_WARNINGS}\n"
    text += f"📝 **Reason:** {reason}"
    
    if warn_count >= Config.MAX_WARNINGS:
        try:
            await client.ban_chat_member(message.chat.id, user.id)
            text += f"\n\n🚫 **User banned!** (Max warnings reached)"
            await reset_warnings(message.chat.id, user.id)
        except:
            pass
    
    await message.reply_to_message.reply_text(text)

@app.on_message(filters.command("unwarn") & filters.group)
async def unwarn_user_command(client, message):
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ Sirf admins!")
        return
    
    if not message.reply_to_message:
        await message.reply_text("❌ Kisi user ke message ko reply karo /unwarn se")
        return
    
    user = message.reply_to_message.from_user
    if not user:
        return
    
    await reset_warnings(message.chat.id, user.id)
    await message.reply_text(f"✅ **{user.first_name}** ke saare warnings reset!")

# ================ 27. STATS COMMAND ================
@app.on_message(filters.command("stats") & filters.group)
async def group_stats_command(client, message):
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ Sirf admins!")
        return
    
    chat_id = message.chat.id
    
    # Get group info
    group = await get_group(chat_id)
    settings = await get_settings(chat_id)
    request_stats = await get_request_stats(chat_id)
    warnings_count = len(await get_all_warnings(chat_id))
    filters_count = len(await get_all_filters(chat_id))
    notes_count = len(await get_all_notes(chat_id))
    
    is_premium = await check_is_premium(chat_id)
    premium_status = "⭐ Premium" if is_premium else "Free"
    
    text = f"""📊 **GROUP STATISTICS**

**Group:** {message.chat.title}
**ID:** `{chat_id}`
**Status:** {premium_status}

**📈 Activity:**
• Total Members: {message.chat.members_count if message.chat.members_count else 'N/A'}
• Added: {group.get('added_at', datetime.datetime.now()).strftime('%d-%m-%Y') if group else 'N/A'}
• Last Active: {group.get('last_active', datetime.datetime.now()).strftime('%d-%m-%Y') if group else 'N/A'}

**🎬 Requests:**
• Total: {request_stats.get('total', 0)}
• Pending: {request_stats.get('pending', 0)}
• Completed: {request_stats.get('completed', 0)}
• Rejected: {request_stats.get('rejected', 0)}

**⚙️ Config:**
• Active Warnings: {warnings_count}
• Filters: {filters_count}
• Notes: {notes_count}
• Auto Accept: {'✅' if await get_auto_accept(chat_id) else '❌'}

**📝 Settings:**
• Spelling: {'✅' if settings.get('spelling_on') else '❌'}
• Bio Check: {'✅' if settings.get('bio_check') else '❌'}
• Link Filter: {'✅' if settings.get('link_filter') else '❌'}
• Abuse Filter: {'✅' if settings.get('bad_words_filter') else '❌'}
• AI Chat: {'✅' if settings.get('ai_chat_on') else '❌'}

_Updated: {datetime.datetime.now().strftime('%H:%M:%S')}_"""
    
    await message.reply_text(text)

# ================ 28. BROADCAST COMMAND (OWNER ONLY) ================
@app.on_message(filters.command("broadcast") & filters.user(Config.OWNER_ID))
async def broadcast_command(client, message):
    if len(message.command) < 2 and not message.reply_to_message:
        await message.reply_text(
            "❌ **Usage:**\n"
            "`/broadcast message`\n"
            "Ya kisi message ko reply karo `/broadcast` se"
        )
        return
    
    if message.reply_to_message:
        broadcast_msg = message.reply_to_message
    else:
        broadcast_msg = message
    
    # Get all users
    users = await get_all_users()
    groups = await get_all_groups()
    
    success = 0
    failed = 0
    
    status_msg = await message.reply_text(f"📢 Broadcasting to {len(users)} users and {len(groups)} groups...")
    
    # Broadcast to users
    for user_id in users:
        try:
            await broadcast_msg.copy(user_id)
            success += 1
            await asyncio.sleep(0.05)  # Rate limiting
        except (UserIsBlocked, InputUserDeactivated):
            failed += 1
        except Exception as e:
            failed += 1
            logger.error(f"Broadcast error to {user_id}: {e}")
    
    # Broadcast to groups
    for group_id in groups:
        try:
            await broadcast_msg.copy(group_id)
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
    
    await status_msg.edit_text(
        f"📢 **Broadcast Complete!**\n\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}"
    )

# ================ 29. GROUP JOIN/LEAVE HANDLERS ================
@app.on_chat_member_updated(filters.group)
async def bot_added_or_removed(client: Client, update: ChatMemberUpdated):
    bot_id = (await client.get_me()).id
    
    # Bot added to group
    if update.new_chat_member and update.new_chat_member.user.id == bot_id:
        if update.new_chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
            chat = update.chat
            logger.info(f"✅ Bot added to group: {chat.id} - {chat.title}")
            await add_group(chat.id, chat.title, chat.username)
            
            # Send welcome message
            text = f"""🎉 **Thanks for adding me!**

Group: **{chat.title}**
ID: `{chat.id}`

🚀 **Get Started:**
• /settings - Bot settings
• /request - Movie request
• /help - All commands
• /setwelcome - Custom welcome

💎 **Premium Features:**
• Force Subscribe
• Priority Support
• @asbhai_bsr

_Enjoy! Bot is ready to serve! 🤖_"""
            
            try:
                await client.send_message(chat.id, text)
                
                # Notify owner
                await client.send_message(
                    Config.OWNER_ID,
                    f"✅ **Bot Added**\n"
                    f"Group: {chat.title}\n"
                    f"ID: `{chat.id}`"
                )
            except:
                pass
    
    # Bot removed from group
    elif update.old_chat_member and update.old_chat_member.user.id == bot_id:
        if update.old_chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
            if not update.new_chat_member or update.new_chat_member.status == ChatMemberStatus.LEFT:
                chat_id = update.chat.id
                await mark_bot_removed(chat_id, True)
                
                try:
                    await client.send_message(
                        Config.OWNER_ID,
                        f"❌ **Bot Removed**\n"
                        f"Group: {update.chat.title}\n"
                        f"ID: `{chat_id}`"
                    )
                except:
                    pass

# ================ 30. SCHEDULED TASKS ================
async def scheduled_cleanup():
    """Run cleanup tasks periodically"""
    while True:
        try:
            await asyncio.sleep(Config.CLEANUP_INTERVAL)
            
            # Clear junk from database
            junk_count = await clear_junk()
            
            # Clear caches
            MovieBotUtils.clean_cache()
            MovieBotUtils.clean_rate_limits()
            
            # Clear old cache entries from fsub_cache
            now = datetime.datetime.now()
            expired = []
            for key, timestamp in fsub_cache.items():
                if (now - timestamp).seconds > 3600:  # 1 hour
                    expired.append(key)
            for key in expired:
                del fsub_cache[key]
            
            # Clear admin cache
            expired = []
            for key, (_, expiry) in admin_cache.items():
                if expiry < now:
                    expired.append(key)
            for key in expired:
                del admin_cache[key]
            
            total = sum(junk_count.values())
            if total > 0:
                logger.info(f"Cleanup completed: {total} items removed")
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            await asyncio.sleep(3600)

# ================ 31. START BOT ================
async def start_bot():
    """Start the bot"""
    # Create cleanup task
    asyncio.create_task(scheduled_cleanup())
    
    # Start bot
    await app.start()
    
    # Set bot instance in database
    bot_info = await app.get_me()
    await set_bot_instance(bot_info.id, "running")
    
    logger.info(f"✅ Bot started as @{bot_info.username}")
    
    # Notify owner
    try:
        await app.send_message(
            Config.OWNER_ID,
            f"🤖 **Bot Started!**\n\n"
            f"• **Bot:** @{bot_info.username}\n"
            f"• **ID:** `{bot_info.id}`\n"
            f"• **Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"• **Status:** ✅ Running\n\n"
            f"**Stats:**\n"
            f"• Users: {await get_user_count()}\n"
            f"• Groups: {await get_group_count()}"
        )
    except:
        pass
    
    # Idle
    await idle()
    
    # Cleanup on stop
    await set_bot_instance(bot_info.id, "stopped")
    logger.info("Bot stopped")

# ================ MAIN ================
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 Movie Helper Bot Starting...")
    print("="*60 + "\n")
    
    try:
        app.run(start_bot())
    except KeyboardInterrupt:
        print("\n⏹️ Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot crashed: {e}")
        traceback.print_exc()
