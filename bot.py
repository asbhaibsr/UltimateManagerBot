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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Client(
    name="movie_helper_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    in_memory=True
)

fsub_cache = set()

# ===================== HELPERS =====================

async def is_admin(chat_id, user_id):
    if user_id == Config.OWNER_ID:
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

async def show_typing(chat_id):
    try:
        await app.send_chat_action(chat_id, ChatAction.TYPING)
    except:
        pass

# ===================== SETTINGS MENU =====================

async def show_settings_menu(client, target, is_new=False, menu="main"):
    if is_new:
        chat_id = target.chat.id
        chat_title = target.chat.title
    else:
        chat_id = target.message.chat.id
        chat_title = target.message.chat.title

    st = await get_settings(chat_id)

    if menu == "main":
        spell_status = "✅ ON" if st.get("spelling_on") else "❌ OFF"
        auto_del = "✅ ON" if st.get("auto_delete_on") else "❌ OFF"
        welcome = "✅ ON" if st.get("welcome_enabled", True) else "❌ OFF"
        ai = "✅ ON" if st.get("ai_enabled", True) else "❌ OFF"
        link_prot = "✅ ON" if st.get("link_protection", True) else "❌ OFF"
        abuse_prot = "✅ ON" if st.get("abuse_protection", True) else "❌ OFF"

        text = (
            f"⚙️ **Settings Panel**\n"
            f"📁 Group: **{chat_title}**\n\n"
            f"Koi bhi setting change karne ke liye neeche buttons dabao:"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"✏️ Spelling Check {spell_status}", callback_data="menu_spelling")],
            [InlineKeyboardButton(f"🗑️ Auto Delete {auto_del}", callback_data="menu_autodelete")],
            [InlineKeyboardButton(f"👋 Welcome {welcome}", callback_data="menu_welcome")],
            [InlineKeyboardButton(f"🤖 AI Chat {ai}", callback_data="menu_ai")],
            [InlineKeyboardButton(f"🔗 Link Protection {link_prot}", callback_data="toggle_link_prot"),
             InlineKeyboardButton(f"🤬 Abuse Filter {abuse_prot}", callback_data="toggle_abuse_prot")],
            [InlineKeyboardButton("❌ Band Karo", callback_data="close_settings")]
        ])

    elif menu == "spelling":
        is_on = st.get("spelling_on", True)
        mode = st.get("spelling_mode", "simple")
        text = (
            f"✏️ **Spelling Check Settings**\n\n"
            f"**Status:** {'✅ Chal raha hai' if is_on else '❌ Band hai'}\n"
            f"**Mode:** {'⚡ Simple' if mode == 'simple' else '🧠 Advanced (OMDb)'}\n\n"
            f"**Simple Mode:**\n"
            f"→ Galat format milne pe message delete karke warning bheje.\n\n"
            f"**Advanced Mode:**\n"
            f"→ OMDb se movie search kare, poster ke saath details dikhe."
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{'Band Karo ❌' if is_on else 'Chalu Karo ✅'}", callback_data="toggle_spelling")],
            [InlineKeyboardButton(f"{'🧠 Advanced Mode pe Switch Karo' if mode == 'simple' else '⚡ Simple Mode pe Switch Karo'}", callback_data="toggle_spell_mode")],
            [InlineKeyboardButton("🔙 Wapas Jao", callback_data="settings_main")]
        ])

    elif menu == "autodelete":
        is_on = st.get("auto_delete_on", False)
        del_time = st.get("delete_time", 0)
        text = (
            f"🗑️ **Auto Delete Settings**\n\n"
            f"**Status:** {'✅ Chal raha hai' if is_on else '❌ Band hai'}\n"
            f"**Time:** {del_time} minute{'s' if del_time != 1 else ''}\n\n"
            f"Files group pe aane ke baad automatically delete ho jayenge.\n"
            f"Neeche se time select karo:"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚫 Disable", callback_data="adel_0")],
            [InlineKeyboardButton("⏱ 5 Min", callback_data="adel_5"),
             InlineKeyboardButton("⏱ 10 Min", callback_data="adel_10")],
            [InlineKeyboardButton("⏱ 30 Min", callback_data="adel_30"),
             InlineKeyboardButton("⏱ 1 Ghanta", callback_data="adel_60")],
            [InlineKeyboardButton("⏱ 2 Ghante", callback_data="adel_120"),
             InlineKeyboardButton("⏱ 6 Ghante", callback_data="adel_360")],
            [InlineKeyboardButton("🔙 Wapas Jao", callback_data="settings_main")]
        ])

    elif menu == "welcome":
        is_on = st.get("welcome_enabled", True)
        has_custom = bool(st.get("welcome_text") or st.get("welcome_photo"))
        text = (
            f"👋 **Welcome Message Settings**\n\n"
            f"**Status:** {'✅ Chal raha hai' if is_on else '❌ Band hai'}\n"
            f"**Custom Message:** {'✅ Set hai' if has_custom else '❌ Default chalega'}\n\n"
            f"Custom welcome set karne ke liye:\n"
            f"Kisi photo ya text ko reply karke `/setwelcome` type karo.\n\n"
            f"**Variables use kar sakte ho:**\n"
            f"• `{{name}}` → User ka naam\n"
            f"• `{{chat}}` → Group ka naam"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{'Band Karo ❌' if is_on else 'Chalu Karo ✅'}", callback_data="toggle_welcome")],
            [InlineKeyboardButton("🗑️ Custom Welcome Hatao", callback_data="clear_welcome")],
            [InlineKeyboardButton("🔙 Wapas Jao", callback_data="settings_main")]
        ])

    elif menu == "ai":
        is_on = st.get("ai_enabled", True)
        text = (
            f"🤖 **AI Chat Settings**\n\n"
            f"**Status:** {'✅ Chal raha hai' if is_on else '❌ Band hai'}\n\n"
            f"**AI Chat kya karta hai:**\n"
            f"→ Jab koi group mein akele message kare (kisi ko tag kiye bina), "
            f"bot AI se jawab deta hai.\n"
            f"→ Movie recommendations, reviews, etc.\n\n"
            f"**Direct use:** `/ai [sawaal]`"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{'Band Karo ❌' if is_on else 'Chalu Karo ✅'}", callback_data="toggle_ai")],
            [InlineKeyboardButton("🔙 Wapas Jao", callback_data="settings_main")]
        ])

    if is_new:
        msg = await target.reply_text(text, reply_markup=buttons)
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))
    else:
        try:
            await target.message.edit_text(text, reply_markup=buttons)
        except:
            pass

