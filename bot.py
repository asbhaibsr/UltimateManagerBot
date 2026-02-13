# bot.py - Movie Helper Bot Main File
# Complete rewrite with all changes: Daily Limit, Welcome Image, Admin Tags, FSub Strict, Logs Fixed

import asyncio
import logging
import re
import datetime
import time
import aiohttp
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

# ================ SETUP ================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Client(
    name="movie_helper_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    in_memory=True,
    workers=20
)

fsub_cache = []
admin_cache = {}

# ================ HELPER FUNCTIONS ================
async def is_admin(chat_id, user_id):
    """Check if user is admin (cached)"""
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
    except:
        return False

async def show_typing(chat_id):
    try:
        await app.send_chat_action(chat_id, ChatAction.TYPING)
    except:
        pass

# ================ 1. SET COMMANDS (ADMIN) ================
@app.on_message(filters.command("setcommands") & filters.user(Config.OWNER_ID))
async def force_set_commands(client, message):
    """Bot commands manually refresh"""
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
    ]
    
    try:
        await client.set_bot_commands(commands, scope=BotCommandScopeAllGroupChats())
        await client.send_message(
            message.chat.id,
            "✅ **Commands refresh ho gaye!**\n\n"
            "Ab group mein /help type karo sab commands dekhne ke liye."
        )
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

# ================ 2. START COMMAND ================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    user = message.from_user
    await add_user(user.id, user.username, user.first_name, user.last_name)
    
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

👇 **Group mein add karo aur enjoy karo!** 🚀"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Group Mein Add Karo", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [
            InlineKeyboardButton("⚡ Auto Accept Setup", callback_data="help_autoaccept"),
            InlineKeyboardButton("📚 Commands", callback_data="help_menu")
        ],
        [InlineKeyboardButton("💎 Premium Features", callback_data="premium_info")]
    ])
    
    await message.reply_text(text, reply_markup=buttons)

# ================ 3. HELP COMMAND ================
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

**👑 ADMIN KE LIYE:**
• /settings - Bot settings
• /addfsub - Force subscribe
• /cleanjoin - Join msg delete
• /setwelcome - Welcome set

**💎 PREMIUM:**
Force Subscribe, No Ads, Priority Support

❓ **Koi problem?** @asbhai_bsr ko msg karo!"""
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 Examples", callback_data="help_examples"),
            InlineKeyboardButton("⚙️ Settings Guide", callback_data="help_settings")
        ],
        [InlineKeyboardButton("💎 Premium", callback_data="premium_info")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])
    
    await message.reply_text(text, reply_markup=buttons)

# ================ 4. SETTINGS COMMAND ================
@app.on_message(filters.command("settings") & filters.group)
async def settings_command(client: Client, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ **Sorry!** Sirf admin hi settings change kar sakte hain.")
        await MovieBotUtils.auto_delete_message(client, msg, 5)
        return
    
    await show_settings_menu(client, message, is_new=True)

async def show_settings_menu(client, message_or_query, is_new=False):
    """Settings panel dikhao"""
    if is_new:
        message = message_or_query
        chat_id = message.chat.id
    else:
        message = message_or_query.message
        chat_id = message.chat.id

    settings = await get_settings(chat_id)
    auto_acc = await get_auto_accept(chat_id)
    
    # Status
    s_spell = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
    s_bio = "✅ ON" if settings.get("bio_check", True) else "❌ OFF"
    s_clean = "✅ ON" if settings.get("clean_join", True) else "❌ OFF"
    s_auto = "✅ ON" if auto_acc else "❌ OFF"
    s_ai = "✅ ON" if settings.get("ai_chat_on", False) else "❌ OFF"
    
    mode = "Advanced 📊" if settings.get("spelling_mode") == "advanced" else "Simple 📝"
    
    text = f"""╔══════════════════════════╗
        ⚙️  SETTINGS  ⚙️  
╚══════════════════════════╝

**Group:** {message.chat.title}

📝 **Spelling Check:** {s_spell} ({mode})
🛡️ **Bio Protection:** {s_bio}
🧹 **Clean Join:** {s_clean}
⚡ **Auto Accept:** {s_auto}
🤖 **AI Chat:** {s_ai}

