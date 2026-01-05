import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message, InlineKeyboardMarkup, 
    InlineKeyboardButton, CallbackQuery,
    ChatPermissions
)
from flask import Flask, request
from threading import Thread
import time

from config import Config
from database import db
from handlers import (
    movie_checker, fsub_handler, 
    fjoin_handler, broadcast_handler
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app for Render 24/7
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <html>
        <head><title>🤖 Movie Bot - Running 24/7</title></head>
        <body style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-align: center; padding: 50px;">
            <h1>🎬 Movie Bot is Running!</h1>
            <p>Bot Status: <span style="color: #4CAF50; font-weight: bold;">ONLINE ✅</span></p>
            <p>Made with ❤️ by @asbhai_bsr</p>
            <p>Users: Loading...</p>
        </body>
    </html>
    """

@app.route('/ping')
def ping():
    return "pong", 200

def run_flask():
    """Run Flask server in separate thread"""
    app.run(host='0.0.0.0', port=Config.PORT, debug=False, use_reloader=False)

# Initialize Bot
bot = Client(
    name="MovieBotPro",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="plugins")
)

# ========== START COMMAND ==========
@bot.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Start command with beautiful menu"""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    # Add user to database
    await db.add_user(user_id, username)
    
    # Create buttons
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", 
          url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton("📢 Official Channel", 
          url=f"https://t.me/{Config.CHANNEL_USERNAME}")],
        [InlineKeyboardButton("🎬 Movie Channel", 
          url=Config.MOVIE_CHANNEL)],
        [InlineKeyboardButton("🆘 Help", callback_data="help"),
         InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("👨‍💻 Owner", url="https://t.me/asbhai_bsr")]
    ])
    
    # Send welcome message
    await message.reply_photo(
        photo=Config.START_IMAGE,
        caption=f"""
        🎬 **Welcome to Movie Bot Pro!** 🚀

        **Hi {message.from_user.first_name}!** 👋

        I'm your AI-powered movie assistant with amazing features:

        ✅ **Smart Name Checker** - Automatically corrects movie names
        ✅ **Season Detection** - Reminds you to add S01, S02
        ✅ **Force Subscribe** - Channel join required
        ✅ **Force Group Join** - Add members before posting
        ✅ **Auto Cleanup** - Keeps group clean
        ✅ **Movie Details** - Get info with one click

        **⚡ How to use:**
        1. Add me to your group
        2. Make me **Admin**
        3. Start typing movie names!

        **👨‍💻 Developer:** @asbhai_bsr
        """,
        reply_markup=keyboard
    )

# ========== HELP COMMAND ==========
@bot.on_message(filters.command("help") & filters.private)
async def help_command(client: Client, message: Message):
    """Help command"""
    help_text = """
    **🤖 MOVIE BOT HELP GUIDE** 📖

    **📌 HOW TO USE IN GROUPS:**
    1. Just type any movie/series name
    2. I'll automatically check spelling
    3. If wrong → I'll suggest correct name
    4. If correct → I'll stay silent

    **🔧 ADMIN COMMANDS:**
    • `/stats` - Bot statistics
    • `/broadcast` - Send message to all users
    • `/clearjunk` - Remove inactive users
    • `/fsub @channel_id` - Setup force subscribe
    • `/offfsub` - Disable force subscribe
    • `/forcejoin 2` - Force join (2,3,5,10 members)
    • `/offforcejoin` - Disable force join

    **🎯 FEATURES:**
    • AI-powered name checking
    • Season number verification
    • Movie details with download link
    • Multi-language support (Hindi/English)
    • Force subscribe system
    • Force group join system
    • Auto-delete messages

    **📞 SUPPORT:** @asbhai_bsr
    """
    await message.reply(help_text)

# ========== STATS COMMAND ==========
@bot.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
async def stats_command(client: Client, message: Message):
    """Show bot statistics"""
    stats = await db.get_stats()
    
    stats_text = f"""
    **📊 BOT STATISTICS** 📈

    👤 **Total Users:** `{stats['users']:,}`
    👥 **Total Groups:** `{stats['groups']:,}`
    🚫 **Blocked Users:** `{stats['blocked']:,}`

    **💾 DATABASE:**
    • MongoDB: ✅ Connected
    • Storage: Calculating...

    **⚡ BOT STATUS:**
    • Uptime: 100%
    • Memory: Optimal
    • API: Working ✅

    **👨‍💻 Owner:** @asbhai_bsr
    """
    await message.reply(stats_text)

# ========== BROADCAST COMMAND ==========
@bot.on_message(filters.command("broadcast") & filters.user(Config.OWNER_ID))
async def broadcast_command(client: Client, message: Message):
    """Broadcast message to all users"""
    if not message.reply_to_message:
        await message.reply("Please reply to a message to broadcast!")
        return
    
    await broadcast_handler.send_broadcast(client, message.reply_to_message)