# ===================== START =====================

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    user = message.from_user
    await add_user(user.id, user.username, user.first_name)

    if Config.LOGS_CHANNEL:
        try:
            await client.send_message(Config.LOGS_CHANNEL, f"🧑‍💻 New User: {user.mention} [`{user.id}`]")
        except:
            pass

    text = (
        f"👋 **Kya haal hai {user.first_name}!**\n\n"
        f"Main **Movie Helper Bot** hoon 🤖\n"
        f"Movie groups manage karna aur movies dhundhne mein help karta hoon.\n\n"
        f"**Main kya karta hoon:**\n"
        f"• ✏️ Movie names ki spelling check karta hoon\n"
        f"• ✅ Channel join requests auto-approve karta hoon\n"
        f"• 🤖 AI se movie recommendations deta hoon\n"
        f"• 🛡️ Links aur abuse se group ko bachata hoon\n\n"
        f"Group mein add karo aur Admin banao!"
    )
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Group Mein Add Karo", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton("📢 Channel Auto Accept Setup", callback_data="channel_setup_home")],
        [InlineKeyboardButton("❓ Help", callback_data="help_main"),
         InlineKeyboardButton("👑 Owner", url="https://t.me/asbhai_bsr")]
    ])
    await message.reply_text(text, reply_markup=buttons)

# ===================== HELP =====================

@app.on_message(filters.command("help"))
async def help_cmd(client, message: Message):
    text = (
        f"**🆘 Help Menu**\n\n"
        f"**Group Admins ke liye:**\n"
        f"• `/settings` — Group settings\n"
        f"• `/setwelcome` — Custom welcome set karo\n"
        f"• `/addfsub` — Force subscribe (Premium)\n"
        f"• `/clean` — Deleted accounts hatao\n\n"
        f"**Sabke liye:**\n"
        f"• `/request [movie]` — Movie request karo\n"
        f"• `/ai [sawaal]` — AI se poocho\n"
        f"• `/ping` — Bot status\n"
        f"• `/id` — Apna ya group ka ID dekho\n\n"
        f"**Channel Auto Accept:**\n"
        f"• `/mychannels` — Apne connected channels dekho\n\n"
        f"**Premium Features:**\n"
        f"• 🔗 Force Subscribe System\n"
        f"• 🔇 No Broadcasts\n"
        f"• ⚡ Priority Support"
    )
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Premium Info", callback_data="premium_info")],
        [InlineKeyboardButton("📢 Channel Setup", callback_data="channel_setup_home")],
        [InlineKeyboardButton("❌ Band Karo", callback_data="close_help")]
    ])
    msg = await message.reply_text(text, reply_markup=buttons)
    if message.chat.type != ChatType.PRIVATE:
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 120))

# ===================== SETTINGS COMMAND =====================

@app.on_message(filters.command("settings") & filters.group)
async def settings_cmd(client, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ Sirf admins settings change kar sakte hain!")
        return asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 5))
    await show_settings_menu(client, message, is_new=True)

# ===================== CHANNEL AUTO ACCEPT SYSTEM =====================

@app.on_message(filters.command("mychannels") & filters.private)
async def my_channels_cmd(client, message: Message):
    user_id = message.from_user.id
    channels = await get_user_channels(user_id)
    await send_channels_panel(client, message, user_id, channels)

async def send_channels_panel(client, message, user_id, channels, edit=False):
    if not channels:
        text = (
            "📢 **Aapke Connected Channels**\n\n"
            "Abhi koi channel connected nahi hai.\n\n"
            "Channel add karne ke 2 tarike:\n"
            "1️⃣ Neeche **Add Channel** button dabao aur channel ID daalo\n"
            "2️⃣ Ya apne channel se koi bhi message is bot pe forward karo"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Channel Add Karo", callback_data="add_channel_prompt")],
            [InlineKeyboardButton("❓ Help", callback_data="channel_setup_home")]
        ])
    else:
        text = f"📢 **Aapke Connected Channels** ({len(channels)})\n\n"
        btn_rows = []
        for ch in channels:
            status = "🟢" if ch.get("connected") else "🔴"
            title = ch.get("channel_title", "Unknown")
            ch_id = ch.get("channel_id")
            btn_rows.append([
                InlineKeyboardButton(f"{status} {title}", callback_data=f"ch_detail_{ch_id}")
            ])
        btn_rows.append([InlineKeyboardButton("➕ Naya Channel Add Karo", callback_data="add_channel_prompt")])
        buttons = InlineKeyboardMarkup(btn_rows)

    if edit:
        try:
            await message.edit_text(text, reply_markup=buttons)
        except:
            pass
    else:
        await message.reply_text(text, reply_markup=buttons)

@app.on_message(filters.command("mychannels") & filters.private)
async def mychannels_cmd(client, message: Message):
    channels = await get_user_channels(message.from_user.id)
    await send_channels_panel(client, message, message.from_user.id, channels)

# Jab user apne channel se message forward kare
@app.on_message(filters.private & filters.forwarded)
async def handle_forwarded(client, message: Message):
    if not message.forward_from_chat:
        return
    
    chat = message.forward_from_chat
    if chat.type.name not in ["CHANNEL", "SUPERGROUP"]:
        return

    user_id = message.from_user.id
    channel_id = chat.id
    channel_title = chat.title or "Unknown Channel"
    channel_username = chat.username

    # Check karo existing hai ya nahi
    existing = await get_user_channel(user_id, channel_id)
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Haan, Add Karo!", callback_data=f"confirm_add_ch_{channel_id}"),
            InlineKeyboardButton("❌ Nahi", callback_data="cancel_add_ch")
        ]
    ])
    
    if existing:
        await message.reply_text(
            f"📢 **{channel_title}** pehle se connected hai!\n\n"
            f"Manage karne ke liye `/mychannels` use karo.",
        )
        return

    await message.reply_text(
        f"📢 **Channel Mila!**\n\n"
        f"**Naam:** {channel_title}\n"
        f"**ID:** `{channel_id}`\n\n"
        f"Kya aap is channel ko Auto Accept ke liye add karna chahte hain?",
        reply_markup=buttons
    )
    # Save temporarily
    await update_settings(user_id * -1, f"pending_channel_{user_id}", {
        "channel_id": channel_id,
        "channel_title": channel_title,
        "channel_username": channel_username
    })