⬇️ **Option select karo:**"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📝 Spelling ({s_spell})", callback_data="spelling_menu")],
        [InlineKeyboardButton(f"🛡️ Bio Protection ({s_bio})", callback_data="bio_menu")],
        [
            InlineKeyboardButton(f"⚡ Auto Accept", callback_data="toggle_auto_accept"),
            InlineKeyboardButton(f"🧹 Clean Join", callback_data="toggle_cleanjoin")
        ],
        [InlineKeyboardButton(f"🤖 AI Chat ({s_ai})", callback_data="toggle_ai")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

    if is_new:
        msg = await message.reply_text(text, reply_markup=buttons)
        await MovieBotUtils.auto_delete_message(client, msg, 300)
    else:
        await message.edit_text(text, reply_markup=buttons)

# ================ 5. REQUEST HANDLER ================
@app.on_message((filters.command("request") | filters.regex(r'^#request\s+', re.IGNORECASE)) & filters.group)
async def request_handler(client: Client, message: Message):
    """Movie request handle karo - Admin tag ke saath (FIXED)"""
    if not message.from_user:
        return
    
    # Movie name extract karo
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
    
    chat_id = message.chat.id
    
    # Movie name clean karo
    validation = MovieBotUtils.validate_movie_format_advanced(movie_name)
    movie_display = validation['correct_format'] or validation['clean_name']
    
    # Admin mentions - PROPER TAGGING FIX
    admin_mentions = []
    try:
        async for member in client.get_chat_members(chat_id, filter=ChatMemberStatus.ADMINISTRATOR):
            if not member.user.is_bot:
                # Is format se user hamesha tag hoga chahe username na ho
                admin_mentions.append(f"<a href='tg://user?id={member.user.id}'>👮 {member.user.first_name}</a>")
    except:
        admin_mentions = ["👮 Admins"]
    
    admin_text = ", ".join(admin_mentions[:5])
    
    # Request Message - INDIAN STYLE
    text = f"""╔══════════════════════════╗
        🎬  MOVIE REQUEST  🎬  
╚══════════════════════════╝

📽️ **Movie:** `{movie_display}`

👤 **Requester:** {message.from_user.mention}
🆔 **ID:** `{message.from_user.id}`

👑 **Admins:**
{admin_text}

━━━━━━━━━━━━━━━━━━━━━
_Admins, please check karke upload karein!_ 🙏"""

    # BUTTONS - VERTICAL
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Upload Ho Gayi", callback_data=f"req_accept_{message.from_user.id}")],
        [InlineKeyboardButton("❌ Available Nahi Hai", callback_data=f"req_reject_{message.from_user.id}")],
        [InlineKeyboardButton("🔍 OMDb Search", callback_data=f"omdb_{validation['clean_name']}")]
    ])

    await client.send_message(chat_id, text, reply_markup=buttons)
    
    try:
        await message.delete()
    except:
        pass
    
    # Log channel - FIXED
    if Config.LOGS_CHANNEL:
        try:
            await client.send_message(
                Config.LOGS_CHANNEL,
                f"📨 **New Request**\n"
                f"Group: {message.chat.title}\n"
                f"Movie: {movie_display}\n"
                f"User: {message.from_user.id}"
            )
        except Exception as e:
            print(f"Log Error: {e}")

# ================ 6. BIO PROTECTION ================
@app.on_chat_member_updated(filters.group)
async def check_new_member_bio(client: Client, update: ChatMemberUpdated):
    """Naye member ki bio check karo - link ho to action"""
    if not update.new_chat_member:
        return
    
    # Sirf naye members
    if update.new_chat_member.status == ChatMemberStatus.MEMBER:
        user = update.new_chat_member.user
        chat_id = update.chat.id
        
        if user.is_bot or user.is_self:
            return
        
        settings = await get_settings(chat_id)
        if not settings.get("bio_check", True):
            return
        
        try:
            full_user = await client.get_chat(user.id)
            bio = full_user.bio or ""
            
            # Deep scan
            bio_check = MovieBotUtils.check_bio_safety_deep(bio)
            
            if not bio_check["safe"]:
                # Warning count
                warnings = await add_bio_warning(chat_id, user.id)
                bio_action = settings.get("bio_action", "mute")
                
                # Action message
                if warnings >= 3 and bio_action == "ban":
                    try:
                        await client.ban_chat_member(chat_id, user.id)
                        action_msg = f"🚫 **{user.first_name}** ko ban kar diya!\nReason: Bio mein {', '.join(bio_check['issues'])}"
                    except:
                        action_msg = None
                
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
                        action_msg = None
                
                else:
                    action_msg = f"⚠️ **{user.first_name}**, aapki bio mein {', '.join(bio_check['issues'])} hai.\nPlease remove karo!"
                
                if action_msg:
                    warn_msg = await client.send_message(chat_id, action_msg)
                    await MovieBotUtils.auto_delete_message(client, warn_msg, 30)
                    
        except Exception as e:
            logger.error(f"Bio Check Error: {e}")