# ========== CLEAR JUNK COMMAND ==========
@bot.on_message(filters.command("clearjunk") & filters.user(Config.OWNER_ID))
async def clear_junk_command(client: Client, message: Message):
    """Clear blocked/deleted users"""
    deleted = await db.clear_junk()
    await message.reply(f"✅ **Cleanup Complete!**\n\nRemoved {deleted} blocked/deleted users.")

# ========== FSUB COMMAND ==========
@bot.on_message(filters.command("fsub") & filters.group)
async def fsub_setup_command(client: Client, message: Message):
    """Setup force subscribe"""
    # Check if user is admin
    try:
        user = await client.get_chat_member(message.chat.id, message.from_user.id)
        if user.status not in ["creator", "administrator"]:
            await message.reply("❌ You need to be admin to use this command!")
            return
    except:
        pass
    
    # Get channel from command
    if len(message.command) < 2:
        await message.reply(
            "**Usage:** `/fsub @channelusername`\n\n"
            "**Example:** `/fsub @asbhai_bsr`\n"
            "**Max 3 channels:** `/fsub @channel1 @channel2 @channel3`"
        )
        return
    
    channels = message.command[1:]
    if len(channels) > Config.MAX_FSUB_CHANNELS:
        await message.reply(f"❌ Maximum {Config.MAX_FSUB_CHANNELS} channels allowed!")
        return
    
    # Save to database
    await db.set_fsub(message.chat.id, channels)
    
    channels_list = "\n".join([f"• {ch}" for ch in channels])
    await message.reply(
        f"✅ **Force Subscribe Enabled!**\n\n"
        f"Users must join these channels:\n{channels_list}\n\n"
        f"To disable: `/offfsub`"
    )

# ========== OFF FSUB COMMAND ==========
@bot.on_message(filters.command("offfsub") & filters.group)
async def off_fsub_command(client: Client, message: Message):
    """Disable force subscribe"""
    await db.disable_fsub(message.chat.id)
    await message.reply("✅ Force Subscribe has been disabled!")

# ========== FORCE JOIN COMMAND ==========
@bot.on_message(filters.command("forcejoin") & filters.group)
async def force_join_command(client: Client, message: Message):
    """Setup force join"""
    # Check admin
    try:
        user = await client.get_chat_member(message.chat.id, message.from_user.id)
        if user.status not in ["creator", "administrator"]:
            await message.reply("❌ You need to be admin!")
            return
    except:
        pass
    
    if len(message.command) < 2:
        await message.reply(
            "**Usage:** `/forcejoin NUMBER`\n\n"
            "**Options:** 1, 2, 3, 5, 10\n"
            "**Example:** `/forcejoin 2`\n"
            "Users will need to add 2 members before posting."
        )
        return
    
    try:
        count = int(message.command[1])
        if count not in Config.FORCE_JOIN_OPTIONS:
            await message.reply(f"❌ Invalid number! Use: {', '.join(map(str, Config.FORCE_JOIN_OPTIONS))}")
            return
        
        await db.set_force_join(message.chat.id, count)
        await message.reply(
            f"✅ **Force Join Enabled!**\n\n"
            f"New users must add **{count} members** to this group.\n"
            f"To disable: `/offforcejoin`"
        )
    except ValueError:
        await message.reply("❌ Please provide a valid number!")

# ========== OFF FORCE JOIN COMMAND ==========
@bot.on_message(filters.command("offforcejoin") & filters.group)
async def off_force_join_command(client: Client, message: Message):
    """Disable force join"""
    await db.disable_force_join(message.chat.id)
    await message.reply("✅ Force Join has been disabled!")

