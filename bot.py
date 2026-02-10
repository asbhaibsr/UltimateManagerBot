import asyncio
import logging
import time
import re
import datetime
import os
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

# Cache
fsub_cache = []
command_cache = {}
ai_typing_cache = {}

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

# ================ CLEAN JOIN COMMAND ================
@app.on_message(filters.command("cleanjoin") & filters.group)
async def cleanjoin_command(client, message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("❌ Only Admins can use this!")
    
    if len(message.command) < 2:
        return await message.reply("Usage: /cleanjoin on | off")
    
    status = message.command[1].lower()
    if status == "on":
        await set_cleanjoin(message.chat.id, True)
        await message.reply("✅ **Clean Join Enabled!** Ab group mein 'User Joined' message auto-delete honge.")
    elif status == "off":
        await set_cleanjoin(message.chat.id, False)
        await message.reply("❌ **Clean Join Disabled!**")
    else:
        await message.reply("Usage: /cleanjoin on | off")

# ================ SERVICE MESSAGE CLEANER ================
@app.on_message(filters.service & filters.group, group=1)
async def service_cleaner(client, message):
    try:
        # Check if cleanjoin is ON
        if await get_cleanjoin(message.chat.id):
            await message.delete()
    except:
        pass

# ================ SETTINGS MENU (UPDATED) ================
async def refresh_settings_menu(client, message_or_query, is_new=False, menu_type="main"):
    if is_new:
        message = message_or_query
        chat_id = message.chat.id
    else:
        message = message_or_query.message
        chat_id = message.chat.id

    st = await get_settings(chat_id)
    auto_acc = await get_auto_accept(chat_id)

    if menu_type == "main":
        s_spell = "✅ ON" if st.get("spelling_on") else "❌ OFF"
        s_bio = "✅ ON" if st.get("bio_protection") else "❌ OFF"
        s_copyright = "✅ ON" if st.get("copyright_protection") else "❌ OFF"
        
        text = f"⚙️ **SETTINGS PANEL**\nGroup: {message.chat.title}\n\nSelect a category to configure:"
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📝 Spelling Check ({s_spell})", callback_data="open_spell_menu")],
            [InlineKeyboardButton(f"🛡️ Bio Protection ({s_bio})", callback_data="toggle_bio_protection")],
            [InlineKeyboardButton(f"⚖️ Copyright ({s_copyright})", callback_data="toggle_copyright")],
            [InlineKeyboardButton(f"🗑️ Auto Delete", callback_data="setup_autodelete")],
            [InlineKeyboardButton(f"⚡ Auto Accept ({'ON' if auto_acc else 'OFF'})", callback_data="toggle_auto_accept")],
            [InlineKeyboardButton(f"👋 Welcome", callback_data="toggle_welcome")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ])

    elif menu_type == "spelling_menu":
        is_on = st.get("spelling_on", True)
        mode = st.get("spelling_mode", "simple")
        
        status_icon = "✅ Enabled" if is_on else "❌ Disabled"
        mode_icon = "⚡ Simple" if mode == "simple" else "🧠 Advanced (OMDb)"
        
        text = (
            f"✏️ **SPELLING CHECK SETTINGS**\n\n"
            f"*Current Status:* {status_icon}\n"
            f"*Current Mode:* {mode_icon}\n\n"
            f"ℹ️ **Info:**\n"
            f"• **Simple:** Delete wrong messages & warn user\n"
            f"• **Advanced:** Search movie on OMDb & suggest details."
        )
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Turn {'OFF' if is_on else 'ON'}", callback_data="toggle_spelling")],
            [InlineKeyboardButton(f"Switch Mode to {'Advanced' if mode=='simple' else 'Simple'}", callback_data="toggle_spell_mode")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="settings_menu")]
        ])

    if is_new:
        msg = await message.reply_text(text, reply_markup=buttons)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))
    else:
        await message.edit_text(text, reply_markup=buttons)

# ================ START COMMAND ================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    user = message.from_user
    await add_user(user.id, user.username, user.first_name)
    
    if Config.LOGS_CHANNEL:
        try:
            log_text = f"🧑‍💻 User: {user.mention} [{user.id}] Started Bot."
            await client.send_message(Config.LOGS_CHANNEL, log_text)
        except Exception as e:
            logger.error(f"Log Error: {e}")

    welcome_text = f"""👋 **Hello {user.first_name}!**

I am **Movie Helper Bot** 🤖
Main groups manage karne aur movies dhoondne mein madad karta hun.

✨ **Top Features:**
✅ **Auto Accept:** Join requests automatically
✅ **Spelling Check:** Correct movie names
✅ **Request System:** Proper formatting ke sath
✅ **Bio Protection:** Link detection in bio
✅ **Copyright Guard:** Fake report protection

Click buttons to setup:"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton("⚡ Auto Accept Setup", callback_data="auto_accept_setup")],
        [InlineKeyboardButton("⚙️ Help & Settings", callback_data="help_main")],
        [InlineKeyboardButton("👑 Owner", url="https://t.me/asbhai_bsr")]
    ])
    
    msg = await message.reply_text(welcome_text, reply_markup=buttons)
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ HELP COMMAND (UPDATED WITH PAGES) ================
@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    help_text = """╔══════════════════════════╗
        🆘  HELP MENU  🆘  
