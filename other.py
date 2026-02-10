import asyncio
import datetime
import re
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from config import Config
from database import *
from utils import MovieBotUtils

# ================ HELPER ================
# Database wala is_admin use karenge consistency ke liye

# ================ CLEAN GROUP COMMAND ================
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

# ================ BIO PROTECTION ADMIN COMMANDS (NEW) ================
@app.on_message(filters.command("bioconfig") & filters.group)
async def bio_config_command(client: Client, message: Message):
    """Configure bio protection settings"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can configure bio protection!")
    
    if len(message.command) < 2:
        # Show current settings
        settings = await get_bio_protection(message.chat.id)
        status = "✅ ON" if settings["enabled"] else "❌ OFF"
        
        text = (
            f"🛡️ **Bio Protection Settings**\n\n"
            f"Status: {status}\n"
            f"Warning Limit: {settings['warn_limit']}\n"
            f"Penalty: {settings['penalty'].title()}\n\n"
            f"**Usage:**\n"
            f"/bioconfig on - Enable bio protection\n"
            f"/bioconfig off - Disable bio protection\n"
            f"/bioconfig limit <number> - Set warning limit (3-5)\n"
            f"/bioconfig penalty <mute/ban> - Set penalty"
        )
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Enable", callback_data="bio_on"),
             InlineKeyboardButton("❌ Disable", callback_data="bio_off")],
            [InlineKeyboardButton("🔢 Set Limit", callback_data="bio_limit"),
             InlineKeyboardButton("⚖️ Set Penalty", callback_data="bio_penalty")]
        ])
        
        await message.reply_text(text, reply_markup=buttons)
        return
    
    action = message.command[1].lower()
    
    if action == "on":
        await set_bio_protection(message.chat.id, True)
        await message.reply("✅ Bio Protection enabled!")
    
    elif action == "off":
        await set_bio_protection(message.chat.id, False)
        await message.reply("❌ Bio Protection disabled!")
    
    elif action == "limit" and len(message.command) > 2:
        try:
            limit = int(message.command[2])
            if 3 <= limit <= 5:
                settings = await get_bio_protection(message.chat.id)
                await set_bio_protection(
                    message.chat.id, 
                    settings["enabled"], 
                    limit, 
                    settings["penalty"]
                )
                await message.reply(f"✅ Warning limit set to {limit}")
            else:
                await message.reply("❌ Limit must be between 3 and 5")
        except:
            await message.reply("❌ Invalid number")
    
    elif action == "penalty" and len(message.command) > 2:
        penalty = message.command[2].lower()
        if penalty in ["mute", "ban"]:
            settings = await get_bio_protection(message.chat.id)
            await set_bio_protection(
                message.chat.id, 
                settings["enabled"], 
                settings["warn_limit"], 
                penalty
            )
            await message.reply(f"✅ Penalty set to {penalty}")
        else:
            await message.reply("❌ Penalty must be 'mute' or 'ban'")

# ================ WHITELIST COMMANDS (NEW) ================
@app.on_message(filters.command("biowhitelist") & filters.group)
async def bio_whitelist_command(client: Client, message: Message):
    """Add user to bio protection whitelist"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can whitelist users!")
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
        except:
            return await message.reply("❌ Invalid user ID!")
    else:
        return await message.reply("❌ Reply to a user or provide user ID!")
    
    await add_whitelist(message.chat.id, user_id)
    await reset_bio_warnings(message.chat.id, user_id)
    
    try:
        user = await client.get_users(user_id)
        await message.reply(f"✅ {user.mention} added to bio protection whitelist!")
    except:
        await message.reply(f"✅ User {user_id} added to whitelist!")

@app.on_message(filters.command("biounwhitelist") & filters.group)
async def bio_unwhitelist_command(client: Client, message: Message):
    """Remove user from bio protection whitelist"""
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can unwhitelist users!")
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
        except:
            return await message.reply("❌ Invalid user ID!")
    else:
        return await message.reply("❌ Reply to a user or provide user ID!")
    
    await remove_whitelist(message.chat.id, user_id)
    
    try:
        user = await client.get_users(user_id)
        await message.reply(f"❌ {user.mention} removed from bio protection whitelist!")
    except:
        await message.reply(f"❌ User {user_id} removed from whitelist!")

