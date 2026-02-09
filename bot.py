# bot.py - COMPLETE FILE
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
from bio_protection import BioLinkProtector
from fun_commands import FunCommands
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

# ================ SETTINGS MENU ================
async def refresh_settings_menu(client, message_or_query, is_new=False, menu_type="main"):
    """
    menu_type: 'main' | 'spelling_menu'
    """
    if is_new:
        message = message_or_query
        chat_id = message.chat.id
    else:
        message = message_or_query.message
        chat_id = message.chat.id

    st = await get_settings(chat_id)
    auto_acc = await get_auto_accept(chat_id)

    # --- MAIN MENU ---
    if menu_type == "main":
        s_spell = "✅ ON" if st.get("spelling_on") else "❌ OFF"
        bio_status = "✅ ON" if st.get("bio_protection", False) else "❌ OFF"
        clean_join_status = "✅ ON" if st.get("clean_join", True) else "❌ OFF"
        
        text = f"""
⚙️ **SETTINGS PANEL**
Group: {message.chat.title}

Select a category to configure:"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📝 Spelling Check ({s_spell})", callback_data="open_spell_menu")],
            [InlineKeyboardButton(f"🛡️ Bio Protection ({bio_status})", callback_data="toggle_bio_protection")],
            [InlineKeyboardButton(f"🗑️ Auto Delete", callback_data="setup_autodelete")],
            [InlineKeyboardButton(f"⚡ Auto Accept ({'ON' if auto_acc else 'OFF'})", callback_data="toggle_auto_accept")],
            [InlineKeyboardButton(f"👋 Welcome", callback_data="toggle_welcome")],
            [InlineKeyboardButton(f"🧹 Clean Join ({clean_join_status})", callback_data="toggle_clean_join")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ])

    # --- SPELLING SUB-MENU ---
    elif menu_type == "spelling_menu":
        is_on = st.get("spelling_on", True)
        mode = st.get("spelling_mode", "simple")
        
        status_icon = "✅ Enabled" if is_on else "❌ Disabled"
        mode_icon = "⚡ Simple" if mode == "simple" else "🧠 Advanced (OMDb)"
        
        text = f"""
✏️ **SPELLING CHECK SETTINGS**

Current Status: {status_icon}
Current Mode: {mode_icon}

ℹ️ **Info:**
• **Simple:** Delete wrong messages & warn user
• **Advanced:** Search movie on OMDb & suggest details"""
        
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
    """Handle /start command"""
    user = message.from_user
    
    await add_user(user.id, user.username, user.first_name)
    
    if Config.LOGS_CHANNEL:
        try:
            log_text = f"🧑‍💻 User: {user.mention} [{user.id}] Started Bot."
            await client.send_message(Config.LOGS_CHANNEL, log_text)
        except Exception as e:
            logger.error(f"Log Error: {e}")

    welcome_text = f"""
Hello {user.first_name}! 👋

🤖 **Movie Helper Bot** 🤖
Main groups manage karne aur movies dhoondne mein madad karta hoon.

✨ **Top Features:**
• ✅ **Auto Accept:** Join requests automatically
• ✏️ **Spelling Check:** Correct movie names
• 📨 **Request System:** Proper formatting ke sath
• 🤖 **AI Chat:** Movie recommendations

Click buttons to setup:"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton("⚡ Auto Accept Setup", callback_data="auto_accept_setup")],
        [InlineKeyboardButton("⚙️ Help & Settings", callback_data="help_main")],
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

👑 **Group Owners/Admins:**
1. Add me to group & make Admin
2. Use /settings - Configure bot
3. /addfsub - Force Subscribe Setup

✨ **Main Features:**
• ✏️ Spelling Check - Auto-corrects movie names
• 🗑️ Auto Delete - Auto deletes files
• ⚡ Auto Accept - Auto approves join requests
• 🤖 AI Chat - Movie recommendations
• 🛡️ Security - Link & abuse protection

👤 **User Commands:**
• /start - Start bot
• /request <movie> - Request movie
• /ai <question> - Ask AI
• /ping - Check status
• /id - Get user/group ID
• /movieoftheday - Today's featured movie
• /groupstats - Group information

💎 **Premium Features:**
• 🔇 No Ads/Broadcasts
• 🔗 Force Subscribe System
• ⚡ Priority Support
• 🎯 Advanced Tools

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
        msg = await message.reply_text(help_text, reply_markup=buttons)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 120))

# ================ SETTINGS COMMAND ================
@app.on_message(filters.command("settings") & filters.group)
async def settings_command(client: Client, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ **Only Admins can use settings!**")
        return asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 5))
    
    await refresh_settings_menu(client, message, is_new=True)