╚══════════════════════════╝

**Group Owners/Admins:**
1. Add me to group & make Admin
2. Use /settings - Configure bot
3. /addfsub - Force Subscribe Setup

**Main Features:**
• ✏️ Spelling Check - Auto-corrects movie names
• 🗑️ Auto Delete - Auto deletes media files
• ⚡ Auto Accept - Auto approves join requests
• 🤖 AI Chat - Movie recommendations & chat
• 🛡️ Bio Protection - Detects links in user bio
• ⚖️ Copyright Guard - Protection from fake reports

**User Commands:**
• /start - Start bot
• /request <movie> - Request movie
• /ai <question> - Ask AI
• /ping - Check status
• /id - Get user ID
• /google <query> - Google search
• /anime <name> - Anime search
• /movieoftheday - Daily featured movie
• /groupstats - Group information

**Support:**
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
        [
            InlineKeyboardButton("🔍 Search Help", callback_data="search_help"),
            InlineKeyboardButton("📊 Stats Help", callback_data="stats_help")
        ],
        [
            InlineKeyboardButton("📋 Commands", callback_data="help_main"),
            InlineKeyboardButton("❌ Close", callback_data="close_help")
        ]
    ])
    
    if message.chat.type == "private":
        msg = await message.reply_text(help_text, reply_markup=buttons)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))
    else:
        msg = await message.reply_text(help_text, reply_markup=buttons)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 120))

# ================ SETTINGS COMMAND ================
@app.on_message(filters.command("settings") & filters.group)
async def settings_command(client: Client, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ **Only Admins can use settings!**")
        return asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 5))
    
    await refresh_settings_menu(client, message, is_new=True)

