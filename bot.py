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

# ================ BOT COMMANDS SETUP ================
async def set_bot_commands():
    commands = [
        BotCommand("start", "🤖 Bot start karo"),
        BotCommand("help", "📚 Commands aur help"),
        BotCommand("request", "🎬 Movie request karo"),
        BotCommand("ai", "🤖 AI se movie pucho"),
        BotCommand("google", "🔍 Google search"),
        BotCommand("anime", "🇯🇵 Anime search"),
        BotCommand("motd", "🎥 Movie of the day"),
        BotCommand("ping", "🏓 Bot status check"),
        BotCommand("id", "🆔 ID dekho"),
        BotCommand("settings", "⚙️ Group settings (Admin)"),
        BotCommand("addfsub", "📢 Force subscribe lagawo (Premium)"),
        BotCommand("cleanjoin", "🧹 Join message delete"),
        BotCommand("setwelcome", "👋 Welcome message set karo"),
        BotCommand("stats", "📊 Bot stats (Owner)")
    ]
    
    try:
        await app.set_bot_commands(commands, scope=BotCommandScopeAllGroupChats())
        logger.info("✅ Bot commands set successfully")
    except Exception as e:
        logger.warning(f"⚠️ Could not set commands: {e}")

# ================ GROUP JOIN/LEAVE HANDLERS ================
@app.on_chat_member_updated(filters.group)
async def bot_added_or_removed(client: Client, update: ChatMemberUpdated):
    bot_id = (await client.get_me()).id
    
    if update.new_chat_member and update.new_chat_member.user.id == bot_id:
        if update.new_chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
            chat = update.chat
            logger.info(f"✅ Bot added to group: {chat.id} - {chat.title}")
            await add_group(chat.id, chat.title, chat.username)
            
            try:
                await client.send_message(
                    Config.OWNER_ID,
                    f"✅ **Bot Added to Group**\n\n"
                    f"Group: {chat.title}\n"
                    f"ID: {chat.id}\n"
                    f"Username: @{chat.username if chat.username else 'Private'}"
                )
            except:
                pass
    
    elif update.old_chat_member and update.old_chat_member.user.id == bot_id:
        if update.old_chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
            if not update.new_chat_member or update.new_chat_member.status == ChatMemberStatus.LEFT:
                chat_id = update.chat.id
                chat_title = update.chat.title
                logger.info(f"❌ Bot removed from group: {chat_id}")
                await mark_bot_removed(chat_id, True)
                
                try:
                    await client.send_message(
                        Config.OWNER_ID,
                        f"❌ **Bot Removed from Group**\n\n"
                        f"Group: {chat_title}\n"
                        f"ID: {chat_id}"
                    )
                except:
                    pass

# ================ BIO PROTECTION SYSTEM ================
@app.on_chat_member_updated(filters.group)
async def check_new_member_bio(client: Client, update: ChatMemberUpdated):
    if not update.new_chat_member:
        return
    
    if update.new_chat_member.status == ChatMemberStatus.MEMBER:
        if update.new_chat_member.user.id == (await client.get_me()).id:
            return
            
        chat_id = update.chat.id
        user = update.new_chat_member.user
        settings = await get_settings(chat_id)
        
        if settings.get("clean_join", True):
            try:
                await update.message.delete()
            except:
                pass

        if settings.get("bio_check", True):
            try:
                full_user = await client.get_chat(user.id)
                bio = full_user.bio or ""
                
                bio_check = MovieBotUtils.check_bio_safety_deep(bio)
                
                if not bio_check["safe"]:
                    warnings = await add_bio_warning(chat_id, user.id)
                    bio_action = settings.get("bio_action", "mute")
                    
                    action_msg = ""
                    
                    if warnings >= 3 and bio_action == "ban":
                        try:
                            await client.ban_chat_member(chat_id, user.id)
                            action_msg = f"🚫 **{user.first_name}** ko ban kar diya gaya (Bio mein link/username)"
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
                            action_msg = f"🔇 **{user.first_name}** ko 1 hour ke liye mute kiya (Bio mein link/username)"
                        except:
                            pass
                    
                    else:
                        action_msg = f"⚠️ **{user.first_name}**, aapki bio mein link/username hai. Please remove karo!"
                    
                    if action_msg:
                        warn_msg = await client.send_message(chat_id, action_msg)
                        asyncio.create_task(MovieBotUtils.auto_delete_message(client, warn_msg, 30))
                        
            except Exception as e:
                logger.error(f"Bio Check Error: {e}")

# ================ START COMMAND ================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    user = message.from_user
    await add_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text = f"""🎬 **Namaste {user.first_name}!** 🤗

Main hoon **Movie Helper Bot** - Aapka personal group assistant!

✨ **Kya kya kar sakta hoon?**
• ✅ Movie requests handle karta hoon
• ✅ Spelling check with OMDb
• ✅ Bio mein link ho to action leta hoon
• ✅ Auto accept join requests
• ✅ Force subscribe (Premium)
• ✅ AI se baat karo movie ke baare mein

👇 **Button dabao aur group mein add karo!**"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Group Mein Add Karo", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton("⚙️ Auto Accept Setup", callback_data="auto_accept_setup"),
         InlineKeyboardButton("📚 Commands", callback_data="help_main")],
        [InlineKeyboardButton("👑 Owner", url="https://t.me/asbhai_bsr")]
    ])
    
    msg = await message.reply_text(welcome_text, reply_markup=buttons)
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ HELP COMMAND ================
@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    help_text = """╔══════════════════════════╗
        🆘  HELP MENU  🆘  
╚══════════════════════════╝