# ================ BROADCAST COMMAND ================
@app.on_message(filters.command(["broadcast", "grp_broadcast"]) & filters.user(Config.OWNER_ID))
async def broadcast_command(client: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("❌ Reply to a message to broadcast!")
    
    is_group = "grp_broadcast" in message.text
    target_ids = await get_all_groups() if is_group else await get_all_users()
    
    if is_group:
        target_ids = [g for g in target_ids if not await check_is_premium(g)]

    progress = await message.reply_text(f"📤 Broadcasting to {len(target_ids)} chats...")
    success, failed, deleted = 0, 0, 0
    
    for chat_id in target_ids:
        try:
            await message.reply_to_message.copy(chat_id)
            success += 1
        except (PeerIdInvalid, UserNotParticipant):
            if is_group: await remove_group(chat_id)
            else: await delete_user(chat_id)
            deleted += 1
        except Exception as e:
            err_str = str(e)
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
        try:
            owner = await client.get_chat_member(chat_id, Config.OWNER_ID)
            if owner: mentions_list.append(f"👑 <a href='tg://user?id={Config.OWNER_ID}'>Owner</a>")
        except: pass

        async for member in client.get_chat_members(chat_id, filter="administrators"):
            if not member.user.is_bot and not member.user.is_deleted:
                if member.user.id != Config.OWNER_ID:
                    mentions_list.append(member.user.mention)
                if len(mentions_list) >= 5: break
                
    except Exception as e:
        logger.error(f"Tag Error: {e}")
        mentions_list = ["👑 Admins"]

    tag_text = ", ".join(mentions_list) if mentions_list else "👑 Admins"
    
    request_text = f"""
🎬 **New Request!**

🎥 **Movie:** {movie_name}
👤 **Requester:** {message.from_user.mention}
🔔 **Notify:** {tag_text}
"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Uploaded", callback_data=f"req_accept_{message.from_user.id}"),
         InlineKeyboardButton("❌ Unavailable", callback_data=f"req_reject_{message.from_user.id}")]
    ])

    await client.send_message(chat_id, request_text, reply_markup=buttons)

# ================ AUTO APPROVE JOIN ================
@app.on_chat_join_request()
async def auto_approve_join(client: Client, request: ChatJoinRequest):
    chat_id = request.chat.id
    user_id = request.from_user.id
    
    if await get_auto_accept(chat_id):
        try:
            await client.approve_chat_join_request(chat_id, user_id)
            
            msg_text = f"""
✅ **Request Approved!**

Hello {request.from_user.first_name},
Aapki request approve kar di gayi hai. Ab aap channel/group ka content dekh sakte hain.

Welcome to the family! ❤️"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 Open Channel", url=request.chat.invite_link or f"https://t.me/{request.chat.username}")],
                [InlineKeyboardButton("⚡ Use Auto Accept Feature", callback_data="auto_accept_setup")]
            ])
            
            await client.send_message(user_id, msg_text, reply_markup=buttons)
        except Exception as e:
            logger.error(f"Auto Accept Error: {e}")

# ================ SET WELCOME ================
@app.on_message(filters.command("setwelcome") & filters.group)
async def set_welcome_command(client, message):
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
    await message.reply_text("✅ **Custom Welcome Set Successfully!**")

# ================ WELCOME NEW MEMBERS ================
@app.on_message(filters.new_chat_members & filters.group)
async def welcome_new_members(client, message):
    """Handle new members with clean join option"""
    
    # Check clean join setting
    settings = await get_settings(message.chat.id)
    if settings.get("clean_join", True):
        try:
            await message.delete()
        except:
            pass
    
    # Baaki ka welcome logic
    for member in message.new_chat_members:
        if member.is_self:
            continue
        
        # Custom welcome check
        custom_welcome = await get_welcome_message(message.chat.id)
        
        if not custom_welcome:
            # Default welcome
            welcome_text = f"""
🎉 **WELCOME TO THE GROUP!** 🎉

👤 **New Member:** {member.mention}
🆔 **ID:** `{member.id}`
📅 **Joined:** {datetime.datetime.now().strftime('%d %B %Y')}

📌 **Group Rules:**
✅ Use proper movie format
✅ No spam or links
✅ Respect all members
✅ Follow admin instructions

🎬 **Getting Started:**
• Use `/help` for commands
• Check pinned messages
• Request movies using `/request`

Enjoy your stay! 🍿
"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Rules", callback_data="show_rules")],
                [InlineKeyboardButton("🎬 Request Movie", switch_inline_query_current_chat="/request ")],
                [InlineKeyboardButton("🤖 Bot Help", callback_data="help_main")]
            ])
            
            # Photo ke saath bhejo
            welcome_msg = await MovieBotUtils.send_welcome_with_photo(
                client, message.chat.id, member, welcome_text, buttons
            )
            
        else:
            # Custom welcome use karo
            text = custom_welcome['text']
            text = text.replace("{name}", member.mention)
            text = text.replace("{chat}", message.chat.title)
            
            if custom_welcome['photo_id']:
                await client.send_photo(
                    message.chat.id,
                    photo=custom_welcome['photo_id'],
                    caption=text
                )
            else:
                await MovieBotUtils.send_welcome_with_photo(
                    client, message.chat.id, member, text
                )
        
        # Auto delete after 2 minutes
        if welcome_msg:
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, welcome_msg, 120))

# ================ MESSAGE FILTER ================
@app.on_message(filters.group & filters.text & ~filters.command([
    "start", "help", "settings", "request", "setwelcome", "addfsub", "stats", "ai", 
    "broadcast", "ban", "unban", "add_premium", "remove_premium", "premiumstats", "ping", "id", "clean",
    "cleangroup", "pinmovie", "feature", "movieoftheday",
    "motd", "poll", "moviepoll", "purge", "clearchat",
    "groupstats", "ginfo", "cleanjoin", "slap", "runs", "roll", "toss"
]))
async def group_message_filter(client, message):
    if not message.from_user: return
    if await is_admin(message.chat.id, message.from_user.id): return

    # First check bio protection
    bio_blocked = await BioLinkProtector.check_bio_links(client, message)
    if bio_blocked:
        return

    settings = await get_settings(message.chat.id)
    
    # Check message quality
    quality = MovieBotUtils.check_message_quality(message.text)

    # LINK HANDLING
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

    # ABUSE HANDLING
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

    # SPELLING & FORMAT CHECKER
    elif settings.get("spelling_on", True) and quality == "JUNK":
        mode = settings.get("spelling_mode", "simple")
        
        validation = MovieBotUtils.validate_movie_format(message.text)
        
        if not validation['is_valid']:
            try: await message.delete()
            except: pass
            
            junk_list = ", ".join(validation['found_junk'])
            
            if mode == "simple":
                warning_text = f"""
