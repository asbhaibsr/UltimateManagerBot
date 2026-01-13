#  bot.py

import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, ChatMemberUpdated, ChatJoinRequest
)
from pyrogram.errors import FloodWait, UserNotParticipant
from config import Config
from database import *
from utils import MovieBotUtils
from flask import Flask, jsonify
import datetime
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Pyrogram Client
app = Client(
    "movie_helper_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    in_memory=True
)

# Flask app for Koyeb health check
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Movie Helper Bot</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 50px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            .container {
                background: rgba(255,255,255,0.1);
                padding: 30px;
                border-radius: 15px;
                backdrop-filter: blur(10px);
                max-width: 600px;
                margin: 0 auto;
            }
            h1 {
                font-size: 2.5em;
                margin-bottom: 20px;
            }
            .status {
                background: green;
                color: white;
                padding: 10px 20px;
                border-radius: 25px;
                display: inline-block;
                margin: 20px 0;
            }
            .info {
                text-align: left;
                margin-top: 20px;
                background: rgba(255,255,255,0.1);
                padding: 15px;
                border-radius: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎬 Movie Helper Bot</h1>
            <div class="status">✅ Bot is Running</div>
            <p>This bot helps with movie recommendations, spelling correction, and more!</p>
            
            <div class="info">
                <h3>📊 Bot Status:</h3>
                <p>• Telegram Bot: <strong>Connected</strong></p>
                <p>• Server: <strong>Active</strong></p>
                <p>• Health Check: <strong>Passing</strong></p>
                <p>• Last Updated: {}</p>
            </div>
            
            <p style="margin-top: 30px;">
                <a href="/health" style="color: #fff; text-decoration: underline;">Check API Health</a> | 
                <a href="https://t.me/{}" style="color: #fff; text-decoration: underline;">Contact Bot</a>
            </p>
        </div>
    </body>
    </html>
    """.format(
        datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        Config.BOT_USERNAME
    )

@flask_app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "service": "movie_helper_bot",
        "timestamp": str(datetime.datetime.now()),
        "telegram_bot": "running",
        "version": "2.0.0"
    })

@flask_app.route('/ping')
def ping():
    return "pong"

# ================ COMMAND HANDLERS ================

@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Handle /start command"""
    user = message.from_user
    await add_user(user.id, user.username, user.first_name)
    
    welcome_text = f"""🎬 **Welcome {user.first_name}!** 🎬

I'm your Movie Helper Bot! 🤖

**Features:**
✅ Spelling Correction in Groups
✅ Auto Delete Files
✅ AI Movie Recommendations
✅ Force Subscribe Channel
✅ Broadcast Messages
✅ Beautiful UI with Buttons

**Admin Commands:**
• /settings - Group settings
• /stats - Bot statistics
• /ai [query] - Ask AI anything
• /addfsub - Set force subscribe
• /broadcast - Broadcast to users
• /grp_broadcast - Broadcast to groups

Add me to your groups and make me admin! 😊"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/asbhai_bsr")],
        [InlineKeyboardButton("🤖 Help", callback_data="help")]
    ])
    
    await message.reply_text(welcome_text, reply_markup=buttons)
    await MovieBotUtils.auto_delete_message(client, message)

@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    """Handle /help command"""
    help_text = """🆘 **Help Guide** 🆘

**For Group Admins:**
1. Add me to your group
2. Make me admin with delete message permission
3. Use /settings to configure

**Group Features:**
• **Spelling Correction:** Auto-corrects movie names
• **Auto Delete Files:** Remove unwanted media
• **Force Subscribe:** Force users to join channel
• **AI Chat:** Ask about movies/series

**Commands List:**
• /start - Start the bot
• /help - This message
• /settings - Group settings (admin only)
• /stats - Bot statistics
• /ai [question] - Ask AI
• /setcommands - Set bot commands

**Owner Commands:**
• /broadcast - Broadcast to users
• /grp_broadcast - Broadcast to groups
• /ban [user_id] - Ban user
• /unban [user_id] - Unban user

Need help? Contact @asbhai_bsr 😊"""
    
    await message.reply_text(help_text)
    await MovieBotUtils.auto_delete_message(client, message)

@app.on_message(filters.command("settings") & filters.group)
async def settings_command(client: Client, message: Message):
    """Group settings menu"""
    # Check if user is admin
    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in ["creator", "administrator"]:
            await message.reply_text("❌ Only admins can change settings!")
            return
    except:
        await message.reply_text("❌ Couldn't verify admin status!")
        return
    
    settings = await get_settings(message.chat.id)
    
    # Create settings buttons
    spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
    delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
    delete_time = settings.get("delete_time", 0)
    time_text = f"{delete_time} min" if delete_time > 0 else "Permanent"
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Spelling Correction: {spelling_status}", callback_data="toggle_spelling")],
        [InlineKeyboardButton(f"Auto Delete Files: {delete_status}", callback_data="toggle_auto_delete")],
        [InlineKeyboardButton(f"Delete Time: {time_text}", callback_data="set_delete_time")],
        [InlineKeyboardButton("🔗 Force Subscribe", callback_data="force_sub_menu")],
        [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
    ])
    
    await message.reply_text(
        f"⚙️ **Settings for {message.chat.title}**\n\n"
        "Configure your group settings below:",
        reply_markup=buttons
    )

@app.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats_command(client: Client, message: Message):
    """Bot statistics"""
    users = await get_user_count()
    groups = await get_group_count()
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Clear Junk", callback_data="clear_junk")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]
    ])
    
    stats_text = f"""📊 **Bot Statistics**

👥 **Total Users:** {users}
👥 **Total Groups:** {groups}
⚡ **Bot Uptime:** 24/7
🔄 **Last Updated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Database Status:** ✅ Connected
**AI Status:** ✅ Active
**Broadcast System:** ✅ Ready"""
    
    await message.reply_text(stats_text, reply_markup=buttons)

@app.on_message(filters.command("ai"))
async def ai_command(client: Client, message: Message):
    """AI chat feature"""
    if len(message.command) < 2:
        await message.reply_text("Usage: `/ai your question`\nExample: `/ai Tell me about Inception movie`")
        return
    
    query = ' '.join(message.command[1:])
    waiting_msg = await message.reply_text("🤔 Thinking... Please wait!")
    
    response = await MovieBotUtils.get_ai_response(query)
    
    await waiting_msg.delete()
    await message.reply_text(response)
    await MovieBotUtils.auto_delete_message(client, message)

@app.on_message(filters.command(["broadcast", "grp_broadcast"]) & filters.user(Config.OWNER_ID))
async def broadcast_command(client: Client, message: Message):
    """Broadcast messages to users/groups"""
    if not message.reply_to_message:
        await message.reply_text("❌ Please reply to a message to broadcast!")
        return
    
    broadcast_type = "users" if "broadcast" in message.command else "groups"
    target_ids = await get_all_users() if broadcast_type == "users" else await get_all_groups()
    
    if not target_ids:
        await message.reply_text(f"❌ No {broadcast_type} found!")
        return
    
    progress_msg = await message.reply_text(f"📤 Broadcasting to {len(target_ids)} {broadcast_type}...\nProgress: 0/{len(target_ids)}")
    
    success = 0
    failed = 0
    
    for idx, target_id in enumerate(target_ids, 1):
        try:
            await message.reply_to_message.copy(target_id)
            success += 1
            if idx % 10 == 0:  # Update progress every 10 sends
                await progress_msg.edit_text(
                    f"📤 Broadcasting to {len(target_ids)} {broadcast_type}...\n"
                    f"Progress: {idx}/{len(target_ids)}\n"
                    f"✅ Success: {success} | ❌ Failed: {failed}"
                )
            await asyncio.sleep(Config.BROADCAST_DELAY)
        except Exception as e:
            failed += 1
            logger.error(f"Failed to send to {target_id}: {e}")
    
    await progress_msg.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"📊 **Results:**\n"
        f"• Total {broadcast_type.capitalize()}: {len(target_ids)}\n"
        f"• ✅ Successful: {success}\n"
        f"• ❌ Failed: {failed}\n"
        f"• 📈 Success Rate: {(success/len(target_ids)*100):.1f}%"
    )

@app.on_message(filters.command("addfsub") & filters.group)
async def addfsub_command(client: Client, message: Message):
    """Set force subscribe channel"""
    if not message.reply_to_message or not message.reply_to_message.forward_from_chat:
        await message.reply_text("❌ Please forward a message from the channel and reply with `/addfsub`")
        return
    
    channel = message.reply_to_message.forward_from_chat
    if channel.type != "channel":
        await message.reply_text("❌ Please forward from a channel, not a group!")
        return
    
    try:
        # Check if bot is admin in channel
        await client.get_chat_member(channel.id, (await client.get_me()).id)
    except UserNotParticipant:
        await message.reply_text("❌ Make me admin in the channel first!")
        return
    
    await set_force_sub(message.chat.id, channel.id)
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{channel.username}")],
        [InlineKeyboardButton("✅ Test Force Sub", callback_data="test_fsub")]
    ])
    
    await message.reply_text(
        f"✅ **Force Subscribe Enabled!**\n\n"
        f"**Channel:** {channel.title}\n"
        f"New users will need to join this channel before chatting.",
        reply_markup=buttons
    )

@app.on_message(filters.command("setcommands"))
async def setcommands_command(client: Client, message: Message):
    """Set bot commands"""
    commands = [
        {"command": "start", "description": "Start the bot"},
        {"command": "help", "description": "Get help"},
        {"command": "settings", "description": "Group settings"},
        {"command": "stats", "description": "Bot statistics"},
        {"command": "ai", "description": "Ask AI about movies"},
        {"command": "addfsub", "description": "Set force subscribe"}
    ]
    
    await client.set_bot_commands(commands)
    await message.reply_text("✅ Bot commands set successfully!")

# ================ SPELLING CORRECTION ================

@app.on_message(filters.group & filters.text)
async def spelling_correction(client: Client, message: Message):
    """Auto correct spelling for movie names"""
    settings = await get_settings(message.chat.id)
    if not settings.get("spelling_on", True):
        return
    
    text = message.text.lower()
    extra_words = ["dedo", "chahiye", "link", "download", "movie", "film", 
                  "ye movie", "dedijye", "do", "de do", "chaiye", "chaiyea"]
    
    # Check if message contains movie name with extra words
    movie_name = MovieBotUtils.extract_movie_name(text)
    if movie_name and any(word in text for word in extra_words):
        try:
            await client.delete_messages(message.chat.id, message.id)
            
            correction_msg = await message.reply_text(
                f"🚫 **Oye {message.from_user.first_name}!**\n\n"
                f"Movie/series name ke aage faltu words mat likho!\n"
                f"✅ **Correct Format:** `{movie_name} 2023` ya `{movie_name} S01 E01`\n\n"
                f"Sirf naam likho, baaki main samajh jaungi! 😊",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("😊 OK", callback_data="ok_correction")]
                ])
            )
            
            await MovieBotUtils.auto_delete_message(client, correction_msg)
        except:
            pass

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
            f"🗑️ **File Auto-Deleted**\n"
            f"Files are automatically deleted after {delete_time} minutes in this group.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu")]
            ])
        )
        await MovieBotUtils.auto_delete_message(client, notification)
    except:
        pass

# ================ FORCE SUBSCRIBE ================

@app.on_chat_member_updated()
async def handle_new_member(client: Client, update: ChatMemberUpdated):
    """Handle new members for force subscribe"""
    if update.new_chat_member and update.new_chat_member.status == "member":
        chat_id = update.chat.id
        user_id = update.new_chat_member.user.id
        
        # Get force sub channel
        force_sub = await get_force_sub(chat_id)
        if not force_sub:
            return
        
        channel_id = force_sub.get("channel_id")
        if not channel_id:
            return
        
        try:
            # Check if user is in channel
            await client.get_chat_member(channel_id, user_id)
            return  # User is subscribed
        except UserNotParticipant:
            # User not in channel, restrict them
            await client.restrict_chat_member(
                chat_id,
                user_id,
                permissions=dict(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False
                )
            )
            
            # Get channel info
            channel = await client.get_chat(channel_id)
            channel_link = f"https://t.me/{channel.username}" if channel.username else ""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url=channel_link)],
                [InlineKeyboardButton("✅ I've Joined", callback_data=f"verify_{user_id}")]
            ])
            
            welcome_msg = await client.send_message(
                chat_id,
                f"👋 **Welcome {update.new_chat_member.user.first_name}!**\n\n"
                f"📢 Please join our channel to continue chatting:\n"
                f"**Channel:** {channel.title}\n\n"
                f"After joining, click the 'I've Joined' button below!",
                reply_markup=buttons
            )
            
            # Store message ID for later deletion
            await asyncio.sleep(300)  # Delete after 5 minutes
            try:
                await welcome_msg.delete()
            except:
                pass

# ================ CALLBACK QUERY HANDLERS ================

@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    """Handle all callback queries"""
    data = query.data
    chat_id = query.message.chat.id if query.message else query.from_user.id
    
    if data == "help":
        await help_command(client, query.message)
        await query.answer()
    
    elif data == "toggle_spelling":
        settings = await get_settings(chat_id)
        new_value = not settings.get("spelling_on", True)
        await update_settings(chat_id, "spelling_on", new_value)
        
        status = "✅ ON" if new_value else "❌ OFF"
        await query.message.edit_reply_markup(
            InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Spelling Correction: {status}", callback_data="toggle_spelling")],
                [InlineKeyboardButton(f"Auto Delete Files: {'✅ ON' if settings.get('auto_delete_on', False) else '❌ OFF'}", callback_data="toggle_auto_delete")],
                [InlineKeyboardButton(f"Delete Time: {settings.get('delete_time', 0)} min", callback_data="set_delete_time")],
                [InlineKeyboardButton("🔗 Force Subscribe", callback_data="force_sub_menu")],
                [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
            ])
        )
        await query.answer(f"Spelling correction turned {status}")
    
    elif data == "toggle_auto_delete":
        settings = await get_settings(chat_id)
        new_value = not settings.get("auto_delete_on", False)
        await update_settings(chat_id, "auto_delete_on", new_value)
        
        status = "✅ ON" if new_value else "❌ OFF"
        await query.message.edit_reply_markup(
            InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Spelling Correction: {'✅ ON' if settings.get('spelling_on', True) else '❌ OFF'}", callback_data="toggle_spelling")],
                [InlineKeyboardButton(f"Auto Delete Files: {status}", callback_data="toggle_auto_delete")],
                [InlineKeyboardButton(f"Delete Time: {settings.get('delete_time', 0)} min", callback_data="set_delete_time")],
                [InlineKeyboardButton("🔗 Force Subscribe", callback_data="force_sub_menu")],
                [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
            ])
        )
        await query.answer(f"Auto delete turned {status}")
    
    elif data == "set_delete_time":
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("5 Minutes", callback_data="time_5")],
            [InlineKeyboardButton("10 Minutes", callback_data="time_10")],
            [InlineKeyboardButton("15 Minutes", callback_data="time_15")],
            [InlineKeyboardButton("Permanent", callback_data="time_0")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_settings")]
        ])
        await query.message.edit_text("⏰ **Select Auto-Delete Time:**", reply_markup=buttons)
        await query.answer()
    
    elif data.startswith("time_"):
        minutes = int(data.split("_")[1])
        await update_settings(chat_id, "delete_time", minutes)
        
        time_text = f"{minutes} minutes" if minutes > 0 else "Permanent"
        await query.answer(f"Delete time set to {time_text}")
        await query.message.delete()
    
    elif data == "force_sub_menu":
        force_sub = await get_force_sub(chat_id)
        if force_sub:
            channel_id = force_sub.get("channel_id")
            try:
                channel = await client.get_chat(channel_id)
                channel_link = f"https://t.me/{channel.username}" if channel.username else ""
                
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Visit Channel", url=channel_link)],
                    [InlineKeyboardButton("❌ Disconnect", callback_data="disconnect_fsub")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_settings")]
                ])
                await query.message.edit_text(
                    f"🔗 **Force Subscribe Channel:**\n\n"
                    f"**Channel:** {channel.title}\n"
                    f"**Status:** ✅ Connected\n\n"
                    f"New members must join this channel.",
                    reply_markup=buttons
                )
            except:
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back_settings")]
                ])
                await query.message.edit_text(
                    "❌ **Channel Not Found!**\n\n"
                    "The channel is no longer accessible or bot was removed.",
                    reply_markup=buttons
                )
        else:
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Set Channel", callback_data="set_fsub")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_settings")]
            ])
            await query.message.edit_text(
                "🔗 **Force Subscribe**\n\n"
                "No channel set yet. Set a channel that new members must join.",
                reply_markup=buttons
            )
        await query.answer()
    
    elif data == "disconnect_fsub":
        await remove_force_sub(chat_id)
        await query.answer("✅ Force subscribe disconnected!")
        await query.message.delete()
    
    elif data == "clear_junk":
        junk_count = await clear_junk()
        await query.answer(f"🧹 Cleared {junk_count} junk entries!")
        await query.message.edit_text(
            f"✅ **Junk Cleared!**\n\n"
            f"Removed {junk_count} inactive entries from database.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh Stats", callback_data="refresh_stats")]
            ])
        )
    
    elif data == "refresh_stats":
        users = await get_user_count()
        groups = await get_group_count()
        
        stats_text = f"""📊 **Bot Statistics**

👥 **Total Users:** {users}
👥 **Total Groups:** {groups}
⚡ **Bot Uptime:** 24/7
🔄 **Last Updated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        await query.message.edit_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🧹 Clear Junk", callback_data="clear_junk")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]
            ])
        )
        await query.answer("✅ Stats refreshed!")
    
    elif data.startswith("verify_"):
        user_id = int(data.split("_")[1])
        if query.from_user.id == user_id:
            try:
                # Unrestrict user
                await client.unrestrict_chat_member(
                    query.message.chat.id,
                    user_id,
                    permissions=dict(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True
                    )
                )
                await query.answer("✅ Verified! Welcome to the group!")
                await query.message.delete()
            except:
                await query.answer("❌ Verification failed!")
        else:
            await query.answer("❌ This button is not for you!")
    
    elif data == "ok_correction":
        await query.message.delete()
        await query.answer()
    
    elif data == "close_settings":
        await query.message.delete()
        await query.answer("Settings closed!")
    
    elif data == "back_settings":
        settings = await get_settings(chat_id)
        spelling_status = "✅ ON" if settings.get("spelling_on", True) else "❌ OFF"
        delete_status = "✅ ON" if settings.get("auto_delete_on", False) else "❌ OFF"
        delete_time = settings.get("delete_time", 0)
        time_text = f"{delete_time} min" if delete_time > 0 else "Permanent"
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Spelling Correction: {spelling_status}", callback_data="toggle_spelling")],
            [InlineKeyboardButton(f"Auto Delete Files: {delete_status}", callback_data="toggle_auto_delete")],
            [InlineKeyboardButton(f"Delete Time: {time_text}", callback_data="set_delete_time")],
            [InlineKeyboardButton("🔗 Force Subscribe", callback_data="force_sub_menu")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")]
        ])
        
        await query.message.edit_text(
            f"⚙️ **Settings for {query.message.chat.title}**\n\n"
            "Configure your group settings below:",
            reply_markup=buttons
        )
        await query.answer()