**Sabke liye commands:**
• /start - Bot start
• /help - Yeh menu
• /request <movie> - Movie request
• /ai <question> - AI se pucho
• /google <query> - Google search
• /anime <name> - Anime search
• /motd - Aaj ki movie
• /ping - Bot check
• /id - ID dekho

**👑 Admin commands:**
• /settings - Bot settings
• /addfsub - Force subscribe (Premium)
• /cleanjoin - Join message delete
• /setwelcome - Welcome set karo

**💎 Premium features:**
• Force Subscribe System
• No ads
• Priority support

Contact @asbhai_bsr for premium!"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Settings Guide", callback_data="help_settings"),
         InlineKeyboardButton("💎 Premium", callback_data="premium_info")],
        [InlineKeyboardButton("📖 Examples", callback_data="help_example"),
         InlineKeyboardButton("❌ Close", callback_data="close_help")]
    ])
    
    msg = await message.reply_text(help_text, reply_markup=buttons)
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ SETTINGS COMMAND ================
@app.on_message(filters.command("settings") & filters.group)
async def settings_command(client: Client, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ Sirf admins hi settings change kar sakte hain!")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 5))
        return
    
    await show_settings_menu(client, message, is_new=True)

async def show_settings_menu(client, message_or_query, is_new=False):
    if is_new:
        message = message_or_query
        chat_id = message.chat.id
    else:
        message = message_or_query.message
        chat_id = message.chat.id

    settings = await get_settings(chat_id)
    auto_acc = await get_auto_accept(chat_id)
    
    s_spell = "✅ ON" if settings.get("spelling_on") else "❌ OFF"
    s_mode = "Advanced" if settings.get("spelling_mode") == "advanced" else "Simple"
    s_ai = "✅ ON" if settings.get("ai_chat_on") else "❌ OFF"
    s_bio = "✅ ON" if settings.get("bio_check") else "❌ OFF"
    s_clean = "✅ ON" if settings.get("clean_join") else "❌ OFF"
    s_auto = "✅ ON" if auto_acc else "❌ OFF"
    
    text = f"""⚙️ **SETTINGS PANEL** - {message.chat.title}

📝 **Spelling Check:** {s_spell} ({s_mode})
🤖 **AI Chat:** {s_ai}
🛡️ **Bio Protect:** {s_bio}
🧹 **Clean Join:** {s_clean}
⚡ **Auto Accept:** {s_auto}

⬇️ **Options select karo:**"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📝 Spelling ({s_spell})", callback_data="spelling_menu")],
        [InlineKeyboardButton(f"🛡️ Bio Protection ({s_bio})", callback_data="bio_menu")],
        [InlineKeyboardButton(f"⚡ Auto Accept ({s_auto})", callback_data="toggle_auto_accept"),
         InlineKeyboardButton(f"🧹 Clean Join ({s_clean})", callback_data="toggle_cleanjoin")],
        [InlineKeyboardButton(f"🤖 AI Chat ({s_ai})", callback_data="toggle_ai")],
        [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
    ])

    if is_new:
        msg = await message.reply_text(text, reply_markup=buttons)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))
    else:
        await message.edit_text(text, reply_markup=buttons)

# ================ BROADCAST COMMAND ================
@app.on_message(filters.command(["broadcast", "grp_broadcast"]) & filters.user(Config.OWNER_ID))
async def broadcast_command(client: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("❌ Kisi message ko reply karo broadcast karne ke liye!")
    
    is_group = "grp_broadcast" in message.text
    target_ids = await get_all_groups() if is_group else await get_all_users()
    total = len(target_ids)
    
    progress_msg = await message.reply_text(f"📤 **Broadcast shuru...**\n\nTotal targets: {total}")
    
    success, failed, removed = 0, 0, 0
    
    for i, chat_id in enumerate(target_ids, 1):
        try:
            await message.reply_to_message.copy(chat_id)
            success += 1
            
            if i % 10 == 0:
                bar = MovieBotUtils.get_progress_bar(i, total)
                await progress_msg.edit_text(f"📤 **Broadcasting...**\n\n{bar}\n✅ Success: {success}\n❌ Failed: {failed}")
            
            await asyncio.sleep(Config.BROADCAST_DELAY)
            
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await message.reply_to_message.copy(chat_id)
                success += 1
            except:
                failed += 1
                
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["USER_IS_BLOCKED", "INPUT_USER_DEACTIVATED", "chat not found", "PEER_ID_INVALID"]):
                if is_group:
                    await mark_bot_removed(chat_id, True)
                else:
                    await delete_user(chat_id)
                removed += 1
            else:
                failed += 1
                logger.error(f"Broadcast fail {chat_id}: {e}")
    
    await progress_msg.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"📤 **Target:** {total}\n"
        f"✅ **Success:** {success}\n"
        f"❌ **Failed:** {failed}\n"
        f"🗑️ **Removed:** {removed}"
    )

# ================ REQUEST HANDLER ================
@app.on_message((filters.command("request") | filters.regex(r'^#request\s+', re.IGNORECASE)) & filters.group)
async def request_handler(client: Client, message: Message):
    if not message.from_user:
        return
    
    if message.text.startswith("/"):
        if len(message.command) < 2:
            msg = await message.reply_text("❌ **Usage:** /request Movie Name")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 5))
            return
        movie_name = " ".join(message.command[1:])
    else:
        movie_name = message.text.split('#request', 1)[1].strip()
    
    chat_id = message.chat.id
    
    # Get admin mentions
    admin_mentions = await MovieBotUtils.get_admin_mentions(client, chat_id)
    
    # Check spelling
    validation = MovieBotUtils.validate_movie_format_advanced(movie_name)
    
    if validation['clean_name']:
        movie_display = validation['correct_format']
    else:
        movie_display = movie_name
    
    request_text = (
        f"🎬 **Naya Movie Request!**\n\n"
        f"📽️ **Movie:** `{movie_display}`\n"
        f"👤 **Requester:** {message.from_user.mention}\n"
        f"🆔 **ID:** `{message.from_user.id}`\n\n"
        f"🔔 **Admin Tag:**\n{admin_mentions}\n\n"
        f"_Admins please check karo!_ 🙏"
    )

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Upload Ho Gayi", callback_data=f"req_accept_{message.from_user.id}"),
            InlineKeyboardButton("❌ Available Nahi", callback_data=f"req_reject_{message.from_user.id}")
        ],
        [InlineKeyboardButton("🔍 OMDb Search", callback_data=f"omdb_{validation['clean_name']}")]
    ])

    await client.send_message(chat_id, request_text, reply_markup=buttons)
    
    try:
        await message.delete()
    except:
        pass

# ================ AUTO APPROVE JOIN ================
@app.on_chat_join_request()
async def auto_approve_join(client: Client, request: ChatJoinRequest):
    chat_id = request.chat.id
    user_id = request.from_user.id
    
    if await get_auto_accept(chat_id):
        try:
            await client.approve_chat_join_request(chat_id, user_id)
            
            welcome_text = (
                f"🎉 **Welcome {request.from_user.first_name}!**\n\n"
                f"Aapki request **{request.chat.title}** mein approve ho gayi!\n"
                f"Group mein enjoy karo aur rules follow karo! ❤️"
            )
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 Group Open Karo", url=request.chat.invite_link or f"https://t.me/{request.chat.username}")],
            ])
            
            await client.send_message(user_id, welcome_text, reply_markup=buttons)
        except Exception as e:
            logger.error(f"Auto Accept Error: {e}")

# ================ SET WELCOME ================
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
        return await message.reply("❌ Kisi photo ya text ko reply karo ya welcome message likho!")
        
    await set_welcome_message(message.chat.id, welcome_text, photo_id)
    await message.reply("✅ **Custom Welcome Set!** ✅")

# ================ WELCOME NEW MEMBERS ================
@app.on_message(filters.new_chat_members)
async def welcome_new_members(client, message):
    try:
        await message.delete()
    except:
        pass
    
    custom_welcome = await get_welcome_message(message.chat.id)
    
    for member in message.new_chat_members:
        if member.is_self:
            continue
        
        # Get user photo for welcome
        user_photo = None
        if member.photo:
            try:
                photo = await client.download_media(member.photo.big_file_id, in_memory=True)
                user_photo = photo.getvalue()
            except:
                pass
        
        if custom_welcome:
            text = custom_welcome['text'].replace("{name}", member.mention).replace("{chat}", message.chat.title)
            photo = custom_welcome['photo_id']
            
            if photo:
                welcome_msg = await client.send_photo(message.chat.id, photo=photo, caption=text)
            else:
                welcome_msg = await client.send_message(message.chat.id, text)
        else:
            # Default welcome with DP
            caption = (
                f"👋 **Welcome {member.mention}!** 🎉\n\n"
                f"🏠 Group: {message.chat.title}\n"
                f"🆔 ID: `{member.id}`\n\n"
                f"📝 **Rules:**\n"
                f"• No spam/abuse\n"
                f"• No links without permission\n"
                f"• Request movie: /request Movie Name\n\n"
                f"**Enjoy your stay!** ❤️"
            )
            
            if user_photo:
                try:
                    welcome_sticker = await MovieBotUtils.create_welcome_sticker(
                        user_photo, 
                        message.chat.title[:20], 
                        Config.BOT_USERNAME
                    )
                    if welcome_sticker:
                        welcome_msg = await client.send_photo(
                            message.chat.id,
                            photo=welcome_sticker,
                            caption=caption
                        )
                    else:
                        welcome_msg = await client.send_photo(
                            message.chat.id,
                            photo=member.photo.big_file_id,
                            caption=caption
                        )
                except:
                    welcome_msg = await message.reply_text(caption)
            else:
                welcome_msg = await message.reply_text(caption)
        
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 120))

# ================ GROUP MESSAGE FILTER ================
@app.on_message(filters.group & filters.text & ~filters.command([
    "start", "help", "settings", "request", "setwelcome", "addfsub", "stats", 
    "ai", "broadcast", "google", "anime", "cleanjoin", "ping", "id", "motd"
]))
async def group_message_filter(client, message):
    if not message.from_user:
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # --- CHECK ADMIN FIRST (CACHED) ---
    if await is_admin(chat_id, user_id):
        return
    
    settings = await get_settings(chat_id)
    text = message.text

    # --- 0. FSUB CHECK FOR EXISTING MEMBERS (CRITICAL FIX) ---
    # Yeh check karega ki jo user pehle se group mein hai aur channel leave kar chuka hai
    fsub_data = await get_force_sub(chat_id)
    if fsub_data:
        channel_id = fsub_data["channel_id"]
        cache_key = f"fsub_{user_id}_{channel_id}"
        
        # Agar cache mein nahi hai to verify karo
        if cache_key not in fsub_cache:
            try:
                member = await client.get_chat_member(channel_id, user_id)
                # Agar user channel mein nahi hai (LEFT/BANNED/KICKED)
                if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED, ChatMemberStatus.KICKED]:
                    # User channel join nahi hai - message delete karo aur force sub message bhejo
                    await message.delete()
                    
                    try:
                        chat_info = await client.get_chat(channel_id)
                        channel_name = chat_info.title
                        link = chat_info.invite_link or f"https://t.me/{chat_info.username}"
                    except:
                        channel_name = "Channel"
                        link = "https://t.me/asbhai_bsr"
                    
                    buttons = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📢 Join Channel", url=link)],
                        [InlineKeyboardButton("✅ I've Joined", callback_data=f"fsub_verify_{user_id}")]
                    ])
                    
                    msg = await message.reply_text(
                        f"🔒 **Arey {message.from_user.first_name}!**\n\n"
                        f"Aapne hamara channel **{channel_name}** leave kar diya hai.\n"
                        f"Group mein message karne ke liye wapis join karo!",
                        reply_markup=buttons
                    )
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 60))
                    return  # IMPORTANT: Yahan return karo, aage ka code execute nahi hoga
                
                else:
                    # User channel mein hai, cache mein daaldo
                    fsub_cache.append(cache_key)
                    if len(fsub_cache) > 1000:
                        fsub_cache.clear()
                        
            except UserNotParticipant:
                # User channel ka member hi nahi hai
                await message.delete()
                try:
                    chat_info = await client.get_chat(channel_id)
                    link = chat_info.invite_link or f"https://t.me/{chat_info.username}"
                except:
                    link = "https://t.me/asbhai_bsr"
                
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Join Channel", url=link)],
                    [InlineKeyboardButton("✅ I've Joined", callback_data=f"fsub_verify_{user_id}")]
                ])
                
                msg = await message.reply_text(
                    f"🔒 **Arey {message.from_user.first_name}!**\n\n"
                    f"Group mein message karne ke liye pehle hamara channel join karo!",
                    reply_markup=buttons
                )
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 60))
                return
                
            except Exception as e:
                # Agar koi error hai (bot admin nahi hai etc) to ignore karo
                pass

    # 1. Check for links/abuse
    quality = MovieBotUtils.check_message_quality(text)
    
    if quality == "LINK" and settings.get("link_filter", True):
        try:
            await message.delete()
            warn_count = await add_warning(chat_id, message.from_user.id)
            
            if warn_count >= Config.MAX_WARNINGS:
                try:
                    await client.restrict_chat_member(
                        chat_id, 
                        message.from_user.id, 
                        ChatPermissions(can_send_messages=False),
                        until_date=datetime.datetime.now() + datetime.timedelta(hours=24)
                    )
                    msg = await message.reply_text(f"🚫 {message.from_user.first_name}, aapko 24hr mute kiya (Links)!")
                    await reset_warnings(chat_id, message.from_user.id)
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))
                except:
                    pass
            else:
                msg = await message.reply_text(
                    f"⚠️ **Warning {warn_count}/{Config.MAX_WARNINGS}**\n\n"
                    f"{message.from_user.mention}, group mein links allowed nahi hain!\n"
                    f"Next warning par action hoga!"
                )
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))
        except:
            pass
        return
    
    elif quality == "ABUSE" and settings.get("bad_words_filter", True):
        try:
            await message.delete()
            warn_count = await add_warning(chat_id, message.from_user.id)
            
            if warn_count >= Config.MAX_WARNINGS:
                try:
                    await client.ban_chat_member(chat_id, message.from_user.id)
                    msg = await message.reply_text(f"🚫 {message.from_user.first_name} banned (Abuse)!")
                    await reset_warnings(chat_id, message.from_user.id)
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))
                except:
                    pass
            else:
                msg = await message.reply_text(
                    f"⚠️ **Warning {warn_count}/{Config.MAX_WARNINGS}**\n\n"
                    f"{message.from_user.mention}, abusive language use mat karo!\n"
                    f"Group culture maintain karo!"
                )
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))
        except:
            pass
        return
    
    # 2. Spelling check
    if settings.get("spelling_on", True):
        validation = MovieBotUtils.validate_movie_format_advanced(text)
        
        if not validation['is_valid'] and validation['clean_name']:
            mode = settings.get("spelling_mode", "simple")
            
            if mode == "simple":
                try:
                    await message.delete()
                    
                    if validation['found_junk']:
                        junk_text = ", ".join(validation['found_junk'])
                        extra_msg = f"\n❌ Extra words: `{junk_text}`\n✅ Sirf movie naam likho!"
                    else:
                        extra_msg = ""
                    
                    msg = await message.reply_text(
                        f"❌ **Wrong Format!** {message.from_user.mention}\n\n"
                        f"✅ **Correct:** `{validation['correct_format']}`{extra_msg}\n\n"
                        f"💡 **Example:** `/request {validation['clean_name']}`"
                    )
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 20))
                except:
                    pass
                
            elif mode == "advanced" and Config.OMDB_API_KEY:
                try:
                    await message.delete()
                    waiting = await message.reply_text(f"🔍 Searching for `{validation['clean_name']}`...")
                    
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
                            f"✅ **Correct Name:** `{validation['clean_name']}`\n\n"
                            f"{omdb_info}",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton(f"🔍 Request This", 
                                    switch_inline_query_current_chat=f"/request {validation['clean_name']}")]
                            ])
                        )
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
                except:
                    pass
            return
    
    # 3. AI Chat
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
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ GOOGLE SEARCH ================
@app.on_message(filters.command("google"))
async def google_search_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** /google search query")
    
    query = " ".join(message.command[1:])
    msg = await message.reply("🔍 **Google search ho raha hai...**")
    
    results = await MovieBotUtils.get_google_search(query)
    
    if not results:
        return await msg.edit_text(
            "❌ **Koi result nahi mila!**\n\n"
            "🔍 Different keywords try karo ya spelling check karo."
        )
    
    text = f"🔍 **Search Results:** {query}\n\n"
    for i, (href, title) in enumerate(results[:5], 1):
        text += f"{i}. [{title}]({href})\n"
    
    await msg.edit_text(text, disable_web_page_preview=True)

# ================ ANIME SEARCH ================
@app.on_message(filters.command("anime"))
async def anime_search_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** /anime Anime Name")
    
    query = " ".join(message.command[1:])
    msg = await message.reply("🇯🇵 **Anime search ho raha hai...**")
    
    data = await MovieBotUtils.get_anime_info(query)
    
    if data:
        text = (
            f"🎬 **{data['title']}**\n\n"
            f"⭐ **Rating:** {data['score']}/10\n"
            f"📺 **Episodes:** {data['episodes']}\n"
            f"📝 **Story:** {data['synopsis']}"
        )
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("📖 More Info", url=data['url'])]])
        await msg.edit_text(text, reply_markup=buttons)
    else:
        await msg.edit_text("❌ **Anime nahi mila!** Check spelling karo.")

# ================ MOVIE OF THE DAY ================
@app.on_message(filters.command(["movieoftheday", "motd"]))
async def movie_of_the_day(client: Client, message: Message):
    if not Config.OMDB_API_KEY:
        await message.reply_text("❌ OMDb API key missing!")
        return
    
    msg = await message.reply_text("🎬 **Aaj ki movie dhundh raha hoon...**")
    
    movie = await MovieBotUtils.get_random_movie()
    
    if movie:
        motd_text = (
            f"🎬 **MOVIE OF THE DAY** 🎬\n\n"
            f"📽️ **{movie['title']}** ({movie['year']})\n"
            f"🎭 **Genre:** {movie['genre']}\n"
            f"⭐ **IMDb:** {movie['rating']}/10\n\n"
            f"📅 **Date:** {datetime.datetime.now().strftime('%d %B %Y')}\n\n"
            f"💡 **Request karo:** `/request {movie['title']}`\n\n"
            f"**Happy Watching!** 🍿"
        )
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Request This Movie", 
                switch_inline_query_current_chat=f"/request {movie['title']}")]
        ])
        
        await msg.edit_text(motd_text, reply_markup=buttons)
    else:
        await msg.edit_text(
            "❌ **Aaj ki movie nahi mil sakti!**\n\n"
            "Thodi der baad try karo ya OMDB API check karo."
        )

# ================ CLEAN JOIN TOGGLE ================
@app.on_message(filters.command("cleanjoin") & filters.group)
async def cleanjoin_toggle(client, message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    
    settings = await get_settings(message.chat.id)
    new_val = not settings.get("clean_join", True)
    await update_settings(message.chat.id, "clean_join", new_val)
    
    status = "✅ ON" if new_val else "❌ OFF"
    msg = await message.reply(f"🧹 **Clean Join:** {status}")
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))

# ================ FORCE SUBSCRIBE ================
@app.on_chat_member_updated()
async def handle_fsub_join(client, update: ChatMemberUpdated):
    if update.from_user and update.from_user.id == (await client.get_me()).id:
        return

    if update.old_chat_member and update.old_chat_member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
        return

    if not update.new_chat_member or update.new_chat_member.user.is_bot:
        return

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
    
    # Check if already joined
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
            
            welcome_msg = await client.send_message(
                chat_id, 
                f"✅ **{user.first_name}** verified! Ab aap group mein chat kar sakte ho! 🎉"
            )
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 60))
        except:
            pass
        return

    # User hasn't joined - restrict and ask to join
    try:
        await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
        
        try:
            chat_info = await client.get_chat(channel_id)
            channel_name = chat_info.title
            link = chat_info.invite_link or f"https://t.me/{chat_info.username}"
        except:
            channel_name = "Channel"
            link = "https://t.me/asbhai_bsr"

        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=link)],
            [InlineKeyboardButton("✅ I've Joined", callback_data=f"fsub_verify_{user_id}")]
        ])
        
        welcome_txt = (
            f"🔒 **Group Locked!**\n\n"
            f"Hello {user.mention}!\n\n"
            f"Group mein chat karne ke liye pehle hamara channel join karo:\n"
            f"📢 **{channel_name}**\n\n"
            f"✅ Channel join karne ke baad **'I've Joined'** button dabao!"
        )
        
        fsub_msg = await client.send_message(chat_id, welcome_txt, reply_markup=buttons)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, fsub_msg, 300))
        
    except Exception as e:
        logger.error(f"FSub Action Error: {e}")

# ================ ADDFSUB COMMAND ================
@app.on_message(filters.command("addfsub") & filters.group)
async def addfsub_command(client: Client, message: Message):
    if not message.from_user:
        return
        
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ Sirf admins!")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 5))
        return

    if not await check_is_premium(message.chat.id):
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Buy Premium", url="https://t.me/asbhai_bsr")],
        ])
        msg = await message.reply_text(
            "💎 **Force Subscribe is Premium Feature!**\n\n"
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
            msg = await message.reply_text("❌ Invalid Channel ID!\nNumeric ID do: -100xxxxxxx")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 5))
            return

    elif message.reply_to_message and message.reply_to_message.forward_from_chat:
        channel_id = message.reply_to_message.forward_from_chat.id
    else:
        msg = await message.reply_text(
            "❌ **Usage:**\n"
            "1. `/addfsub -100xxxxxxx`\n"
            "2. Channel ki kisi post ko reply karo `/addfsub` se"
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))
        return

    try:
        chat = await client.get_chat(channel_id)
        bot_member = await client.get_chat_member(channel_id, (await client.get_me()).id)
        if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            msg = await message.reply_text("❌ Main uss channel mein admin nahi hoon!")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 5))
            return
    except Exception as e:
        msg = await message.reply_text(f"❌ Error: Mujhe channel mein admin banao pehle!")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 5))
        return

    await set_force_sub(message.chat.id, channel_id)
    msg = await message.reply_text(
        f"✅ **Force Subscribe Enabled!**\n\n"
        f"📢 **Channel:** {chat.title}\n\n"
        f"Ab naye members ko channel join karna hoga group mein chat karne ke liye!"
    )
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))

# ================ AI COMMAND ================
@app.on_message(filters.command("ai"))
async def ai_command(client: Client, message: Message):
    if len(message.command) < 2:
        msg = await message.reply_text(
            "❌ **Usage:** /ai your question\n\n"
            "**Examples:**\n"
            "• `/ai Inception movie ka story kya hai?`\n"
            "• `/ai Best action movies 2024`\n"
            "• `/ai Suggest me a comedy movie`"
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return
    
    query = ' '.join(message.command[1:])
    
    await show_typing(message.chat.id)
    waiting_msg = await message.reply_text("💭 **Soch raha hoon...**")
    
    response = await MovieBotUtils.get_ai_response(query)
    
    await waiting_msg.delete()
    msg = await message.reply_text(response)
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ STATS COMMAND ================
@app.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats_command(client: Client, message: Message):
    stats = await get_bot_stats()
    
    stats_text = f"""╔══════════════════════════╗
     📊  BOT STATISTICS  📊  
╚══════════════════════════╝

👥 **Total Users:** {stats['total_users']}
📁 **Active Groups:** {stats['total_groups']}
🚫 **Banned Users:** {stats['banned_users']}
💎 **Premium Groups:** {stats['premium_groups']}

📨 **Movie Requests:**
├─ Pending: {stats['pending_requests']}
└─ Total: {stats['total_requests']}

⚡ **Status:** ✅ Running
🕐 **Updated:** {datetime.datetime.now().strftime('%H:%M:%S')}"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Clear Junk Data", callback_data="clear_junk")],
        [InlineKeyboardButton("🔄 Refresh Stats", callback_data="refresh_stats")]
    ])
    
    await message.reply_text(stats_text, reply_markup=buttons)

