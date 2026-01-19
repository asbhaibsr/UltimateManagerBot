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
from pyrogram.errors import FloodWait, UserNotParticipant, ChatAdminRequired
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

# User states maintain karne ke liye (Channel ID lene ke liye)
user_states = {}

# Cache for Force Sub to prevent double messages
fsub_cache = []

# ================ HELPER FUNCTIONS ================
async def is_admin(chat_id, user_id):
    if user_id == Config.OWNER_ID:
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

async def handle_request_logic(client, message, movie_name):
    """Common logic for /request and #request"""
    if not movie_name:
        msg = await message.reply_text("❌ Movie ka naam likhein! Example: /request Kalki")
        await MovieBotUtils.auto_delete_message(client, msg, 10)
        return

    chat = message.chat
    user = message.from_user

    # Group ke Owner/Admins ki list nikalo tag karne ke liye
    admin_mentions = []
    try:
        async for member in client.get_chat_members(chat.id, filter=ChatMemberStatus.ADMINISTRATOR):
            if not member.user.is_bot:
                admin_mentions.append(member.user.mention)
    except:
        pass # Admin rights issue
    
    # Sirf top 3-4 admins ko tag karo taaki spam na ho
    tags = ", ".join(admin_mentions[:4]) if admin_mentions else "Admins"

    text = (
        f"🔔 **New Request!**\n\n"
        f"👤 **Requester:** {user.mention}\n"
        f"🎬 **Movie:** `{movie_name}`\n"
        f"👮‍♂️ **Admins:** {tags}\n"
    )

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Available", callback_data=f"req_accept_{user.id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"req_reject_{user.id}")
        ]
    ])

    req_msg = await message.reply_text(text, reply_markup=buttons)
    # 5 Minute baad request msg auto delete
    await MovieBotUtils.auto_delete_message(client, req_msg, 300)

# ================ START COMMAND (New Layout) ================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Handle /start command with New Layout"""
    user = message.from_user
    await add_user(user.id, user.username, user.first_name)
    
    # Log Channel me bhejo
    if Config.LOGS_CHANNEL:
        try:
            log_text = (
                f"🧑‍💻 **New User Started Bot**\n\n"
                f"👤 Name: {user.mention}\n"
                f"🆔 ID: `{user.id}`\n"
                f"🔗 Username: @{user.username if user.username else 'N/A'}"
            )
            await client.send_message(Config.LOGS_CHANNEL, log_text)
        except Exception:
            pass

    welcome_text = f"""🎬 **Namaste {user.first_name}!** 🎬

Main hoon apka **Movie Helper Bot!** 🤖

Main Groups me spelling theek karta hoon aur Movies manage karta hoon.
Mujhe apne Group me add karein! 👇"""
    
    # New Button Layout as per request
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add me to Group ➕", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [
            InlineKeyboardButton("💎 Premium", callback_data="premium_info"),
            InlineKeyboardButton("🆘 Help", callback_data="help_page_1")
        ],
        [InlineKeyboardButton("⚡ Auto Accept Setup", callback_data="auto_accept_setup")]
    ])
    
    await message.reply_text(welcome_text, reply_markup=buttons)
    # Auto delete start message after 5 mins
    await MovieBotUtils.auto_delete_message(client, message, 300)

