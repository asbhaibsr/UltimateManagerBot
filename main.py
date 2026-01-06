# main.py

import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message, InlineKeyboardMarkup, 
    InlineKeyboardButton, CallbackQuery,
    ChatPermissions
)
from pyrogram.enums import ChatMemberStatus
from flask import Flask
from threading import Thread
import time
import re

from config import Config
from database import db
from features import feature_manager
from buttons import buttons
from premium_menu import premium_ui

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app for Koyeb
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <html>
        <head>
            <title>🎬 Movie Bot Pro - Running 24/7</title>
            <meta http-equiv="refresh" content="30">
            <style>
                body {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                }
                .container {
                    background: rgba(255, 255, 255, 0.1);
                    backdrop-filter: blur(10px);
                    border-radius: 20px;
                    padding: 30px;
                    max-width: 600px;
                    margin: 0 auto;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                }
                .status {
                    display: inline-block;
                    padding: 5px 15px;
                    background: #4CAF50;
                    border-radius: 20px;
                    font-weight: bold;
                    animation: pulse 2s infinite;
                }
                @keyframes pulse {
                    0% { opacity: 1; }
                    50% { opacity: 0.7; }
                    100% { opacity: 1; }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎬 Movie Bot Pro</h1>
                <p>Status: <span class="status">ONLINE ✅</span></p>
                <p>24/7 Running on Koyeb</p>
                <p>Made with ❤️ by @asbhai_bsr</p>
                <p>Bot: @{}</p>
                <p>🆔 Version: 2.0 with Premium System</p>
            </div>
        </body>
    </html>
    """.format(Config.BOT_USERNAME)

@app.route('/ping')
def ping():
    return "pong", 200

@app.route('/health')
def health():
    return {"status": "healthy", "timestamp": time.time()}, 200

def run_flask():
    """Run Flask server for Koyeb health checks"""
    app.run(host='0.0.0.0', port=Config.PORT, debug=False, use_reloader=False)

# Initialize Bot
bot = Client(
    name="MovieBotPro",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    workers=100,
    sleep_threshold=60
)

# ========== START COMMAND ==========
@bot.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    await db.add_user(user_id, username)
    
    welcome_text = f"""
    🎬 **Welcome {message.from_user.first_name}!** 🤖

    I'm **Movie Bot Pro** - Your Smart Movie Assistant!

    ✅ **Features:**
    • 🔤 Smart Spelling Correction
    • 📺 Season Number Detection  
    • 🎬 Movie Request System
    • 🗑️ Auto File Cleaner
    • 💎 Premium System (Ad-free)
    • ⚙️ Fully Customizable
    • 👥 Force Subscribe/Join

    **📌 How to use in Groups:**
    1. Add me to your group
    2. Make me **Admin**
    3. Use `/settings` to configure
    4. Members can request movies!

    **👨‍💻 Owner:** @asbhai_bsr
    **📢 Channel:** @{Config.MAIN_CHANNEL}
    """
    
    await message.reply_text(
        text=welcome_text,
        reply_markup=buttons.start_menu(user_id),
        disable_web_page_preview=True
    )

# ========== PREMIUM COMMANDS ==========
@bot.on_message(filters.command("premium") & filters.private)
async def premium_command(client: Client, message: Message):
    """Show premium information"""
    await message.reply_text(
        text=premium_ui.main_premium_text(),
        reply_markup=premium_ui.premium_buttons(),
        disable_web_page_preview=True
    )

@bot.on_message(filters.command("addpremium") & filters.user(Config.OWNER_ID))
async def add_premium_cmd(client, message: Message):
    """Add premium to a group (Owner only)"""
    if len(message.command) < 2:
        return await message.reply("Usage: `/addpremium <group_id>`")
    
    group_id = int(message.command[1])
    
    await message.reply(
        f"Select duration for Group `{group_id}`:",
        reply_markup=premium_ui.admin_premium_select(group_id)
    )

@bot.on_callback_query(filters.regex(r"addprem_"))
async def process_premium(client, callback: CallbackQuery):
    """Process premium activation"""
    data = callback.data.split("_")
    group_id = int(data[1])
    months = int(data[2])
    
    expiry = await db.set_premium(group_id, months)
    await callback.message.edit(
        f"✅ Premium Activated for `{group_id}`!\n"
        f"Duration: {months} months\n"
        f"Expiry: {expiry.strftime('%Y-%m-%d')}\n"
        f"Price: ₹{Config.PREMIUM_PRICES.get(str(months), 'N/A')}"
    )
    
    # Notify Group
    try:
        await client.send_message(
            group_id,
            f"🎊 **CONGRATULATIONS!**\n"
            f"This group is now **PREMIUM** for {months} months!\n"
            f"✅ Ads are disabled\n"
            f"✅ All features unlocked\n"
            f"✅ Priority support"
        )
    except:
        pass
    
    await callback.answer("Premium activated!")

@bot.on_callback_query(filters.regex("show_premium"))
async def show_premium_handler(client, callback: CallbackQuery):
    """Show premium menu"""
    await callback.message.edit(
        text=premium_ui.main_premium_text(),
        reply_markup=premium_ui.premium_buttons(),
        disable_web_page_preview=True
    )

# ========== SETTINGS COMMAND ==========
@bot.on_message(filters.command("settings") & filters.group)
async def settings_command(client: Client, message: Message):
    """Show settings menu to group admins"""
    chat_id = message.chat.id
    
    # Check if user is admin
    try:
        user = await client.get_chat_member(chat_id, message.from_user.id)
        if user.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await message.reply("❌ Only admins can use this command!")
            return
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
        return
    
    settings = await db.get_group_settings(chat_id)
    is_premium = await db.check_premium(chat_id)
    
    premium_status = "🟢 PREMIUM" if is_premium else "🔴 FREE"
    
    settings_text = f"""
    ⚙️ **Group Settings for {message.chat.title}**
    
    **{premium_status} VERSION**
    
    **🔧 Features Status:**
    • 🔤 Spelling Check: {'✅ ON' if settings['features']['spell_check'] else '❌ OFF'}
    • 📺 Season Check: {'✅ ON' if settings['features']['season_check'] else '❌ OFF'}
    • 🗑️ Auto Delete: {'✅ ON' if settings['features']['auto_delete'] else '❌ OFF'}
    • 📁 File Cleaner: {'✅ ON' if settings['features']['file_cleaner'] else '❌ OFF'}
    • 🎬 Request System: {'✅ ON' if settings['features']['request_system'] else '❌ OFF'}
    
    **⏰ Timing Settings:**
    • Auto Delete: {settings['auto_delete_time']} seconds
    • File Clean: {settings['file_clean_time']} seconds
    
    **👥 Verification:**
    • Force Subscribe: {'✅ ON' if settings['fsub_enabled'] else '❌ OFF'}
    • Force Join: {'✅ ON' if settings['force_join_enabled'] else '❌ OFF'}
    
    Click buttons below to change settings:
    """
    
    await message.reply(
        settings_text,
        reply_markup=buttons.features_menu(chat_id)
    )

# ========== REQUEST COMMAND ==========
@bot.on_message(filters.command("request") & filters.group)
async def request_command(client: Client, message: Message):
    """Handle movie requests"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Check request system is enabled
    if not await db.get_feature_status(chat_id, "request_system"):
        await message.reply("❌ Request system is disabled in this group!")
        return
    
    # Check cooldown
    user_data = await db.get_user(user_id)
    if user_data and user_data.get('last_request'):
        last_request = user_data['last_request']
        cooldown = (await db.get_group_settings(chat_id))['cooldown_time']
        
        time_diff = (message.date - last_request).seconds
        if time_diff < cooldown:
            remaining = cooldown - time_diff
            await message.reply(f"⏳ Please wait {remaining} seconds before another request!")
            return
    
    # Extract movie name
    if len(message.command) < 2:
        await message.reply("""
        **Usage:** `/request Movie Name`
        
        **Examples:**
        `/request Kalki 2898 AD`
        `/request The Boys Season 4`
        `/request Stree 2`
        """)
        return
    
    movie_name = ' '.join(message.command[1:])
    cleaned_name = await feature_manager.clean_movie_request(movie_name)
    
    # Create request
    request_id = await db.add_request(chat_id, user_id, cleaned_name)
    
    # Send confirmation
    confirm_text = f"""
    🎬 **Movie Request Created!**
    
    **Movie:** {cleaned_name}
    **Requested by:** {message.from_user.mention}
    **Request ID:** `{request_id}`
    
    ✅ Admins have been notified!
    ⏳ You'll be updated when it's ready.
    """
    
    await message.reply(confirm_text)
    
    # Notify admins (with premium check for ads)
    is_premium = await db.check_premium(chat_id)
    
    admins_text = f"""
    🔔 **New Movie Request!**
    
    **Group:** {message.chat.title}
    **Movie:** {cleaned_name}
    **User:** {message.from_user.mention} (@{message.from_user.username or 'N/A'})
    **Request ID:** `{request_id}`
    **Premium:** {'✅ Yes' if is_premium else '❌ No'}
    """
    
    # Send to owner
    try:
        await client.send_message(
            chat_id=Config.OWNER_ID,
            text=admins_text
        )
    except:
        pass

# ========== FUNCTION COMMAND ==========
@bot.on_message(filters.command("function") & filters.group)
async def function_command(client: Client, message: Message):
    """Show all functions with buttons"""
    functions_text = """
    ⚙️ **ALL BOT FUNCTIONS** 🎯

    **🔧 FEATURE TOGGLES:**
    • 🔤 Spelling Checker - Auto-correct movie names
    • 📺 Season Checker - Detect missing season numbers  
    • 🗑️ Auto Delete - Delete messages after time
    • 📁 File Cleaner - Auto delete files/videos/photos
    • 🎬 Request System - Movie request management
    • 👥 Force Subscribe - Channel join required
    • 👥 Force Join - Add members before posting
    
    **💎 PREMIUM FEATURES:**
    • Ad-free experience
    • Priority support
    • Faster responses
    • All features unlocked
    
    **⏰ TIME SETTINGS:**
    • Set different timings for each feature
    • Options: 2min, 5min, 10min, 30min, 1hr, Permanent
    
    Use buttons below to configure:
    """
    
    await message.reply(
        functions_text,
        reply_markup=buttons.features_menu(message.chat.id)
    )

# ========== STATS COMMAND ==========
@bot.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats_command(client: Client, message: Message):
    """Show bot statistics (Owner only)"""
    stats = await db.get_bot_stats()
    
    stats_text = f"""
    📊 **BOT STATISTICS** 📈
    
    **👥 Users:**
    • Total Users: {stats['total_users']}
    • Blocked Users: {stats['blocked_users']}
    
    **👥 Groups:**
    • Total Groups: {stats['total_groups']}
    
    **💎 Premium:**
    • Active Premium: {stats['premium_stats']['active_premium']}
    • Total Premium: {stats['premium_stats']['total_premium']}
    • Expired Premium: {stats['premium_stats']['expired_premium']}
    
    **🎬 Requests:**
    • Total Requests: {stats['total_requests']}
    • Pending Requests: {stats['pending_requests']}
    • Today's Requests: {stats['today_requests']}
    
    **📈 Usage:**
    • Bot is running 24/7
    • Koyeb Port: {Config.PORT}
    • Version: 2.0
    """
    
    await message.reply(stats_text)

# ========== BROADCAST COMMAND (AD-FREE FOR PREMIUM) ==========
@bot.on_message(filters.command("broadcast") & filters.user(Config.OWNER_ID))
async def broadcast_command(client: Client, message: Message):
    """Broadcast message to all groups (skip premium)"""
    if not message.reply_to_message:
        return await message.reply("Reply to a message to broadcast.")
    
    all_groups = await db.db.groups.find().to_list(None)
    sent = 0
    skipped_premium = 0
    
    for group in all_groups:
        chat_id = group['chat_id']
        
        # Skip if Premium (Ad-free)
        if await db.check_premium(chat_id):
            skipped_premium += 1
            continue
            
        try:
            await message.reply_to_message.copy(chat_id)
            sent += 1
            await asyncio.sleep(0.5)  # Avoid flood
        except:
            pass
    
    await message.reply(
        f"✅ Broadcast completed!\n"
        f"• Sent to: {sent} groups\n"
        f"• Skipped (Premium): {skipped_premium} groups\n"
        f"• Total groups: {len(all_groups)}"
    )

# ========== MAIN GROUP MESSAGE HANDLER ==========
@bot.on_message(filters.group & ~filters.bot & ~filters.service)
async def group_message_handler(client: Client, message: Message):
    """Handle all group messages"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text or message.caption or ""
    
    # Update user activity
    await db.update_user_activity(user_id)
    
    # Check if message is a file/video/photo for auto-clean
    file_info = await feature_manager.extract_file_info(message)
    if file_info and await db.get_feature_status(chat_id, "file_cleaner"):
        settings = await db.get_group_settings(chat_id)
        clean_time = settings['file_clean_time']
        
        if clean_time > 0:
            await db.add_file_to_cleaner(chat_id, message.id, clean_time)
    
    # Skip short messages
    if len(text) < 3:
        return
    
    # Check for movie name (if features enabled)
    if len(text) > 2:
        # Extract clean movie name
        query, year = await feature_manager.extract_movie_name(text)
        
        if query and len(query) > 2:
            responses = []
            
            # Spelling Check
            if await db.get_feature_status(chat_id, "spell_check"):
                spell_result = await feature_manager.check_spelling_correction(query)
                if spell_result['needs_correction']:
                    responses.append(f"**🔤 Did you mean:** {spell_result['suggested']}")
            
            # Season Check  
            if await db.get_feature_status(chat_id, "season_check"):
                needs_season, suggestion = await feature_manager.check_season_requirement(text)
                if needs_season:
                    responses.append(f"**📺 Add season:** {suggestion}")
            
            # Send response if needed
            if responses:
                response_text = "\n\n".join(responses)
                
                # Add suggestion buttons
                keyboard_buttons = []
                
                if 'spell_result' in locals() and spell_result['needs_correction']:
                    keyboard_buttons.append([
                        InlineKeyboardButton(f"✅ {spell_result['suggested']}", 
                         callback_data=f"use_suggested_{spell_result['suggested']}")
                    ])
                
                if needs_season:
                    keyboard_buttons.append([
                        InlineKeyboardButton(f"📺 {suggestion}", 
                         callback_data=f"add_season_full_{suggestion}")
                    ])
                
                if keyboard_buttons:
                    keyboard = InlineKeyboardMarkup(keyboard_buttons)
                    sent_msg = await message.reply(response_text, reply_markup=keyboard)
                else:
                    sent_msg = await message.reply(response_text)
                
                # Auto delete if enabled
                if await db.get_feature_status(chat_id, "auto_delete"):
                    delete_time = (await db.get_group_settings(chat_id))['auto_delete_time']
                    if delete_time > 0:
                        await asyncio.sleep(delete_time)
                        try:
                            await sent_msg.delete()
                        except:
                            pass

# ========== CALLBACK QUERY HANDLER ==========
@bot.on_callback_query()
async def callback_handler(client: Client, callback: CallbackQuery):
    """Handle all button clicks"""
    data = callback.data
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id if callback.message else None
    
    # Feature Toggles
    if data.startswith("toggle_"):
        feature = data.replace("toggle_", "")
        settings = await db.get_group_settings(chat_id)
        current = settings['features'].get(feature, True)
        new_value = not current
        
        await db.toggle_feature(chat_id, feature, new_value)
        
        status = "✅ ENABLED" if new_value else "❌ DISABLED"
        await callback.answer(f"{feature.replace('_', ' ').title()} {status}!")
        
        # Refresh settings message
        if callback.message:
            await settings_command(client, callback.message)
    
    # Premium Status Check
    elif data == "check_premium_status":
        if chat_id:
            is_premium = await db.check_premium(chat_id)
            settings = await db.get_group_settings(chat_id)
            expiry = settings.get('premium_expiry')
            
            status_text = premium_ui.premium_status_text(chat_id, is_premium, expiry)
            await callback.message.edit(
                text=status_text,
                reply_markup=buttons.premium_status_buttons(is_premium),
                disable_web_page_preview=True
            )
    
    # Time Setting Menu
    elif data == "set_time_menu":
        await callback.message.edit(
            text="⏰ **Select Time Setting to Configure:**",
            reply_markup=buttons.time_selection_menu("menu")
        )
    
    # Set Specific Time
    elif data.startswith("set_time_"):
        parts = data.split("_")
        if len(parts) >= 4:
            feature_type = parts[2]
            time_seconds = int(parts[3])
            
            if feature_type == "auto_delete":
                await db.set_auto_delete_time(chat_id, time_seconds)
            elif feature_type == "file_clean":
                await db.set_file_clean_time(chat_id, time_seconds)
            elif feature_type == "cooldown":
                await db.update_group_settings(chat_id, {"cooldown_time": time_seconds})
            
            time_text = "Permanent" if time_seconds == 0 else f"{time_seconds//60} minutes"
            await callback.answer(f"⏰ {feature_type.replace('_', ' ').title()} set to {time_text}!")
    
    # Use Suggested Name
    elif data.startswith("use_suggested_"):
        suggested = data.replace("use_suggested_", "")
        await callback.message.edit(
            text=f"✅ **Using:** {suggested}\n\nMovie request updated!",
            reply_markup=None
        )
        await callback.answer("Name updated!")
    
    # Add Season
    elif data.startswith("add_season_full_"):
        season_name = data.replace("add_season_full_", "")
        await callback.message.edit(
            text=f"✅ **Season Added:** {season_name}",
            reply_markup=None
        )
        await callback.answer("Season number added!")
    
    # Show Features
    elif data == "show_features":
        await callback.message.edit(
            text="⚙️ **Feature Configuration**\n\nToggle features ON/OFF:",
            reply_markup=buttons.features_menu(chat_id)
        )
    
    # Back to Start
    elif data == "back_to_start":
        await callback.message.delete()
        await start_command(client, callback.message)
    
    # Show Help
    elif data == "show_help":
        help_text = """
        🆘 **HELP GUIDE** 📖

        **📌 HOW TO USE:**
        1. Add bot to group
        2. Make bot admin
        3. Use `/settings` to configure
        4. Members can request movies with `/request`

        **🔧 ADMIN COMMANDS:**
        • `/settings` - Configure bot features
        • `/function` - Show all functions
        • `/stats` - View group statistics
        • `/broadcast` - Send message to all groups
        • `/clean` - Clean old files

        **💎 PREMIUM COMMANDS:**
        • `/premium` - Show premium plans
        • `/addpremium <group_id>` - Add premium (Owner only)

        **👤 USER COMMANDS:**
        • `/request Movie Name` - Request a movie
        • `/myrequests` - View your requests
        • `/help` - Show this guide

        **📞 SUPPORT:** @asbhai_bsr
        """
        
        await callback.message.edit(
            text=help_text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="back_to_start"),
                InlineKeyboardButton("💎 Premium", callback_data="show_premium")
            ]])
        )
    
    # Show Stats
    elif data == "show_stats":
        if user_id == Config.OWNER_ID:
            await stats_command(client, callback.message)
        else:
            await callback.answer("Only owner can view stats!", show_alert=True)
    
    # Request Movie
    elif data == "request_movie":
        await callback.message.edit(
            text="🎬 **Movie Request**\n\nPlease use `/request Movie Name` in a group where I'm added!\n\nExample: `/request Kalki 2898 AD`",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="back_to_start")
            ]])
        )
    
    await callback.answer()

# ========== FILE CLEANER TASK ==========
async def file_cleaner_task():
    """Background task to clean files"""
    while True:
        try:
            files_to_clean = await db.get_files_to_clean()
            
            for file_data in files_to_clean:
                try:
                    await bot.delete_messages(
                        chat_id=file_data['chat_id'],
                        message_ids=file_data['message_id']
                    )
                    await db.mark_file_cleaned(file_data['message_id'])
                except Exception as e:
                    print(f"Failed to delete file: {e}")
            
            # Clean old data weekly
            if len(files_to_clean) > 0:
                cleaned = await db.cleanup_old_data()
                print(f"Cleaned {cleaned['old_requests']} old requests and {cleaned['old_files']} old files")
            
        except Exception as e:
            print(f"File cleaner error: {e}")
        
        # Check every 30 seconds
        await asyncio.sleep(30)

async def main():
    """Start the bot"""
    print("🚀 Bot starting...")
    
    # 1. Database Initialize karein
    if not await db.init_db():
        print("❌ Failed to connect to database!")
        return
    
    # 2. Bot Start karein
    await bot.start()
    print("🤖 Bot is Online!")

    # 3. Background tasks start karein
    asyncio.create_task(file_cleaner_task())
    
    # Startup message
    try:
        await bot.send_message(Config.OWNER_ID, "✅ Bot has been deployed and is now Online!")
    except:
        pass
    
    # 4. Bot ko chalta rehne dein
    await idle()
    
    # 5. Stop bot gracefully
    await bot.stop()

if __name__ == "__main__":
    # Flask ko thread mein chalayein taki Koyeb health check pass ho jaye
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    # Bot ko main loop mein chalayein
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot Stopped!")