# ================ BROADCAST COMMAND (FIXED) ================
@app.on_message(filters.command(["broadcast", "grp_broadcast"]) & filters.user(Config.OWNER_ID))
async def broadcast_command(client: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("❌ Reply to a message to broadcast!")
    
    is_group = "grp_broadcast" in message.text
    target_ids = await get_all_groups() if is_group else await get_all_users()
    
    # Premium check
    if is_group:
        target_ids = [g for g in target_ids if not await check_is_premium(g)]

    progress = await message.reply_text(f"📤 Broadcasting to {len(target_ids)} chats...")
    success, failed, deleted = 0, 0, 0
    
    for chat_id in target_ids:
        try:
            await message.reply_to_message.copy(chat_id)
            success += 1
        except (PeerIdInvalid, UserNotParticipant):
            # Invalid ID hai to delete karo
            if is_group: 
                await remove_group(chat_id)
            else: 
                await delete_user(chat_id)
            deleted += 1
        except Exception as e:
            err_str = str(e)
            # Agar user blocked hai ya account deleted hai
            if "USER_IS_BLOCKED" in err_str or "INPUT_USER_DEACTIVATED" in err_str or "chat not found" in err_str.lower():
                if not is_group:
                    await delete_user(chat_id)
                else:
                    await remove_group(chat_id)
                deleted += 1
            else:
                logger.error(f"Broadcast Fail {chat_id}: {e}")
                failed += 1
        
        await asyncio.sleep(0.1)
        
    await progress.edit_text(
        f"✅ Broadcast Complete!\n\n"
        f"🎯 Target: {len(target_ids)}\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}\n"
        f"🗑️ Removed (Blocked/Invalid): {deleted}"
    )

# ================ MESSAGE FILTER WITH ALL PROTECTIONS ================
@app.on_message(filters.group & filters.text & ~filters.command([
    "start", "help", "settings", "request", "setwelcome", "addfsub", "stats", "ai", 
    "broadcast", "ban", "unban", "cleanjoin", "movieoftheday", "motd", "google", "anime",
    "groupstats", "ginfo", "clean", "cleangroup", "pinmovie", "feature", "poll", "moviepoll",
    "purge", "clearchat", "ping", "id", "add_premium", "remove_premium", "premiumstats"
]), group=2)
async def group_message_filter(client, message):
    if not message.from_user: return
    chat_id = message.chat.id
    settings = await get_settings(chat_id)

    # 1. AI CHAT HANDLING
    if settings.get("ai_chat_on", False) and not message.text.startswith("/"):
        is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == client.me.id
        has_bot_name = client.me.username.lower() in message.text.lower() or "bot" in message.text.lower()
        
        if is_reply_to_bot or has_bot_name:
            await client.send_chat_action(chat_id, ChatAction.TYPING)
            response = await MovieBotUtils.get_ai_response(message.text)
            await message.reply_text(response)
            return

    # Check admin
    if await is_admin(chat_id, message.from_user.id): return

    quality = MovieBotUtils.check_message_quality(message.text)
    
    # 2. COPYRIGHT PROTECTION
    if settings.get("copyright_protection", False):
        if re.search(r'copyright|dmca|infringement|strike|report|legal', message.text, flags=re.IGNORECASE):
            try:
                await message.delete()
                warn = await message.reply_text(
                    "🛡️ **Copyright Protection Active**\n\n"
                    "This group complies with DMCA. We do not host illegal content. "
                    "The message was removed to protect the group."
                )
                await asyncio.sleep(10)
                await warn.delete()
                return
            except:
                pass

    # 3. LINK HANDLING
    if quality == "LINK":
        await message.delete()
        warn_count = await add_warning(chat_id, message.from_user.id)
        limit = Config.MAX_WARNINGS
        
        if warn_count >= limit:
            try:
                await client.restrict_chat_member(
                    chat_id, 
                    message.from_user.id, 
                    ChatPermissions(can_send_messages=False),
                    until_date=datetime.datetime.now() + datetime.timedelta(hours=24)
                )
                warn_msg = await message.reply_text(
                    f"❌ {message.from_user.mention} has been muted for 24 hours!\n"
                    f"Reason: Links not allowed in this group."
                )
                await reset_warnings(chat_id, message.from_user.id)
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

    # 4. ABUSE HANDLING
    elif quality == "ABUSE":
        await message.delete()
        warn_count = await add_warning(chat_id, message.from_user.id)
        limit = Config.MAX_WARNINGS
        
        if warn_count >= limit:
            try:
                await client.ban_chat_member(chat_id, message.from_user.id)
                ban_msg = await message.reply_text(
                    f"❌ {message.from_user.mention} has been banned!\n"
                    f"Reason: Abusive language not tolerated."
                )
                await reset_warnings(chat_id, message.from_user.id)
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

    # 5. SPELLING & FORMAT CHECKER
    elif settings.get("spelling_on", True) and quality == "JUNK":
        mode = settings.get("spelling_mode", "simple")
        validation = MovieBotUtils.validate_movie_format(message.text)
        
        if not validation['is_valid']:
            try: 
                await message.delete()
            except: 
                pass
            
            junk_list = ", ".join(validation['found_junk'])
            
            if mode == "simple":
                warning_text = (
                    f"❌ **Galt Format!**\n\n"
                    f"🚫 **Extra Words Hataye:** {junk_list}\n"
                    f"✅ **Sahi Format Ye Hai:** {validation['correct_format']}\n\n"
                    f"⚠️ Aage se dhyan rakhein!\n\n"
                    f"📌 **Tip:** @asfilter_bot par search karein!"
                )
                
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 @asfilter_bot par Search Karein", 
                                          url="https://t.me/asfilter_bot")]
                ])
                
                msg = await message.reply_text(warning_text, reply_markup=buttons)
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 15))
                
            elif mode == "advanced":
                search_query = validation['clean_name']
                omdb_info = await MovieBotUtils.get_omdb_info(search_query)
                
                if "Not Found" not in omdb_info and "Error" not in omdb_info:
                    msg_text = (
                        f"🔍 **Auto-Corrected Search**\n"
                        f"🚫 Removed: {junk_list}\n"
                        f"✅ **{search_query}**\n\n"
                        f"{omdb_info}"
                    )
                    await message.reply_text(msg_text)
                else:
                    msg = await message.reply_text(f"❌ {message.from_user.mention}, Spelling sahi karo! {junk_list} mat likho.")
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))