❌ **Galt Format!**

🚫 **Extra Words Hataye:** {junk_list}
✅ **Sahi Format Ye Hai:** {validation['correct_format']}

⚠️ Aage se dhyan rakhein!"""
                msg = await message.reply_text(warning_text)
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 15))
                
            elif mode == "advanced":
                search_query = validation['clean_name']
                omdb_info = await MovieBotUtils.get_omdb_info(search_query)
                
                if "Not Found" not in omdb_info and "Error" not in omdb_info:
                    msg_text = f"""
🔍 **Auto-Corrected Search**

🚫 Removed: {junk_list}
✅ **Searching:** {search_query}

{omdb_info}"""
                    await message.reply_text(msg_text)
                else:
                    msg = await message.reply_text(f"❌ {message.from_user.mention}, Spelling sahi karo! {junk_list} mat likho.")
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))

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
        
        notification_text = f"""
🗑️ **File Auto-Deleted**

Files auto-delete after {delete_time} minutes."""
        
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
            
            welcome_text = f"""
╔══════════════════════════╗
     🎉  WELCOME  🎉       
╚══════════════════════════╝

👤 **User:** {user.mention}
✅ **Verification Complete!**

✨ You can now chat in the group.
Enjoy your stay! 😊"""
            
            try:
                welcome_msg = await MovieBotUtils.send_welcome_with_photo(client, chat_id, user, welcome_text)
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
        
        welcome_txt = f"""
╔══════════════════════════╗
     🔒  GROUP LOCKED  🔒   
╚══════════════════════════╝

Hello {user.mention}! 👋

🔐 **To unlock chatting:**
1. **Join:** {channel_name}
2. **Click 'I've Joined' button**

❌ **Without joining, you cannot send messages!**
✅ **After joining, you'll be auto-unmuted.**
"""
        
        try:
            fsub_msg = await MovieBotUtils.send_welcome_with_photo(client, chat_id, user, welcome_txt, buttons)
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, fsub_msg, 300))
        except FloodWait as e:
            await asyncio.sleep(e.value)
            fsub_msg = await client.send_message(chat_id, welcome_txt, reply_markup=buttons)
        except Exception as e:
            logger.error(f"FSub Send Error: {e}")

    except Exception as e:
        logger.error(f"FSub Action Error: {e}")

# ================ CALLBACK QUERY HANDLERS ================
@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    """Handle all callback queries"""
    try:
        data = query.data
        chat_id = query.message.chat.id if query.message else query.from_user.id
        user_id = query.from_user.id
        
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, query.message, 300))
        
        # HELP SYSTEM
        if data == "help_main":
            help_text = """╔══════════════════════════╗
        🤖  BOT FEATURES  🤖  
╚══════════════════════════╝

✨ **Main Functions:**
✅ ✏️ Spelling Checker
✅ 🗑️ Auto Delete Files  
✅ ✅ Auto Accept Requests
✅ 🤖 AI Movie Recommendations
✅ 🛡️ Advanced Security

📜 **Commands Available:**
• /start - Start bot
• /help - This menu  
• /settings - Group settings
• /request - Request movies
• /ai - Ask AI questions
• /ping - Check status
• /movieoftheday - Featured movie
• /groupstats - Group info

💎 **Premium Features:**
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

✨ **Premium Benefits:**
✅ No Ads/Broadcasts
✅ Force Subscribe System
✅ Priority Support
✅ Advanced Tools
✅ Custom Features

