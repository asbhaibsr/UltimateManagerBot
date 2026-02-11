import asyncio
import logging
import time
import re
import datetime
import random
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

# Cache for Force Sub
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

async def show_typing_indicator(chat_id):
    """Show typing indicator"""
    try:
        await app.send_chat_action(chat_id, ChatAction.TYPING)
    except:
        pass

# ================ GROUP JOIN/LEAVE HANDLERS (FIXED) ================
@app.on_chat_member_updated(filters.group)
async def bot_added_or_removed(client: Client, update: ChatMemberUpdated):
    """Detect when bot is added to or removed from a group"""
    bot_id = (await client.get_me()).id
    
    # Check if this update is about the bot
    if update.new_chat_member and update.new_chat_member.user.id == bot_id:
        # Bot added to group
        if update.new_chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
            chat = update.chat
            logger.info(f"Bot added to group: {chat.id} - {chat.title}")
            
            # Add group to database
            await add_group(chat.id, chat.title, chat.username)
            
            # Log to owner
            try:
                await client.send_message(
                    Config.OWNER_ID,
                    f"✅ **Bot Added to Group**\n\n"
                    f"**Group:** {chat.title}\n"
                    f"**ID:** `{chat.id}`\n"
                    f"**Username:** @{chat.username if chat.username else 'Private'}"
                )
            except:
                pass
    
    # Bot removed from group
    elif update.old_chat_member and update.old_chat_member.user.id == bot_id:
        if update.old_chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
            if not update.new_chat_member or update.new_chat_member.status == ChatMemberStatus.LEFT:
                chat_id = update.chat.id
                chat_title = update.chat.title
                logger.info(f"Bot removed from group: {chat_id} - {chat_title}")
                
                # Mark bot as removed
                await mark_bot_removed(chat_id, True)
                
                # Log to owner
                try:
                    await client.send_message(
                        Config.OWNER_ID,
                        f"❌ **Bot Removed from Group**\n\n"
                        f"**Group:** {chat_title}\n"
                        f"**ID:** `{chat_id}`"
                    )
                except:
                    pass

# ================ BIO & USERNAME PROTECTION ================
@app.on_chat_member_updated(filters.group)
async def check_new_member_bio(client: Client, update: ChatMemberUpdated):
    """Scan Bio of new members"""
    if not update.new_chat_member:
        return
    
    # Only check new members
    if update.new_chat_member.status == ChatMemberStatus.MEMBER:
        # Skip if this is bot addition
        if update.new_chat_member.user.id == (await client.get_me()).id:
            return
            
        chat_id = update.chat.id
        user = update.new_chat_member.user
        settings = await get_settings(chat_id)
        
        # Clean Join - Delete service message
        if settings.get("clean_join", False):
            try:
                await update.message.delete()
            except:
                pass

        # Bio Check
        if settings.get("bio_check", True):
            try:
                full_user = await client.get_chat(user.id)
                bio = full_user.bio or ""
                
                is_safe = MovieBotUtils.check_bio_safety(bio)
                
                if not is_safe:
                    try:
                        await client.restrict_chat_member(
                            chat_id, user.id,
                            ChatPermissions(can_send_messages=False)
                        )
                        
                        warn_msg = await client.send_message(
                            chat_id,
                            f"🛡️ **Security Alert!**\n\n"
                            f"👤 **User:** {user.mention}\n"
                            f"⚠️ **Reason:** Links/Username detected in Bio\n"
                            f"🚫 **Action:** Muted\n\n"
                            f"Please remove links from bio to chat."
                        )
                        asyncio.create_task(MovieBotUtils.auto_delete_message(client, warn_msg, 30))
                    except Exception as e:
                        logger.error(f"Bio Restrict Error: {e}")
            except Exception as e:
                logger.error(f"Bio Check Error: {e}")

# ================ START COMMAND ================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Handle /start command"""
    user = message.from_user
    
    # Add user to database
    await add_user(user.id, user.username, user.first_name, user.last_name)
    
    # Log to channel
    if Config.LOGS_CHANNEL:
        try:
            log_text = f"🧑‍💻 **User Started Bot**\n\n**User:** {user.mention}\n**ID:** `{user.id}`"
            await client.send_message(Config.LOGS_CHANNEL, log_text)
        except:
            pass

    welcome_text = f"""👋 **Hello {user.first_name}!**

I am **Movie Helper Bot** - Group management aur movie requests ke liye!

**🎯 Main Features:**
• ✅ Auto Accept Join Requests
• ✅ Spelling Check with OMDb
• ✅ Force Subscribe (Premium)
• ✅ AI Chat Assistant
• ✅ Bio Protection
• ✅ Auto Delete Media

**👇 Click buttons to get started:**"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton("⚡ Auto Accept Setup", callback_data="auto_accept_setup")],
        [InlineKeyboardButton("📚 Commands", callback_data="help_main")],
        [InlineKeyboardButton("👑 Owner", url="https://t.me/asbhai_bsr")]
    ])
    
    msg = await message.reply_text(welcome_text, reply_markup=buttons)
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ HELP COMMAND ================
@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    """Handle /help command"""
    help_text = """╔══════════════════════════╗
        🆘  HELP MENU  🆘  
