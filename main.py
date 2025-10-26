import os
import asyncio
import logging
import json
import time
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
)
from pyrogram.enums import ChatMemberStatus
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image
import io
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURATION (KRIPYA IN VALUES KO BHARAIN) ---

# Agar aapko Pyrogram/MongoDB ki keys nahi pata, to ye default values ka upyog karein.
# Deployment ke samay inhe environment variables se load kiya jaata hai.

API_ID = int(os.environ.get("API_ID", "123456")) # Apni Telegram API ID yahan bharein
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH") # Apni Telegram API Hash yahan bharein
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN") # Apni Bot Token yahan bharein
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017") # Apni MongoDB Atlas URI
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", -1001234567890)) # Bot ke logs ke liye ek private channel ID
FORCE_SUBSCRIBE_ID = os.environ.get("FORCE_SUBSCRIBE_ID", "@asbhai_bsr") # Compulsory Join Channel ka Username

# Bot Owner ID (Aapki Telegram User ID)
OWNER_ID = int(os.environ.get("OWNER_ID", 123456789)) # Apni User ID yahan bharein

# --- 2. LOGGING aur DATABASE INITIALIZATION ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MongoDB Client (Async - Motor)
MONGO_CLIENT = AsyncIOMotorClient(MONGODB_URI)
DATABASE = MONGO_CLIENT.channel_protection_bot

# Collections
USERS_COL = DATABASE.users
CHANNELS_COL = DATABASE.channels
SCHEDULE_COL = DATABASE.schedules

# Pyrogram Client
app = Client(
    "ChannelProtectorBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- 3. UTILITY FUNCTIONS ---

# Floodwait handling ke liye (Pyrogram khud bhi handle karta hai, lekin manual control zaruri hai)
async def handle_flood_wait(error):
    """Floodwait error ko handle karne ke liye."""
    sleep_time = error.value + 5 # Thoda extra time
    logger.warning(f"FloodWait: {error.value} seconds. Sleeping for {sleep_time} seconds.")
    await asyncio.sleep(sleep_time)

async def check_user_membership(user_id):
    """Force Subscribe channel mein user ki membership check karta hai."""
    try:
        member = await app.get_chat_member(FORCE_SUBSCRIBE_ID, user_id)
        # Agar user member hai (status 'member', 'creator', ya 'administrator' hai)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception as e:
        logger.error(f"Membership check failed: {e}")
        return False # Default fail

def get_feature_buttons(features: dict):
    """Channel features control panel ke liye inline buttons banata hai."""
    btn_data = {
        "auto_accept": "Auto Accept Requests",
        "auto_reaction": "Auto Reaction",
        "user_left_ban": "Users Left & Ban",
        "media_obfuscation": "Media Obfuscation (Anti-Theft)"
    }
    
    keyboard = []
    for key, text in btn_data.items():
        status = "✅ ON" if features.get(key, False) else "❌ OFF"
        keyboard.append([
            InlineKeyboardButton(f"{text}: {status}", callback_data=f"toggle_{key}")
        ])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

async def log_new_user(user: Message.from_user):
    """Naye user ko database mein add karta hai aur log channel mein alert bhejta hai."""
    user_data = {
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "join_date": time.time(),
        "is_blocked": False
    }
    
    # Check karein agar user pehle se nahi hai
    if await USERS_COL.find_one({"user_id": user.id}) is None:
        await USERS_COL.insert_one(user_data)
        
        # Log Channel Alert
        log_message = (
            f"#newuseralater\n"
            f"Username: @{user.username or 'N/A'}\n"
            f"Name: {user.first_name}\n"
            f"ID: `{user.id}`"
        )
        try:
            await app.send_message(LOG_CHANNEL_ID, log_message)
        except Exception as e:
            logger.error(f"Log channel par message nahi bhej paya: {e}")

async def obfuscate_media(client: Client, message: Message):
    """Media ko halka sa modify karke re-upload karta hai."""
    try:
        # Step 1: Media file download karein
        file_path = await message.download()
        
        # Step 2: Media ko modify karein (Simple PIL modification for image)
        if message.photo:
            with Image.open(file_path) as img:
                img = img.convert("RGB")
                # Halka sa change: 1x1 pixel watermark (bottom-right corner)
                img.putpixel((img.width - 1, img.height - 1), (0, 0, 1)) # B-channel ko halka sa change kiya
                
                # Modified image ko memory mein save karein
                bio = io.BytesIO()
                bio.name = "obfuscated_image.png"
                img.save(bio, format='PNG')
                bio.seek(0)
                
                # Step 3: Naya media post karein
                await client.send_photo(
                    message.chat.id, 
                    photo=bio, 
                    caption=message.caption or "",
                    reply_to_message_id=message.id # Original message ke reply mein bhejte hain
                )
                
        # Video obfuscation complex hota hai, sirf basic re-upload/metadata change karenge (yahan skip kiya hai)
        # Agar video hai toh hum sirf caption change karke ya metadata change karke re-upload kar sakte hain.
        # Ya, abhi ke liye, video ke liye sirf Anti-Forward protection par depend karte hain.

        # Step 4: Purane message ko delete karein
        await message.delete()
        os.remove(file_path) # Downloaded file delete karein
        
    except Exception as e:
        logger.error(f"Media Obfuscation error: {e}")
        try:
            # Agar obfuscation fail ho toh original message ko delete kar dein
            await message.delete() 
        except:
            pass
        finally:
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)