💰 **Pricing:**
• 1 Month: ₹100
• 3 Months: ₹250 (Save ₹50)
• 6 Months: ₹500 (Save ₹100)
• Lifetime: ₹1500 (One Time)

🛒 **Buy Premium:**
Contact @asbhai_bsr for premium.

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

👑 **Group Admins Can Use:**
• /settings - Configure bot
• /addfsub <channel_id> - Force Subscribe (Premium)
• /stats - View bot statistics
• /cleanjoin on/off - Hide join messages
• /pinmovie - Pin important messages
• /poll - Create movie polls

👑 **Bot Owner Commands:**
• /add_premium <group_id> <months> - Add premium
• /remove_premium <group_id> - Remove premium  
• /broadcast - Send to all users
• /grp_broadcast - Send to all groups
• /ban <user_id> - Ban user from bot
• /unban <user_id> - Unban user

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

🎬 **How to Request Movies:**
1. Use /request Movie Name
2. Or use #request Movie Name  
3. Admin will be notified
4. Check group for updates

🤖 **Using AI Chat:**
• /ai Tell me about Inception
• /ai Best movies of 2023
• /ai Comedy movies list

⚙️ **Group Rules:**
• No spam or links
• No abusive language  
• Use proper movie format
• Follow admin instructions

📞 **Support:** @asbhai_bsr"""
            
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

✅ **Correct Format:**
• /request Pushpa 2 2024
• /request Kalki 2898 AD
• /request Animal 2023
• #request Jawan 2023

❌ **Wrong Format:**
• movie dedo
• send pushpa
• pushpa movie chahiye
• plz send movie

📌 **Tips:**
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

⚙️ **Available Settings:**
1. ✏️ **Spelling Check** - ON/OFF
2. 🗑️ **Auto Delete** - ON/OFF
3. ⚡ **Auto Accept** - ON/OFF
4. 👋 **Welcome Message** - ON/OFF
5. 🛡️ **Bio Protection** - ON/OFF
6. 🧹 **Clean Join** - ON/OFF

⏰ **Delete Timer:**
• 5, 10, 30, 60 minutes
• Set timer as needed

🔧 **How to Configure:**
1. Use /settings in group
2. Click buttons to toggle  
3. Set delete time
4. Save automatically

💎 **Note:** Need admin rights and premium for extra features."""
            
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

✨ **Benefits:**
✅ Ads Free Experience
✅ Force Subscribe Feature
✅ Priority Support
✅ Advanced Features
✅ Custom Commands

💰 **Pricing:**
• 1 Month: ₹100
• 3 Months: ₹250 (Save ₹50)
• 6 Months: ₹500 (Save ₹100)
• *Lifetime: ₹1500 (One Time)*

🛒 **How to Buy:**
1. Contact @asbhai_bsr
2. Send payment screenshot
3. Get premium activated

🎁 **Free Trial:** 3 days trial available!"""
            
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

✨ **I can Approve Join Requests Automatically!**

👑 **Admin Setup:**
1. Add me to your Group/Channel
2. Enable **Auto Accept** in settings
3. I'll auto-approve all requests

⚡ **Features:**
✅ Auto approve join requests
✅ Welcome new members  
✅ No manual approval needed
✅ Works 24/7

🔧 **Setup for:**"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 For Group", callback_data="auto_group")],
                [InlineKeyboardButton("📢 For Channel", callback_data="auto_channel")],
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
            
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
        
        elif data == "auto_group":
            text = """╔══════════════════════════╗
     👥  GROUP AUTO ACCEPT  
╚══════════════════════════╝

🔧 **Setup Steps:**
1. Add me to your **Group**
2. Make me **Admin** with join request permission
3. Use /settings in group
4. Enable **Auto Accept** feature

⚡ **Result:**
✅ I'll auto-approve all join requests

🔒 **Requirements:**
• Bot must be admin
• Join requests must be enabled
• Auto Accept must be ON in settings

📝 **Note:** Works for private groups with join requests."""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
                [InlineKeyboardButton("⚙️ Group Settings", switch_inline_query_current_chat="/settings")],
                [InlineKeyboardButton("🔙 Back", callback_data="auto_accept_setup")]
            ])
            
            await query.message.edit_text(text, reply_markup=buttons)
            await query.answer()
        
        elif data == "auto_channel":
            text = """╔══════════════════════════╗
     📢  CHANNEL AUTO ACCEPT  
╚══════════════════════════╝

🔧 **Setup Steps:**
1. Add me to your **Channel**
2. Make me Admin with invite permission
3. Send me your **Channel ID**

📝 **Channel ID Format:** -100xxxxxxxxx

🔍 **How to get Channel ID:**
1. Forward any message from channel to @userinfobot
2. Or add @getidsbot to your channel
3. Copy ID starting with -100