╚══════════════════════════╝

**📌 Commands for Everyone:**
• /start - Start bot
• /help - Show this menu
• /request <movie> - Request movie
• /ai <question> - Ask AI about movies
• /google <query> - Search Google
• /anime <name> - Search Anime
• /ping - Check bot status
• /id - Get IDs

**👑 Admin Commands:**
• /settings - Configure bot
• /addfsub - Force subscribe (Premium)
• /cleanjoin - Toggle join msg deletion
• /setwelcome - Set custom welcome

**💎 Premium Features:**
• Force Subscribe System
• No Ads/Broadcasts
• Priority Support

Contact @asbhai_bsr for premium!"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Settings", callback_data="help_settings"),
         InlineKeyboardButton("💎 Premium", callback_data="premium_info")],
        [InlineKeyboardButton("📖 Examples", callback_data="help_example")],
        [InlineKeyboardButton("❌ Close", callback_data="close_help")]
    ])
    
    msg = await message.reply_text(help_text, reply_markup=buttons)
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ SETTINGS COMMAND ================
@app.on_message(filters.command("settings") & filters.group)
async def settings_command(client: Client, message: Message):
    """Open settings panel"""
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ **Only Admins can use settings!**")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 5))
        return
    
    await show_settings_menu(client, message, is_new=True)