# ================ BIO PROTECTION ================
@app.on_message(filters.group & filters.new_chat_members)
async def check_bio_on_join(client, message):
    chat_id = message.chat.id
    settings = await get_settings(chat_id)
    
    if not settings.get("bio_protection", False):
        return
    
    for member in message.new_chat_members:
        if member.is_bot: continue
        
        try:
            full_user = await client.get_chat(member.id)
            bio = full_user.bio or ""
            username = full_user.username or ""
            
            # Detect links in bio or username
            link_patterns = [
                r't\.me/', r'telegram\.me/', r'http://', r'https://', 
                r'www\.', r'\.com', r'\.in', r'\.net', r'\.org', r'\.io',
                r'joinchat', r'bit\.ly', r'tinyurl', r'goo\.gl'
            ]
            
            has_link = False
            for pattern in link_patterns:
                if re.search(pattern, bio, flags=re.IGNORECASE):
                    has_link = True
                    break
            
            # Also check username for links
            if any(pattern in username for pattern in ['http', 'www', '.com', '.net']):
                has_link = True
            
            if has_link:
                # Get bio protection settings
                bio_settings = await get_bio_protection(chat_id)
                warn_count = await add_bio_warning(chat_id, member.id)
                
                if warn_count >= bio_settings["warn_limit"]:
                    if bio_settings["penalty"] == "mute":
                        await client.restrict_chat_member(
                            chat_id, 
                            member.id, 
                            ChatPermissions(can_send_messages=False)
                        )
                        action_text = "muted"
                    else:
                        await client.ban_chat_member(chat_id, member.id)
                        action_text = "banned"
                    
                    await message.reply(
                        f"🛑 **Link Detected in Bio!**\n"
                        f"👤 {member.mention} has been {action_text}.\n"
                        f"⚠️ Remove link from bio to get unmuted."
                    )
                else:
                    await message.reply(
                        f"⚠️ **Warning {warn_count}/{bio_settings['warn_limit']}**\n"
                        f"👤 {member.mention} has link in bio!\n"
                        f"Please remove it to avoid {bio_settings['penalty']}."
                    )
        except Exception as e:
            logger.error(f"Bio check error: {e}")

# ================ REQUEST HANDLER ================
@app.on_message((filters.command("request") | filters.regex(r'^#request\s+', re.IGNORECASE)) & filters.group)
async def request_handler(client: Client, message: Message):
    if not message.from_user: return
    
    if message.text.startswith("/"):
        if len(message.command) < 2:
            msg = await message.reply_text("❌ Format: /request Movie Name")
            return asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))
        movie_name = " ".join(message.command[1:])
    else:
        movie_name = message.text.split('#request', 1)[1].strip()

    chat_id = message.chat.id
    mentions_list = []
    
    try:
        # Owner ko tag karo
        try:
            owner = await client.get_chat_member(chat_id, Config.OWNER_ID)
            if owner: mentions_list.append(f"👑 <a href='tg://user?id={Config.OWNER_ID}'>Owner</a>")
        except: pass

        # Admins fetch karo
        from pyrogram.enums import ChatMembersFilter
        async for member in client.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
            if not member.user.is_bot and not member.user.is_deleted:
                if member.user.id != Config.OWNER_ID:
                    mentions_list.append(member.user.mention)
                
            if len(mentions_list) >= 5: break
            
    except Exception as e:
        logger.error(f"Tag Error: {e}")
        mentions_list = ["👑 Admins"]

    tag_text = ", ".join(mentions_list) if mentions_list else "👑 Admins"
    
    request_text = (
        f"🎬 **New Request!**\n\n"
        f"📽️ **Movie:** {movie_name}\n"
        f"👤 **Requested by:** {message.from_user.mention}\n"
        f"🔔 **Notify:** {tag_text}\n"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Uploaded", callback_data=f"req_accept_{message.from_user.id}"),
         InlineKeyboardButton("❌ Unavailable", callback_data=f"req_reject_{message.from_user.id}")]
    ])

    await client.send_message(chat_id, request_text, reply_markup=buttons)

# ================ SET WELCOME COMMAND (ADDED) ================
@app.on_message(filters.command("setwelcome") & filters.group)
async def set_welcome_command(client, message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("❌ Only Admins!")
    
    # Check if reply has photo or text
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
    await message.reply("✅ **Custom Welcome Set Successfully!**")

# ================ WELCOME WITH PHOTO FIX ================
@app.on_message(filters.new_chat_members)
async def welcome_new_members(client, message):
    try:
        # Delete service message if cleanjoin is on
        if await get_cleanjoin(message.chat.id):
            await message.delete()
    except: 
        pass
    
    # Check custom welcome
    custom_welcome = await get_welcome_message(message.chat.id)
    
    for member in message.new_chat_members:
        if member.is_self: 
            continue
        
        if not custom_welcome:
            caption = (
                f"🎉 **Welcome {member.mention}!**\n\n"
                f"Welcome to **{message.chat.title}** ❤️\n"
                f"🆔 ID: {member.id}\n\n"
                f"🎬 **Movie Request:** /request Name use karein.\n"
                f"✅ **Rules:** Spam aur links allowed nahi hai."
            )
            
            # Photo Logic with proper error handling
            sent = False
            if member.photo:
                try:
                    # Download photo first
                    photo_path = await client.download_media(member.photo.big_file_id)
                    
                    # Send with caption
                    welcome_msg = await client.send_photo(
                        message.chat.id,
                        photo=photo_path,
                        caption=caption
                    )
                    sent = True
                    
                    # Clean up downloaded file
                    if os.path.exists(photo_path):
                        os.remove(photo_path)
                        
                except Exception as e:
                    logger.error(f"Photo error: {e}")
                    sent = False
            
            if not sent:
                welcome_msg = await message.reply_text(caption)
            
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 120))
        else:
            text = custom_welcome['text'].replace("{name}", member.mention).replace("{chat}", message.chat.title)
            photo = custom_welcome['photo_id']
            
            if photo:
                await client.send_photo(message.chat.id, photo=photo, caption=text)
            else:
                await client.send_message(message.chat.id, text)