# ================ PING COMMAND ================
@app.on_message(filters.command("ping"))
async def ping_command(client: Client, message: Message):
    start = time.time()
    msg = await message.reply_text("🏓 **Pinging...**")
    end = time.time()
    ping = round((end - start) * 1000, 2)
    await msg.edit_text(f"🏓 **Pong!** `{ping}ms`")

# ================ ID COMMAND ================
@app.on_message(filters.command("id"))
async def id_command(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else "Unknown"
    text = f"👤 **Your ID:** `{user_id}`\n"
    if message.chat.type != "private":
        text += f"👥 **Group ID:** `{message.chat.id}`\n"
    
    await message.reply_text(text)

# ================ BOT ADMIN COMMANDS ================
@app.on_message(filters.command("ban") & filters.user(Config.OWNER_ID))
async def ban_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /ban <user_id>")
    try:
        user_id = int(message.command[1])
        await ban_user(user_id)
        await message.reply_text(f"✅ **User {user_id} banned!**")
    except:
        await message.reply_text("❌ Invalid user ID!")

@app.on_message(filters.command("unban") & filters.user(Config.OWNER_ID))
async def unban_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /unban <user_id>")
    try:
        user_id = int(message.command[1])
        await unban_user(user_id)
        await message.reply_text(f"✅ **User {user_id} unbanned!**")
    except:
        await message.reply_text("❌ Invalid user ID!")

# ================ PREMIUM COMMANDS ================
@app.on_message(filters.command("add_premium") & filters.user(Config.OWNER_ID))
async def add_premium_cmd(client: Client, message: Message):
    try:
        if len(message.command) < 3:
            return await message.reply_text("Usage: /add_premium <group_id> <months>")

        group_id = int(message.command[1])
        months = int(message.command[2])
        expiry = await add_premium(group_id, months)
        
        await message.reply_text(
            f"✅ **Premium Added!**\n\n"
            f"📁 **Group:** `{group_id}`\n"
            f"📆 **Months:** {months}\n"
            f"⏰ **Expires:** {expiry.strftime('%Y-%m-%d')}"
        )
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {e}")

@app.on_message(filters.command("remove_premium") & filters.user(Config.OWNER_ID))
async def remove_premium_cmd(client: Client, message: Message):
    try:
        if len(message.command) < 2:
            return await message.reply_text("Usage: /remove_premium <group_id>")
            
        group_id = int(message.command[1])
        await remove_premium(group_id)
        await message.reply_text(f"✅ **Premium removed for** `{group_id}`")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {e}")

# ================ CALLBACK HANDLERS ================
@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    try:
        data = query.data
        chat_id = query.message.chat.id if query.message else query.from_user.id
        user_id = query.from_user.id
        
        # --- SETTINGS CALLBACKS ---
        if data == "settings_menu":
            await show_settings_menu(client, query, is_new=False)
            await query.answer()
            
        elif data == "spelling_menu":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            
            settings = await get_settings(chat_id)
            current_mode = settings.get("spelling_mode", "simple")
            
            text = f"""📝 **Spelling Check Settings**

**Simple Mode:** 
• Extra words hata ke correct format batayega
• Movie naam ke saath season/episode detect karega

**Advanced Mode:** 
• OMDb se movie info search karega
• Correct spelling suggest karega
• IMDb rating/genre batayega

**Current Mode:** {'Advanced' if current_mode == 'advanced' else 'Simple'}"""
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔵 Simple Mode", callback_data="set_spelling_simple"),
                    InlineKeyboardButton("🟣 Advanced Mode", callback_data="set_spelling_advanced")
                ],
                [InlineKeyboardButton("❌ Disable Spelling", callback_data="toggle_spelling")],
                [InlineKeyboardButton("🔙 Back", callback_data="settings_menu")]
            ])
            
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
            
        elif data == "set_spelling_simple":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            await update_settings(chat_id, "spelling_mode", "simple")
            await update_settings(chat_id, "spelling_on", True)
            await query.answer("✅ Simple Mode ON")
            await show_settings_menu(client, query, is_new=False)
            
        elif data == "set_spelling_advanced":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            
            if not Config.OMDB_API_KEY:
                return await query.answer("❌ OMDb API key missing! Owner se contact karo.", show_alert=True)
                
            await update_settings(chat_id, "spelling_mode", "advanced")
            await update_settings(chat_id, "spelling_on", True)
            await query.answer("✅ Advanced Mode ON")
            await show_settings_menu(client, query, is_new=False)
            
        elif data == "bio_menu":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            
            settings = await get_settings(chat_id)
            bio_status = "✅ ON" if settings.get("bio_check") else "❌ OFF"
            bio_action = settings.get("bio_action", "mute")
            
            action_text = "Mute" if bio_action == "mute" else "Ban"
            
            text = f"""🛡️ **Bio Protection Settings**

**Kya karta hai?**
• Naye members ki bio scan karta hai
• Links/usernames detect karta hai
• Warning/Mute/Ban action leta hai

**Status:** {bio_status}
**Action:** {action_text}

**Rules:**
• 1st Warning → Warning message
• 2nd Warning → Mute for 1 hour
• 3rd Warning → Ban"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{'✅' if settings.get('bio_check') else '❌'} Bio Protect", callback_data="toggle_bio")],
                [
                    InlineKeyboardButton("🔇 Action: Mute", callback_data="bio_action_mute"),
                    InlineKeyboardButton("🚫 Action: Ban", callback_data="bio_action_ban")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="settings_menu")]
            ])
            
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
            
        elif data == "bio_action_mute":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            await update_settings(chat_id, "bio_action", "mute")
            await query.answer("✅ Bio Action: Mute")
            await show_settings_menu(client, query, is_new=False)
            
        elif data == "bio_action_ban":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            await update_settings(chat_id, "bio_action", "ban")
            await query.answer("✅ Bio Action: Ban")
            await show_settings_menu(client, query, is_new=False)
            
        elif data == "toggle_spelling":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("spelling_on", True)
            await update_settings(chat_id, "spelling_on", new_val)
            await query.answer(f"Spelling Check: {'ON' if new_val else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
            
        elif data == "toggle_ai":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("ai_chat_on", False)
            await update_settings(chat_id, "ai_chat_on", new_val)
            await query.answer(f"AI Chat: {'ON' if new_val else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
            
        elif data == "toggle_bio":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("bio_check", True)
            await update_settings(chat_id, "bio_check", new_val)
            await query.answer(f"Bio Protect: {'ON' if new_val else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
            
        elif data == "toggle_cleanjoin":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("clean_join", True)
            await update_settings(chat_id, "clean_join", new_val)
            await query.answer(f"Clean Join: {'ON' if new_val else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
            
        elif data == "toggle_auto_accept":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            
            current = await get_auto_accept(chat_id)
            await set_auto_accept(chat_id, not current)
            await query.answer(f"Auto Accept: {'ON' if not current else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
            
        # --- REQUEST CALLBACKS ---
        elif data.startswith("req_accept_"):
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            
            parts = data.split("_")
            if len(parts) >= 3:
                req_user_id = int(parts[2])
                await client.send_message(
                    chat_id,
                    f"✅ **Movie Uploaded!**\n\n"
                    f"{query.from_user.mention} ne movie upload kar di hai!\n"
                    f"<a href='tg://user?id={req_user_id}'>Requester</a>, please check karo!"
                )
                await query.message.delete()
                await query.answer("✅ Request accepted!")
            
        elif data.startswith("req_reject_"):
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            
            parts = data.split("_")
            if len(parts) >= 3:
                await client.send_message(
                    chat_id,
                    f"❌ **Movie Not Available**\n\n"
                    f"Request rejected by {query.from_user.mention}.\n"
                    f"Sorry, ye movie abhi available nahi hai!"
                )
                await query.message.delete()
                await query.answer("❌ Request rejected!")
                
        elif data.startswith("omdb_"):
            movie_name = data[5:]
            await query.answer("🔍 Searching OMDb...")
            
            omdb_info = await MovieBotUtils.get_omdb_info(movie_name)
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Request This", 
                    switch_inline_query_current_chat=f"/request {movie_name}")],
                [InlineKeyboardButton("🔙 Back", callback_data="settings_menu")]
            ])
            
            await query.message.edit_text(omdb_info, reply_markup=buttons)
        
        # --- FSUB CALLBACKS ---
        elif data.startswith("fsub_verify_"):
            target_id = int(data.split("_")[2])
            if user_id != target_id:
                return await query.answer("❌ Yeh button aapke liye nahi hai!", show_alert=True)
            
            fsub_data = await get_force_sub(chat_id)
            if not fsub_data:
                return await query.message.delete()
            
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
                    welcome_msg = await client.send_message(
                        chat_id, 
                        f"✅ **{query.from_user.first_name} verified!** Ab aap group mein chat kar sakte ho! 🎉"
                    )
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 60))
                    await query.answer("✅ Verified!")
                    
                    # Cache add karo
                    cache_key = f"fsub_{user_id}_{channel_id}"
                    fsub_cache.append(cache_key)
                    if len(fsub_cache) > 1000:
                        fsub_cache.clear()
                        
                except Exception as e:
                    await query.answer("❌ Verification failed!", show_alert=True)
            else:
                await query.answer("❌ Aapne channel join nahi kiya!", show_alert=True)
        
        # --- STATS CALLBACKS ---
        elif data == "clear_junk":
            if user_id != Config.OWNER_ID:
                return await query.answer("❌ Sirf owner!", show_alert=True)
            
            junk_count = await clear_junk()
            total = sum(junk_count.values())
            await query.answer(f"✅ {total} items clear!")
            await query.message.edit_text(
                f"🧹 **Cleanup Complete!**\n\n"
                f"• Banned Users: {junk_count.get('banned_users', 0)}\n"
                f"• Inactive Groups: {junk_count.get('inactive_groups', 0)}\n"
                f"• Old Warnings: {junk_count.get('old_warnings', 0)}\n"
                f"• Bio Warnings: {junk_count.get('bio_warnings', 0)}\n"
                f"• Old Requests: {junk_count.get('old_requests', 0)}\n\n"
                f"📊 **Total:** {total} items removed"
            )
            
        elif data == "refresh_stats":
            if user_id != Config.OWNER_ID:
                return await query.answer("❌ Sirf owner!", show_alert=True)
            
            stats = await get_bot_stats()
            text = (
                f"📊 **Updated Statistics**\n\n"
                f"👥 Users: {stats['total_users']}\n"
                f"📁 Active Groups: {stats['total_groups']}\n"
                f"💎 Premium: {stats['premium_groups']}\n"
                f"📨 Pending Requests: {stats['pending_requests']}"
            )
            
            await query.message.edit_text(text)
            await query.answer("✅ Stats refreshed!")
        
        # --- HELP CALLBACKS ---
        elif data == "help_main":
            text = """📚 **Commands & Features**