async def show_settings_menu(client, message_or_query, is_new=False):
    """Show main settings menu"""
    if is_new:
        message = message_or_query
        chat_id = message.chat.id
    else:
        message = message_or_query.message
        chat_id = message.chat.id

    settings = await get_settings(chat_id)
    auto_acc = await get_auto_accept(chat_id)
    
    # Status icons
    s_spell = "✅" if settings.get("spelling_on") else "❌"
    s_ai = "✅" if settings.get("ai_chat_on") else "❌"
    s_copy = "✅" if settings.get("copyright_mode") else "❌"
    s_bio = "✅" if settings.get("bio_check") else "❌"
    s_cleanjoin = "✅" if settings.get("clean_join") else "❌"
    
    text = f"""⚙️ **SETTINGS PANEL**
Group: {message.chat.title}

**Current Settings:**
📝 Spelling Check: {s_spell}
🤖 AI Chat: {s_ai}
🛡️ Bio Protect: {s_bio}
© Auto Delete: {s_copy}
🧹 Clean Join: {s_cleanjoin}
⚡ Auto Accept: {'✅' if auto_acc else '❌'}

Select options below:"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📝 Spelling ({s_spell})", callback_data="toggle_spelling"),
         InlineKeyboardButton(f"🤖 AI Chat ({s_ai})", callback_data="toggle_ai")],
        [InlineKeyboardButton(f"🛡️ Bio Protect ({s_bio})", callback_data="toggle_bio"),
         InlineKeyboardButton(f"© Auto Delete ({s_copy})", callback_data="setup_autodelete")],
        [InlineKeyboardButton(f"🧹 Clean Join ({s_cleanjoin})", callback_data="toggle_cleanjoin"),
         InlineKeyboardButton(f"⚡ Auto Accept ({'ON' if auto_acc else 'OFF'})", callback_data="toggle_auto_accept")],
        [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
    ])

    if is_new:
        msg = await message.reply_text(text, reply_markup=buttons)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))
    else:
        await message.edit_text(text, reply_markup=buttons)

# ================ BROADCAST COMMAND (FIXED) ================
@app.on_message(filters.command(["broadcast", "grp_broadcast"]) & filters.user(Config.OWNER_ID))
async def broadcast_command(client: Client, message: Message):
    """Broadcast to all users or groups"""
    if not message.reply_to_message:
        return await message.reply_text("❌ Reply to a message to broadcast!")
    
    is_group = "grp_broadcast" in message.text
    target_ids = await get_all_groups() if is_group else await get_all_users()
    
    progress = await message.reply_text(f"📤 Broadcasting to {len(target_ids)} chats...")
    success, failed, removed = 0, 0, 0
    
    for chat_id in target_ids:
        try:
            await message.reply_to_message.copy(chat_id)
            success += 1
            await asyncio.sleep(0.2)
        except Exception as e:
            err = str(e)
            if "USER_IS_BLOCKED" in err or "INPUT_USER_DEACTIVATED" in err or "chat not found" in err.lower():
                if is_group:
                    await mark_bot_removed(chat_id, True)
                else:
                    await delete_user(chat_id)
                removed += 1
            else:
                failed += 1
                logger.error(f"Broadcast fail {chat_id}: {e}")
    
    await progress.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"📤 Target: {len(target_ids)}\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}\n"
        f"🗑️ Removed: {removed}"
    )

# ================ REQUEST HANDLER ================
@app.on_message((filters.command("request") | filters.regex(r'^#request\s+', re.IGNORECASE)) & filters.group)
async def request_handler(client: Client, message: Message):
    """Handle movie requests"""
    if not message.from_user:
        return
    
    # Extract movie name
    if message.text.startswith("/"):
        if len(message.command) < 2:
            msg = await message.reply_text("❌ **Usage:** `/request Movie Name`")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))
            return
        movie_name = " ".join(message.command[1:])
    else:
        movie_name = message.text.split('#request', 1)[1].strip()
    
    chat_id = message.chat.id
    
    # Get admins to mention
    mentions = []
    try:
        async for member in client.get_chat_members(chat_id, filter="administrators"):
            if not member.user.is_bot and member.user.id != Config.OWNER_ID:
                mentions.append(member.user.mention)
                if len(mentions) >= 3:
                    break
    except:
        pass
    
    admin_text = ", ".join(mentions) if mentions else "👑 Admins"
    
    # Request message
    request_text = (
        f"📨 **New Movie Request!**\n\n"
        f"🎬 **Movie:** `{movie_name}`\n"
        f"👤 **Requester:** {message.from_user.mention}\n"
        f"🔔 **Notify:** {admin_text}\n"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Uploaded", callback_data=f"req_accept_{message.from_user.id}"),
         InlineKeyboardButton("❌ Not Available", callback_data=f"req_reject_{message.from_user.id}")]
    ])

    await client.send_message(chat_id, request_text, reply_markup=buttons)
    await message.delete()

# ================ AUTO APPROVE JOIN ================
@app.on_chat_join_request()
async def auto_approve_join(client: Client, request: ChatJoinRequest):
    """Auto approve join requests"""
    chat_id = request.chat.id
    user_id = request.from_user.id
    
    if await get_auto_accept(chat_id):
        try:
            await client.approve_chat_join_request(chat_id, user_id)
            
            # Welcome message
            welcome_text = (
                f"🎉 **Request Approved!**\n\n"
                f"Hello {request.from_user.first_name},\n"
                f"Your request to join {request.chat.title} has been approved.\n\n"
                f"Welcome to the community! ❤️"
            )
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 Open", url=request.chat.invite_link or f"https://t.me/{request.chat.username}")],
            ])
            
            await client.send_message(user_id, welcome_text, reply_markup=buttons)
        except Exception as e:
            logger.error(f"Auto Accept Error: {e}")

# ================ SET WELCOME ================
@app.on_message(filters.command("setwelcome") & filters.group)
async def set_welcome_command(client, message):
    """Set custom welcome message"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("❌ Only Admins!")
    
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
        return await message.reply("❌ Reply to a photo/text or type message to set welcome.")
        
    await set_welcome_message(message.chat.id, welcome_text, photo_id)
    await message.reply("✅ **Custom Welcome Set!**")

# ================ WELCOME NEW MEMBERS ================
@app.on_message(filters.new_chat_members)
async def welcome_new_members(client, message):
    """Welcome new members"""
    try:
        await message.delete()
    except:
        pass
    
    custom_welcome = await get_welcome_message(message.chat.id)
    
    for member in message.new_chat_members:
        if member.is_self:
            continue
        
        if not custom_welcome:
            caption = (
                f"👋 **Welcome {member.mention}!**\n\n"
                f"Welcome to **{message.chat.title}** ❤️\n"
                f"🆔 ID: `{member.id}`\n\n"
                f"🎬 **Request:** `/request Movie Name`"
            )
            
            # Try with photo, fallback to text
            try:
                if member.photo:
                    welcome_msg = await client.send_photo(
                        message.chat.id,
                        photo=member.photo.big_file_id,
                        caption=caption
                    )
                else:
                    welcome_msg = await message.reply_text(caption)
            except:
                welcome_msg = await message.reply_text(caption)
        else:
            text = custom_welcome['text'].replace("{name}", member.mention).replace("{chat}", message.chat.title)
            photo = custom_welcome['photo_id']
            
            if photo:
                await client.send_photo(message.chat.id, photo=photo, caption=text)
            else:
                await client.send_message(message.chat.id, text)
        
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 120))