# ================ GOOGLE SEARCH ================
@app.on_message(filters.command(["google", "search"]))
async def google_search_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: /google query")
    
    query = " ".join(message.command[1:])
    m = await message.reply("🔎 Searching Google...")
    
    try:
        from search_engine_parser.core.engines.google import Search as GoogleSearch
        gsearch = GoogleSearch()
        results = await gsearch.async_search(query, page=1)
        
        if not results:
            return await m.edit("❌ No results found.")
            
        text = f"🔎 **Results for: {query}**\n\n"
        for i, result in enumerate(results[:5], 1):
            text += f"{i}. [{result['titles']}]({result['links']})\n{result['descriptions'][:100]}...\n\n"
            
        await m.edit(text, disable_web_page_preview=True)
    except Exception as e:
        await m.edit(f"❌ Error: {e}")

# ================ ANIME SEARCH ================
@app.on_message(filters.command("anime"))
async def anime_search_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: /anime name")
        
    query = " ".join(message.command[1:])
    m = await message.reply("⛩ Searching Anime...")
    try:
        from search_engine_parser.core.engines.myanimelist import Search as AnimeSearch
        anisearch = AnimeSearch()
        results = await anisearch.async_search(query, page=1)
        
        if not results:
            return await m.edit("❌ No anime found.")
            
        res = results[0]
        text = f"⛩ **{res['titles']}**\n\n📝 {res['descriptions'][:300]}...\n\n🔗 [More Info]({res['links']})"
        await m.edit(text)
    except Exception as e:
        await m.edit(f"❌ Error: {e}")

# ================ MOVIE OF THE DAY ================
@app.on_message(filters.command(["movieoftheday", "motd"]) & filters.group)
async def movie_of_the_day(client: Client, message: Message):
    """Feature a dynamic movie using OMDb"""
    import random
    
    # Try to get trending movie from OMDb
    trending_movies = ["Kalki 2898 AD", "Salaar", "Animal", "Dunki", "Tiger 3", "Jawan", "Oppenheimer", "Leo"]
    movie_name = random.choice(trending_movies)
    
    # OMDb se details lo
    omdb_info = await MovieBotUtils.get_omdb_info(movie_name)
    
    # Agar OMDb se nahi mila to default dikhao
    if "Not Found" in omdb_info or "Error" in omdb_info:
        movie_name = random.choice(trending_movies)
        omdb_info = f"🎬 **{movie_name}**\n⭐ Rating: 8.5/10\n🎭 Genre: Action/Thriller\n📅 Year: 2024"
    
    msg_text = f"🎬 **MOVIE OF THE DAY** 🎬\n\n{omdb_info}\n\n🔥 **Trending Now!**"
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Download Movie", url="https://t.me/asfilter_bot")],
        [InlineKeyboardButton("⭐ Check Rating", url=f"https://www.imdb.com/find?q={movie_name}")]
    ])
    
    await message.reply_text(msg_text, reply_markup=buttons)

# ================ GROUP STATS ================
@app.on_message(filters.command(["groupstats", "ginfo"]) & filters.group)
async def group_stats_fix(client: Client, message: Message):
    try:
        chat = await client.get_chat(message.chat.id)
        members = await client.get_chat_members_count(message.chat.id)
        
        # Admins count
        admins = 0
        async for _ in client.get_chat_members(message.chat.id, filter="administrators"):
            admins += 1
            
        # Bot count
        bot_count = 0
        async for member in client.get_chat_members(message.chat.id):
            if member.user.is_bot:
                bot_count += 1
        
        text = (
            f"📊 **Group Stats: {chat.title}**\n"
            f"🆔 ID: `{chat.id}`\n"
            f"👥 Total Members: {members}\n"
            f"🤖 Bots: {bot_count}\n"
            f"👤 Users: {members - bot_count}\n"
            f"👑 Admins: {admins}\n"
            f"🔗 Username: @{chat.username if chat.username else 'Private'}\n"
            f"📅 Created: {chat.date.strftime('%d %b %Y') if chat.date else 'N/A'}"
        )
        await message.reply(text)
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