**👤 User Commands:**
• /start - Bot start
• /help - Help menu
• /request - Movie request
• /ai - AI se pucho
• /google - Google search
• /anime - Anime search
• /motd - Aaj ki movie
• /ping - Status check
• /id - ID dekho

**👑 Admin Commands:**
• /settings - Bot settings
• /addfsub - Force subscribe
• /cleanjoin - Join msg delete
• /setwelcome - Welcome set

**💎 Premium:**
Contact @asbhai_bsr"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Settings Guide", callback_data="help_settings"),
                 InlineKeyboardButton("💎 Premium", callback_data="premium_info")],
                [InlineKeyboardButton("📖 Examples", callback_data="help_example")]
            ])
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
            
        elif data == "help_settings":
            text = """⚙️ **Settings Guide**

**Available Settings:**

1. 📝 **Spelling Check**
   - Simple Mode: Extra words hatao
   - Advanced: OMDb se info

2. 🛡️ **Bio Protect**
   - Bio mein link/username detect
   - Warning → Mute → Ban

3. ⚡ **Auto Accept**
   - Join requests auto approve

4. 🧹 **Clean Join**
   - Service messages delete

5. 🤖 **AI Chat**
   - Bot auto-reply on mention

**How to use:**
• /settings - Open settings
• Admin rights required!"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
            
        elif data == "help_example":
            text = """📖 **Examples**