# ================ GROUP MESSAGE FILTER ================
@app.on_message(filters.group & filters.text & ~filters.command([
    "start", "help", "settings", "request", "setwelcome", "addfsub", "stats", "ai", 
    "broadcast", "google", "anime", "cleanjoin", "ping", "id"
]))
async def group_message_filter(client, message):
    """Filter group messages"""
    if not message.from_user:
        return
    if await is_admin(message.chat.id, message.from_user.id):
        return
    
    chat_id = message.chat.id
    settings = await get_settings(chat_id)
    text = message.text
    
    # 1. Check for links/abuse
    quality = MovieBotUtils.check_message_quality(text)
    
    if quality == "LINK":
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
                    msg = await message.reply_text(f"🚫 {message.from_user.mention} muted for 24h (Links)")
                    await reset_warnings(chat_id, message.from_user.id)
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))
                except:
                    pass
            else:
                msg = await message.reply_text(f"⚠️ Warning {warn_count}/{Config.MAX_WARNINGS}: Links not allowed!")
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))
        except:
            pass
        return
    
    elif quality == "ABUSE":
        try:
            await message.delete()
            warn_count = await add_warning(chat_id, message.from_user.id)
            
            if warn_count >= Config.MAX_WARNINGS:
                try:
                    await client.ban_chat_member(chat_id, message.from_user.id)
                    msg = await message.reply_text(f"🚫 {message.from_user.mention} banned (Abuse)")
                    await reset_warnings(chat_id, message.from_user.id)
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))
                except:
                    pass
            else:
                msg = await message.reply_text(f"⚠️ Warning {warn_count}/{Config.MAX_WARNINGS}: Abusive language!")
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))
        except:
            pass
        return
    
    # 2. Spelling check
    if settings.get("spelling_on", True):
        validation = MovieBotUtils.validate_movie_format(text)
        
        if not validation['is_valid'] and validation['clean_name']:
            mode = settings.get("spelling_mode", "simple")
            
            if mode == "simple":
                try:
                    await message.delete()
                    msg = await message.reply_text(
                        f"❌ {message.from_user.mention}, **Wrong Format!**\n\n"
                        f"✅ **Correct Format:** `{validation['correct_format']}`"
                    )
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 15))
                except:
                    pass
                
            elif mode == "advanced" and Config.OMDB_API_KEY:
                # Get OMDb info
                omdb_info = await MovieBotUtils.get_omdb_info(validation['clean_name'])
                
                if "Movie Information" in omdb_info:
                    try:
                        await message.delete()
                        msg = await message.reply_text(
                            f"❌ **Wrong Format**\n\n"
                            f"✅ **Correct Name:** `{validation['clean_name']}`\n\n"
                            f"{omdb_info}",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton(f"🔍 Request", switch_inline_query_current_chat=f"/request {validation['clean_name']}")]
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
            await show_typing_indicator(chat_id)
            await asyncio.sleep(1)
            
            response = await MovieBotUtils.get_ai_response(text)
            await message.reply_text(response)

# ================ GOOGLE SEARCH COMMAND (FIXED) ================
@app.on_message(filters.command("google"))
async def google_search_cmd(client, message):
    """Search Google - Working without API"""
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/google search query`")
    
    query = " ".join(message.command[1:])
    msg = await message.reply("🔍 **Searching Google...**")
    
    results = await MovieBotUtils.get_google_search(query)
    
    if not results:
        return await msg.edit_text(
            "❌ **No results found**\n\n"
            "Try different keywords or check spelling."
        )
    
    text = f"🔍 **Search Results:** `{query}`\n\n"
    for i, (href, title) in enumerate(results[:5], 1):
        text += f"{i}. [{title}]({href})\n"
    
    await msg.edit_text(text, disable_web_page_preview=True)

# ================ ANIME SEARCH COMMAND ================
@app.on_message(filters.command("anime"))
async def anime_search_cmd(client, message):
    """Search anime using Jikan API"""
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/anime Anime Name`")
    
    query = " ".join(message.command[1:])
    msg = await message.reply("🇯🇵 **Searching anime...**")
    
    data = await MovieBotUtils.get_anime_info(query)
    
    if data:
        text = (
            f"🎬 **{data['title']}**\n\n"
            f"⭐ **Score:** {data['score']}\n"
            f"📺 **Episodes:** {data['episodes']}\n"
            f"📝 **Synopsis:** {data['synopsis']}"
        )
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("More Info", url=data['url'])]])
        await msg.edit_text(text, reply_markup=buttons)
    else:
        await msg.edit_text("❌ **Anime not found!**")