# ================ CALLBACK QUERY HANDLERS (COMPLETE UPDATED) ================
@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    try:
        data = query.data
        chat_id = query.message.chat.id if query.message else query.from_user.id
        user_id = query.from_user.id
        
        # Bio Protection Toggle
        if data == "toggle_bio_protection":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            settings = await get_settings(chat_id)
            new_value = not settings.get("bio_protection", False)
            await update_settings(chat_id, "bio_protection", new_value)
            status = "ON ✅" if new_value else "OFF ❌"
            await query.answer(f"🛡️ Bio Protection: {status}")
            await refresh_settings_menu(client, query, menu_type="main")
        
        # Copyright Protection Toggle
        elif data == "toggle_copyright":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            settings = await get_settings(chat_id)
            new_value = not settings.get("copyright_protection", False)
            await update_settings(chat_id, "copyright_protection", new_value)
            status = "ON ✅" if new_value else "OFF ❌"
            await query.answer(f"⚖️ Copyright Protection: {status}")
            await refresh_settings_menu(client, query, menu_type="main")
        
        # HELP SYSTEM PAGES (ADDED FROM OLD CODE)
        elif data == "help_main":
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
        
        # Search Help
        elif data == "search_help":
            text = """
🔍 **SEARCH COMMANDS**

**Google Search:**
• /google <query> - Search anything on Google
• /search <query> - Same as /google

**Anime Search:**
• /anime <name> - Search anime on MyAnimeList

**Movie Search:**
• Use proper format: Movie Name (Year)
• Bot auto-corrects spelling
• OMDb integration for details

**Examples:**
• /google best movies 2024
• /anime Naruto Shippuden
• Kalki 2898 AD (2024)"""
            
            await query.message.edit_text(text)
            await query.answer()
        
        # Stats Help
        elif data == "stats_help":
            text = """
📊 **STATISTICS COMMANDS**

**Group Statistics:**
• /groupstats - Detailed group info
• /ginfo - Short group info

**Bot Statistics:**
• /stats - Bot usage stats (Owner only)
• /premiumstats - Premium groups list

**User Statistics:**
• /id - Get your user ID
• Clean group feature to remove inactive members

**Features:**
• Member count with bot/user separation
• Admin count
• Group creation date
• Activity status"""
            
            await query.message.edit_text(text)
            await query.answer()
        
        # Auto Accept Setup
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
        
        # Existing callbacks
        elif data == "settings_menu":
            await refresh_settings_menu(client, query, menu_type="main")
            
        elif data == "open_spell_menu":
            await refresh_settings_menu(client, query, menu_type="spelling_menu")
            
        elif data == "toggle_spelling":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Only Admins!", show_alert=True)
                
            settings = await get_settings(chat_id)
            new_value = not settings.get("spelling_on", True)
            await update_settings(chat_id, "spelling_on", new_value)
            status = "ON ✅" if new_value else "OFF ❌"
            await query.answer(f"✏️ Spelling: {status}")
            await refresh_settings_menu(client, query, menu_type="spelling_menu")

        elif data == "toggle_spell_mode":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Only Admins!", show_alert=True)
            
            st = await get_settings(chat_id)
            new_mode = "advanced" if st.get("spelling_mode") == "simple" else "simple"
            await update_settings(chat_id, "spelling_mode", new_mode)
            await query.answer(f"🔄 Mode switched to: {new_mode.upper()}")
            await refresh_settings_menu(client, query, menu_type="spelling_menu")

        elif data == "setup_autodelete":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Only Admins!", show_alert=True)
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Disable", callback_data="time_0")],
                [InlineKeyboardButton("⏱ 5 Mins", callback_data="time_5"),
                 InlineKeyboardButton("⏱ 10 Mins", callback_data="time_10")],
                [InlineKeyboardButton("⏱ 30 Mins", callback_data="time_30"),
                 InlineKeyboardButton("⏱ 1 Hour", callback_data="time_60")],
                [InlineKeyboardButton("🔙 Back", callback_data="settings_menu")]
            ])
            await query.message.edit_text("🗑️ **Select Auto Delete Time:**", reply_markup=buttons)

        elif data.startswith("time_"):
            minutes = int(data.split("_")[1])
            if minutes == 0:
                await update_settings(chat_id, "auto_delete_on", False)
                await update_settings(chat_id, "delete_time", 0)
                msg = "❌ Auto Delete Disabled"
            else:
                await update_settings(chat_id, "auto_delete_on", True)
                await update_settings(chat_id, "delete_time", minutes)
                msg = f"✅ Auto Delete set to {minutes} mins"
            
            await query.answer(msg)
            await refresh_settings_menu(client, query, menu_type="main")

        elif data == "toggle_auto_accept":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            current = await get_auto_accept(chat_id)
            await set_auto_accept(chat_id, not current)
            status = "ON ✅" if not current else "OFF ❌"
            await query.answer(f"✅ Auto Accept: {status}")
            await refresh_settings_menu(client, query, menu_type="main")
        
        elif data == "toggle_welcome":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only admins can change settings!", show_alert=True)
                return
                
            settings = await get_settings(chat_id)
            new_value = not settings.get("welcome_enabled", True)
            await update_settings(chat_id, "welcome_enabled", new_value)
            status = "ON ✅" if new_value else "OFF ❌"
            await query.answer(f"👋 Welcome: {status}")
            await refresh_settings_menu(client, query, menu_type="main")
        
        # Request handling
        elif data.startswith("req_accept_"):
            parts = data.split("_")
            if len(parts) >= 3:
                req_user_id = int(parts[2])
                
                if not await is_admin(query.message.chat.id, query.from_user.id):
                    await query.answer("❌ Only admins can use this button!", show_alert=True)
                    return
                
                try:
                    await client.send_message(
                        req_user_id,
                        f"✅ **Movie Available!**\n"
                        f"{query.from_user.mention} has uploaded it.\n\n"
                        f"Please check the group!"
                    )
                    await query.message.delete()
                except:
                    pass
                await query.answer("✅ Request accepted!")
        
        elif data.startswith("req_reject_"):
            parts = data.split("_")
            if len(parts) >= 3:
                req_user_id = int(parts[2])
                
                if not await is_admin(query.message.chat.id, query.from_user.id):
                    await query.answer("❌ Only admins can use this button!", show_alert=True)
                    return
                
                try:
                    await client.send_message(
                        req_user_id,
                        f"❌ **Movie Not Available**\n\n"
                        f"Request rejected by Admin {query.from_user.mention}."
                    )
                    await query.message.delete()
                except:
                    pass
                await query.answer("❌ Request rejected!")
        
        # Clear Junk
        elif data == "clear_junk":
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
        
        notification_text = (
            f"🗑️ **File Auto-Deleted**\n"
            f"Files auto-deleted after **{delete_time} minutes**."
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
                
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 60))
            except:
                pass
            return
            
    except UserNotParticipant:
        pass
    except Exception as e:
        logger.error(f"FSub Check Error: {e}")
        return

    # If user hasn't joined:
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
            f"╔══════════════════════════╗\n"
            f"     🔒  GROUP LOCKED  🔒   \n"
            f"╚══════════════════════════╝\n\n"
            f"**Hello {user.mention}!**\n\n"
            f"**To unlock chatting:**\n"
            f"1. **Join:** {channel_name}\n"
            f"2. **Click 'I've Joined' button**\n\n"
            f"**Without joining, you cannot send messages!**\n"
            f"**After joining, you'll be auto-unmuted.**"
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
            await asyncio.sleep(e.value)
            fsub_msg = await client.send_message(chat_id, welcome_txt, reply_markup=buttons)
        except Exception as e:
            logger.error(f"FSub Send Error: {e}")

    except Exception as e:
        logger.error(f"FSub Action Error: {e}")