# ================ 7. FORCE SUBSCRIBE (STRICT MODE - MUTE FIRST) ================
@app.on_chat_member_updated(filters.group)
async def handle_fsub_join(client: Client, update: ChatMemberUpdated):
    """FSub Logic: Join -> Check -> Mute if not subbed (STRICT)"""
    if not update.new_chat_member:
        return
    
    # Sirf naye members ya wapis join karne wale
    if update.old_chat_member and update.old_chat_member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
        return
        
    user = update.new_chat_member.user
    chat_id = update.chat.id
    if user.is_bot: return

    # Check Settings
    fsub_data = await get_force_sub(chat_id)
    if not fsub_data: return

    channel_id = fsub_data["channel_id"]

    # Check Membership
    is_joined = await MovieBotUtils.check_fsub_member(client, channel_id, user.id)

    if not is_joined:
        # 1. IMMEDIATELY MUTE (Strict)
        try:
            await client.restrict_chat_member(
                chat_id, user.id,
                ChatPermissions(can_send_messages=False)
            )
        except:
            pass

        # 2. Get Channel Info
        try:
            chat_info = await client.get_chat(channel_id)
            link = chat_info.invite_link or f"https://t.me/{chat_info.username}"
            ch_name = chat_info.title
        except:
            link = "https://t.me/asbhai_bsr"
            ch_name = "Channel"

        # 3. Send Warning Message
        text = f"""🔒 **Group Locked!**
        
Arey {user.mention}! 👋

Ye group **Protected** hai. Message karne ke liye aapko channel join karna padega.

📢 **Channel:** {ch_name}

👇 **Steps:**
1. Niche button se Join karo.
2. Wapis aake "Unmute Me" dabao.
3. Agar leave kiya to wapis mute ho jaoge!

_Join karke verify karo, tabhi chat khulegi!_"""

        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=link)],
            [InlineKeyboardButton("✅ Unmute Me / Verify", callback_data=f"fsub_verify_{user.id}")]
        ])

        msg = await client.send_message(chat_id, text, reply_markup=buttons)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 120))

# ================ 8. AUTO ACCEPT JOIN REQUEST ================
@app.on_chat_join_request()
async def auto_approve_join(client: Client, request: ChatJoinRequest):
    """Auto accept join requests"""
    chat_id = request.chat.id
    user_id = request.from_user.id
    
    should_approve = False
    
    # Channel hai to always approve
    if request.chat.type == ChatType.CHANNEL:
        should_approve = True
    else:
        # Group hai to settings check
        if await get_auto_accept(chat_id):
            should_approve = True
    
    if should_approve:
        try:
            await client.approve_chat_join_request(chat_id, user_id)
            
            # PM Message
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
            
            await client.send_message(user_id, text, reply_markup=buttons)
            
            # Log - FIXED
            if Config.LOGS_CHANNEL:
                await client.send_message(
                    Config.LOGS_CHANNEL,
                    f"⚡ **Auto Accept**\nUser: {user_id}\nChat: {request.chat.title}"
                )
                
        except Exception as e:
            logger.error(f"Auto Accept Error: {e}")