# ================ CLEAN JOIN TOGGLE ================
@app.on_message(filters.command("cleanjoin") & filters.group)
async def cleanjoin_toggle(client, message):
    """Toggle clean join feature"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    
    settings = await get_settings(message.chat.id)
    new_val = not settings.get("clean_join", False)
    await update_settings(message.chat.id, "clean_join", new_val)
    
    status = "✅ ON" if new_val else "❌ OFF"
    msg = await message.reply(f"🧹 **Clean Join:** {status}")
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))

# ================ AUTO DELETE FILES ================
@app.on_message(filters.group & (filters.document | filters.video | filters.audio | filters.photo))
async def auto_delete_files(client: Client, message: Message):
    """Auto delete media files"""
    settings = await get_settings(message.chat.id)
    if not settings.get("copyright_mode", False):
        return
    
    delete_time = settings.get("delete_time", 0)
    
    if delete_time > 0:
        await asyncio.sleep(delete_time * 60)
    
    try:
        await client.delete_messages(message.chat.id, message.id)
        notification = await message.reply_text(f"🗑️ **File auto-deleted after {delete_time} minutes**")
        await MovieBotUtils.auto_delete_message(client, notification, 5)
    except:
        pass

# ================ FORCE SUBSCRIBE ================
@app.on_chat_member_updated()
async def handle_fsub_join(client, update: ChatMemberUpdated):
    """Handle force subscribe"""
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
    
    try:
        member = await client.get_chat_member(channel_id, user_id)
        if member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
            # User already joined, unmute
            try:
                await client.restrict_chat_member(
                    chat_id, user_id,
                    ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_other_messages=True
                    )
                )
                
                welcome_text = f"✅ **Verified!** {user.mention} can now chat."
                welcome_msg = await client.send_message(chat_id, welcome_text)
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 60))
            except:
                pass
            return
            
    except UserNotParticipant:
        pass
    except Exception as e:
        logger.error(f"FSub Check Error: {e}")
        return

    # User hasn't joined - restrict and ask to join
    try:
        await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
        
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
        
        welcome_txt = (
            f"🔒 **Group Locked**\n\n"
            f"Hello {user.mention}!\n\n"
            f"To chat in this group, please join:\n"
            f"📢 **{channel_name}**\n\n"
            f"Click 'I've Joined' after subscribing."
        )
        
        fsub_msg = await client.send_message(chat_id, welcome_txt, reply_markup=buttons)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, fsub_msg, 300))
        
    except Exception as e:
        logger.error(f"FSub Action Error: {e}")

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

    # Check Premium
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
            msg = await message.reply_text("❌ **Invalid Channel ID!**\nUse numeric ID: -100xxxxxxx")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            return

    elif message.reply_to_message and message.reply_to_message.forward_from_chat:
        channel_id = message.reply_to_message.forward_from_chat.id
    else:
        msg = await message.reply_text(
            "❌ **Usage:**\n"
            "1. `/addfsub -100xxxxxxx`\n"
            "2. Reply to channel message with `/addfsub`"
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return

    # Verify bot is admin in channel
    try:
        chat = await client.get_chat(channel_id)
        bot_member = await client.get_chat_member(channel_id, (await client.get_me()).id)
        if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            msg = await message.reply_text("❌ **I'm not Admin in that channel!**")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            return
    except Exception as e:
        msg = await message.reply_text(f"❌ **Error:** Add me to channel as Admin first!")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return

    await set_force_sub(message.chat.id, channel_id)
    msg = await message.reply_text(
        f"✅ **Force Subscribe Enabled!**\n\n"
        f"**Channel:** {chat.title}\n"
        f"New users must join channel to chat."
    )
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))

# ================ AI COMMAND ================
@app.on_message(filters.command("ai"))
async def ai_command(client: Client, message: Message):
    """AI chat command"""
    if len(message.command) < 2:
        msg = await message.reply_text(
            "**Usage:** `/ai your question`\n"
            "**Examples:**\n"
            "• `/ai Tell me about Inception`\n"
            "• `/ai Best action movies`"
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return
    
    query = ' '.join(message.command[1:])
    
    await show_typing_indicator(message.chat.id)
    waiting_msg = await message.reply_text("💭 **Thinking...**")
    
    response = await MovieBotUtils.get_ai_response(query)
    
    await waiting_msg.delete()
    msg = await message.reply_text(response)
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ STATS COMMAND ================
@app.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats_command(client: Client, message: Message):
    """Bot statistics"""
    stats = await get_bot_stats()
    
    stats_text = f"""╔══════════════════════════╗
     📊  BOT STATISTICS  📊  
╚══════════════════════════╝

👥 **Users:** `{stats['total_users']}`
📁 **Active Groups:** `{stats['total_groups']}`
🚫 **Banned Users:** `{stats['banned_users']}`
💎 **Premium Groups:** `{stats['premium_groups']}`

📨 **Requests:**
├─ Pending: `{stats['pending_requests']}`
└─ Total: `{stats['total_requests']}`

⚡ **Status:** ✅ Running
🕐 **Updated:** {datetime.datetime.now().strftime('%H:%M:%S')}"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Clear Junk", callback_data="clear_junk")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]
    ])
    
    await message.reply_text(stats_text, reply_markup=buttons)