# ================ COPYRIGHT PROTECTION (NEW) ================
@app.on_message(filters.group & filters.text & ~filters.command(["purge", "clearchat"]), group=5)
async def copyright_monitor(client, message):
    """Monitor and protect against copyright claims"""
    settings = await get_settings(message.chat.id)
    
    if not settings.get("copyright_protection", False):
        return
    
    # Copyright keywords
    copyright_keywords = [
        r'copyright', r'dmca', r'infringement', r'strike', 
        r'legal', r'notice', r'violation', r'takedown',
        r'pirate', r'illegal', r'download', r'leak',
        r'report', r'complaint', r'action', r'warning'
    ]
    
    message_lower = message.text.lower()
    
    # Check for copyright related messages
    is_copyright_issue = False
    for keyword in copyright_keywords:
        if re.search(keyword, message_lower):
            is_copyright_issue = True
            break
    
    if is_copyright_issue:
        try:
            await message.delete()
            
            # Fake legal response
            response_text = (
                "🛡️ **Copyright Protection System Activated**\n\n"
                "⚠️ **Important Notice:**\n"
                "This group operates in compliance with DMCA regulations.\n"
                "We do not host or distribute copyrighted content illegally.\n\n"
                "🔒 **Action Taken:**\n"
                "• Message removed for safety\n"
                "• No actual copyright infringement exists\n"
                "• Group protection protocols activated\n\n"
                "📞 **For legitimate concerns:**\n"
                "Contact group administration via proper channels.\n\n"
                "✅ **Status:** Group is safe and compliant"
            )
            
            warning_msg = await message.reply_text(response_text)
            await asyncio.sleep(15)
            await warning_msg.delete()
            
            # Log to owner
            if Config.LOGS_CHANNEL:
                log_text = (
                    f"⚖️ **Copyright Alert**\n\n"
                    f"👤 User: {message.from_user.mention}\n"
                    f"💬 Message: {message.text[:100]}...\n"
                    f"📊 Group: {message.chat.title}\n"
                    f"🆔 Group ID: {message.chat.id}\n"
                    f"⏰ Time: {datetime.datetime.now()}"
                )
                await client.send_message(Config.LOGS_CHANNEL, log_text)
                
        except Exception as e:
            print(f"Copyright protection error: {e}")

# ================ PINNED MOVIES SYSTEM (RESTORED) ================
@app.on_message(filters.command(["pinmovie", "feature"]) & filters.group)
async def pin_movie_command(client: Client, message: Message):
    """Pin important movie messages"""
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ **Only admins can pin messages!**")
        await asyncio.sleep(5)
        await msg.delete()
        return
    
    if not message.reply_to_message:
        msg = await message.reply_text("❌ **Reply to a movie message to pin it!**")
        await asyncio.sleep(5)
        await msg.delete()
        return
    
    try:
        # Pin the message
        await client.pin_chat_message(
            message.chat.id,
            message.reply_to_message.id,
            disable_notification=False
        )
        
        # Send confirmation
        confirmation = await message.reply_text(
            "📌 **Movie Pinned Successfully!**\n\n"
            "This movie will stay at the top for easy access. 🎬"
        )
        await asyncio.sleep(5)
        await confirmation.delete()
        await message.delete()
        
    except Exception as e:
        await message.reply_text(f"❌ **Error:** Cannot pin message. Make sure I have pin permissions!")