# ================ 9. WELCOME NEW MEMBERS (FUNNY & 5 MIN DELETE) ================
@app.on_message(filters.new_chat_members)
async def welcome_new_members(client, message):
    """Funny Welcome with Auto Delete (5 Mins)"""
    try:
        await message.delete()
    except:
        pass
    
    chat_id = message.chat.id
    
    for member in message.new_chat_members:
        if member.is_self:
            continue
        
        # 1. Generate Image
        user_photo = None
        if member.photo:
            try:
                photo = await client.download_media(member.photo.big_file_id, in_memory=True)
                user_photo = photo.getvalue()
            except: 
                pass
            
        welcome_img = await MovieBotUtils.create_welcome_image(
            member.first_name, member.id, user_photo, message.chat.title
        )

        # 2. Funny/Roast Caption
        caption = f"""
👋 **Arey {member.mention}, Swagat hai!** Group: **{message.chat.title}**

Sunn bhai/behen:
🎥 **Movie chahiye?** /request MovieName likh.
🔍 **Search karna hai?** Spelling sahi likhna!
🚫 **Bakwaas ki to?** Admin seedha uda dega.

_Shanti se raho, movie dekho aur moj karo!_ 😎
"""
        
        # 3. Send & Auto Delete (300 seconds = 5 Mins)
        if welcome_img:
            msg = await client.send_photo(chat_id, photo=welcome_img, caption=caption)
        else:
            msg = await client.send_message(chat_id, caption)
            
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ 10. GROUP MESSAGE FILTER ================
@app.on_message(filters.group & filters.text & ~filters.command([
    "start", "help", "settings", "request", "setwelcome", "addfsub", "stats", 
    "ai", "broadcast", "google", "anime", "cleanjoin", "ping", "id", "motd"
]))
async def group_message_filter(client, message):
    """Group messages filter - FSUB, Links, Abuse, Spelling with Daily Limit"""
    if not message.from_user:
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Admin check
    if await is_admin(chat_id, user_id):
        return
    
    settings = await get_settings(chat_id)
    text = message.text
    
    # 1. FSUB CHECK FOR EXISTING MEMBERS
    fsub_data = await get_force_sub(chat_id)
    if fsub_data:
        channel_id = fsub_data["channel_id"]
        cache_key = f"fsub_{user_id}_{channel_id}"
        
        if cache_key not in fsub_cache:
            try:
                member = await client.get_chat_member(channel_id, user_id)
                if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                    await message.delete()
                    
                    try:
                        chat_info = await client.get_chat(channel_id)
                        link = chat_info.invite_link or f"https://t.me/{chat_info.username}"
                    except:
                        link = "https://t.me/asbhai_bsr"
                    
                    text = f"""🔒 **Arey {message.from_user.first_name}!**

Aapne hamara **channel leave kar diya**? 🤔

Group mein message karne ke liye 
wapis channel join karo!

✅ Join karo
✅ "I've Joined" dabao
✅ Phir message karo"""
                    
                    buttons = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📢 Join Channel", url=link)],
                        [InlineKeyboardButton("✅ I've Joined", callback_data=f"fsub_verify_{user_id}")]
                    ])
                    
                    msg = await message.reply_text(text, reply_markup=buttons)
                    await MovieBotUtils.auto_delete_message(client, msg, 60)
                    return
                else:
                    fsub_cache.append(cache_key)
                    if len(fsub_cache) > 1000:
                        fsub_cache.clear()
                        
            except UserNotParticipant:
                await message.delete()
                try:
                    chat_info = await client.get_chat(channel_id)
                    link = chat_info.invite_link or f"https://t.me/{chat_info.username}"
                except:
                    link = "https://t.me/asbhai_bsr"
                
                text = f"""🔒 **Hello {message.from_user.first_name}!**

Group mein message karne ke liye 
pehle hamara **channel join karo**:

✅ Join karo
✅ "I've Joined" dabao
✅ Phir message karo"""
                
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Join Channel", url=link)],
                    [InlineKeyboardButton("✅ I've Joined", callback_data=f"fsub_verify_{user_id}")]
                ])
                
                msg = await message.reply_text(text, reply_markup=buttons)
                await MovieBotUtils.auto_delete_message(client, msg, 60)
                return
            except:
                pass
    
    # 2. LINK FILTER
    quality = MovieBotUtils.check_message_quality(text)
    
    if quality == "LINK" and settings.get("link_filter", True):
        try:
            await message.delete()
            warn_count = await add_warning(chat_id, user_id)
            
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
    
    # 3. ABUSE FILTER
    elif quality == "ABUSE" and settings.get("bad_words_filter", True):
        try:
            await message.delete()
            warn_count = await add_warning(chat_id, user_id)
            
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
    
    # 4. SPELLING CHECK & AUTO CORRECT (ADVANCED LIMIT SYSTEM)
    if settings.get("spelling_on", True):
        validation = MovieBotUtils.validate_movie_format_advanced(text)
        
        if not validation['is_valid'] and validation['clean_name']:
            try:
                await message.delete()
                
                user = message.from_user
                clean_name = validation['clean_name']
                
                can_use_advanced = await check_daily_limit(user.id)
                
                if can_use_advanced and Config.OMDB_API_KEY:
                    
                    status_msg = await message.reply_text(f"🔍 **Checking:** `{clean_name}`...")
                    data = await MovieBotUtils.get_omdb_info(clean_name)
                    await status_msg.delete()

                    if data and data['found']:
                        report = f"""🎬 **Movie Correction Report** 🎬

Hey {user.mention}, aap thoda bhatak gaye ho! 🧭

❌ **Galat Message:** `{text[:50]}`
✅ **Sahi Naam:** `{data['title']}`

✨ **Movie Details (OMDb):**
📅 Year: {data['year']} | ⭐ Rating: {data['rating']}/10
🎭 Genre: {data['genre']}
📜 Story: {data['plot']}...

⚠️ **Ab Kya Karein?**
Aapne jo extra words ya galat spelling likhi thi, use system ne sahi kar diya hai.

👉 **Ab is sahi name (`{data['title']}`) ko copy karke `/request {data['title']}` karein!** 🚀"""
                        
                        if data.get('poster') and data['poster'] != 'N/A':
                            final_msg = await client.send_photo(chat_id, data['poster'], caption=report)
                        else:
                            final_msg = await client.send_message(chat_id, report)
                        
                        await increment_daily_limit(user.id)
                        
                    else:
                        msg_text = f"""{user.mention} bhai, itna lamba kyun likh rahe ho? 🤦‍♂️

📝 **Galat:** `{text}`
🎯 **Sahi:** `{clean_name}`

Ye extra words hata kar sirf **Movie ka Naam** dalo. 
System ko confuse mat karo, warna movie nahi milegi! 🚫🎥"""
                        final_msg = await client.send_message(chat_id, msg_text)

                else:
                    msg_text = f"""{user.mention} bhai, itna lamba kyun likh rahe ho? 🤦‍♂️

📝 **Galat:** `{text}`
🎯 **Sahi:** `{clean_name}`

Ye extra words hata kar sirf **Movie ka Naam** dalo. 
System ko confuse mat karo, warna movie nahi milegi! 🚫🎥
_(Daily Advanced Limit reached 1/1)_"""
                    
                    final_msg = await client.send_message(chat_id, msg_text)
                
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, final_msg, 60))
                
            except Exception as e:
                logger.error(f"Spelling check error: {e}")
                pass
    
    # 5. AI CHAT
    if settings.get("ai_chat_on", False):
        bot_id = (await client.get_me()).id
        
        should_reply = False
        if message.reply_to_message and message.reply_to_message.from_user.id == bot_id:
            should_reply = True
        elif not message.reply_to_message:
            should_reply = True
        
        if should_reply:
            await show_typing(chat_id)
            await asyncio.sleep(0.5)
            
            response = await MovieBotUtils.get_ai_response(text)
            msg = await message.reply_text(response)
            await MovieBotUtils.auto_delete_message(client, msg, 300)