# ================ PING COMMAND ================
@app.on_message(filters.command("ping"))
async def ping_command(client: Client, message: Message):
    """Check bot status"""
    start = time.time()
    msg = await message.reply_text("🏓 **Pinging...**")
    end = time.time()
    ping = round((end - start) * 1000, 2)
    await msg.edit_text(f"🏓 **Pong!** `{ping}ms`")

# ================ ID COMMAND ================
@app.on_message(filters.command("id"))
async def id_command(client: Client, message: Message):
    """Get IDs"""
    user_id = message.from_user.id if message.from_user else "Unknown"
    text = f"👤 **Your ID:** `{user_id}`\n"
    if message.chat.type != "private":
        text += f"👥 **Group ID:** `{message.chat.id}`\n"
    
    await message.reply_text(text)

# ================ BAN/UNBAN COMMANDS ================
@app.on_message(filters.command("ban") & filters.user(Config.OWNER_ID))
async def ban_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/ban <user_id>`")
    try:
        user_id = int(message.command[1])
        await ban_user(user_id)
        await message.reply_text(f"✅ **User `{user_id}` banned!**")
    except:
        await message.reply_text("❌ **Invalid user ID!**")

@app.on_message(filters.command("unban") & filters.user(Config.OWNER_ID))
async def unban_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/unban <user_id>`")
    try:
        user_id = int(message.command[1])
        await unban_user(user_id)
        await message.reply_text(f"✅ **User `{user_id}` unbanned!**")
    except:
        await message.reply_text("❌ **Invalid user ID!**")

# ================ PREMIUM ADMIN COMMANDS ================
@app.on_message(filters.command("add_premium") & filters.user(Config.OWNER_ID))
async def add_premium_cmd(client: Client, message: Message):
    try:
        if len(message.command) < 3:
            return await message.reply_text("❌ **Usage:** `/add_premium <group_id> <months>`")

        group_id = int(message.command[1])
        months = int(message.command[2])
        expiry = await add_premium(group_id, months)
        
        await message.reply_text(
            f"✅ **Premium Added!**\n\n"
            f"**Group:** `{group_id}`\n"
            f"**Months:** {months}\n"
            f"**Expires:** {expiry.strftime('%Y-%m-%d')}"
        )
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {e}")

@app.on_message(filters.command("remove_premium") & filters.user(Config.OWNER_ID))
async def remove_premium_cmd(client: Client, message: Message):
    try:
        if len(message.command) < 2:
            return await message.reply_text("❌ **Usage:** `/remove_premium <group_id>`")
            
        group_id = int(message.command[1])
        await remove_premium(group_id)
        await message.reply_text(f"❌ **Premium removed for** `{group_id}`")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {e}")