# ================ GROUP EVENTS ================

@app.on_message(filters.new_chat_members)
async def welcome_new_members(client: Client, message: Message):
    """Welcome new members and add group to database"""
    for member in message.new_chat_members:
        if member.is_self:  # Bot added to group
            await add_group(
                message.chat.id,
                message.chat.title,
                message.chat.username
            )
            
            # Send welcome message to group
            welcome_text = f"""🎬 **Thanks for adding me!** 🎬

I'm Movie Helper Bot! Here's what I can do:

✅ **Auto-correct movie names** (remove extra words)
✅ **Auto-delete files** after set time
✅ **Force subscribe** to your channel
✅ **AI movie recommendations**
✅ **Beautiful settings menu**

**Setup Instructions:**
1. Make me admin with delete permissions
2. Use /settings to configure
3. Set up force subscribe with /addfsub

Need help? Use /help 😊"""
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu")],
                [InlineKeyboardButton("📚 Help", callback_data="help")]
            ])
            
            await message.reply_text(welcome_text, reply_markup=buttons)
            
            # Notify owner
            if Config.OWNER_ID:
                owner_msg = (
                    f"🤖 **Bot Added to New Group!**\n\n"
                    f"**Group:** {message.chat.title}\n"
                    f"**ID:** `{message.chat.id}`\n"
                    f"**Username:** @{message.chat.username or 'N/A'}\n"
                    f"**Members:** {await client.get_chat_members_count(message.chat.id)}\n"
                    f"**Added by:** {message.from_user.mention if message.from_user else 'Unknown'}"
                )
                try:
                    await client.send_message(Config.OWNER_ID, owner_msg)
                except:
                    pass
            
            break  # Only need to handle bot addition once