# ================ 11. CALLBACK HANDLER ================
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
                    await client.restrict_chat_member(
                        chat_id, user_id,
                        ChatPermissions(
                            can_send_messages=True,
                            can_send_media_messages=True,
                            can_send_other_messages=True
                        )
                    )
                    await query.message.delete()
                    msg = await client.send_message(
                        chat_id,
                        f"✅ **{query.from_user.first_name} verified!**\n\nAb aap group mein chat kar sakte ho! 🎉"
                    )
                    await MovieBotUtils.auto_delete_message(client, msg, 60)
                    await query.answer("✅ Verified!")
                    
                    cache_key = f"fsub_{user_id}_{channel_id}"
                    fsub_cache.append(cache_key)
                    
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
            if len(parts) >= 3:
                req_user_id = int(parts[2])
                await client.send_message(
                    chat_id,
                    f"✅ **Movie Upload Ho Gayi!** 🎉\n\n"
                    f"{query.from_user.mention} ne movie upload kar di hai!\n"
                    f"<a href='tg://user?id={req_user_id}'>Requester</a>, please check karo!"
                )
                await query.message.delete()
                await query.answer("✅ Request accepted!")
        
        # === REQUEST REJECT ===
        elif data.startswith("req_reject_"):
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            parts = data.split("_")
            if len(parts) >= 3:
                await client.send_message(
                    chat_id,
                    f"❌ **Movie Available Nahi Hai!**\n\n"
                    f"Request rejected by {query.from_user.mention}.\n"
                    f"Sorry, ye movie abhi available nahi hai! 😔"
                )
                await query.message.delete()
                await query.answer("❌ Request rejected!")
        
        # === OMDb SEARCH ===
        elif data.startswith("omdb_"):
            movie_name = data[5:]
            await query.answer("🔍 Searching OMDb...")
            omdb_info = await MovieBotUtils.get_omdb_info(movie_name)
            await query.message.edit_text(omdb_info)
        
        # === SPELLING MENU ===
        elif data == "spelling_menu":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            
            settings = await get_settings(chat_id)
            current_mode = settings.get("spelling_mode", "simple")
            
            text = f"""📝 **Spelling Check Settings**

**Simple Mode:** 
• Extra words hata ke correct format batayega
• Movie naam saaf karega

**Advanced Mode:** 
• OMDb se movie info search karega
• Correct spelling suggest karega
• IMDb rating + Genre batayega

**Current Mode:** {'Advanced' if current_mode == 'advanced' else 'Simple'}"""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📝 Simple", callback_data="set_spelling_simple"),
                    InlineKeyboardButton("📊 Advanced", callback_data="set_spelling_advanced")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="settings_menu")]
            ])
            
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
        
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
                await query.answer("❌ OMDb API key missing!", show_alert=True)
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
            action_text = "Mute" if bio_action == "mute" else "Ban"
            
            text = f"""🛡️ **Bio Protection Settings**

**Kya karta hai?**
• Naye members ki bio scan
• Links/usernames detect
• Warning → Mute → Ban

**Status:** {bio_status}
**Action:** {action_text}

**Rules:**
• 1st time: Warning
• 2nd time: 1 hour Mute
• 3rd time: Ban"""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔇 Mute", callback_data="bio_action_mute"),
                    InlineKeyboardButton("🚫 Ban", callback_data="bio_action_ban")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="settings_menu")]
            ])
            
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
        
        # === BIO ACTION ===
        elif data == "bio_action_mute":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            await update_settings(chat_id, "bio_action", "mute")
            await query.answer("✅ Action: Mute")
            await show_settings_menu(client, query, is_new=False)
        
        elif data == "bio_action_ban":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Sirf admins!", show_alert=True)
                return
            await update_settings(chat_id, "bio_action", "ban")
            await query.answer("✅ Action: Ban")
            await show_settings_menu(client, query, is_new=False)
        
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
        
        # === SETTINGS MENU ===
        elif data == "settings_menu":
            await show_settings_menu(client, query, is_new=False)
            await query.answer()
        
        # === HELP AUTOACCEPT (NEW) ===
        elif data == "help_autoaccept":
            text = """⚡ **Auto Accept Setup Guide**

**For Channel:**
1. Bot ko Channel mein Admin banao.
2. Bas! Bot apne aap requests accept karega.

**For Group:**
1. Bot ko Group mein Admin banao.
2. Group mein `/settings` type karo.
3. 'Auto Accept' button ko ON karo.

_Note: Bot user ko PM bhi karega jab accept hoga._"""
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_menu")]]))
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