📤 **Send your Channel ID now:**"""
            
            await query.message.edit_text(text)
            await query.answer("Send your channel ID in reply")
        
        # Request Accept Logic
        elif data.startswith("req_accept_"):
            parts = data.split("_")
            if len(parts) >= 3:
                req_user_id = int(parts[2])
                
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
        
        elif data.startswith("req_reject_"):
            parts = data.split("_")
            if len(parts) >= 3:
                req_user_id = int(parts[2])
                
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
        
        # --- SETTINGS CALLBACKS ---
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

        elif data == "toggle_bio_protection":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only Admins!", show_alert=True)
                return
            
            settings = await get_settings(chat_id)
            current = settings.get("bio_protection", False)
            new_value = not current
            
            await update_settings(chat_id, "bio_protection", new_value)
            
            status = "✅ ENABLED" if new_value else "❌ DISABLED"
            await query.answer(f"Bio Protection {status}")
            await refresh_settings_menu(client, query, menu_type="main")

        elif data == "toggle_clean_join":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only Admins!", show_alert=True)
                return
            
            settings = await get_settings(chat_id)
            current = settings.get("clean_join", True)
            new_value = not current
            
            await update_settings(chat_id, "clean_join", new_value)
            
            status = "✅ ON" if new_value else "❌ OFF"
            action = "Hide" if new_value else "Show"
            await query.answer(f"Clean Join: {status}")
            
            info_text = f"""
🧹 **CLEAN JOIN SETTINGS**

**Status:** {status}

**What it does:**
• {action} 'User joined' messages
• {action} 'User left' messages
• Keep chat clean

**Note:** This only affects service messages. Welcome messages will still be sent."""
            
            await query.message.reply_text(info_text)
            await refresh_settings_menu(client, query, menu_type="main")

        elif data == "setup_autodelete":
            if not await is_admin(chat_id, user_id):
                await query.answer("❌ Only Admins!", show_alert=True)
                return
            
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
     📊  BOT STATISTICS  
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
            detailed_text = f"""