# --- 4. MESSAGE HANDLERS (COMMANDS) ---

@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Bot ka shuruati (start) aur main menu command."""
    await log_new_user(message.from_user)
    
    # 1. Force Subscribe Check
    is_joined = await check_user_membership(message.from_user.id)
    
    if not is_joined:
        keyboard = [
            [InlineKeyboardButton("Official Channel Join Karein", url=f"https://t.me/{FORCE_SUBSCRIBE_ID[1:]}")],
            [InlineKeyboardButton("✅ Verify Karein / Try Again", callback_data="verify_join")]
        ]
        await message.reply_text(
            f"Namaste, {message.from_user.first_name}!\n\nBot ka istemaal karne ke liye, kripya pehle hamare official channel **{FORCE_SUBSCRIBE_ID}** ko join karein.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # 2. Main Menu
    await message.reply_text(
        f"**🛡️ Suraksha aur Suvidha Bot**\n\n"
        f"Aapka swagat hai, {message.from_user.first_name}! Main aapke Telegram channel ko protect karne aur uske management ko automate karne ke liye yahan hoon.\n\n"
        f"**Bot Features:**\n"
        f"1. Automatic Join Request Approval\n"
        f"2. Anti-Theft (Copyright Protection)\n"
        f"3. User Management (Left & Ban)\n\n",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ Connect Channel / Features", callback_data="channel_connect_menu")],
            [InlineKeyboardButton("❓ Help & Commands", callback_data="help_menu"),
             InlineKeyboardButton("📢 Bot Update Channel", url="https://t.me/asbhai_bsr")]
        ])
    )

@app.on_message(filters.command("help") & filters.private)
async def help_command(client: Client, message: Message):
    """User ke liye help command."""
    await message.reply_text(
        "**📚 Bot Commands Guide**\n\n"
        "**User Commands (Aapke liye):**\n"
        "1. `/start`: Main menu aur shuruati jankari.\n"
        "2. `/help`: Yeh commands guide.\n"
        "\n**Admin Commands (Sirf Bot Owner ke liye):**\n"
        "3. `/users`: Total users count aur user data file.\n"
        "4. `/channels`: Total connected channels count.\n"
        "5. `/broadcast [message]`: Sabhi users ko message bhejta hai.\n"
        "6. `/channel_brodcast [message]`: Sabhi connected channels par message post karta hai.\n"
        "7. `/clearjank`: Database se blocked users aur dead channels ko hataata hai.\n"
        "8. `/schedule [time]`: Channel post schedule karta hai (Example: `/schedule 1h`)\n"
    )

@app.on_message(filters.command("deletereport") & filters.private)
async def delete_report_command(client: Client, message: Message):
    """Admin ke liye Anti-Report/Deletion tool (reply mein)."""
    if message.chat.id != OWNER_ID:
        await message.reply_text("Yeh command sirf bot owner ke liye hai.")
        return

    if not message.reply_to_message:
        await message.reply_text("Kripya us message ka reply karein jise aap channel se delete karna chahte hain.")
        return

    try:
        # Message ke source channel ID ko nikalte hain
        source_channel_id = message.reply_to_message.forward_from_chat.id
        message_id_to_delete = message.reply_to_message.forward_from_message_id

        if not source_channel_id or not message_id_to_delete:
            await message.reply_text("Forwarded message ki jankari nahi mil payi.")
            return

        # Original channel se message delete karte hain
        await client.delete_messages(source_channel_id, message_id_to_delete)
        await message.reply_text(f"✅ Message ID `{message_id_to_delete}` Channel `{source_channel_id}` se delete kar diya gaya hai.")

    except Exception as e:
        await message.reply_text(f"❌ Deletion mein error: {e}")
        logger.error(f"Deletion error: {e}")

# --- 5. ADMIN UTILITY COMMANDS (Broadcast, Stats, Jank Cleaner) ---

@app.on_message(filters.command("users") & filters.user(OWNER_ID))
async def users_command(client: Client, message: Message):
    """Total users count aur data dump karta hai."""
    total_users = await USERS_COL.count_documents({})
    
    # Data Dump
    cursor = USERS_COL.find({})
    user_data_string = "user_id,username,first_name,join_date\n"
    async for doc in cursor:
        username = doc.get("username", "N/A")
        first_name = doc.get("first_name", "N/A").replace(',', ' ')
        join_date = datetime.fromtimestamp(doc.get("join_date", 0)).strftime('%Y-%m-%d %H:%M:%S')
        user_data_string += f"{doc['user_id']},{username},{first_name},{join_date}\n"
        
    bio = io.BytesIO(user_data_string.encode('utf-8'))
    bio.name = "users_data.txt"

    await message.reply_document(
        bio,
        caption=f"**Total Users:** {total_users}\n\nUser data file mein uplabdh hai."
    )

@app.on_message(filters.command("channels") & filters.user(OWNER_ID))
async def channels_command(client: Client, message: Message):
    """Total connected channels count."""
    total_channels = await CHANNELS_COL.count_documents({})
    await message.reply_text(f"**Total Connected Channels:** {total_channels}")

@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_command(client: Client, message: Message):
    """Sabhi users ko message broadcast karta hai."""
    if not message.reply_to_message:
        await message.reply_text("Kripya us message ka reply karein jise aap broadcast karna chahte hain.")
        return

    sent_count = 0
    blocked_count = 0
    total_users = await USERS_COL.count_documents({})
    
    await message.reply_text(f"Broadcast shuru kar raha hoon... {total_users} users ko.")
    
    cursor = USERS_COL.find({"is_blocked": False})
    
    async for doc in cursor:
        user_id = doc['user_id']
        try:
            await message.reply_to_message.copy(user_id)
            sent_count += 1
            # FloodWait se bachne ke liye chota sa sleep
            await asyncio.sleep(0.05) 
        except Exception as e:
            if 'USER_BLOCKED_BOT' in str(e) or 'ChatIdInvalid' in str(e):
                await USERS_COL.update_one({"user_id": user_id}, {"$set": {"is_blocked": True}})
                blocked_count += 1
                log_message = (
                    f"#blockalert\n"
                    f"Type: User Blocked\n"
                    f"ID: `{user_id}`"
                )
                try:
                    await app.send_message(LOG_CHANNEL_ID, log_message)
                except:
                    pass
            elif 'FloodWait' in str(e):
                await handle_flood_wait(e)
            else:
                logger.error(f"Broadcast error to user {user_id}: {e}")
                
    await message.reply_text(
        f"✅ Broadcast Poora Hua!\n"
        f"🌐 Sent to: {sent_count}\n"
        f"🚫 Blocked/Failed: {blocked_count}"
    )

@app.on_message(filters.command("clearjank") & filters.user(OWNER_ID))
async def clear_jank_command(client: Client, message: Message):
    """Blocked users aur dead channels ko database se hataata hai."""
    await message.reply_text("Jank cleaning shuru ho rahi hai... Kripya intezaar karein.")
    
    # 1. User cleaning
    user_deleted_count = 0
    user_cursor = USERS_COL.find({"is_blocked": False})
    
    async for doc in user_cursor:
        user_id = doc['user_id']
        try:
            # Check karne ke liye ek chota message bhejte hain
            await app.send_message(user_id, "Checking connectivity...", disable_notification=True)
            await asyncio.sleep(0.01) # Minimum sleep
        except Exception as e:
            if 'USER_BLOCKED_BOT' in str(e) or 'ChatIdInvalid' in str(e):
                await USERS_COL.delete_one({"user_id": user_id})
                user_deleted_count += 1
                log_message = f"#jankdeleted\nType: User Blocked\nID: `{user_id}`"
                try: await app.send_message(LOG_CHANNEL_ID, log_message)
                except: pass
            elif 'FloodWait' in str(e):
                await handle_flood_wait(e)
            
    # 2. Channel cleaning
    channel_deleted_count = 0
    channel_cursor = CHANNELS_COL.find({})
    
    async for doc in channel_cursor:
        channel_id = doc['channel_id']
        try:
            # Bot ka status check karte hain
            member = await app.get_chat_member(channel_id, client.get_me().id)
            if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                raise Exception("Bot is not admin anymore")
            await asyncio.sleep(0.01) # Minimum sleep
        except Exception as e:
            await CHANNELS_COL.delete_one({"channel_id": channel_id})
            channel_deleted_count += 1
            log_message = f"#jankdeleted\nType: Channel Removed\nID: `{channel_id}`\nReason: Bot removed/Not Admin"
            try: await app.send_message(LOG_CHANNEL_ID, log_message)
            except: pass
            
    await message.reply_text(
        f"✅ Jank Cleaning Poori Hui!\n"
        f"🧹 Deleted {user_deleted_count} Blocked Users.\n"
        f"🗑️ Deleted {channel_deleted_count} Dead Channels."
    )


# --- 6. CALLBACK QUERY HANDLERS (BUTTONS) ---

@app.on_callback_query(filters.regex("^verify_join$"))
async def verify_join_callback(client: Client, callback_query: CallbackQuery):
    """Verify button par click hone par membership check karta hai."""
    await callback_query.answer("Membership check ho rahi hai...")
    
    is_joined = await check_user_membership(callback_query.from_user.id)
    
    if is_joined:
        await callback_query.message.edit_text(
            f"✅ Safalta! Ab aap bot ka istemaal kar sakte hain. Dohbara command /start chalaaiye.",
            reply_markup=None
        )
        # Main menu dikhane ke liye /start ko emulate karte hain
        await start_command(client, callback_query.message)
    else:
        await callback_query.answer("❌ Aapne abhi tak channel join nahi kiya hai ya server par update hone mein deri ho rahi hai. Kripya phir se koshish karein.", show_alert=True)

@app.on_callback_query(filters.regex("^channel_connect_menu$"))
async def channel_connect_menu(client: Client, callback_query: CallbackQuery):
    """Channel connection shuru karne ka menu."""
    await callback_query.answer()
    
    # Check if user already has a connected channel (Simple version: one channel per user)
    connected_channel = await CHANNELS_COL.find_one({"owner_id": callback_query.from_user.id})

    if connected_channel:
        channel_title = connected_channel.get('title', 'N/A')
        await callback_query.message.edit_text(
            f"**⚙️ Connected Channel Features**\n\n"
            f"Aapka channel **{channel_title}** ({connected_channel['channel_id']}) pehle se connected hai. Yahan se features ON/OFF karein.",
            reply_markup=get_feature_buttons(connected_channel.get('features', {}))
        )
    else:
        await callback_query.message.edit_text(
            "**🔗 Channel Connect Karein**\n\n"
            "**Kripya yeh steps follow karein:**\n"
            "1. Bot ko apne channel mein **Administrator** banaayein.\n"
            "2. Permissions mein 'Can Manage Channels', 'Can Invite Users', aur 'Can Delete Messages' dein.\n"
            "3. **Is message ko reply** karke apne channel ka **ID** (`-100...`) ya **Username** (`@example`) bhejien.\n\n"
            "**Abort karne ke liye /start type karein.**"
        )
        # Next message handler ko tayyar karte hain (state management simple rakhenge)
        # Note: Pyrogram mein proper state management complex hai, yahan hum reply_to_message ID par depend karenge.
        
@app.on_callback_query(filters.regex("^toggle_"))
async def toggle_feature_callback(client: Client, callback_query: CallbackQuery):
    """Feature ON/OFF karta hai."""
    await callback_query.answer()
    
    feature_key = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id
    
    channel_doc = await CHANNELS_COL.find_one({"owner_id": user_id})
    if not channel_doc:
        await callback_query.message.edit_text("❌ Aapka koi channel connected nahi hai. Kripya pehle channel connect karein.")
        return

    current_state = channel_doc.get("features", {}).get(feature_key, False)
    new_state = not current_state
    
    # DB update
    await CHANNELS_COL.update_one(
        {"owner_id": user_id},
        {"$set": {f"features.{feature_key}": new_state}}
    )
    
    # UI update
    updated_doc = await CHANNELS_COL.find_one({"owner_id": user_id})
    
    await callback_query.message.edit_reply_markup(
        get_feature_buttons(updated_doc.get('features', {}))
    )
    await callback_query.answer(f"Feature '{feature_key.replace('_', ' ').title()}' {('ON' if new_state else 'OFF')} ho gaya.", show_alert=True)

# --- 7. CHANNEL CONNECTION HANDLER (REPLY LOGIC) ---

@app.on_message(filters.private & filters.text & filters.reply)
async def channel_id_reply_handler(client: Client, message: Message):
    """Channel ID ya username ke reply ko handle karta hai."""
    
    if message.reply_to_message.text and "**Is message ko reply** karke apne channel ka" in message.reply_to_message.text:
        channel_input = message.text.strip()
        user_id = message.from_user.id
        
        await message.reply_text("Channel ki jaankari check ho rahi hai...")
        
        try:
            # 1. Channel ki jaankari (ID/Username) se fetch karte hain
            chat = await client.get_chat(channel_input)
            channel_id = chat.id
            channel_title = chat.title
            
            if chat.type not in ["channel", "supergroup"]:
                await message.reply_text("❌ Kripya channel ya supergroup ka ID/Username dein.")
                return
            
            # 2. Bot ke admin status ko check karte hain
            me_member = await client.get_chat_member(channel_id, client.get_me().id)
            
            if me_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                await message.reply_text("❌ Bot ko pehle channel mein **Admin** banaayein.")
                return

            # Check for required permissions
            required_permissions = [me_member.can_manage_chat, me_member.can_invite_users, me_member.can_delete_messages]
            if not all(required_permissions):
                 await message.reply_text("❌ Bot ko 'Manage Chat', 'Invite Users', aur 'Delete Messages' ki permissions dein.")
                 return

            # 3. Channel ko DB mein save/update karte hain
            channel_doc = {
                "channel_id": channel_id,
                "title": channel_title,
                "owner_id": user_id,
                "features": {
                    "auto_accept": False,
                    "auto_reaction": False,
                    "user_left_ban": False,
                    "media_obfuscation": False
                }
            }
            
            await CHANNELS_COL.update_one(
                {"channel_id": channel_id},
                {"$set": channel_doc},
                upsert=True
            )
            
            # 4. Success message aur log
            await message.reply_to_message.delete()
            await message.reply_text(
                f"✅ **{channel_title}** successfully connected!\n\n"
                f"Ab aap features control panel ka istemaal kar sakte hain.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚙️ Features Control Panel", callback_data="channel_connect_menu")]
                ])
            )
            
            # Log Channel Alert
            log_message = (
                f"#newchannelalert\n"
                f"Channel: {channel_title} (`{channel_id}`)\n"
                f"Added by: {message.from_user.first_name} (`{user_id}`)"
            )
            await app.send_message(LOG_CHANNEL_ID, log_message)

        except Exception as e:
            await message.reply_text(f"❌ Connection Fail Hua: Channel ID/Username sahi nahi hai ya bot admin nahi hai. Error: {e}")
            logger.error(f"Channel connection failed: {e}")


# --- 8. CHANNEL EVENT HANDLERS (AUTOMATION) ---

@app.on_chat_join_request(filters.channel)
async def handle_join_request(client: Client, join_request):
    """Auto Accept Requests feature ko handle karta hai."""
    channel_id = join_request.chat.id
    
    channel_doc = await CHANNELS_COL.find_one({"channel_id": channel_id})
    
    if channel_doc and channel_doc.get("features", {}).get("auto_accept", False):
        try:
            await client.approve_chat_join_request(channel_id, join_request.from_user.id)
            logger.info(f"Join request for {join_request.from_user.id} in {channel_id} approved.")
        except Exception as e:
            logger.error(f"Auto-accept failed in {channel_id}: {e}")

@app.on_chat_member_updated(filters.channel)
async def handle_member_update(client: Client, member_update):
    """Users Left & Ban feature ko handle karta hai."""
    channel_id = member_update.chat.id
    
    channel_doc = await CHANNELS_COL.find_one({"channel_id": channel_id})

    if channel_doc and channel_doc.get("features", {}).get("user_left_ban", False):
        # User Left and Ban Logic
        old_status = member_update.old_chat_member.status if member_update.old_chat_member else None
        new_status = member_update.new_chat_member.status
        user_id = member_update.from_user.id

        # Agar user left hua hai
        if old_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR] and new_status == ChatMemberStatus.LEFT:
            try:
                # User ko kick (permanent ban) karte hain
                await client.ban_chat_member(channel_id, user_id)
                logger.info(f"User {user_id} left {channel_id} and was banned.")
            except Exception as e:
                logger.error(f"Failed to ban user {user_id} in {channel_id}: {e}")


@app.on_message(filters.channel & filters.media)
async def handle_new_post(client: Client, message: Message):
    """Auto Reaction aur Media Obfuscation ko handle karta hai."""
    channel_id = message.chat.id
    
    channel_doc = await CHANNELS_COL.find_one({"channel_id": channel_id})
    
    if channel_doc:
        # 1. Media Obfuscation (Anti-Theft)
        if channel_doc.get("features", {}).get("media_obfuscation", False) and (message.photo or message.video):
            # Obfuscation sirf photo par implement kiya gaya hai (Video bahut complex hota hai)
            await obfuscate_media(client, message)
            
        # 2. Auto Reaction
        elif channel_doc.get("features", {}).get("auto_reaction", False):
            try:
                # Pyrogram v2 mein send_reaction/set_reaction use hota hai. 
                # Hum yahan default 'fire' reaction bhej rahe hain.
                await client.send_reaction(channel_id, message.id, "🔥")
            except Exception as e:
                logger.error(f"Auto-reaction failed in {channel_id}: {e}")
                
        # 3. Anti-Forward Protection (Har naye channel post ke saath ensure karte hain)
        try:
            # Permissions ko set karte hain taki Forwarding band ho
            await client.set_chat_permissions(
                channel_id,
                permissions=None, # Saare permissions default rakhe
                slow_mode_delay=0,
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
                can_manage_topics=False,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True
            )
            # Forward protection ek channel setting hai jo `set_chat_member` se control nahi hoti. 
            # Aise mein, hum Pyrogram ke `edit_channel_info` ko use karke content protection on kar sakte hain.
            await client.set_chat_protected_content(channel_id, enabled=True)
            logger.info(f"Anti-forward protection ensured for {channel_id}.")
        except Exception as e:
            logger.warning(f"Failed to set Anti-Forward protection for {channel_id}: {e}")

# --- 9. SCHEDULER (BACKGROUND TASK) ---

async def scheduler_task():
    """Background task jo scheduled posts ko check aur post karta hai."""
    while True:
        now = time.time()
        
        # Check karein agar koi post schedule time se guzar chuka hai
        cursor = SCHEDULE_COL.find({"schedule_time": {"$lte": now}})
        
        async for doc in cursor:
            try:
                # Post message
                await app.copy_message(
                    chat_id=doc['channel_id'],
                    from_chat_id=OWNER_ID, # Jahan se message copy hua tha
                    message_id=doc['message_id']
                )
                logger.info(f"Scheduled post delivered to {doc['channel_id']}.")
            except Exception as e:
                logger.error(f"Scheduled post delivery failed for {doc['channel_id']}: {e}")
            finally:
                # DB se scheduled entry ko hata dein
                await SCHEDULE_COL.delete_one({"_id": doc['_id']})
                
        # Har 60 second mein check karein
        await asyncio.sleep(60)

@app.on_message(filters.command("schedule") & filters.user(OWNER_ID))
async def schedule_post_command(client: Client, message: Message):
    """Admin ke liye channel post schedule karne ka command."""
    if not message.reply_to_message:
        await message.reply_text("Kripya us post ka reply karein jise aap schedule karna chahte hain.")
        return
        
    try:
        # Time nikalte hain (Example: /schedule 1h, /schedule 30m)
        time_str = message.text.split(" ", 1)[1].strip().lower()
        match = re.match(r"(\d+)([hmd])", time_str)
        if not match:
            await message.reply_text("❌ Galat time format. Example: `/schedule 1h` (1 hour) ya `/schedule 30m` (30 minutes).")
            return

        amount = int(match.group(1))
        unit = match.group(2)
        
        if unit == 'h':
            delay = amount * 3600
        elif unit == 'm':
            delay = amount * 60
        elif unit == 'd':
            delay = amount * 86400
        else:
            await message.reply_text("❌ Invalid time unit.")
            return

        schedule_time = time.time() + delay
        target_channel_id = int(message.text.split(" ", 2)[2].strip()) if len(message.text.split(" ")) > 2 else message.chat.id # Target channel (agar specify ho)
        
        # Schedule data DB mein store karte hain
        await SCHEDULE_COL.insert_one({
            "message_id": message.reply_to_message.id,
            "channel_id": target_channel_id,
            "schedule_time": schedule_time,
            "owner_id": OWNER_ID,
            "created_at": time.time()
        })
        
        scheduled_date = datetime.fromtimestamp(schedule_time).strftime('%Y-%m-%d %H:%M:%S')
        await message.reply_text(f"✅ Post **{target_channel_id}** channel mein **{scheduled_date}** ko schedule kar diya gaya hai.")

    except IndexError:
        await message.reply_text("Kripya schedule time aur channel ID/Username dein. Example: `/schedule 1h -1001234567890`")
    except Exception as e:
        await message.reply_text(f"❌ Scheduling error: {e}")
        logger.error(f"Scheduling error: {e}")


# --- 10. MAIN BOT EXECUTION ---

async def main():
    """Bot ko shuru karta hai aur background tasks chalata hai."""
    try:
        await app.start()
        logger.info("Bot started successfully!")
        
        # Background tasks (Scheduler) shuru karte hain
        await asyncio.gather(
            scheduler_task(),
            # Future mein aur background tasks yahan add kiye ja sakte hain
        )
        
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")

if __name__ == "__main__":
    # Python 3.7+ mein, asyncio.run() ka upyog karte hain
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