**👑 Admin ke liye:**
• /settings - Bot settings
• /addfsub - Force subscribe
• /cleanjoin - Join msg delete
• /setwelcome - Welcome set

**💎 Premium:**
Contact @asbhai_bsr"""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📖 Examples", callback_data="help_examples"),
                    InlineKeyboardButton("⚙️ Settings Guide", callback_data="help_settings")
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
• `/anime Demon Slayer`"""
            
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

**How to use:**
/settings - Admin rights required!"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_menu")]
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

**💰 Pricing:**
• 1 Month: ₹100
• 3 Months: ₹250
• 6 Months: ₹450
• 1 Year: ₹800

**🛒 Buy Premium:**
Contact @asbhai_bsr

🎁 **3 Days Trial Available!**"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Contact Owner", url="https://t.me/asbhai_bsr")],
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

# ================ 12. AI COMMAND ================
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
    
    await show_typing(message.chat.id)
    waiting_msg = await message.reply_text("💭 **Soch raha hoon...**")
    
    response = await MovieBotUtils.get_ai_response(query)
    
    await waiting_msg.delete()
    msg = await message.reply_text(response)
    await MovieBotUtils.auto_delete_message(client, msg, 300)

# ================ 13. GOOGLE SEARCH ================
@app.on_message(filters.command("google"))
async def google_search_cmd(client, message):
    if len(message.command) < 2:
        await message.reply_text("❌ **Usage:** /google search query")
        return
    
    query = " ".join(message.command[1:])
    msg = await message.reply_text("🔍 **Google search ho raha hai...**")
    
    results = await MovieBotUtils.get_google_search(query)
    
    if not results:
        await msg.edit_text(
            "❌ **Koi result nahi mila!**\n\n"
            "🔍 Different keywords try karo ya spelling check karo."
        )
        return
    
    text = f"🔍 **Search Results:** {query}\n\n"
    for i, (href, title) in enumerate(results[:5], 1):
        text += f"{i}. [{title}]({href})\n"
    
    await msg.edit_text(text, disable_web_page_preview=True)