# ================ CALLBACK HANDLERS ================
@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    """Handle all callback queries"""
    try:
        data = query.data
        chat_id = query.message.chat.id if query.message else query.from_user.id
        user_id = query.from_user.id
        
        # Auto delete callback messages
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, query.message, 300))
        
        # --- SETTINGS CALLBACKS ---
        if data == "settings_menu":
            await show_settings_menu(client, query, is_new=False)
            await query.answer()
            
        elif data == "toggle_spelling":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Only Admins!", show_alert=True)
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("spelling_on", True)
            await update_settings(chat_id, "spelling_on", new_val)
            await query.answer(f"Spelling: {'ON' if new_val else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
            
        elif data == "toggle_ai":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Only Admins!", show_alert=True)
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("ai_chat_on", False)
            await update_settings(chat_id, "ai_chat_on", new_val)
            await query.answer(f"AI Chat: {'ON' if new_val else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
            
        elif data == "toggle_bio":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Only Admins!", show_alert=True)
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("bio_check", True)
            await update_settings(chat_id, "bio_check", new_val)
            await query.answer(f"Bio Protect: {'ON' if new_val else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
            
        elif data == "toggle_cleanjoin":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Only Admins!", show_alert=True)
            
            settings = await get_settings(chat_id)
            new_val = not settings.get("clean_join", False)
            await update_settings(chat_id, "clean_join", new_val)
            await query.answer(f"Clean Join: {'ON' if new_val else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
            
        elif data == "toggle_auto_accept":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Only Admins!", show_alert=True)
            
            current = await get_auto_accept(chat_id)
            await set_auto_accept(chat_id, not current)
            await query.answer(f"Auto Accept: {'ON' if not current else 'OFF'}")
            await show_settings_menu(client, query, is_new=False)
            
        elif data == "setup_autodelete":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Only Admins!", show_alert=True)
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Disable", callback_data="time_0"),
                 InlineKeyboardButton("5 Mins", callback_data="time_5")],
                [InlineKeyboardButton("10 Mins", callback_data="time_10"),
                 InlineKeyboardButton("30 Mins", callback_data="time_30")],
                [InlineKeyboardButton("1 Hour", callback_data="time_60")],
                [InlineKeyboardButton("🔙 Back", callback_data="settings_menu")]
            ])
            await query.message.edit_text("🗑️ **Select Auto Delete Time:**", reply_markup=buttons)
            await query.answer()
            
        elif data.startswith("time_"):
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Only Admins!", show_alert=True)
            
            minutes = int(data.split("_")[1])
            if minutes == 0:
                await update_settings(chat_id, "copyright_mode", False)
                await update_settings(chat_id, "delete_time", 0)
                await query.answer("❌ Auto Delete Disabled")
            else:
                await update_settings(chat_id, "copyright_mode", True)
                await update_settings(chat_id, "delete_time", minutes)
                await query.answer(f"✅ Auto Delete: {minutes} mins")
            
            await show_settings_menu(client, query, is_new=False)
            
        # --- REQUEST CALLBACKS ---
        elif data.startswith("req_accept_"):
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Only Admins!", show_alert=True)
            
            parts = data.split("_")
            if len(parts) >= 3:
                req_user_id = int(parts[2])
                await client.send_message(
                    chat_id,
                    f"✅ **Movie Available!**\n\n"
                    f"{query.from_user.mention} has uploaded the movie.\n"
                    f"<a href='tg://user?id={req_user_id}'>Requester</a>, please check!"
                )
                await query.message.delete()
                await query.answer("✅ Request accepted!")
            
        elif data.startswith("req_reject_"):
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Only Admins!", show_alert=True)
            
            parts = data.split("_")
            if len(parts) >= 3:
                await client.send_message(
                    chat_id,
                    f"❌ **Movie Not Available**\n\n"
                    f"Request rejected by {query.from_user.mention}."
                )
                await query.message.delete()
                await query.answer("❌ Request rejected!")
        
        # --- FSUB CALLBACKS ---
        elif data.startswith("fsub_verify_"):
            target_id = int(data.split("_")[2])
            if user_id != target_id:
                return await query.answer("❌ Not for you!", show_alert=True)
            
            fsub_data = await get_force_sub(chat_id)
            if not fsub_data:
                return await query.message.delete()
            
            channel_id = fsub_data["channel_id"]
            try:
                member = await client.get_chat_member(channel_id, user_id)
                if member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                    await client.restrict_chat_member(
                        chat_id, user_id,
                        ChatPermissions(
                            can_send_messages=True,
                            can_send_media_messages=True,
                            can_send_other_messages=True
                        )
                    )
                    await query.message.delete()
                    welcome_msg = await client.send_message(chat_id, f"✅ {query.from_user.mention} verified! You can chat now.")
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 60))
                    await query.answer("✅ Verified!")
                else:
                    await query.answer("❌ You haven't joined the channel!", show_alert=True)
            except UserNotParticipant:
                await query.answer("❌ You haven't joined the channel!", show_alert=True)
            except Exception as e:
                await query.answer("❌ Error verifying, try again!", show_alert=True)
        
        # --- STATS CALLBACKS ---
        elif data == "clear_junk":
            if user_id != Config.OWNER_ID:
                return await query.answer("❌ Only owner!", show_alert=True)
            
            junk_count = await clear_junk()
            total = sum(junk_count.values())
            await query.answer(f"✅ Cleared {total} items!")
            await query.message.edit_text(
                f"✅ **Cleanup Complete!**\n\n"
                f"• Banned Users: {junk_count.get('banned_users', 0)}\n"
                f"• Inactive Groups: {junk_count.get('inactive_groups', 0)}\n"
                f"• Old Warnings: {junk_count.get('old_warnings', 0)}\n"
                f"• Old Requests: {junk_count.get('old_requests', 0)}\n\n"
                f"**Total:** {total} items removed"
            )
            
        elif data == "refresh_stats":
            if user_id != Config.OWNER_ID:
                return await query.answer("❌ Only owner!", show_alert=True)
            
            stats = await get_bot_stats()
            text = f"""📊 **Updated Statistics**

👥 Users: {stats['total_users']}
📁 Active Groups: {stats['total_groups']}
💎 Premium: {stats['premium_groups']}
📨 Pending Requests: {stats['pending_requests']}"""
            
            await query.message.edit_text(text)
            await query.answer("✅ Stats refreshed!")
        
        # --- HELP CALLBACKS ---
        elif data == "help_main":
            text = """📚 **Commands & Features**

**📌 User Commands:**
• /start - Start bot
• /help - This menu
• /request - Request movies
• /ai - Ask AI about movies
• /google - Search Google
• /anime - Search Anime
• /ping - Check status
• /id - Get IDs

**👑 Admin Commands:**
• /settings - Configure bot
• /addfsub - Force subscribe
• /cleanjoin - Toggle join msg
• /setwelcome - Set welcome

**💎 Premium:**
Contact @asbhai_bsr"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Settings", callback_data="help_settings"),
                 InlineKeyboardButton("💎 Premium", callback_data="premium_info")],
                [InlineKeyboardButton("📖 Examples", callback_data="help_example")]
            ])
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
            
        elif data == "help_settings":
            text = """⚙️ **Settings Guide**