# Channel ID manually dalne pe
@app.on_message(filters.private & filters.regex(r'^-100\d{10,}$'))
async def handle_channel_id_input(client, message: Message):
    channel_id = int(message.text.strip())
    user_id = message.from_user.id
    
    try:
        chat = await client.get_chat(channel_id)
        channel_title = chat.title
        channel_username = chat.username

        # Bot admin hai?
        try:
            bot_me = await client.get_me()
            bot_member = await client.get_chat_member(channel_id, bot_me.id)
            if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                await message.reply_text(
                    f"❌ **Bot admin nahi hai `{channel_title}` mein!**\n\n"
                    f"Pehle bot ko admin banao, phir dobara try karo."
                )
                return
        except:
            await message.reply_text(
                f"❌ Bot is channel mein nahi hai ya access nahi hai.\n"
                f"Bot ko pehle channel mein add karo as Admin."
            )
            return

        # User admin hai?
        try:
            user_member = await client.get_chat_member(channel_id, user_id)
            if user_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                await message.reply_text("❌ Tum is channel ke admin nahi ho!")
                return
        except:
            pass

        existing = await get_user_channel(user_id, channel_id)
        if existing:
            await message.reply_text(f"📢 **{channel_title}** pehle se connected hai!")
            return

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Haan, Add Karo!", callback_data=f"confirm_add_ch_{channel_id}"),
                InlineKeyboardButton("❌ Nahi", callback_data="cancel_add_ch")
            ]
        ])
        
        # Store pending
        import json
        pending_key = f"pending_ch_{user_id}"
        await update_settings(-99999999, pending_key, json.dumps({
            "channel_id": channel_id,
            "channel_title": channel_title,
            "channel_username": channel_username,
            "user_id": user_id
        }))

        await message.reply_text(
            f"📢 **Channel Mila!**\n\n"
            f"**Naam:** {channel_title}\n"
            f"**ID:** `{channel_id}`\n\n"
            f"Is channel ko Auto Accept ke liye add karna chahte ho?",
            reply_markup=buttons
        )

    except Exception as e:
        await message.reply_text(
            f"❌ Channel nahi mila!\n\n"
            f"Check karo:\n"
            f"• Bot channel mein admin hai?\n"
            f"• Channel ID sahi hai?\n\n"
            f"Error: `{e}`"
        )

# ===================== AUTO ACCEPT - JOIN REQUEST =====================

@app.on_chat_join_request()
async def auto_approve(client, request: ChatJoinRequest):
    chat_id = request.chat.id
    user_id = request.from_user.id

    if await get_auto_accept(chat_id):
        try:
            await client.approve_chat_join_request(chat_id, user_id)
            try:
                chat_title = request.chat.title or "channel"
                invite = request.chat.invite_link or (f"https://t.me/{request.chat.username}" if request.chat.username else "")
                
                buttons = []
                if invite:
                    buttons.append([InlineKeyboardButton(f"📂 {chat_title} Kholo", url=invite)])

                await client.send_message(
                    user_id,
                    f"🎉 **Request Approve Ho Gayi!**\n\n"
                    f"Hello {request.from_user.first_name}!\n"
                    f"**{chat_title}** join karne ki request approve kar di gayi hai.\n\n"
                    f"Welcome! ❤️",
                    reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
                )
            except:
                pass
        except Exception as e:
            logger.error(f"Auto accept error: {e}")

# ===================== MESSAGE FILTER =====================

IGNORE_COMMANDS = [
    "start", "help", "settings", "request", "setwelcome", "addfsub", "stats",
    "ai", "broadcast", "ban", "unban", "add_premium", "remove_premium",
    "premiumstats", "ping", "id", "clean", "mychannels", "groupstats"
]

@app.on_message(filters.group & filters.text & ~filters.command(IGNORE_COMMANDS))
async def group_filter(client, message: Message):
    if not message.from_user:
        return
    if await is_admin(message.chat.id, message.from_user.id):
        return

    settings = await get_settings(message.chat.id)
    quality = MovieBotUtils.check_message_quality(message.text)
    user_name = message.from_user.first_name or "User"

    # --- LINK ---
    if quality == "LINK" and settings.get("link_protection", True):
        try:
            await message.delete()
        except:
            pass
        count = await add_warning(message.chat.id, message.from_user.id)
        limit = Config.MAX_WARNINGS
        
        if count >= limit:
            try:
                until = datetime.datetime.now() + datetime.timedelta(hours=24)
                await client.restrict_chat_member(
                    message.chat.id, message.from_user.id,
                    ChatPermissions(can_send_messages=False), until_date=until
                )
                msg = await message.reply_text(
                    f"🚫 **{message.from_user.mention} ko 24 ghante ke liye mute kar diya!**\n"
                    f"Wajah: Links allowed nahi hain."
                )
                await reset_warnings(message.chat.id, message.from_user.id)
            except:
                msg = await message.reply_text(f"⚠️ {message.from_user.mention}, links mat bhejo!")
        else:
            warn_text = MovieBotUtils.get_link_warning(user_name, count, limit)
            msg = await message.reply_text(warn_text)
        
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))

    # --- ABUSE ---
    elif quality == "ABUSE" and settings.get("abuse_protection", True):
        try:
            await message.delete()
        except:
            pass
        count = await add_warning(message.chat.id, message.from_user.id)
        limit = Config.MAX_WARNINGS
        
        if count >= limit:
            try:
                await client.ban_chat_member(message.chat.id, message.from_user.id)
                msg = await message.reply_text(
                    f"🚫 **{message.from_user.mention} ban ho gaye!**\n"
                    f"Wajah: Gali dena allowed nahi."
                )
                await reset_warnings(message.chat.id, message.from_user.id)
            except:
                msg = await message.reply_text(f"⚠️ {message.from_user.mention}, galiyaan mat do!")
        else:
            warn_text = MovieBotUtils.get_abuse_warning(user_name, count, limit)
            msg = await message.reply_text(warn_text)
        
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))

    # --- JUNK (SPELLING CHECK) ---
    elif quality == "JUNK" and settings.get("spelling_on", True):
        validation = MovieBotUtils.validate_movie_format(message.text)
        if not validation['is_valid']:
            try:
                await message.delete()
            except:
                pass

            mode = settings.get("spelling_mode", "simple")
            junk_str = ", ".join(validation['found_junk'])

            if mode == "simple":
                warn_text = MovieBotUtils.get_junk_warning(
                    user_name, junk_str,
                    message.text, validation['correct_format']
                )
                msg = await message.reply_text(warn_text)
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 15))

            elif mode == "advanced":
                clean_name = validation['clean_name']
                omdb = await MovieBotUtils.get_omdb_info(clean_name)

                if omdb["found"]:
                    header = MovieBotUtils.get_advanced_found_msg(user_name, message.text)
                    full_text = f"{header}\n\n{omdb['text']}"

                    if omdb.get("poster"):
                        try:
                            await client.send_photo(
                                message.chat.id,
                                photo=omdb["poster"],
                                caption=full_text
                            )
                        except:
                            await message.reply_text(full_text)
                    else:
                        await message.reply_text(full_text)
                else:
                    not_found_text = MovieBotUtils.get_advanced_not_found_msg(user_name, message.text)
                    msg = await message.reply_text(not_found_text)
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 15))

    # --- AI CHAT (jab koi akela message kare bina tag kiye) ---
    elif quality in ["CLEAN", "IGNORE"] and settings.get("ai_enabled", True):
        # Check karo message kisi ko tag kar raha hai ya reply hai
        if message.reply_to_message or "@" in message.text:
            return
        # Sirf agar clearly kuch sawaal jaisa ho
        if len(message.text.split()) < 3:
            return
        # Movie related lagta hai?
        movie_hints = ["kaisa", "kya", "kon", "kahani", "batao", "bolo", "recommend",
                       "suggest", "movie", "film", "series", "dekhu", "dekhna"]
        if any(hint in message.text.lower() for hint in movie_hints):
            await show_typing(message.chat.id)
            response = await MovieBotUtils.get_ai_response(message.text)
            if response:
                msg = await message.reply_text(response)
                asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 180))