📊 **Detailed Statistics**

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
                    welcome_text = f"""
✅ **Verification Successful!**

Welcome {query.from_user.mention}!
You can now chat in the group.

Enjoy your stay! 😊"""
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
        
        elif data == "back_settings":
            await refresh_settings_menu(client, query, menu_type="main")
        
        elif data == "features_list":
            features_text = """╔══════════════════════════╗
     ✨  BOT FEATURES  ✨  
╚══════════════════════════╝

🎬 **Movie Features:**
✅ Smart Format Correction
✅ Movie Recommendations
✅ Auto Spelling Check

🛡️ **Security Features:**
✅ Bio Link Protection
✅ Link Filtering System
✅ Auto Mute/Ban

⚙️ **Group Management:**
✅ Auto Accept Requests
✅ Welcome Messages
✅ File Auto Delete

🤖 **AI Features:**
✅ Chat Assistance
✅ Movie Recommendations
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

# ================ CHANNEL ID HANDLER ================
@app.on_message(filters.private & filters.regex(r'^-100\d+$'))
async def handle_channel_id(client: Client, message: Message):
    """Handle channel ID for auto accept setup"""
    channel_id = int(message.text.strip())
    user_id = message.from_user.id
    
    try:
        chat = await client.get_chat(channel_id)
        member = await client.get_chat_member(channel_id, user_id)
        
        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await message.reply_text(
                f"❌ **You are not admin in {chat.title}!**\n"
                f"You need to be admin to setup auto accept."
            )
            return
        
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
        
        await set_auto_accept(channel_id, True)
        
        await message.reply_text(
            f"✅ **Auto Accept Enabled for {chat.title}!**\n\n"
            f"**Channel:** {chat.title}\n"
            f"**ID:** {channel_id}\n\n"
            f"Now I'll auto-approve all join requests.\n\n"
            f"**Note:** Make sure join requests are enabled in channel settings."
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

# ================ SETCOMMANDS COMMAND ================
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
        BotCommand("movieoftheday", "Featured movie"),
        BotCommand("cleanjoin", "Hide join messages"),
        BotCommand("slap", "Fun command"),
        BotCommand("roll", "Roll dice"),
        BotCommand("toss", "Toss coin")
    ]
    
    try:
        await client.set_bot_commands(commands)
        await message.reply_text("✅ **Bot commands set successfully!**")
        
        group_commands = [
            BotCommand("request", "Request movie"),
            BotCommand("help", "Help menu"),
            BotCommand("settings", "Group settings"),
            BotCommand("ai", "Ask AI"),
            BotCommand("movieoftheday", "Featured movie"),
            BotCommand("id", "Get ID"),
            BotCommand("cleanjoin", "Hide join messages"),
            BotCommand("groupstats", "Group info"),
            BotCommand("slap", "Fun command"),
            BotCommand("roll", "Roll dice")
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
        f"📶 **Ping:** {ping_time}ms\n"
        f"⚡ **Status:** Online\n"
        f"☁️ **Server:** Koyeb Cloud\n"
        f"📊 **Uptime:** 24/7"
    )

# ================ ID COMMAND ================
@app.on_message(filters.command("id"))
async def id_command(client: Client, message: Message):
    """Get user/group ID"""
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else "Unknown"
    text = f"👤 **Your ID:** {user_id}\n"
    if message.chat.type != "private":
        text += f"🏷️ **Group ID:** {chat_id}\n"
        text += f"📝 **Group Title:** {message.chat.title}\n"
        if message.chat.username:
            text += f"🔗 **Group Link:** https://t.me/{message.chat.username}\n"
    
    await message.reply_text(text)

# ================ BAN/UNBAN COMMANDS ================
@app.on_message(filters.command("ban") & filters.user(Config.OWNER_ID))
async def ban_command(client: Client, message: Message):
    """Ban a user from Bot"""
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
    """Unban a user from Bot"""
    if len(message.command) < 2:
        await message.reply_text("**Usage:** /unban <user_id>")
        return
    try:
        user_id = int(message.command[1])
        await unban_user(user_id)
        await message.reply_text(f"✅ **User {user_id} unbanned from Bot successfully!**")
    except:
        await message.reply_text("❌ **Invalid user ID!**")

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

    if not await check_is_premium(message.chat.id):
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Buy Premium", url="https://t.me/asbhai_bsr")],
            [InlineKeyboardButton("ℹ️ Premium Info", callback_data="premium_info")]
        ])
        msg = await message.reply_text(
            "╔══════════════════════════╗\n"
            "      💎  PREMIUM  💎      \n"
            "╚══════════════════════════╝\n\n"
            "🚫 **Force Subscribe - Premium Feature!**\n\n"
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
        except:
            msg = await message.reply_text("❌ **Invalid ID!** Use numeric ID (e.g. -100xxxxxxx)")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            return

    elif message.reply_to_message:
        if message.reply_to_message.forward_from_chat:
            channel_id = message.reply_to_message.forward_from_chat.id
        else:
            msg = await message.reply_text(
                "❌ **Channel ID not found.**\n"
                "Forward privacy is on.\n"
                "**Try:** /addfsub -100xxxxxxx"
            )
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
    else:
        msg = await message.reply_text(
            "**❌ Usage:**\n"
            "1. /addfsub -100xxxxxxx\n"
            "2. Reply to channel message with /addfsub"
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
        msg = await message.reply_text(f"❌ **Error:** Add me to channel and make Admin!\n{e}")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return

    await set_force_sub(message.chat.id, channel_id)
    msg = await message.reply_text(
        f"✅ **Force Subscribe Enabled!**\n\n"
        f"**Channel:** {chat.title}\n"
        f"**ID:** {channel_id}\n\n"
        f"New users must join channel to chat in group."
    )
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))

# ================ PREMIUM ADMIN COMMANDS ================
@app.on_message(filters.command("add_premium") & filters.user(Config.OWNER_ID))
async def add_premium_cmd(client: Client, message: Message):
    try:
        if len(message.command) < 3:
            msg = await message.reply_text("❌ **Usage:** /add_premium <group_id> <months>")
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
        
        await message.reply_text(
            f"✅ **Premium Added Successfully!**\n\n"
            f"**Group:** {group_id}\n"
            f"**Months:** {months}\n"
            f"**Expires:** {expiry.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        try:
            await client.send_message(
                group_id,
                f"╔══════════════════════════╗\n"
                f"      💎  PREMIUM  💎      \n"
                f"╚══════════════════════════╝\n\n"
                f"🎉 **Premium Activated!**\n\n"
                f"✨ **Benefits:**\n"
                f"• No Ads/Broadcasts\n"
                f"• Force Subscribe Enabled\n"
                f"• Priority Support\n"
                f"• Advanced Features\n\n"
                f"Thank you for your support! ❤️"
            )
        except:
            await message.reply_text("✅ **Database updated but message not sent to group.**")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
    except Exception as e:
        msg = await message.reply_text(f"❌ **Error:** {e}")
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))

@app.on_message(filters.command("remove_premium") & filters.user(Config.OWNER_ID))
async def remove_premium_cmd(client: Client, message: Message):
    try:
        if len(message.command) < 2:
            msg = await message.reply_text("❌ **Usage:** /remove_premium <group_id>")
            asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
            return
            
        group_id = int(message.command[1])
        await remove_premium(group_id)
        await message.reply_text(f"❌ **Premium removed for** {group_id}")
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
                premium_list.append(f"• {chat.title} ({g})")
            except:
                premium_list.append(f"• Unknown ({g})")
    
    premium_text = f"╔══════════════════════════╗\n"
    premium_text += f"     💎  PREMIUM STATS  💎    \n"
    premium_text += f"╚══════════════════════════╝\n\n"
    premium_text += f"**Total Premium Groups:** {count}\n\n"
    
    if premium_list:
        premium_text += "\n".join(premium_list[:10])
        if len(premium_list) > 10:
            premium_text += f"\n\n...and {len(premium_list) - 10} more"
    
    await message.reply_text(premium_text)

# ================ AI COMMAND ================
@app.on_message(filters.command("ai"))
async def ai_command(client: Client, message: Message):
    """AI chat feature with typing indicator"""
    if len(message.command) < 2:
        msg = await message.reply_text(
            "**Usage:** /ai your question\n"
            "**Examples:**\n"
            "• /ai Tell me about Inception\n"
            "• /ai Best movies of 2023\n"
            "• /ai Comedy movies list"
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))
        return
    
    query = ' '.join(message.command[1:])
    
    await show_typing_indicator(message.chat.id)
    waiting_msg = await message.reply_text("💭 **Thinking... Please wait...**")
    
    response = await MovieBotUtils.get_ai_response(query)
    
    await waiting_msg.delete()
    msg = await message.reply_text(response)
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
     📊  BOT STATISTICS  
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

# ================ CLEANJOIN COMMAND ================
@app.on_message(filters.command("cleanjoin") & filters.group)
async def clean_join_command(client: Client, message: Message):
    """Toggle clean join service messages"""
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ **Only admins can use this command!**")
        await asyncio.sleep(5)
        await msg.delete()
        return
    
    if len(message.command) < 2:
        settings = await get_settings(message.chat.id)
        current_status = settings.get("clean_join", True)
        status_text = "✅ ON" if current_status else "❌ OFF"
        
        await message.reply_text(
            f"🛠️ **Clean Join Settings**\n\n"
            f"Current Status: {status_text}\n\n"
            f"**Usage:**\n"
            f"• `/cleanjoin on` - Hide join/leave messages\n"
            f"• `/cleanjoin off` - Show join/leave messages\n\n"
            f"**Note:** This hides 'User joined' and 'User left' service messages."
        )
        return
    
    action = message.command[1].lower()
    
    if action in ["on", "yes", "enable", "true"]:
        await update_settings(message.chat.id, "clean_join", True)
        msg = await message.reply_text("✅ **Clean Join Enabled!**\nJoin/Leave messages will be hidden.")
    elif action in ["off", "no", "disable", "false"]:
        await update_settings(message.chat.id, "clean_join", False)
        msg = await message.reply_text("❌ **Clean Join Disabled!**\nJoin/Leave messages will be shown.")
    else:
        msg = await message.reply_text("❌ **Invalid option!** Use 'on' or 'off'")
    
    await asyncio.sleep(5)
    await msg.delete()

# ================ GROUPSTATS COMMAND ================
@app.on_message(filters.command(["groupstats", "ginfo"]) & filters.group)
async def group_statistics(client: Client, message: Message):
    """Show group statistics"""
    try:
        chat = await client.get_chat(message.chat.id)
        
        member_count = await client.get_chat_members_count(message.chat.id)
        
        admin_count = 0
        admin_list = []
        async for member in client.get_chat_members(message.chat.id, filter="administrators"):
            admin_count += 1
            if not member.user.is_bot and not member.user.is_deleted:
                admin_list.append(f"👑 {member.user.first_name}")
        
        bot_count = 0
        async for member in client.get_chat_members(message.chat.id):
            if member.user.is_bot:
                bot_count += 1
        
        if admin_list:
            admin_display = "\n".join(admin_list[:10])
            if len(admin_list) > 10:
                admin_display += f"\n... and {len(admin_list) - 10} more"
        else:
            admin_display = "No admins found"
        
        stats_text = f"""