# ================ BULK DELETE MESSAGES (RESTORED) ================
@app.on_message(filters.command(["purge", "clearchat"]) & filters.group)
async def purge_messages(client: Client, message: Message):
    """Delete multiple messages"""
    if not await is_admin(message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ **Only admins can purge messages!**")
        await asyncio.sleep(5)
        await msg.delete()
        return
    
    if not message.reply_to_message:
        msg = await message.reply_text("❌ **Reply to a message to start purging from there!**")
        await asyncio.sleep(5)
        await msg.delete()
        return
    
    try:
        message_ids = []
        # Reply wale message se lekar current message tak sab delete karo
        for i in range(message.reply_to_message.id, message.id + 1):
            message_ids.append(i)
        
        # Delete in chunks of 100 (Telegram limit)
        for i in range(0, len(message_ids), 100):
            chunk = message_ids[i:i + 100]
            await client.delete_messages(message.chat.id, chunk)
            await asyncio.sleep(1)
        
        # Send confirmation
        confirmation = await message.reply_text(
            f"✅ **Purged {len(message_ids)} messages successfully!**"
        )
        await asyncio.sleep(5)
        await confirmation.delete()
        
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")

# ================ GROUP STATISTICS (RESTORED) ================
@app.on_message(filters.command(["groupstats", "ginfo"]) & filters.group)
async def group_statistics(client: Client, message: Message):
    """Show group statistics"""
    try:
        chat = await client.get_chat(message.chat.id)
        
        # Get member count
        member_count = await client.get_chat_members_count(message.chat.id)
        
        # Get admin count
        admin_count = 0
        async for member in client.get_chat_members(message.chat.id, filter="administrators"):
            admin_count += 1
        
        # Get bot count
        bot_count = 0
        async for member in client.get_chat_members(message.chat.id):
            if member.user.is_bot:
                bot_count += 1
        
        stats_text = f"""
📊 **GROUP STATISTICS**

🏷️ **Name:** {chat.title}
👥 **Members:** {member_count}
👑 **Admins:** {admin_count}
🤖 **Bots:** {bot_count}
👤 **Users:** {member_count - bot_count}

📅 **Created:** {chat.date.strftime('%d %b %Y') if chat.date else 'N/A'}
🔗 **Username:** @{chat.username if chat.username else 'Private'}

📈 **Activity:** High
⚡ **Status:** Active
"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_group_stats")],
            [InlineKeyboardButton("📋 Export Data", callback_data="export_group_data")]
        ])
        
        await message.reply_text(stats_text, reply_markup=buttons)
        
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")

# ================ MOVIE OF THE DAY (RESTORED) ================
@app.on_message(filters.command(["movieoftheday", "motd"]) & filters.group)
async def movie_of_the_day(client: Client, message: Message):
    """Feature a movie of the day"""
    popular_movies = [
        {"title": "Kalki 2898 AD", "year": "2024", "genre": "Sci-Fi/Action", "rating": "8.5/10"},
        {"title": "Pushpa 2: The Rule", "year": "2024", "genre": "Action/Drama", "rating": "8.7/10"},
        {"title": "Jawan", "year": "2023", "genre": "Action/Thriller", "rating": "8.2/10"},
        {"title": "Animal", "year": "2023", "genre": "Action/Drama", "rating": "7.8/10"},
        {"title": "Gadar 2", "year": "2023", "genre": "Action/Drama", "rating": "7.5/10"},
        {"title": "OMG 2", "year": "2023", "genre": "Drama/Comedy", "rating": "8.0/10"},
    ]
    
    import random
    movie = random.choice(popular_movies)
    
    motd_text = f"""
🎬 **MOVIE OF THE DAY** 🎬

🌟 **{movie['title']} ({movie['year']})**
⭐ **Rating:** {movie['rating']}
🎭 **Genre:** {movie['genre']}
📅 **Featured:** {datetime.datetime.now().strftime('%d %B %Y')}

📌 **Why Watch Today?**
This movie is trending across platforms with excellent reviews from both critics and audience!

🎯 **Available in:** HD | 720p | 1080p
🔊 **Audio:** Hindi Dual Audio
📝 **Subtitles:** English

💬 **Group Discussion:** Share your reviews below!
"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎥 Watch Trailer", url="https://youtube.com")],
        [InlineKeyboardButton("⭐ Rate This Movie", callback_data="rate_movie")],
        [InlineKeyboardButton("📋 Request Similar", callback_data="request_similar")]
    ])
    
    await message.reply_text(motd_text, reply_markup=buttons)

# ================ QUICK POLL (RESTORED) ================
@app.on_message(filters.command(["poll", "moviepoll"]) & filters.group)
async def create_movie_poll(client: Client, message: Message):
    """Create a movie poll"""
    if len(message.command) < 2:
        options = ["Kalki 2898 AD", "Pushpa 2", "Jawan", "Animal", "Gadar 2"]
    else:
        options = message.command[1:]
    
    try:
        poll = await client.send_poll(
            chat_id=message.chat.id,
            question="🎬 **Which movie should we feature next?**",
            options=options,
            is_anonymous=False,
            allows_multiple_answers=False
        )
        
        # Pin the poll
        await client.pin_chat_message(message.chat.id, poll.id)
        
    except Exception as e:
        await message.reply_text(f"❌ **Cannot create poll:** {str(e)}")