# ================ PRIVATE SETUP HANDLER (For Channel ID) ================
@app.on_message(filters.private & filters.text & ~filters.command(["start", "help"]))
async def handle_private_setup(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Check agar user ID bhejne wala state me hai
    if user_id in user_states and user_states[user_id] == "waiting_for_channel_id":
        try:
            channel_id = int(message.text)
            # Setup Auto Accept for this ID (Assuming set_auto_accept works for channels too in your DB)
            await set_auto_accept(channel_id, True)
            
            del user_states[user_id]
            await message.reply_text(
                f"✅ **Done!**\n\nChannel ID `{channel_id}` ke liye Auto Accept ON kar diya gaya hai.\n\nAb jo bhi request aayegi, main accept kar lunga. Bas mujhe wahan **Admin** bana do!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data="start_back")]])
            )
        except ValueError:
            await message.reply_text("❌ Invalid ID! Number wala ID bhejein (Example: -1001234567890).")

# ================ HELP COMMAND ================
@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    """Handle /help command"""
    help_text = "Click the button below for Help Menu 👇"
    buttons = InlineKeyboardMarkup([[InlineKeyboardButton("🆘 Open Help", callback_data="help_page_1")]])
    await message.reply_text(help_text, reply_markup=buttons)

# ================ SETTINGS COMMAND ================
@app.on_message(filters.command("settings") & filters.group)
async def settings_command(client: Client, message: Message):
    """Group settings menu"""
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ Only Group Admins/Owner can use settings!")
        await asyncio.sleep(5)
        await msg.delete()
        return
    
    settings = await get_settings(message.chat.id)
    is_prem = await check_is_premium(message.chat.id)
    auto_accept = await get_auto_accept(message.chat.id)
    
    prem_status = "💎 Active" if is_prem else "❌ Free"
    spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
    delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
    accept_status = "✅ ON" if auto_accept else "❌ OFF"
    time_text = f"{settings.get('delete_time', 0)} min" if settings.get('delete_time', 0) > 0 else "Permanent"
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Spelling: {spelling_status}", callback_data="toggle_spelling")],
        [InlineKeyboardButton(f"Auto Delete: {delete_status}", callback_data="toggle_auto_delete")],
        [InlineKeyboardButton(f"Auto Accept: {accept_status}", callback_data="toggle_auto_accept")],
        [InlineKeyboardButton(f"Time: {time_text}", callback_data="set_delete_time")],
        [InlineKeyboardButton(f"Premium: {prem_status}", callback_data="premium_info")],
        [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
    ])
    
    await message.reply_text(f"⚙️ Settings for **{message.chat.title}**", reply_markup=buttons)

# ================ REQUEST HANDLER ================
@app.on_message(filters.command("request") & filters.group)
async def request_handler(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Movie ka naam to likho!\nExample: /request Pushpa 2")
    
    movie_name = " ".join(message.command[1:])
    await handle_request_logic(client, message, movie_name)

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
        [InlineKeyboardButton("🧹 Clear Junk", callback_data="clear_junk")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]
    ])
    
    stats_text = f"""📊 Bot Statistics

👥 Total Users: {users}
👥 Total Groups: {groups}
💎 Premium Groups: {premium_count}
⚡ Bot Uptime: 24/7
🔄 Last Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Database Status: ✅ Connected
AI Status: ✅ Active
Server: Koyeb Cloud
Status: ✅ Running"""
    
    await message.reply_text(stats_text, reply_markup=buttons)

# ================ AI COMMAND ================
@app.on_message(filters.command("ai"))
async def ai_command(client: Client, message: Message):
    """AI chat feature"""
    if len(message.command) < 2:
        await message.reply_text("Usage: /ai your question\nExample: /ai Tell me about Inception movie")
        return
    
    query = ' '.join(message.command[1:])
    waiting_msg = await message.reply_text("🤔 Soch raha hu...")
    
    response = await MovieBotUtils.get_ai_response(query)
    
    await waiting_msg.delete()
    await message.reply_text(response)
    await MovieBotUtils.auto_delete_message(client, message)