# ===================== FILE AUTO DELETE =====================

@app.on_message(filters.group & (filters.document | filters.video | filters.audio | filters.photo))
async def auto_delete_files(client, message: Message):
    settings = await get_settings(message.chat.id)
    if not settings.get("auto_delete_on"):
        return
    
    delete_time = settings.get("delete_time", 0)
    if delete_time <= 0:
        return

    await asyncio.sleep(delete_time * 60)
    
    try:
        await client.delete_messages(message.chat.id, message.id)
        notif = await message.reply_text(
            f"🗑️ File auto-delete ho gayi ({delete_time} min ke baad).",
        )
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, notif, 10))
    except:
        pass

# ===================== WELCOME =====================

@app.on_message(filters.new_chat_members)
async def welcome_new(client, message: Message):
    try:
        await message.delete()
    except:
        pass

    settings = await get_settings(message.chat.id)
    if not settings.get("welcome_enabled", True):
        return

    custom = await get_welcome_message(message.chat.id)

    for member in message.new_chat_members:
        if member.is_self:
            # Bot add hua
            await add_group(message.chat.id, message.chat.title)
            continue

        if custom:
            text = custom.get("text", "")
            text = text.replace("{name}", member.mention).replace("{chat}", message.chat.title or "")
            photo = custom.get("photo_id")
            raw_buttons = custom.get("buttons", [])

            markup = None
            if raw_buttons:
                rows = [[InlineKeyboardButton(b["text"], url=b["url"])] for b in raw_buttons if b.get("text") and b.get("url")]
                if rows:
                    markup = InlineKeyboardMarkup(rows)

            if photo:
                try:
                    wm = await client.send_photo(message.chat.id, photo=photo, caption=text or "", reply_markup=markup)
                except:
                    wm = await client.send_message(message.chat.id, text or "Welcome!", reply_markup=markup)
            else:
                wm = await client.send_message(message.chat.id, text or "Welcome!", reply_markup=markup)
        else:
            # Default welcome
            caption = (
                f"👋 **{member.mention} aagaye!**\n\n"
                f"**{message.chat.title or 'Group'}** mein aapka swagat hai! 🎬\n\n"
                f"**Group ke kuch kaam ki baatein:**\n"
                f"• Movie request ke liye `/request Movie Naam` likho\n"
                f"• Seedha movie/series ka naam likho — bot help karega!\n"
                f"• Links aur abuse allowed nahi hain\n\n"
                f"Enjoy karo! 🍿"
            )
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎬 Movie Request Karo", switch_inline_query_current_chat="/request ")],
                [InlineKeyboardButton("❓ Help", callback_data="help_main")]
            ])
            
            sent = False
            if member.photo:
                try:
                    wm = await client.send_photo(message.chat.id, photo=member.photo.big_file_id, caption=caption, reply_markup=buttons)
                    sent = True
                except:
                    pass
            
            if not sent:
                wm = await message.reply_text(caption, reply_markup=buttons)

        asyncio.create_task(MovieBotUtils.auto_delete_message(client, wm, 120))

@app.on_message(filters.command("setwelcome") & filters.group)
async def setwelcome_cmd(client, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ Sirf admins use kar sakte hain!")

    reply = message.reply_to_message
    if not reply and len(message.command) < 2:
        return await message.reply_text(
            "❌ **Usage:**\n"
            "Kisi message/photo ko reply karke `/setwelcome` likho\n"
            "Ya: `/setwelcome {name} welcome kar diya {chat} mein!`"
        )

    photo_id = None
    text = ""

    if reply:
        text = reply.caption or reply.text or ""
        if reply.photo:
            photo_id = reply.photo.file_id
    else:
        text = message.text.split(None, 1)[1]

    await set_welcome_message(message.chat.id, text, photo_id)
    await message.reply_text("✅ **Custom welcome set ho gaya!**")

# ===================== REQUEST SYSTEM =====================

@app.on_message(
    (filters.command("request") | filters.regex(r'^#?request\s+', re.IGNORECASE)) & filters.group
)
async def request_handler(client, message: Message):
    if not message.from_user:
        return

    if message.text.startswith("/"):
        if len(message.command) < 2:
            msg = await message.reply_text("❌ Format: `/request Movie Ka Naam`")
            return asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))
        movie_name = " ".join(message.command[1:])
    else:
        movie_name = re.split(r'request\s+', message.text, flags=re.IGNORECASE, maxsplit=1)[-1].strip()

    if not movie_name:
        msg = await message.reply_text("❌ Movie ka naam bhi likho bhai!")
        return asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 10))

    # Admins tag karo
    mentions = []
    try:
        from pyrogram.enums import ChatMembersFilter
        async for member in client.get_chat_members(message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS):
            if not member.user.is_bot and not member.user.is_deleted:
                mentions.append(member.user.mention)
            if len(mentions) >= 4:
                break
    except:
        mentions = ["Admins"]

    tag_text = " ".join(mentions) if mentions else "Admins"

    req_text = (
        f"📨 **Nayi Request!**\n\n"
        f"🎬 **Movie/Series:** `{movie_name}`\n"
        f"👤 **Request kiya:** {message.from_user.mention}\n"
        f"🔔 **Tag:** {tag_text}\n"
        f"🕐 **Time:** {datetime.datetime.now().strftime('%d %b %Y, %I:%M %p')}"
    )

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Upload Ho Gaya", callback_data=f"req_done_{message.from_user.id}"),
            InlineKeyboardButton("❌ Available Nahi", callback_data=f"req_no_{message.from_user.id}")
        ]
    ])

    await client.send_message(message.chat.id, req_text, reply_markup=buttons)
    try:
        await message.delete()
    except:
        pass