# ================ 14. ANIME SEARCH ================
@app.on_message(filters.command("anime"))
async def anime_search_cmd(client, message):
    if len(message.command) < 2:
        await message.reply_text("❌ **Usage:** /anime Anime Name")
        return
    
    query = " ".join(message.command[1:])
    msg = await message.reply_text("🇯🇵 **Anime search ho raha hai...**")
    
    data = await MovieBotUtils.get_anime_info(query)
    
    if data:
        text = (
            f"🎬 **{data['title']}**\n\n"
            f"⭐ **Rating:** {data['score']}/10\n"
            f"📺 **Episodes:** {data['episodes']}\n"
            f"📝 **Story:** {data['synopsis']}"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 More Info", url=data['url'])]
        ])
        await msg.edit_text(text, reply_markup=buttons)
    else:
        await msg.edit_text("❌ **Anime nahi mila!** Spelling check karo.")

# ================ 15. MOVIE OF THE DAY ================
@app.on_message(filters.command(["movieoftheday", "motd"]))
async def movie_of_the_day(client: Client, message: Message):
    if not Config.OMDB_API_KEY:
        await message.reply_text("❌ OMDb API key missing!")
        return
    
    msg = await message.reply_text("🎬 **Aaj ki movie dhundh raha hoon...**")
    
    movie = await MovieBotUtils.get_random_movie()
    
    if movie:
        text = (
            f"🎬 **MOVIE OF THE DAY** 🎬\n\n"
            f"📽️ **{movie['title']}** ({movie['year']})\n"
            f"🎭 **Genre:** {movie['genre']}\n"
            f"⭐ **IMDb:** {movie['rating']}/10\n\n"
            f"📅 **Date:** {datetime.datetime.now().strftime('%d %B %Y')}\n\n"
            f"💡 **Request karo:** `/request {movie['title']}`\n\n"
            f"**Happy Watching!** 🍿"
        )
        
        await msg.edit_text(text)
    else:
        await msg.edit_text(
            "❌ **Aaj ki movie nahi mil sakti!**\n\n"
            "Thodi der baad try karo."
        )

# ================ 16. SET WELCOME ================
@app.on_message(filters.command("setwelcome") & filters.group)
async def set_welcome_command(client, message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("❌ Sirf admins!")
    
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
            "2. `/setwelcome Welcome {name} to {chat}!`"
        )
        return
    
    await set_welcome_message(message.chat.id, welcome_text, photo_id)
    await message.reply("✅ **Custom Welcome Set!** ✅")

# ================ 17. CLEAN JOIN TOGGLE ================
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

# ================ 18. FORCE SUBSCRIBE COMMAND ================
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
            [InlineKeyboardButton("💎 Buy Premium", url="https://t.me/asbhai_bsr")]
        ])
        msg = await message.reply_text(
            "💎 **Force Subscribe is Premium Feature!**\n\n"
            "Contact @asbhai_bsr for premium.",
            reply_markup=buttons
        )
        await MovieBotUtils.auto_delete_message(client, msg, 30)
        return

    channel_id = None
    
    if len(message.command) > 1:
        try:
            channel_id = int(message.command[1])
        except ValueError:
            msg = await message.reply_text("❌ Invalid Channel ID!\nNumeric ID do: -100xxxxxxx")
            await MovieBotUtils.auto_delete_message(client, msg, 5)
            return

    elif message.reply_to_message and message.reply_to_message.forward_from_chat:
        channel_id = message.reply_to_message.forward_from_chat.id
    else:
        msg = await message.reply_text(
            "❌ **Usage:**\n"
            "1. `/addfsub -100xxxxxxx`\n"
            "2. Channel ki kisi post ko reply karo `/addfsub` se"
        )
        await MovieBotUtils.auto_delete_message(client, msg, 10)
        return

    try:
        chat = await client.get_chat(channel_id)
        bot_member = await client.get_chat_member(channel_id, (await client.get_me()).id)
        if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            msg = await message.reply_text("❌ Main uss channel mein admin nahi hoon!")
            await MovieBotUtils.auto_delete_message(client, msg, 5)
            return
    except Exception as e:
        msg = await message.reply_text("❌ Error: Mujhe channel mein admin banao pehle!")
        await MovieBotUtils.auto_delete_message(client, msg, 5)
        return

    await set_force_sub(message.chat.id, channel_id)
    msg = await message.reply_text(
        f"✅ **Force Subscribe Enabled!**\n\n"
        f"📢 **Channel:** {chat.title}\n\n"
        f"Ab naye members ko channel join karna hoga group mein chat karne ke liye!"
    )
    await MovieBotUtils.auto_delete_message(client, msg, 30)