# ================ BROADCAST COMMAND (AUTO CLEAN JUNK) ================
@app.on_message(filters.command(["broadcast", "grp_broadcast"]) & filters.user(Config.OWNER_ID))
async def broadcast_command(client: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("❌ Reply to a message!")
    
    is_group = "grp_broadcast" in message.text
    target_ids = await get_all_groups() if is_group else await get_all_users()
    
    # Premium Filter for Groups (Don't broadcast to Premium)
    if is_group:
        target_ids = [g for g in target_ids if not await check_is_premium(g)]

    progress = await message.reply_text(f"🚀 Broadcasting to {len(target_ids)} chats...")
    success, failed, deleted = 0, 0, 0
    
    for id in target_ids:
        try:
            await message.reply_to_message.copy(id)
            success += 1
        except Exception as e:
            # Agar bot block hai ya kick hai to DB se hata do
            if "PeerIdInvalid" in str(e) or "UserDeactivated" in str(e) or "ChannelPrivate" in str(e) or "ChatWriteForbidden" in str(e):
                if is_group:
                    await remove_group(id)
                else:
                    pass # User removal logic
                deleted += 1
            failed += 1
        await asyncio.sleep(0.5)
        
    await progress.edit_text(
        f"✅ Broadcast Complete!\n\n"
        f"🎯 Total: {len(target_ids)}\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}\n"
        f"🗑️ Cleaned Junk: {deleted}"
    )

# ================ ADDFSUB COMMAND ================
@app.on_message(filters.command("addfsub") & filters.group)
async def addfsub_command(client: Client, message: Message):
    """Set force subscribe channel"""
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ Only Admins can use this!")
        await asyncio.sleep(5)
        await msg.delete()
        return

    # Check Premium First
    if not await check_is_premium(message.chat.id):
        return await message.reply_text(
            "💎 **Premium Feature!**\n\n"
            "Force Subscribe use karne ke liye Premium lena padega.\n"
            "Buy Premium: @asbhai_bsr",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Buy Premium", url="https://t.me/asbhai_bsr")]])
        )

    channel_id = None
    
    if len(message.command) > 1:
        try:
            channel_id = int(message.command[1])
        except ValueError:
            return await message.reply_text("❌ Invalid ID! Numeric ID daalo (e.g. -100...)")

    elif message.reply_to_message:
        if message.reply_to_message.forward_from_chat:
            channel_id = message.reply_to_message.forward_from_chat.id
        else:
            return await message.reply_text("❌ Channel ID nahi mili. Forward privacy on hai. \nTry command: `/addfsub <channel_id>`")
    else:
        return await message.reply_text("❌ Usage:\n1. `/addfsub -100xxxx`\n2. Reply to channel message with `/addfsub`")

    try:
        chat = await client.get_chat(channel_id)
        me = await client.get_chat_member(channel_id, (await client.get_me()).id)
        if not me.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
             return await message.reply_text("❌ Main us channel me Admin nahi hu!")
    except Exception as e:
        return await message.reply_text(f"❌ Error: Bot ko Channel me add karo aur Admin banao!\nError: {e}")

    await set_force_sub(message.chat.id, channel_id)
    await message.reply_text(f"✅ **Force Subscribe Connected!**\n\nLinked to: {chat.title}")

# ================ PREMIUM ADMIN COMMANDS ================
@app.on_message(filters.command("add_premium") & filters.user(Config.OWNER_ID))
async def add_premium_cmd(client: Client, message: Message):
    try:
        if len(message.command) < 3:
             await message.reply_text("❌ Usage: `/add_premium <group_id> <months>`")
             return

        group_id = int(message.command[1])
        raw_months = message.command[2].lower()
        clean_months = ''.join(filter(str.isdigit, raw_months))
        
        if not clean_months:
             await message.reply_text("❌ Error: Invalid month format.")
             return
             
        months = int(clean_months)
        expiry = await add_premium(group_id, months)
        
        await message.reply_text(f"✅ **Premium Added!**\nGroup: `{group_id}`\nMonths: {months}\nExpires: {expiry}")
        
        try:
            await client.send_message(
                group_id,
                f"💎 **Premium Activated!** 💎\n\n✅ Ads Removed\n✅ Force Subscribe Enabled (/addfsub)\n\nThank you for support! ❤️"
            )
        except:
            await message.reply_text("⚠️ Database update hua par Group me msg nahi gaya")
            
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

@app.on_message(filters.command("remove_premium") & filters.user(Config.OWNER_ID))
async def remove_premium_cmd(client: Client, message: Message):
    try:
        if len(message.command) < 2:
            await message.reply_text("❌ Usage: `/remove_premium <group_id>`")
            return
            
        group_id = int(message.command[1])
        await remove_premium(group_id)
        await message.reply_text(f"❌ Premium removed for `{group_id}`")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

@app.on_message(filters.command("premiumstats") & filters.user(Config.OWNER_ID))
async def premium_stats_cmd(client: Client, message: Message):
    count = 0
    all_grps = await get_all_groups()
    for g in all_grps:
        if await check_is_premium(g):
            count += 1
    await message.reply_text(f"💎 **Total Premium Groups:** {count}")

# ================ MAIN FILTER (STRONG FSUB, SPELLING, ABUSE, LINKS) ================
@app.on_message(filters.group & filters.text & ~filters.command(["start", "help", "settings", "addfsub", "stats", "ai", "broadcast", "request", "ban", "unban", "add_premium", "remove_premium", "premiumstats", "ping", "id"]))
async def group_message_filter(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # 1. HASHTAG REQUEST SUPPORT (#request)
    if message.text.lower().startswith("#request"):
        return await handle_request_logic(client, message, message.text.replace("#request", "").strip())

    if await is_admin(chat_id, user_id):
        return

    # 2. STRONG FORCE SUBSCRIBE CHECK
    # Har message par check karega agar FSUB on hai
    if await check_is_premium(chat_id): # Sirf premium groups ke liye strict check
        fsub_data = await get_force_sub(chat_id)
        if fsub_data:
            channel_id = fsub_data["channel_id"]
            try:
                await client.get_chat_member(channel_id, user_id)
            except UserNotParticipant:
                # User channel mein nahi hai -> Message delete karo
                try:
                    await message.delete()
                except:
                    pass
                
                # Warning bhejo
                try:
                    chat_info = await client.get_chat(channel_id)
                    link = chat_info.invite_link or f"https://t.me/{chat_info.username}"
                except:
                    link = "https://t.me/your_channel"

                msg = await message.reply_text(
                    f"⚠️ {message.from_user.mention}, Message karne ke liye Channel Join karna zaroori hai!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📢 Join Channel", url=link)],
                        [InlineKeyboardButton("✅ I Joined", callback_data=f"unmute_{user_id}")]
                    ])
                )
                await MovieBotUtils.auto_delete_message(client, msg, 60) # 1 min baad warning delete
                return # Code yahin rok do

    settings = await get_settings(chat_id)
    quality = MovieBotUtils.check_message_quality(message.text)

    # 3. LINK & ABUSE HANDLING
    if quality == "LINK":
        await message.delete()
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
                await message.reply_text(f"🚫 {message.from_user.mention} ko Mute kar diya gaya hai (Links not allowed)!")
                await reset_warnings(message.chat.id, message.from_user.id)
            except:
                pass
        else:
            msg = await message.reply_text(f"⚠️ {message.from_user.mention}, Links allowed nahi hai! (Warning {warn_count}/{limit})")
            await MovieBotUtils.auto_delete_message(client, msg, 10)
    
    elif quality == "ABUSE":
        await message.delete()
        warn_count = await add_warning(message.chat.id, message.from_user.id)
        limit = 3
        
        if warn_count >= limit:
            try:
                await client.ban_chat_member(message.chat.id, message.from_user.id)
                await message.reply_text(f"🚫 {message.from_user.mention} ko Ban kar diya gaya hai (Abusive Language)!")
                await reset_warnings(message.chat.id, message.from_user.id)
            except:
                pass
        else:
            msg = await message.reply_text(f"⚠️ {message.from_user.mention}, Gali mat do! (Warning {warn_count}/{limit})")
            await MovieBotUtils.auto_delete_message(client, msg, 10)

    # 4. SPELLING CHECK (Improved)
    elif settings.get("spelling_on", True) and quality == "JUNK":
        # Delete user message
        try:
            await message.delete()
        except:
            pass
            
        # Sahi naam dhoondho
        corrected_name = MovieBotUtils.extract_movie_name(message.text)
        sahi_text = f"{corrected_name} (Year)" if corrected_name else "Movie Name (Year)"

        msg = await message.reply_text(
            f"✨ **Spelling Check**\n\n"
            f"👤 User: {message.from_user.mention}\n"
            f"❌ **Galat:** {message.text}\n"
            f"✅ **Sahi:** `{sahi_text}`\n\n"
            f"Please sahi spelling likhein! 😊"
        )
        await MovieBotUtils.auto_delete_message(client, msg, 180)

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
        notification = await message.reply_text(
            f"🗑️ File Auto-Deleted\n"
            f"Files are automatically deleted after {delete_time} minutes.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu")]
            ])
        )
        await MovieBotUtils.auto_delete_message(client, notification)
    except:
        pass