# ================ AUTO APPROVE JOIN ================
@app.on_chat_join_request()
async def auto_approve_join(client: Client, request: ChatJoinRequest):
    chat_id = request.chat.id
    user_id = request.from_user.id
    
    if await get_auto_accept(chat_id):
        try:
            await client.approve_chat_join_request(chat_id, user_id)
            
            msg_text = (
                f"✅ **Join Request Approved!**\n\n"
                f"Hello {request.from_user.first_name},\n"
                f"Aapki request approve kar di gayi hai. Ab aap channel/group ka content dekh sakte hain.\n\n"
                f"Welcome to the family! ❤️"
            )
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 Open Channel", url=request.chat.invite_link or f"https://t.me/{request.chat.username}")],
                [InlineKeyboardButton("⚡ Use Auto Accept Feature", callback_data="auto_accept_setup")]
            ])
            
            await client.send_message(user_id, msg_text, reply_markup=buttons)
        except Exception as e:
            logger.error(f"Auto Accept Error: {e}")

# ================ CHANNEL ID HANDLER (ADDED) ================
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

# ================ OTHER COMMANDS ================
@app.on_message(filters.command("ping"))
async def ping_command(client: Client, message: Message):
    start_time = time.time()
    msg = await message.reply_text("🏓 **Pinging...**")
    end_time = time.time()
    ping_time = round((end_time - start_time) * 1000, 2)
    await msg.edit_text(
        f"╔══════════════════════════╗\n"
        f"      🏓  PONG  🏓         \n"
        f"╚══════════════════════════╝\n\n"
        f"📡 **Ping:** {ping_time}ms\n"
        f"🚀 **Status:** ✅ Online\n"
        f"🖥️ **Server:** Koyeb Cloud\n"
        f"📊 **Uptime:** 24/7"
    )