# ===================== AI COMMAND =====================

@app.on_message(filters.command("ai"))
async def ai_cmd(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "**Usage:** `/ai [sawaal]`\n\n"
            "**Misal:**\n"
            "• `/ai Inception kaisi movie hai?`\n"
            "• `/ai 2024 ki best movies kaun si hain?`\n"
            "• `/ai Spider-Man ka review do`"
        )

    query = " ".join(message.command[1:])
    await show_typing(message.chat.id)
    thinking = await message.reply_text(f"💭 {MovieBotUtils.get_ai_thinking()}")
    
    response = await MovieBotUtils.get_ai_response(query)
    await thinking.delete()
    
    msg = await message.reply_text(response)
    if message.chat.type != ChatType.PRIVATE:
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 300))

# ===================== FORCE SUBSCRIBE =====================

@app.on_chat_member_updated()
async def handle_new_member(client, update: ChatMemberUpdated):
    if not update.new_chat_member or update.new_chat_member.user.is_bot:
        return

    old = update.old_chat_member
    new = update.new_chat_member

    if not (old is None or old.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]):
        return

    user_id = new.user.id
    chat_id = update.chat.id
    cache_key = f"{user_id}_{chat_id}"

    if cache_key in fsub_cache:
        return
    fsub_cache.add(cache_key)
    asyncio.get_event_loop().call_later(5, lambda: fsub_cache.discard(cache_key))

    fsub = await get_force_sub(chat_id)
    if not fsub:
        return

    channel_id = fsub["channel_id"]
    user = new.user

    try:
        member = await client.get_chat_member(channel_id, user_id)
        if member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
            # Already joined — unmute
            try:
                await client.restrict_chat_member(chat_id, user_id, ChatPermissions(
                    can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True
                ))
            except:
                pass
            return
    except UserNotParticipant:
        pass
    except:
        return

    # Restrict
    try:
        await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
    except:
        return

    try:
        ch_info = await client.get_chat(channel_id)
        link = ch_info.invite_link or (f"https://t.me/{ch_info.username}" if ch_info.username else None)
        ch_name = ch_info.title
    except:
        link = None
        ch_name = "Channel"

    btn_rows = []
    if link:
        btn_rows.append([InlineKeyboardButton(f"📢 {ch_name} Join Karo", url=link)])
    btn_rows.append([InlineKeyboardButton("✅ Join kar liya", callback_data=f"fsub_verify_{user_id}")])

    text = (
        f"🔒 **Ek kaam karo pehle!**\n\n"
        f"👋 {user.mention}, group mein message bhejne ke liye\n"
        f"pehle **{ch_name}** join karna hoga.\n\n"
        f"Join karo aur phir **'Join kar liya'** button dabao. ✅"
    )

    try:
        fsub_msg = await client.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(btn_rows))
        asyncio.create_task(MovieBotUtils.auto_delete_message(client, fsub_msg, 300))
    except:
        pass

# ===================== ADDFSUB =====================

@app.on_message(filters.command("addfsub") & filters.group)
async def addfsub_cmd(client, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    if not await check_is_premium(message.chat.id):
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Premium Lo", url="https://t.me/asbhai_bsr")]
        ])
        msg = await message.reply_text(
            "💎 **Force Subscribe Premium Feature hai!**\n\nContact @asbhai_bsr",
            reply_markup=buttons
        )
        return asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))

    channel_id = None
    if len(message.command) > 1:
        try:
            channel_id = int(message.command[1])
        except:
            pass
    elif message.reply_to_message and message.reply_to_message.forward_from_chat:
        channel_id = message.reply_to_message.forward_from_chat.id

    if not channel_id:
        return await message.reply_text("❌ Usage: `/addfsub -100xxxxxxx`")

    try:
        chat = await client.get_chat(channel_id)
        me = await client.get_chat_member(channel_id, (await client.get_me()).id)
        if me.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply_text("❌ Mujhe us channel mein admin banao pehle!")
    except:
        return await message.reply_text("❌ Channel nahi mila ya access nahi hai!")

    await set_force_sub(message.chat.id, channel_id)
    msg = await message.reply_text(
        f"✅ **Force Subscribe Set Ho Gaya!**\n\n"
        f"Channel: **{chat.title}**\n"
        f"Naye members ko pehle join karna hoga."
    )
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, msg, 30))

# ===================== CALLBACK QUERIES =====================