# ================ FORCE SUBSCRIBE (Join Event) ================
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
        await client.get_chat_member(channel_id, user_id)
    except UserNotParticipant:
        # Mute User
        await client.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
        
        # Get Channel Link
        try:
            chat_info = await client.get_chat(channel_id)
            link = chat_info.invite_link or f"https://t.me/{chat_info.username}"
        except:
            link = "https://t.me/your_channel"

        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=link)],
            [InlineKeyboardButton("✅ I Joined", callback_data=f"unmute_{user_id}")]
        ])
        
        # Welcome with Photo (Premium Feel)
        welcome_txt = (
            f"👋 **Namaste {user.mention}!**\n\n"
            f"🔒 **Group Locked:** Message karne ke liye channel join karein.\n"
            f"👇 Niche diye gaye button par click karein."
        )
        
        # Agar user ki photo hai to photo bhejo, nahi to text
        try:
            if user.photo:
                await client.send_photo(chat_id, photo=user.photo.big_file_id, caption=welcome_txt, reply_markup=buttons)
            else:
                await client.send_message(chat_id, welcome_txt, reply_markup=buttons)
        except:
            await client.send_message(chat_id, welcome_txt, reply_markup=buttons)

# ================ AUTO ACCEPT JOIN REQUEST ================
@app.on_chat_join_request()
async def auto_approve_join(client: Client, request: ChatJoinRequest):
    chat_id = request.chat.id
    if await get_auto_accept(chat_id):
        try:
            await client.approve_chat_join_request(chat_id, request.from_user.id)
            await client.send_message(
                request.from_user.id, 
                f"✅ Request Approved for **{request.chat.title}**!\nEnjoy movies! 🍿"
            )
        except Exception as e:
            logger.error(f"Auto Accept Error: {e}")