# ================ AUTO RESPONDER (RESTORED) ================
@app.on_message(filters.group & filters.regex(r'(?i)(how|where|when).*(download|watch|get).*(movie|film|series)'))
async def auto_respond_download(client: Client, message: Message):
    """Auto respond to common download questions"""
    if await is_admin(message.chat.id, message.from_user.id):
        return
    
    response_text = """
🔍 **Looking for Movies?**

📌 **How to Find Movies:**
1. Use proper format: `Movie Name (Year) [Language]`
2. Check pinned messages for available content
3. Use `/request` command for specific movies
4. Browse through group files/search

🚫 **Important:**
• Direct download links are not allowed
• Respect copyright laws
• Support official platforms when possible

🎬 **Official Platforms:**
• Netflix, Amazon Prime, Hotstar
• YouTube Movies, Google Play
• Theater releases

Need help? Ask admins politely! 😊
"""
    
    response = await message.reply_text(response_text)
    await asyncio.sleep(120)  # Delete after 2 minutes
    await response.delete()

# ================ CALLBACKS (RESTORED) ================
@app.on_callback_query(filters.regex(r'^refresh_group_stats$'))
async def refresh_group_stats_callback(client, query):
    """Refresh group statistics"""
    try:
        chat = await client.get_chat(query.message.chat.id)
        member_count = await client.get_chat_members_count(query.message.chat.id)
        
        stats_text = f"""
📊 **GROUP STATISTICS (Refreshed)**

🏷️ **Name:** {chat.title}
👥 **Members:** {member_count}
📅 **Updated:** {datetime.datetime.now().strftime('%H:%M:%S')}

🔧 **Bot Features Active:**
✅ Spelling Correction
✅ Auto Format Check
✅ Movie Requests
✅ AI Assistance

⚡ **Status:** All Systems Operational
"""
        
        await query.message.edit_text(stats_text)
        await query.answer("✅ Stats refreshed!")
        
    except Exception as e:
        await query.answer("❌ Error refreshing stats!")

@app.on_callback_query(filters.regex(r'^show_rules$'))
async def show_rules_callback(client, query):
    """Show group rules"""
    rules_text = """
📜 **GROUP RULES**

1. 🎬 **Movie Format:**
   • Use: `Movie Name (Year) [Language]`
   • Example: `Kalki 2898 AD (2024) [Hindi]`
   • Series: `Stranger Things S01 E01`

2. 🚫 **Strictly Prohibited:**
   • Direct download links
   • Spam messages
   • Abusive language
   • Promotion without permission

3. ✅ **Allowed:**
   • Movie requests
   • Discussions/reviews
   • Helpful content
   • Proper queries

4. 👑 **Admin Authority:**
   • Admins can warn/mute/ban
   • Follow admin instructions
   • Respect all decisions

5. 🤝 **Community Spirit:**
   • Help other members
   • Share knowledge
   • Maintain positivity

⚠️ **Violation may result in mute/ban!**
"""
    
    await query.message.reply_text(rules_text)
    await query.answer("📜 Rules displayed!")

# ================ SCHEDULED MOVIE UPDATES ================
async def scheduled_movie_updates(client: Client):
    """Send scheduled movie updates to groups"""
    while True:
        try:
            await asyncio.sleep(6 * 3600)  # 6 hours
            
            groups = await get_all_groups()
            
            for group_id in groups:
                try:
                    group_data = await get_group(group_id)
                    if not group_data or not group_data.get("active", True):
                        continue
                    
                    update_text = """
🎬 **DAILY MOVIE UPDATE** 🎬

🌟 **New Releases:**
• Kalki 2898 AD (Hindi) - Now Available
• Pushpa 2 The Rule - Coming Soon

📈 **Trending Now:**
1. Animal (2023)
2. Jawan (2023)
3. Gadar 2 (2023)

🎯 **Today's Recommendation:**
Watch **Kalki 2898 AD** for an epic sci-fi experience!

💡 **Tip:** Use proper format when requesting movies.
🎥 **Download:** @asfilter_bot

Happy Watching! 🍿
"""
                    
                    await client.send_message(group_id, update_text)
                    await asyncio.sleep(1)
                    
                except:
                    continue
                    
        except Exception as e:
            print(f"Scheduled update error: {e}")
            await asyncio.sleep(60)

# ================ START SCHEDULED TASKS ================
async def start_scheduled_tasks(client: Client):
    """Start all scheduled tasks"""
    asyncio.create_task(scheduled_movie_updates(client))