✅ **Correct:**
• `/request Inception 2010`
• `/request Kalki 2898 AD`
• `#request Jawan`

❌ **Wrong:**
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
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
            
        elif data == "premium_info":
            text = """💎 **PREMIUM FEATURES**

**✨ Benefits:**
✅ Force Subscribe System
✅ No Ads/Broadcasts
✅ Priority Support
✅ Early Access Features

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
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
            
        elif data == "auto_accept_setup":
            text = """⚡ **Auto Accept Setup**

**Kya hai?**
Auto Accept se join requests automatically approve ho jati hain!

**Setup Steps:**
1. Bot ko group mein admin banao
2. Group settings → Join Requests ON karo
3. Yahan se Auto Accept enable karo

**Note:** Ye feature free hai!"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Enable Auto Accept", callback_data="user_enable_auto")],
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
            
        elif data == "user_enable_auto":
            await set_auto_accept(chat_id, True)
            await query.answer("✅ Auto Accept Enabled!", show_alert=True)
            await query.message.delete()
        
        # --- CLOSE CALLBACKS ---
        elif data == "close_settings" or data == "close_help":
            await query.message.delete()
            await query.answer()
    
    except Exception as e:
        logger.error(f"Callback Error: {e}")
        await query.answer("❌ Error!", show_alert=True)