# ================ CALLBACK QUERY HANDLERS ================
@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    """Handle all callback queries"""
    data = query.data
    chat_id = query.message.chat.id if query.message else query.from_user.id
    user_id = query.from_user.id
    
    if data == "premium_info":
        text = """💎 **Premium Plans** 💎

💸 **Pricing:**
• 1 Month: ₹100
• 2 Months: ₹200
• Lifetime: ₹500

🔥 **Benefits:**
1. 🔇 No Broadcast Messages (Ads Free)
2. 🔗 Force Subscribe Feature Access
3. ⚡ Priority Support

Buy karne ke liye owner se contact karein: @asbhai_bsr"""
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="start_back")]]))
        await query.answer()

    # --- AUTO ACCEPT SETUP FLOW ---
    elif data == "auto_accept_setup":
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 For Channel", callback_data="setup_channel_accept")],
            [InlineKeyboardButton("👥 For Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
            [InlineKeyboardButton("🔙 Back", callback_data="start_back")]
        ])
        await query.message.edit_text(
            "⚡ **Auto Accept Setup**\n\nAap kiske liye Auto Accept on karna chahte hain?",
            reply_markup=buttons
        )
    
    elif data == "setup_channel_accept":
        user_states[user_id] = "waiting_for_channel_id"
        await query.message.edit_text(
            "🔢 **Channel ID Bhejein**\n\nJiss Private Channel ki request accept karni hai, uski ID reply mein bhejein.\n(Example: -1001234567890)\n\n⚠️ *Note: Bot wahan Admin hona chahiye!*",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_state")]])
        )

    elif data == "cancel_state":
        if user_id in user_states:
            del user_states[user_id]
        await query.message.edit_text("❌ Cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="start_back")]]))

    elif data == "start_back":
        await start_command(client, query.message) # Wapas start menu

    # --- HELP MENU PAGINATION ---
    elif data.startswith("help_page_"):
        page = int(data.split("_")[2])
        
        if page == 1:
            text = "**🆘 Help Menu - Page 1 (Users)**\n\n• /start - Bot start karein\n• /request <movie> - Movie maangein\n• #request <movie> - Hashtag se maangein\n• /ai <query> - AI se poochein"
            btns = [[InlineKeyboardButton("Next ➡️", callback_data="help_page_2")]]
        elif page == 2:
            text = "**🆘 Help Menu - Page 2 (Admins)**\n\n• /settings - Auto Delete/Spelling on/off\n• /addfsub - Force Subscribe lagayein\n• /ban - User ko ban karein\n• Reply me /ban - Reply karke ban karein"
            btns = [
                [InlineKeyboardButton("⬅️ Back", callback_data="help_page_1"), InlineKeyboardButton("Next ➡️", callback_data="help_page_3")]
            ]
        elif page == 3:
            text = "**🆘 Help Menu - Page 3 (About)**\n\n🤖 **Movie Bot V2**\nCreated with ❤️ using Python.\nContact Owner: @asbhai_bsr for Premium."
            btns = [[InlineKeyboardButton("⬅️ Back", callback_data="help_page_2"), InlineKeyboardButton("🏠 Home", callback_data="start_back")]]
            
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btns))
    
    elif data == "help_main":
        await query.message.delete()
        await help_command(client, query.message)
        await query.answer()

    # Request Accept Logic
    elif data.startswith("req_accept_"):
        req_user_id = int(data.split("_")[2])
        try:
            await client.send_message(query.message.chat.id, f"✅ Movie Available! {query.from_user.mention} ne upload kar di hai. Check karo!")
            # User ko tag karo
            await client.send_message(query.message.chat.id, f"👤 <a href='tg://user?id={req_user_id}'>User</a>, aapki request complete ho gayi!")
            await query.message.delete()
        except:
            pass

    # Request Reject Logic
    elif data.startswith("req_reject_"):
        req_user_id = int(data.split("_")[2])
        await client.send_message(query.message.chat.id, f"❌ Movie Not Available / Reject by Admin.")
        await query.message.delete()

    # Settings Toggles
    elif data == "toggle_spelling":
        settings = await get_settings(chat_id)
        new_value = not settings.get("spelling_on", True)
        await update_settings(chat_id, "spelling_on", new_value)
        status = "✅ ON" if new_value else "❌ OFF"
        await query.answer(f"Spelling correction turned {status}")
        await refresh_settings_menu(client, query) # Helper function call
    
    elif data == "toggle_auto_delete":
        settings = await get_settings(chat_id)
        new_value = not settings.get("auto_delete_on", False)
        await update_settings(chat_id, "auto_delete_on", new_value)
        status = "✅ ON" if new_value else "❌ OFF"
        await query.answer(f"Auto delete turned {status}")
        await refresh_settings_menu(client, query)

    elif data == "toggle_auto_accept":
        current = await get_auto_accept(chat_id)
        await set_auto_accept(chat_id, not current)
        status = "✅ ON" if not current else "❌ OFF"
        await query.answer(f"Auto Accept: {status}")
        await refresh_settings_menu(client, query)
    
    elif data == "set_delete_time":
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("5 Minutes", callback_data="time_5")],
            [InlineKeyboardButton("10 Minutes", callback_data="time_10")],
            [InlineKeyboardButton("15 Minutes", callback_data="time_15")],
            [InlineKeyboardButton("30 Minutes", callback_data="time_30")],
            [InlineKeyboardButton("Permanent", callback_data="time_0")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_settings")]
        ])
        await query.message.edit_text("⏰ Select Auto-Delete Time:", reply_markup=buttons)
        await query.answer()
    
    elif data.startswith("time_"):
        minutes = int(data.split("_")[1])
        await update_settings(chat_id, "delete_time", minutes)
        time_text = f"{minutes} minutes" if minutes > 0 else "Permanent"
        await query.answer(f"Delete time set to {time_text}")
        await refresh_settings_menu(client, query)

    elif data == "clear_junk":
        junk_count = await clear_junk()
        await query.answer(f"🧹 Cleared {junk_count} junk entries!")
        await query.message.edit_text(
            f"✅ Junk Cleared!\n\n"
            f"Removed {junk_count} inactive entries from database.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh Stats", callback_data="refresh_stats")]
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
        
        stats_text = f"""📊 Bot Statistics

👥 Total Users: {users}
👥 Total Groups: {groups}
💎 Premium Groups: {premium_count}
⚡ Bot Uptime: 24/7
🔄 Last Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        await query.message.edit_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🧹 Clear Junk", callback_data="clear_junk")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]
            ])
        )
        await query.answer("✅ Stats refreshed!")
    
    # --- CONGRATULATIONS LOGIC ---
    elif data.startswith("unmute_"):
        target_id = int(data.split("_")[1])
        if user_id != target_id:
            return await query.answer("Ye button apke liye nahi hai!", show_alert=True)
            
        fsub_data = await get_force_sub(chat_id)
        if not fsub_data:
             return await query.message.delete()

        channel_id = fsub_data["channel_id"]
        try:
            # Check if user actually joined
            await client.get_chat_member(channel_id, user_id)
            
            # Unmute User
            await client.restrict_chat_member(
                chat_id, user_id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True
                )
            )
            
            # Delete "Join Channel" message
            await query.message.delete()
            
            # Send Congratulation Message
            congo_msg = await client.send_message(
                chat_id,
                f"🎉 **Congratulations {query.from_user.mention}!**\n\nAapne channel join kar liya hai. Ab aap is group mein message kar sakte hain. ✅"
            )
            # Delete congrats message after 1 minute
            await MovieBotUtils.auto_delete_message(client, congo_msg, 60)
            
        except UserNotParticipant:
            await query.answer("❌ Aapne abhi tak Channel Join nahi kiya! Pehle Join karein.", show_alert=True)
    
    elif data == "close_settings":
        await query.message.delete()
        await query.answer("Settings closed!")
    
    elif data == "back_settings" or data == "settings_menu":
        await refresh_settings_menu(client, query)

# Helper for updating settings menu
async def refresh_settings_menu(client, query):
    chat_id = query.message.chat.id
    settings = await get_settings(chat_id)
    is_prem = await check_is_premium(chat_id)
    auto_accept = await get_auto_accept(chat_id)
    
    prem_status = "💎 Active" if is_prem else "❌ Free"
    spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
    delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
    accept_status = "✅ ON" if auto_accept else "❌ OFF"
    delete_time = settings.get("delete_time", 0)
    time_text = f"{delete_time} min" if delete_time > 0 else "Permanent"
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Spelling: {spelling_status}", callback_data="toggle_spelling")],
        [InlineKeyboardButton(f"Auto Delete: {delete_status}", callback_data="toggle_auto_delete")],
        [InlineKeyboardButton(f"Auto Accept: {accept_status}", callback_data="toggle_auto_accept")],
        [InlineKeyboardButton(f"Time: {time_text}", callback_data="set_delete_time")],
        [InlineKeyboardButton(f"Premium: {prem_status}", callback_data="premium_info")],
        [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
    ])
    
    await query.message.edit_text(
        f"⚙️ Settings for **{query.message.chat.title}**",
        reply_markup=buttons
    )

# ================ GROUP EVENTS (CUTE WELCOME) ================
@app.on_message(filters.new_chat_members)
async def welcome_new_members(client: Client, message: Message):
    """Welcome new members with Photo"""
    for member in message.new_chat_members:
        if member.is_self:
            # Jab Bot khud add ho
            await add_group(message.chat.id, message.chat.title, message.chat.username)
            await message.reply_text("🎬 Thanks for adding me! Please make me Admin.")
        else:
            # Jab koi Naya User aaye
            settings = await get_settings(message.chat.id)
            if settings.get("welcome_enabled", True):
                
                welcome_caption = (
                    f"👋 **Welcome {member.mention}!**\n\n"
                    f"✨ **Group:** {message.chat.title}\n"
                    f"🆔 **User ID:** `{member.id}`\n"
                    f"📅 **Date:** {datetime.datetime.now().strftime('%d/%m/%Y')}\n\n"
                    f"🍿 Movies request karne ke liye `/request movie_name` use karein."
                )
                
                # Agar user ki photo hai to photo ke sath welcome
                try:
                    if member.photo:
                        msg = await client.send_photo(
                            message.chat.id,
                            photo=member.photo.big_file_id,
                            caption=welcome_caption
                        )
                    else:
                        # Photo nahi hai to text bhejo
                        msg = await message.reply_text(welcome_caption)
                        
                    # 5 min baad delete welcome msg
                    await MovieBotUtils.auto_delete_message(client, msg, 300)
                except:
                    pass

# ================ SETCOMMANDS COMMAND ================
@app.on_message(filters.command("setcommands") & filters.user(Config.OWNER_ID))
async def setcommands_command(client: Client, message: Message):
    """Set bot commands"""
    commands = [
        {"command": "start", "description": "Start the bot"},
        {"command": "help", "description": "Get help"},
        {"command": "settings", "description": "Group settings"},
        {"command": "request", "description": "Request a movie"},
        {"command": "stats", "description": "Bot statistics"},
        {"command": "ai", "description": "Ask AI about movies"},
        {"command": "addfsub", "description": "Set force subscribe (Premium)"},
        {"command": "ping", "description": "Check bot status"},
        {"command": "id", "description": "Get user/group ID"}
    ]
    
    try:
        await client.set_bot_commands(commands)
        await message.reply_text("✅ Bot commands set successfully!")
    except Exception as e:
        await message.reply_text(f"❌ Failed to set commands: {e}")

# ================ PING COMMAND ================
@app.on_message(filters.command("ping"))
async def ping_command(client: Client, message: Message):
    """Check if bot is alive"""
    start_time = time.time()
    msg = await message.reply_text("🏓 Pinging...")
    end_time = time.time()
    ping_time = round((end_time - start_time) * 1000, 2)
    await msg.edit_text(f"🏓 Pong!\n\n⏱ Response Time: {ping_time}ms\n🚀 Status: ✅ Alive\n☁️ Server: Koyeb Cloud")

# ================ ID COMMAND ================
@app.on_message(filters.command("id"))
async def id_command(client: Client, message: Message):
    """Get user/group ID"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = f"👤 Your ID: `{user_id}`\n"
    if message.chat.type != "private":
        text += f"👥 Group ID: `{chat_id}`\n"
        text += f"📝 Group Title: {message.chat.title}\n"
    await message.reply_text(text)

# ================ BAN/UNBAN COMMANDS (DB BAN) ================
@app.on_message(filters.command("ban") & filters.user(Config.OWNER_ID))
async def ban_command(client: Client, message: Message):
    """Ban a user from Bot"""
    if len(message.command) < 2:
        await message.reply_text("Usage: /ban <user_id>")
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
        await message.reply_text("Usage: /unban <user_id>")
        return
    try:
        user_id = int(message.command[1])
        await unban_user(user_id)
        await message.reply_text(f"✅ User `{user_id}` unbanned from Bot successfully!")
    except ValueError:
        await message.reply_text("❌ Invalid user ID!")

if __name__ == "__main__":
    print("🚀 Starting Movie Helper Bot...")
    try:
        app.run()
    except KeyboardInterrupt:
        print("⏹️ Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
        import traceback
        traceback.print_exc()