# ========== MAIN GROUP HANDLER ==========
@bot.on_message(filters.group & ~filters.bot & ~filters.service)
async def group_message_handler(client: Client, message: Message):
    """Handle all group messages"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text or message.caption or ""
    
    # Skip if message is too short
    if len(text) < 3:
        return
    
    # 1. Check Force Subscribe
    fsub_result, channel = await fsub_handler.check_user(client, chat_id, user_id)
    if not fsub_result:
        await fsub_handler.send_fsub_message(client, chat_id, user_id, channel)
        return
    
    # 2. Check Force Join
    fjoin_result = await fjoin_handler.check_force_join(client, chat_id, user_id)
    if not fjoin_result:
        count = fjoin_result[1]
        await fjoin_handler.send_force_join_message(client, chat_id, user_id, count)
        return
    
    # 3. Check Movie Name
    query, year = await movie_checker.extract_query(text)
    
    if query and len(query) > 2:
        # Check spelling
        spell_result = await movie_checker.check_spelling(query)
        
        # Check if season required
        season_required = await movie_checker.check_season_required(text)
        
        # Prepare response if needed
        if not spell_result.get('is_correct', True) or season_required:
            keyboard_buttons = []
            
            # Add language buttons
            keyboard_buttons.append([
                InlineKeyboardButton("🇮🇳 Hindi", callback_data=f"lang_hi_{query}"),
                InlineKeyboardButton("🇬🇧 English", callback_data=f"lang_en_{query}")
            ])
            
            # Add correct name button
            if not spell_result.get('is_correct', True):
                corrected = spell_result.get('corrected', query)
                keyboard_buttons.append([
                    InlineKeyboardButton(f"✅ {corrected}", 
                     callback_data=f"movie_details_{corrected}")
                ])
            
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
            
            # Prepare message
            if season_required:
                msg_text = f"❌ **Season Missing!**\n\nPlease add season number:\n**{query} S01**"
            else:
                msg_text = f"🔍 **Spelling Check:**\n\nDid you mean: **{spell_result.get('corrected', query)}**?"
            
            # Send message
            sent_msg = await message.reply(msg_text, reply_markup=keyboard)
            
            # Auto delete after 5 minutes
            await asyncio.sleep(Config.AUTO_DELETE_TIME)
            try:
                await sent_msg.delete()
            except:
                pass

# ========== CALLBACK QUERY HANDLER ==========
@bot.on_callback_query()
async def callback_handler(client: Client, callback: CallbackQuery):
    """Handle button clicks"""
    data = callback.data
    user_id = callback.from_user.id
    
    # FSub Verification
    if data.startswith("fsub_verify_"):
        chat_id = callback.message.chat.id
        target_user = int(data.split("_")[2])
        
        if user_id != target_user:
            await callback.answer("This button is not for you!", show_alert=True)
            return
        
        # Check if user joined
        channels = await db.get_fsub(chat_id)
        all_joined = True
        
        for channel in channels:
            try:
                member = await client.get_chat_member(channel, user_id)
                if member.status in ['left', 'kicked']:
                    all_joined = False
                    break
            except:
                all_joined = False
        
        if all_joined:
            await callback.message.delete()
            await callback.answer("✅ Verified! You can now post.", show_alert=True)
        else:
            await callback.answer("❌ Please join all channels first!", show_alert=True)
    
    # Force Join Verification
    elif data.startswith("fjoin_verify_"):
        chat_id = callback.message.chat.id
        target_user = int(data.split("_")[2])
        
        if user_id != target_user:
            await callback.answer("This button is not for you!", show_alert=True)
            return
        
        # Mark as verified
        await db.set_verified(chat_id, user_id)
        
        # Unmute user
        try:
            await client.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
        except:
            pass
        
        await callback.message.delete()
        await callback.answer("✅ Verified! You can now post.", show_alert=True)
    
    # Movie Details
    elif data.startswith("movie_details_"):
        movie_name = data.split("_", 2)[2]
        details = await movie_checker.get_movie_details(movie_name)
        
        if details:
            text = f"""
            🎬 **{details['title']}** ({details['year']})
            
            ⭐ **Rating:** {details['rating']}/10
            
            📝 **Plot:** {details['overview']}
            
            🎥 **Get this movie:**
            {Config.MOVIE_CHANNEL}
            
            **Note:** Contact @asfilter_bot for movies
            """
            
            if details.get('poster'):
                await callback.message.reply_photo(
                    photo=details['poster'],
                    caption=text
                )
            else:
                await callback.message.reply(text)
        else:
            await callback.answer("Details not found!", show_alert=True)
    
    # Help button
    elif data == "help":
        await callback.message.edit(
            text="Help section will be here...",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Back", callback_data="back_to_start")
            ]])
        )
    
    # Stats button
    elif data == "stats":
        stats = await db.get_stats()
        text = f"Users: {stats['users']}\nGroups: {stats['groups']}"
        await callback.answer(text, show_alert=True)
    
    await callback.answer()

# ========== BOT STARTUP ==========
async def main():
    """Main function to start bot"""
    # Start Flask server in background
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Flask server started on port", Config.PORT)
    
    # Initialize database
    if not await db.init_db():
        print("❌ Failed to connect to MongoDB!")
        return
    
    print("💾 Database connected successfully!")
    
    # Start bot
    await bot.start()
    
    # Send startup message
    try:
        await bot.send_message(
            Config.OWNER_ID,
            f"🤖 **Bot Started Successfully!**\n\n"
            f"✅ Database: Connected\n"
            f"✅ Flask: Running on port {Config.PORT}\n"
            f"✅ Pyrogram: v2.0.106\n\n"
            f"Made with ❤️ by @asbhai_bsr"
        )
    except:
        pass
    
    print("✅ Bot is now running! Press Ctrl+C to stop.")
    
    # Keep running
    await idle()
    
    # Stop bot
    await bot.stop()

# ========== RUN BOT ==========
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Bot stopped by user!")
    except Exception as e:
        print(f"❌ Error: {e}")