@app.on_callback_query()
async def callback_handler(client, query: CallbackQuery):
    data = query.data
    chat_id = query.message.chat.id if query.message else query.from_user.id
    user_id = query.from_user.id

    try:
        # ---- SETTINGS ----
        if data == "settings_main":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            await show_settings_menu(client, query, menu="main")

        elif data == "menu_spelling":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            await show_settings_menu(client, query, menu="spelling")

        elif data == "menu_autodelete":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            await show_settings_menu(client, query, menu="autodelete")

        elif data == "menu_welcome":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            await show_settings_menu(client, query, menu="welcome")

        elif data == "menu_ai":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            await show_settings_menu(client, query, menu="ai")

        elif data == "toggle_spelling":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            st = await get_settings(chat_id)
            new_val = not st.get("spelling_on", True)
            await update_settings(chat_id, "spelling_on", new_val)
            await query.answer(f"✏️ Spelling: {'ON ✅' if new_val else 'OFF ❌'}")
            await show_settings_menu(client, query, menu="spelling")

        elif data == "toggle_spell_mode":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            st = await get_settings(chat_id)
            new_mode = "advanced" if st.get("spelling_mode", "simple") == "simple" else "simple"
            await update_settings(chat_id, "spelling_mode", new_mode)
            await query.answer(f"Mode: {new_mode.upper()}")
            await show_settings_menu(client, query, menu="spelling")

        elif data.startswith("adel_"):
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            mins = int(data.split("_")[1])
            if mins == 0:
                await update_settings(chat_id, "auto_delete_on", False)
                await update_settings(chat_id, "delete_time", 0)
                await query.answer("🗑️ Auto Delete band ho gaya")
            else:
                await update_settings(chat_id, "auto_delete_on", True)
                await update_settings(chat_id, "delete_time", mins)
                await query.answer(f"✅ Auto Delete: {mins} min")
            await show_settings_menu(client, query, menu="autodelete")

        elif data == "toggle_welcome":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            st = await get_settings(chat_id)
            new_val = not st.get("welcome_enabled", True)
            await update_settings(chat_id, "welcome_enabled", new_val)
            await query.answer(f"👋 Welcome: {'ON ✅' if new_val else 'OFF ❌'}")
            await show_settings_menu(client, query, menu="welcome")

        elif data == "clear_welcome":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            await update_settings(chat_id, "welcome_text", "")
            await update_settings(chat_id, "welcome_photo", None)
            await update_settings(chat_id, "welcome_buttons", [])
            await query.answer("🗑️ Custom welcome hata diya!")
            await show_settings_menu(client, query, menu="welcome")

        elif data == "toggle_ai":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            st = await get_settings(chat_id)
            new_val = not st.get("ai_enabled", True)
            await update_settings(chat_id, "ai_enabled", new_val)
            await query.answer(f"🤖 AI Chat: {'ON ✅' if new_val else 'OFF ❌'}")
            await show_settings_menu(client, query, menu="ai")

        elif data == "toggle_link_prot":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            st = await get_settings(chat_id)
            new_val = not st.get("link_protection", True)
            await update_settings(chat_id, "link_protection", new_val)
            await query.answer(f"🔗 Link Protection: {'ON ✅' if new_val else 'OFF ❌'}")
            await show_settings_menu(client, query, menu="main")

        elif data == "toggle_abuse_prot":
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            st = await get_settings(chat_id)
            new_val = not st.get("abuse_protection", True)
            await update_settings(chat_id, "abuse_protection", new_val)
            await query.answer(f"🤬 Abuse Filter: {'ON ✅' if new_val else 'OFF ❌'}")
            await show_settings_menu(client, query, menu="main")

        elif data == "close_settings":
            await query.message.delete()
            await query.answer()

        # ---- CHANNEL MANAGEMENT ----
        elif data == "channel_setup_home":
            text = (
                "📢 **Channel Auto Accept Setup**\n\n"
                "Main aapke channel ki join requests automatically approve karta hoon!\n\n"
                "**Setup kaise karein:**\n"
                "1️⃣ Mujhe apne channel mein **Admin** banao\n"
                "2️⃣ Apne channel se koi bhi message yahan forward karo\n"
                "   Ya channel ID daalo (jaise: `-1001234567890`)\n"
                "3️⃣ Bot automatically sab handle karega!\n\n"
                "**Apne channels manage karne ke liye:**"
            )
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Mere Channels Dekho", callback_data="show_my_channels")],
                [InlineKeyboardButton("➕ Channel Add Karo", callback_data="add_channel_prompt")],
                [InlineKeyboardButton("❌ Band Karo", callback_data="close_help")]
            ])
            try:
                await query.message.edit_text(text, reply_markup=buttons)
            except:
                await query.message.reply_text(text, reply_markup=buttons)

        elif data == "show_my_channels":
            channels = await get_user_channels(user_id)
            await send_channels_panel(client, query.message, user_id, channels, edit=True)

        elif data == "add_channel_prompt":
            await query.message.edit_text(
                "📢 **Channel Add Karo**\n\n"
                "**2 tarike hain:**\n\n"
                "**Tarika 1:** Apne channel se koi bhi message yahan forward karo\n\n"
                "**Tarika 2:** Channel ID daalo\n"
                "Channel ID mila nahi? @username_to_id_bot se pata karo\n"
                "Format: `-100xxxxxxxxxx`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Wapas", callback_data="channel_setup_home")]
                ])
            )

        elif data.startswith("confirm_add_ch_"):
            channel_id = int(data.split("_")[-1])
            try:
                chat = await client.get_chat(channel_id)
                
                # Bot admin check
                bot_me = await client.get_me()
                bot_member = await client.get_chat_member(channel_id, bot_me.id)
                if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                    await query.answer("❌ Bot channel mein admin nahi hai!", show_alert=True)
                    return

                await add_user_channel(user_id, channel_id, chat.title, chat.username)
                await set_auto_accept(channel_id, True)

                await query.message.edit_text(
                    f"✅ **{chat.title} Connected Ho Gaya!**\n\n"
                    f"Ab main is channel ki join requests automatically approve karoonga.\n\n"
                    f"Manage karne ke liye `/mychannels` use karo.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📋 Mere Channels", callback_data="show_my_channels")]
                    ])
                )
            except Exception as e:
                await query.answer(f"Error: {e}", show_alert=True)

        elif data == "cancel_add_ch":
            await query.message.edit_text("❌ Channel add nahi kiya.")

        elif data.startswith("ch_detail_"):
            channel_id = int(data.split("_")[-1])
            ch = await get_user_channel(user_id, channel_id)
            if not ch:
                await query.answer("Channel nahi mila!", show_alert=True)
                return

            is_connected = ch.get("connected", False)
            title = ch.get("channel_title", "Unknown")

            text = (
                f"📢 **{title}**\n\n"
                f"**ID:** `{channel_id}`\n"
                f"**Status:** {'🟢 Connected (Auto Accept ON)' if is_connected else '🔴 Disconnected'}\n\n"
                f"Neeche se manage karo:"
            )
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "🔴 Disconnect Karo" if is_connected else "🟢 Connect Karo",
                    callback_data=f"toggle_ch_{channel_id}"
                )],
                [InlineKeyboardButton("🗑️ Remove Karo", callback_data=f"remove_ch_{channel_id}")],
                [InlineKeyboardButton("🔙 Wapas", callback_data="show_my_channels")]
            ])
            await query.message.edit_text(text, reply_markup=buttons)

        elif data.startswith("toggle_ch_"):
            channel_id = int(data.split("_")[-1])
            ch = await get_user_channel(user_id, channel_id)
            if not ch:
                return await query.answer("Channel nahi mila!", show_alert=True)

            new_status = not ch.get("connected", False)
            await toggle_channel_auto_accept(user_id, channel_id, new_status)
            status_text = "🟢 Connect ho gaya!" if new_status else "🔴 Disconnect ho gaya!"
            await query.answer(status_text)
            # Refresh detail
            query.data = f"ch_detail_{channel_id}"
            await callback_handler(client, query)

        elif data.startswith("remove_ch_"):
            channel_id = int(data.split("_")[-1])
            ch = await get_user_channel(user_id, channel_id)
            title = ch.get("channel_title", "Channel") if ch else "Channel"
            await remove_user_channel(user_id, channel_id)
            await query.answer("🗑️ Remove ho gaya!")
            channels = await get_user_channels(user_id)
            await send_channels_panel(client, query.message, user_id, channels, edit=True)

        # ---- REQUESTS ----
        elif data.startswith("req_done_"):
            req_user_id = int(data.split("_")[-1])
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            await client.send_message(
                chat_id,
                f"✅ **Request Complete!**\n\n"
                f"{query.from_user.mention} ne upload kar diya!\n"
                f"<a href='tg://user?id={req_user_id}'>User</a>, dekho! 🎬"
            )
            await query.message.delete()
            await query.answer("✅ Done!")

        elif data.startswith("req_no_"):
            req_user_id = int(data.split("_")[-1])
            if not await is_admin(chat_id, user_id):
                return await query.answer("❌ Sirf admins!", show_alert=True)
            await client.send_message(
                chat_id,
                f"❌ **Request Reject Ho Gayi**\n\n"
                f"Admin {query.from_user.mention} ne bataya:\n"
                f"Yeh movie/series abhi available nahi hai.\n"
                f"<a href='tg://user?id={req_user_id}'>User</a>, baad mein try karo!"
            )
            await query.message.delete()
            await query.answer("❌ Rejected!")

        # ---- FSUB VERIFY ----
        elif data.startswith("fsub_verify_"):
            target_id = int(data.split("_")[-1])
            if user_id != target_id:
                return await query.answer("❌ Yeh button tumhare liye nahi hai!", show_alert=True)

            fsub = await get_force_sub(chat_id)
            if not fsub:
                return await query.message.delete()

            channel_id = fsub["channel_id"]
            try:
                member = await client.get_chat_member(channel_id, user_id)
                if member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                    await client.restrict_chat_member(chat_id, user_id, ChatPermissions(
                        can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True
                    ))
                    await query.message.delete()
                    wm = await client.send_message(
                        chat_id,
                        f"✅ **{query.from_user.mention} verify ho gaye!**\n"
                        f"Ab message bhej sakte ho. Welcome! 😊"
                    )
                    asyncio.create_task(MovieBotUtils.auto_delete_message(client, wm, 30))
                    await query.answer("✅ Verified!")
                else:
                    await query.answer("❌ Abhi join nahi kiya!", show_alert=True)
            except UserNotParticipant:
                await query.answer("❌ Pehle channel join karo!", show_alert=True)

        # ---- HELP ----
        elif data == "help_main":
            text = (
                "**❓ Help Menu**\n\n"
                "**Bot kya karta hai:**\n"
                "• ✏️ Movie spelling check karta hai\n"
                "• ✅ Channel join requests auto approve karta hai\n"
                "• 🤖 AI se movie suggestions deta hai\n"
                "• 🛡️ Links aur abuse se bachata hai\n\n"
                "**Commands:**\n"
                "• `/settings` — Group settings\n"
                "• `/request [naam]` — Movie request\n"
                "• `/ai [sawaal]` — AI se poocho\n"
                "• `/mychannels` — Channels manage karo\n"
                "• `/ping` — Bot status\n"
                "• `/id` — ID dekho"
            )
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 Premium", callback_data="premium_info")],
                [InlineKeyboardButton("📢 Channel Setup", callback_data="channel_setup_home")],
                [InlineKeyboardButton("❌ Band Karo", callback_data="close_help")]
            ])
            try:
                await query.message.edit_text(text, reply_markup=buttons)
            except:
                await query.message.reply_text(text, reply_markup=buttons)

        elif data == "premium_info":
            text = (
                "💎 **Premium Plans**\n\n"
                "**Fayde:**\n"
                "• 🔗 Force Subscribe System\n"
                "• 🔇 No Broadcasts\n"
                "• ⚡ Priority Support\n"
                "• 🎯 Advanced Features\n\n"
                "**Pricing:**\n"
                "• 1 Mahina: ₹100\n"
                "• 3 Mahine: ₹250\n"
                "• Lifetime: ₹500\n\n"
                "Khareedne ke liye @asbhai_bsr se contact karo."
            )
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Contact Karo", url="https://t.me/asbhai_bsr")],
                [InlineKeyboardButton("🔙 Wapas", callback_data="help_main")]
            ])
            await query.message.edit_text(text, reply_markup=buttons)

        elif data == "close_help":
            await query.message.delete()

        elif data == "auto_accept_setup":
            await callback_handler(client, type('Q', (), {'data': 'channel_setup_home', 'message': query.message, 'from_user': query.from_user, 'answer': query.answer})())

    except Exception as e:
        logger.error(f"Callback error [{data}]: {e}")
        try:
            await query.answer("❌ Kuch error aa gaya!", show_alert=True)
        except:
            pass