@app.on_message(filters.command("id"))
async def id_command(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else "Unknown"
    text = f"👤 **Your ID:** {user_id}\n"
    if message.chat.type != "private":
        text += f"💬 **Group ID:** {chat_id}\n"
        text += f"📝 **Group Title:** {message.chat.title}\n"
        if message.chat.username:
            text += f"🔗 **Group Link:** https://t.me/{message.chat.username}\n"
    
    await message.reply_text(text)

# ================ AI COMMAND (ADDED) ================
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
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ================ CLEAN GROUP COMMAND (ADDED) ================
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

# ================ ADMIN COMMANDS ================
@app.on_message(filters.command("ban") & filters.user(Config.OWNER_ID))
async def ban_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("**Usage:** /ban <user_id>")
        return
    try:
        user_id = int(message.command[1])
        await ban_user(user_id)
        await message.reply_text(f"✅ **User {user_id} banned from Bot successfully!**")
    except:
        await message.reply_text("❌ **Invalid user ID!**")

@app.on_message(filters.command("unban") & filters.user(Config.OWNER_ID))
async def unban_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("**Usage:** /unban <user_id>")
        return
    try:
        user_id = int(message.command[1])
        await unban_user(user_id)
        await message.reply_text(f"✅ **User {user_id} unbanned from Bot successfully!**")
    except:
        await message.reply_text("❌ **Invalid user ID!**")

@app.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats_command(client: Client, message: Message):
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

👥 **Users:** {stats['total_users']}
📁 **Groups:** {stats['total_groups']}
🚫 **Banned:** {stats['banned_users']}
💎 **Premium:** {stats['premium_groups']}
✅ **Active:** {stats['active_groups']}

📨 **Requests:**
├─ Pending: {stats['pending_requests']}
└─ Total: {stats['total_requests']}

⚡ **Status:** ✅ Running
☁️ **Server:** Koyeb Cloud
🕐 **Updated:** {datetime.datetime.now().strftime('%H:%M:%S')}"""
    
    await message.reply_text(stats_text, reply_markup=buttons)

# ================ ADDFSUB COMMAND (ADDED) ================
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

# ================ PREMIUM ADMIN COMMANDS (ADDED) ================
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

# ================ SETCOMMANDS COMMAND (ADDED) ================
@app.on_message(filters.command("setcommands") & filters.user(Config.OWNER_ID))
async def setcommands_command(client: Client, message: Message):
    """Set bot commands"""
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

# ================ COMMAND AUTO DELETE (ADDED) ================
@app.on_message(filters.command([
    "start", "help", "settings", "addfsub", "stats", "ai", 
    "broadcast", "request", "ping", "id"
]) & filters.group)
async def auto_delete_commands(client: Client, message: Message):
    """Auto delete command messages after 5 minutes"""
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, message, 300))

# ================ SCHEDULED CLEANUP TASK ================
async def scheduled_cleanup():
    """Automatically clean junk data"""
    while True:
        try:
            await asyncio.sleep(Config.CLEANUP_INTERVAL)
            
            junk_count = await clear_junk()
            if sum(junk_count.values()) > 0:
                logger.info(f"Scheduled cleanup: {junk_count}")
                
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
            await asyncio.sleep(3600)

# ================ START BOT ================
async def start_bot():
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
            BotCommand("request", "Request a movie"),
            BotCommand("ai", "Ask AI about movies"),
            BotCommand("google", "Google search"),
            BotCommand("anime", "Anime search"),
            BotCommand("movieoftheday", "Featured movie"),
            BotCommand("groupstats", "Group statistics"),
            BotCommand("cleanjoin", "Clean service messages"),
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
            f"     🤖  BOT STARTED  🤖   \n"
            f"╚══════════════════════════╝\n\n"
            f"🎬 **Bot:** @{bot_info.username}\n"
            f"⏰ **Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⚡ **Status:** ✅ Running\n\n"
            f"✨ **All features activated:**\n"
            f"✅ Bio Protection\n"
            f"✅ Copyright Guard\n"
            f"✅ CleanJoin System\n"
            f"✅ OMDb Movie Search\n"
            f"✅ Google/Anime Search\n"
            f"✅ Premium System\n"
            f"✅ Force Subscribe\n\n"
            f"**Bot is now fully operational!**"
        )
    except:
        pass
    
    logger.info("🤖 Bot is now running and ready!")
    await idle()

if __name__ == "__main__":
    print("="*50)
    print("🚀 **Starting Movie Helper Bot...**")
    print("="*50)
    print("\n✅ **All Features Implemented:**")
    print("   1. ✅ Bio Link Protection")
    print("   2. ✅ Copyright Protection")
    print("   3. ✅ CleanJoin System")
    print("   4. ✅ Google & Anime Search")
    print("   5. ✅ OMDb Movie Search")
    print("   6. ✅ Group Statistics Fixed")
    print("   7. ✅ Welcome Photo Fix")
    print("   8. ✅ Premium System Added")
    print("   9. ✅ Force Subscribe Added")
    print("  10. ✅ Help Pages System")
    print("  11. ✅ Auto Accept Setup")
    print("  12. ✅ All Systems Integrated")
    print("\n🤖 **Bot is now professional and complete!**")
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