📊 **GROUP INFORMATION**

🏷️ **Name:** {chat.title}
👥 **Total Members:** {member_count}
📊 **Breakdown:**
   ├─ 👤 Users: {member_count - bot_count}
   └─ 🤖 Bots: {bot_count}

👑 **Admins:** {admin_count}
{admin_display}

📅 **Created:** {chat.date.strftime('%d %b %Y') if chat.date else 'N/A'}
🔗 **Username:** @{chat.username if chat.username else 'Private'}
🆔 **ID:** `{chat.id}`

📈 **Activity Level:** High
⚡ **Bot Features Active:** ✅
"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_group_stats")],
            [InlineKeyboardButton("📋 Export", callback_data="export_group_data")],
            [InlineKeyboardButton("🗑️ Close", callback_data="close_help")]
        ])
        
        await message.reply_text(stats_text, reply_markup=buttons)
        
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")

# ================ MOVIE OF THE DAY COMMAND ================
@app.on_message(filters.command(["movieoftheday", "motd"]) & filters.group)
async def movie_of_the_day(client: Client, message: Message):
    """Feature a movie of the day from OMDb"""
    
    movie = await MovieBotUtils.get_daily_featured_movie()
    
    motd_text = f"""
🎬 **MOVIE OF THE DAY** 🎬

🎭 **{movie['title']} ({movie['year']})**
⭐ **IMDb Rating:** {movie['rating']}/10
⏱️ **Runtime:** {movie['runtime']}
🎭 **Genre:** {movie['genre']}
🎬 **Director:** {movie['director']}
👥 **Cast:** {movie['actors']}

📖 **Plot:**
{movie['plot']}

📅 **Featured:** {datetime.datetime.now().strftime('%d %B %Y')}

🎯 **Why Watch Today?**
This movie is currently trending with excellent reviews from critics and audience alike!
"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎥 Watch/Download", url="https://t.me/asfilter_bot")],
        [InlineKeyboardButton("⭐ IMDb Page", url=f"https://www.imdb.com/title/{movie['imdb_id']}" if movie['imdb_id'] else "https://www.imdb.com")],
        [InlineKeyboardButton("🔍 Search More", switch_inline_query_current_chat="/request ")]
    ])
    
    if movie.get('poster') and movie['poster'] != "N/A":
        try:
            await client.send_photo(
                message.chat.id,
                photo=movie['poster'],
                caption=motd_text,
                reply_markup=buttons
            )
            return
        except:
            pass
    
    await message.reply_text(motd_text, reply_markup=buttons)

# ================ FUN COMMANDS ================
@app.on_message(filters.command("slap") & filters.group)
async def slap_cmd(client: Client, message: Message):
    await FunCommands.slap_command(client, message)

@app.on_message(filters.command("runs") & filters.group)
async def runs_cmd(client: Client, message: Message):
    await FunCommands.runs_command(client, message)

@app.on_message(filters.command("roll") & filters.group)
async def roll_cmd(client: Client, message: Message):
    await FunCommands.roll_command(client, message)

@app.on_message(filters.command("toss") & filters.group)
async def toss_cmd(client: Client, message: Message):
    await FunCommands.toss_command(client, message)

# ================ COMMAND AUTO DELETE ================
@app.on_message(filters.command([
    "start", "help", "settings", "addfsub", "stats", "ai", 
    "broadcast", "request", "ping", "id", "cleanjoin",
    "groupstats", "movieoftheday", "slap", "runs", "roll", "toss"
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
                    cleanup_text = f"""