# ===================== MISC COMMANDS =====================

@app.on_message(filters.command("ping"))
async def ping_cmd(client, message: Message):
    start = time.time()
    msg = await message.reply_text("🏓")
    ms = round((time.time() - start) * 1000, 2)
    await msg.edit_text(f"🏓 **Pong!**\n⏱ `{ms}ms`\n✅ Bot chal raha hai!")

@app.on_message(filters.command("id"))
async def id_cmd(client, message: Message):
    user_id = message.from_user.id if message.from_user else "?"
    text = f"👤 **Tera ID:** `{user_id}`"
    if message.chat.type != ChatType.PRIVATE:
        text += f"\n👥 **Group ID:** `{message.chat.id}`"
    await message.reply_text(text)

@app.on_message(filters.command("ban") & filters.user(Config.OWNER_ID))
async def ban_cmd(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/ban <user_id>`")
    try:
        uid = int(message.command[1])
        await ban_user(uid)
        await message.reply_text(f"✅ User `{uid}` ban ho gaya!")
    except:
        await message.reply_text("❌ Invalid ID!")

@app.on_message(filters.command("unban") & filters.user(Config.OWNER_ID))
async def unban_cmd(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/unban <user_id>`")
    try:
        uid = int(message.command[1])
        await unban_user(uid)
        await message.reply_text(f"✅ User `{uid}` unban ho gaya!")
    except:
        await message.reply_text("❌ Invalid ID!")

@app.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats_cmd(client, message: Message):
    stats = await get_bot_stats()
    text = (
        f"📊 **Bot Stats**\n\n"
        f"👥 Users: `{stats['total_users']}`\n"
        f"📁 Groups: `{stats['total_groups']}`\n"
        f"🚫 Banned: `{stats['banned_users']}`\n"
        f"💎 Premium: `{stats['premium_groups']}`\n"
        f"📨 Requests: `{stats['total_requests']}`\n"
        f"⏳ Pending: `{stats['pending_requests']}`\n\n"
        f"🕐 {datetime.datetime.now().strftime('%d %b %Y, %H:%M')}"
    )
    await message.reply_text(text)

@app.on_message(filters.command(["broadcast", "grp_broadcast"]) & filters.user(Config.OWNER_ID))
async def broadcast_cmd(client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("❌ Kisi message ko reply karke broadcast karo!")

    is_group = "grp_broadcast" in message.text
    target_ids = await get_all_groups() if is_group else await get_all_users()
    progress = await message.reply_text(f"📤 Broadcasting to {len(target_ids)}...")
    success = failed = cleaned = 0

    for cid in target_ids:
        try:
            await message.reply_to_message.copy(cid)
            success += 1
        except (PeerIdInvalid, UserNotParticipant):
            if is_group:
                await remove_group(cid)
            else:
                await delete_user(cid)
            cleaned += 1
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["USER_IS_BLOCKED", "INPUT_USER_DEACTIVATED", "chat not found"]):
                if is_group:
                    await remove_group(cid)
                else:
                    await delete_user(cid)
                cleaned += 1
            else:
                failed += 1
        await asyncio.sleep(0.1)

    await progress.edit_text(
        f"✅ **Broadcast Complete**\n\n"
        f"Target: {len(target_ids)}\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}\n"
        f"🗑️ Cleaned: {cleaned}"
    )

@app.on_message(filters.command("add_premium") & filters.user(Config.OWNER_ID))
async def add_premium_cmd(client, message: Message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: `/add_premium <group_id> <months>`")
    try:
        gid = int(message.command[1])
        months = int(''.join(filter(str.isdigit, message.command[2])))
        expiry = await add_premium(gid, months)
        await message.reply_text(f"✅ Premium add! Expiry: {expiry.strftime('%Y-%m-%d')}")
        try:
            await client.send_message(gid, f"💎 Premium active ho gaya! {months} mahine ke liye. ❤️")
        except:
            pass
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

@app.on_message(filters.command("remove_premium") & filters.user(Config.OWNER_ID))
async def remove_premium_cmd(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/remove_premium <group_id>`")
    try:
        gid = int(message.command[1])
        await remove_premium(gid)
        await message.reply_text(f"✅ Premium remove ho gaya `{gid}` se!")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

@app.on_message(filters.command("clean") & filters.group)
async def clean_cmd(client, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return
    proc = await message.reply_text("🔄 Scan ho raha hai...")
    deleted = 0
    total = 0
    async for member in client.get_chat_members(message.chat.id):
        total += 1
        if member.user.is_deleted:
            try:
                await client.ban_chat_member(message.chat.id, member.user.id)
                deleted += 1
                await asyncio.sleep(0.3)
            except:
                pass
    await proc.edit_text(
        f"✅ **Cleanup done!**\n\n"
        f"👥 Total: {total}\n"
        f"🗑️ Deleted accounts hataye: {deleted}\n"
        f"👤 Active members: {total - deleted}"
    )

# ===================== BOT START =====================

async def start_bot():
    asyncio.create_task(scheduled_cleanup())
    await app.start()
    bot_info = await app.get_me()
    logger.info(f"✅ Bot started: @{bot_info.username}")

    try:
        commands = [
            BotCommand("start", "Bot start karo"),
            BotCommand("help", "Help dekho"),
            BotCommand("settings", "Group settings"),
            BotCommand("request", "Movie request karo"),
            BotCommand("ai", "AI se poocho"),
            BotCommand("mychannels", "Channels manage karo"),
            BotCommand("ping", "Bot status"),
            BotCommand("id", "Apna ID dekho"),
        ]
        await app.set_bot_commands(commands)
        group_cmds = [
            BotCommand("request", "Movie request karo"),
            BotCommand("ai", "AI se poocho"),
            BotCommand("settings", "Settings"),
            BotCommand("id", "ID dekho"),
        ]
        await app.set_bot_commands(group_cmds, scope=BotCommandScopeAllGroupChats())
    except Exception as e:
        logger.warning(f"Commands set failed: {e}")

    if Config.OWNER_ID:
        try:
            await app.send_message(
                Config.OWNER_ID,
                f"🤖 Bot start ho gaya!\n@{bot_info.username}\n{datetime.datetime.now().strftime('%d %b %Y %H:%M')}"
            )
        except:
            pass

    await idle()

async def scheduled_cleanup():
    while True:
        await asyncio.sleep(Config.CLEANUP_INTERVAL)
        try:
            counts = await clear_junk()
            total = sum(counts.values())
            if total > 0:
                logger.info(f"Cleanup: {counts}")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

if __name__ == "__main__":
    print("🚀 Movie Helper Bot starting...")
    try:
        app.run(start_bot())
    except KeyboardInterrupt:
        print("⏹️ Bot stopped.")
    except Exception as e:
        print(f"❌ Crash: {e}")
        import traceback
        traceback.print_exc()