**Available Settings:**
1. 📝 Spelling Check - ON/OFF
2. 🤖 AI Chat - ON/OFF
3. 🛡️ Bio Protect - ON/OFF
4. © Auto Delete - ON/OFF
5. 🧹 Clean Join - ON/OFF
6. ⚡ Auto Accept - ON/OFF

**How to use:**
1. Go to your group
2. Type /settings
3. Toggle options as needed

Need admin rights to change settings!"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
            
        elif data == "help_example":
            text = """🎬 **Examples**

**✅ Correct:**
• `/request Inception 2010`
• `/request Kalki 2898 AD`
• `#request Jawan`

**❌ Wrong:**
• `movie dedo`
• `inception movie chahiye`
• `send jawan link`

**🤖 AI Examples:**
• `/ai Tell me about Inception`
• `/ai Best movies 2024`
• `/ai Comedy movie suggestions`

**🔍 Search Examples:**
• `/google Avengers cast`
• `/anime Demon Slayer`"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
            
        elif data == "premium_info":
            text = """💎 **Premium Features**

**✨ Benefits:**
✅ Force Subscribe System
✅ No Ads/Broadcasts
✅ Priority Support
✅ Advanced Features

**💰 Pricing:**
• 1 Month: ₹100
• 3 Months: ₹250
• Lifetime: ₹500

**🛒 Buy Premium:**
Contact @asbhai_bsr

🎁 3 Days Trial Available!"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Contact", url="https://t.me/asbhai_bsr")],
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
        
        # --- CLOSE CALLBACKS ---
        elif data == "close_settings" or data == "close_help":
            await query.message.delete()
            await query.answer()
    
    except Exception as e:
        logger.error(f"Callback Error: {e}")
        await query.answer("❌ Error processing request!")

# ================ SCHEDULED CLEANUP ================
async def scheduled_cleanup():
    """Automatically clean junk data"""
    while True:
        try:
            await asyncio.sleep(Config.CLEANUP_INTERVAL)
            junk_count = await clear_junk()
            if sum(junk_count.values()) > 0:
                logger.info(f"Scheduled cleanup: {junk_count}")
                
                # Notify owner
                try:
                    text = f"🔄 **Scheduled Cleanup**\n\nRemoved {sum(junk_count.values())} items"
                    await app.send_message(Config.OWNER_ID, text)
                except:
                    pass
        except Exception as e:
            logger.error(f"Scheduled cleanup error: {e}")
            await asyncio.sleep(3600)

# ================ SET BOT COMMANDS ================
async def set_bot_commands():
    """Set bot commands"""
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show help menu"),
        BotCommand("request", "Request a movie"),
        BotCommand("ai", "Ask AI about movies"),
        BotCommand("google", "Search Google"),
        BotCommand("anime", "Search Anime"),
        BotCommand("ping", "Check bot status"),
        BotCommand("id", "Get user/group ID"),
        BotCommand("settings", "Group settings (admins)"),
        BotCommand("addfsub", "Force subscribe (premium)"),
        BotCommand("cleanjoin", "Toggle join message deletion"),
        BotCommand("setwelcome", "Set custom welcome")
    ]
    
    try:
        await app.set_bot_commands(commands)
        logger.info("✅ Bot commands set")
    except Exception as e:
        logger.warning(f"Could not set commands: {e}")

# ================ START BOT ================
async def start_bot():
    """Start bot with all tasks"""
    # Start scheduled cleanup
    asyncio.create_task(scheduled_cleanup())
    
    # Start bot
    await app.start()
    
    # Set bot info
    bot_info = await app.get_me()
    await set_bot_instance(bot_info.id, "running")
    
    # Set commands
    await set_bot_commands()
    
    logger.info(f"✅ Bot started as @{bot_info.username}")
    
    # Notify owner
    try:
        await app.send_message(
            Config.OWNER_ID,
            f"🤖 **Bot Started!**\n\n"
            f"**Bot:** @{bot_info.username}\n"
            f"**Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**Status:** ✅ Running"
        )
    except:
        pass
    
    await idle()

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 Starting Movie Helper Bot...")
    print("="*50)
    
    try:
        app.run(start_bot())
    except KeyboardInterrupt:
        print("\n⏹️ Bot stopped")
    except Exception as e:
        print(f"\n❌ Bot crashed: {e}")