✅ **Scheduled Cleanup Complete**\n\n
🗑️ **Items Cleaned:**
• Banned Users: {junk_count.get('banned_users', 0)}
• Inactive Groups: {junk_count.get('inactive_groups', 0)}\n\n
🔄 **Total:** {sum(junk_count.values())} items"""
                    await app.send_message(Config.OWNER_ID, cleanup_text)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Scheduled cleanup error: {e}")
            await asyncio.sleep(3600)

# ================ START BOT WITH SCHEDULED TASKS ================
async def start_bot():
    """Start bot with scheduled tasks"""
    asyncio.create_task(scheduled_cleanup())
    
    await app.start()
    
    bot_info = await app.get_me()
    logger.info(f"✅ Bot started as @{bot_info.username}")
    
    try:
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Get help"),
            BotCommand("settings", "Group settings"),
            BotCommand("stats", "Bot statistics"),
            BotCommand("ai", "Ask AI about movies"),
            BotCommand("addfsub", "Set force subscribe"),
            BotCommand("ping", "Check bot status"),
            BotCommand("id", "Get user/group ID"),
            BotCommand("groupstats", "Group information"),
            BotCommand("movieoftheday", "Featured movie"),
            BotCommand("cleanjoin", "Hide join messages")
        ]
        
        await app.set_bot_commands(commands)
        logger.info("✅ Bot commands set successfully")
    except Exception as e:
        logger.warning(f"⚠️ Could not set bot commands: {e}")
    
    try:
        await app.send_message(
            Config.OWNER_ID,
            f"╔══════════════════════════╗\n"
            f"      🤖 BOT STARTED 🤖    \n"
            f"╚══════════════════════════╝\n\n"
            f"🎬 **Bot:** @{bot_info.username}\n"
            f"🕐 **Time:** {datetime.datetime.now().strftime('%H:%M:%S')}\n"
            f"⚡ **Status:** ✅ Running\n\n"
            f"✨ **All systems operational!**"
        )
    except:
        pass
    
    logger.info("🤖 Bot is now running and ready!")
    logger.info("📡 Waiting for messages...")
    
    await idle()

# ================ MAIN ENTRY POINT ================
if __name__ == "__main__":
    print("="*50)
    print("🤖 **Starting Movie Helper Bot...**")
    print("="*50)
    print("\n✅ **All Features Implemented:**")
    print("   1. ✅ Clean Start Message with Auto Accept Button")
    print("   2. ✅ Two Spelling Modes: Simple & Advanced")
    print("   3. ✅ Clean Settings Layout")
    print("   4. ✅ Fixed Request System with Admin Tagging")
    print("   5. ✅ Fixed Welcome Message with Photo Support")
    print("   6. ✅ Bio Link Protection System")
    print("   7. ✅ Clean Join Command")
    print("   8. ✅ Groupstats Command Fixed")
    print("   9. ✅ Movie of Day from OMDb API")
    print("   10. ✅ Fun Commands Added")
    print("   11. ✅ All Systems Integrated")
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