# ================ 19. PING ================
@app.on_message(filters.command("ping"))
async def ping_command(client: Client, message: Message):
    start = time.time()
    msg = await message.reply_text("🏓 **Pinging...**")
    end = time.time()
    ping = round((end - start) * 1000, 2)
    await msg.edit_text(f"🏓 **Pong!** `{ping}ms`")

# ================ 20. ID ================
@app.on_message(filters.command("id"))
async def id_command(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else "Unknown"
    text = f"👤 **Your ID:** `{user_id}`\n"
    if message.chat.type != "private":
        text += f"👥 **Group ID:** `{message.chat.id}`\n"
    
    await message.reply_text(text)

# ================ 21. GROUP JOIN/LEAVE (LOGS FIXED) ================
@app.on_chat_member_updated(filters.group)
async def bot_added_or_removed(client: Client, update: ChatMemberUpdated):
    bot_id = (await client.get_me()).id
    
    # BOT ADDED
    if update.new_chat_member and update.new_chat_member.user.id == bot_id:
        if update.new_chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
            chat = update.chat
            logger.info(f"✅ Bot added to group: {chat.id} - {chat.title}")
            await add_group(chat.id, chat.title, chat.username)
            
            # Log Channel - FIXED
            if Config.LOGS_CHANNEL:
                try:
                    invite = "No Link"
                    if chat.username:
                        invite = f"@{chat.username}"
                    
                    await client.send_message(
                        Config.LOGS_CHANNEL,
                        f"🟢 **BOT ADDED TO GROUP**\n\n"
                        f"🏷️ **Name:** {chat.title}\n"
                        f"🆔 **ID:** `{chat.id}`\n"
                        f"🔗 **Link:** {invite}\n"
                        f"👤 **Added By:** {update.from_user.mention if update.from_user else 'Unknown'}"
                    )
                except Exception as e:
                    print(f"Log Error: {e}")
            
            # Welcome message
            text = f"""🎉 **Thanks for adding me!**

Group: **{chat.title}**
ID: `{chat.id}`

🚀 **Get Started:**
• /settings - Bot settings
• /request - Movie request
• /help - All commands

💎 **Premium:**
• Force Subscribe
• @asbhai_bsr

_Enjoy! Bot is ready to serve! 🤖_"""
            
            try:
                await client.send_message(chat.id, text)
            except:
                pass
    
    # BOT REMOVED
    elif update.old_chat_member and update.old_chat_member.user.id == bot_id:
        if update.old_chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
            if not update.new_chat_member or update.new_chat_member.status == ChatMemberStatus.LEFT:
                chat_id = update.chat.id
                await mark_bot_removed(chat_id, True)
                
                # Log Channel - FIXED
                if Config.LOGS_CHANNEL:
                    try:
                        await client.send_message(
                            Config.LOGS_CHANNEL,
                            f"🔴 **BOT REMOVED**\n\n"
                            f"🏷️ **Name:** {update.chat.title}\n"
                            f"🆔 **ID:** `{chat_id}`"
                        )
                    except:
                        pass

# ================ 22. SCHEDULED CLEANUP ================
async def scheduled_cleanup():
    while True:
        try:
            await asyncio.sleep(Config.CLEANUP_INTERVAL)
            
            junk_count = await clear_junk()
            MovieBotUtils.clean_cache()
            
            total = sum(junk_count.values())
            if total > 0:
                logger.info(f"Cleanup: {total} items removed")
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            await asyncio.sleep(3600)

# ================ 23. START BOT ================
async def start_bot():
    asyncio.create_task(scheduled_cleanup())
    
    await app.start()
    
    bot_info = await app.get_me()
    await set_bot_instance(bot_info.id, "running")
    
    await force_set_commands(app, None)
    
    logger.info(f"✅ Bot started as @{bot_info.username}")
    
    try:
        await app.send_message(
            Config.OWNER_ID,
            f"🤖 **Bot Started!**\n\n"
            f"• **Bot:** @{bot_info.username}\n"
            f"• **Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"• **Status:** ✅ Running"
        )
    except:
        pass
    
    await idle()

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 Movie Helper Bot Starting...")
    print("="*50 + "\n")
    
    try:
        app.run(start_bot())
    except KeyboardInterrupt:
        print("\n⏹️ Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot crashed: {e}")
        import traceback
        traceback.print_exc()