# ================ SCHEDULED CLEANUP ================
async def scheduled_cleanup():
    while True:
        try:
            await asyncio.sleep(Config.CLEANUP_INTERVAL)
            
            junk_count = await clear_junk()
            MovieBotUtils.clean_cache()
            
            total = sum(junk_count.values())
            if total > 0:
                logger.info(f"Scheduled cleanup removed {total} items")
                
                try:
                    await app.send_message(
                        Config.OWNER_ID,
                        f"🧹 **Scheduled Cleanup**\n\nRemoved {total} junk items!"
                    )
                except:
                    pass
        except Exception as e:
            logger.error(f"Scheduled cleanup error: {e}")
            await asyncio.sleep(3600)

# ================ START BOT ================
async def start_bot():
    asyncio.create_task(scheduled_cleanup())
    
    await app.start()
    
    bot_info = await app.get_me()
    await set_bot_instance(bot_info.id, "running")
    
    await set_bot_commands()
    
    logger.info(f"✅ Bot started as @{bot_info.username}")
    
    try:
        await app.send_message(
            Config.OWNER_ID,
            f"🤖 **Bot Started Successfully!**\n\n"
            f"• **Bot:** @{bot_info.username}\n"
            f"• **Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"• **Status:** ✅ Running\n"
            f"• **Groups:** {await get_group_count()}\n"
            f"• **Users:** {await get_user_count()}"
        )
    except:
        pass
    
    await idle()

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 Movie Helper Bot Starting...")
    print("="*50)
    
    try:
        app.run(start_bot())
    except KeyboardInterrupt:
        print("\n⏹️ Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot crashed: {e}")
        import traceback
        traceback.print_exc()
