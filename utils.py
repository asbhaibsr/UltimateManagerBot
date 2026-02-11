import asyncio
import datetime
import random
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus
from config import Config
from database import *
from utils import MovieBotUtils

# ================ GROUP MANAGEMENT COMMANDS ================
async def is_group_admin(client, chat_id, user_id):
    """Check if user is admin in group"""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

# --- CLEAN GROUP COMMAND ---
@app.on_message(filters.command(["clean", "cleangroup"]) & filters.group)
async def clean_group_command(client: Client, message: Message):
    """Clean group from inactive members"""
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
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

# --- PINNED MOVIES SYSTEM ---
@app.on_message(filters.command(["pinmovie", "feature"]) & filters.group)
async def pin_movie_command(client: Client, message: Message):
    """Pin important movie messages"""
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
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
        await client.pin_chat_message(
            message.chat.id,
            message.reply_to_message.id,
            disable_notification=False
        )
        
        confirmation = await message.reply_text(
            "📌 **Movie Pinned Successfully!**\n\n"
            "This movie will stay at the top for easy access. 🎬"
        )
        await asyncio.sleep(5)
        await confirmation.delete()
        await message.delete()
        
    except Exception as e:
        await message.reply_text(f"❌ **Error:** Cannot pin message. Make sure I have pin permissions!")

# --- DYNAMIC MOVIE OF THE DAY (UPDATED) ---
@app.on_message(filters.command(["movieoftheday", "motd"]) & filters.group)
async def movie_of_the_day(client: Client, message: Message):
    """Fully Dynamic Movie of the Day using OMDb"""
    
    # Random popular keywords for dynamic discovery
    keywords = ["Avengers", "Batman", "Spider", "Iron", "Mission", "Fast", "Harry", "Jawan", "Pathaan", "KGF", "Pushpa", "Avatar", "Titanic", "Inception"]
    random_query = random.choice(keywords)
    
    # OMDb se fetch karein
    data = await MovieBotUtils.get_omdb_info(random_query)
    
    if "Movie Information" in data:
        # Text ko thoda modify karein header ke liye
        content = data.replace("🎬 **Movie Information** 🎬", f"🎬 **MOVIE OF THE DAY** 🎬\n\n✨ **Featured Pick:** {random_query}")
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 Search This Movie", switch_inline_query_current_chat=f"/request {random_query}")]
        ])
        await message.reply_text(content, reply_markup=buttons)
    else:
        # Fallback agar API fail ho
        fallback_movies = [
            {"title": "Kalki 2898 AD", "year": "2024", "genre": "Sci-Fi/Action"},
            {"title": "Pushpa 2: The Rule", "year": "2024", "genre": "Action/Drama"},
            {"title": "Jawan", "year": "2023", "genre": "Action/Thriller"},
            {"title": "Animal", "year": "2023", "genre": "Action/Drama"},
            {"title": "Gadar 2", "year": "2023", "genre": "Action/Drama"},
            {"title": "OMG 2", "year": "2023", "genre": "Drama/Comedy"},
        ]
        
        movie = random.choice(fallback_movies)
        
        motd_text = f"""
🎬 **MOVIE OF THE DAY** 🎬

🌟 **{movie['title']} ({movie['year']})**
🎭 **Genre:** {movie['genre']}
📅 **Featured:** {datetime.datetime.now().strftime('%d %B %Y')}

📌 **Why Watch Today?**
This movie is trending with excellent reviews!

💬 **Share your reviews below!**
"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 Search This Movie", switch_inline_query_current_chat=f"/request {movie['title']}")],
            [InlineKeyboardButton("📋 Request Similar", callback_data="request_similar")]
        ])
        
        await message.reply_text(motd_text, reply_markup=buttons)

# --- QUICK POLL FOR MOVIES ---
@app.on_message(filters.command(["poll", "moviepoll"]) & filters.group)
async def create_movie_poll(client: Client, message: Message):
    """Create a movie poll"""
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
        msg = await message.reply_text("❌ **Only admins can create polls!**")
        await asyncio.sleep(5)
        await msg.delete()
        return
    
    if len(message.command) < 2:
        options = ["Kalki 2898 AD", "Pushpa 2", "Jawan", "Animal", "Gadar 2"]
    else:
        options = message.command[1:]
        if len(options) < 2:
            await message.reply_text("❌ **Please provide at least 2 options!**")
            return
        if len(options) > 10:
            options = options[:10]
    
    try:
        poll = await client.send_poll(
            chat_id=message.chat.id,
            question="🎬 **Which movie should we feature next?**",
            options=options,
            is_anonymous=False,
            allows_multiple_answers=False
        )
        
        await client.pin_chat_message(message.chat.id, poll.id)
        await message.delete()
        
    except Exception as e:
        await message.reply_text(f"❌ **Cannot create poll:** {str(e)}")

# --- BULK DELETE MESSAGES ---
@app.on_message(filters.command(["purge", "clearchat"]) & filters.group)
async def purge_messages(client: Client, message: Message):
    """Delete multiple messages"""
    if not await is_group_admin(client, message.chat.id, message.from_user.id):
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
        start_id = message.reply_to_message.id
        end_id = message.id
        
        for msg_id in range(start_id, end_id + 1):
            message_ids.append(msg_id)
        
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

# --- GROUP STATISTICS ---
@app.on_message(filters.command(["groupstats", "ginfo"]) & filters.group)
async def group_statistics(client: Client, message: Message):
    """Show group statistics"""
    try:
        chat = await client.get_chat(message.chat.id)
        member_count = await client.get_chat_members_count(message.chat.id)
        
        admin_count = 0
        bot_count = 0
        deleted_count = 0
        
        async for member in client.get_chat_members(message.chat.id):
            if member.user.is_bot:
                bot_count += 1
            if member.user.is_deleted:
                deleted_count += 1
            if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                if not member.user.is_bot:
                    admin_count += 1
        
        stats_text = f"""
📊 **GROUP STATISTICS**

🏷️ **Name:** {chat.title}
👥 **Total Members:** {member_count}
👑 **Admins:** {admin_count}
🤖 **Bots:** {bot_count}
🗑️ **Deleted Accounts:** {deleted_count}
👤 **Active Users:** {member_count - bot_count - deleted_count}

📅 **Created:** {chat.date.strftime('%d %b %Y') if chat.date else 'N/A'}
🔗 **Username:** @{chat.username if chat.username else 'Private'}
🆔 **Group ID:** `{message.chat.id}`

📈 **Activity:** Active
⚡ **Status:** Running
"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_group_stats")]
        ])
        
        await message.reply_text(stats_text, reply_markup=buttons)
        
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")

# --- AUTO RESPONDER FOR COMMON QUESTIONS ---
@app.on_message(filters.group & filters.regex(r'(?i)(how|where|when).*(download|watch|get).*(movie|film|series)'))
async def auto_respond_download(client: Client, message: Message):
    """Auto respond to common download questions"""
    if await is_group_admin(client, message.chat.id, message.from_user.id):
        return
    
    response_text = """
🔍 **Looking for Movies?**

📌 **How to Find Movies:**
1. Use proper format: `Movie Name (Year)`
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
    await asyncio.sleep(120)
    await response.delete()

# --- WELCOME MESSAGE IMPROVEMENT ---
async def send_improved_welcome(client, chat_id, user):
    """Send improved welcome message with user photo"""
    try:
        welcome_text = f"""
🎉 **WELCOME TO THE COMMUNITY!** 🎉

👤 **New Member:** {user.mention}
🆔 **User ID:** `{user.id}`
📅 **Joined:** {datetime.datetime.now().strftime('%d %B %Y')}

✨ **Group Rules:**
✅ Use proper movie format
✅ No spam or links
✅ Respect all members
✅ Follow admin instructions

🎬 **Getting Started:**
• Use `/help` for commands
• Check pinned messages
• Request movies properly

Enjoy your stay! 🍿
"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Group Rules", callback_data="show_rules")],
            [InlineKeyboardButton("🎬 Request Movie", switch_inline_query_current_chat="/request ")],
            [InlineKeyboardButton("🤖 Bot Help", callback_data="help_main")]
        ])
        
        if user.photo:
            try:
                welcome_msg = await client.send_photo(
                    chat_id,
                    photo=user.photo.big_file_id,
                    caption=welcome_text,
                    reply_markup=buttons
                )
            except:
                welcome_msg = await client.send_message(
                    chat_id,
                    welcome_text,
                    reply_markup=buttons
                )
        else:
            welcome_msg = await client.send_message(
                chat_id,
                welcome_text,
                reply_markup=buttons
            )
        
        await asyncio.sleep(300)
        await welcome_msg.delete()
        
    except Exception as e:
        print(f"Welcome error: {e}")

# --- CALLBACK HANDLERS FOR NEW FEATURES ---
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
✅ Bio Protection

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
   • Use: `Movie Name (Year)`
   • Example: `Kalki 2898 AD (2024)`
   • Series: `Stranger Things S01E01`

2. 🚫 **Strictly Prohibited:**
   • Direct download links
   • Spam messages
   • Abusive language
   • Promotion without permission
   • Links/Usernames in bio

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

@app.on_callback_query(filters.regex(r'^request_similar$'))
async def request_similar_callback(client, query):
    """Request similar movies"""
    await query.message.reply_text(
        "🎬 **Request Similar Movie**\n\n"
        "Please use the format:\n"
        "`/request Movie Name`\n\n"
        "Example: `/request Inception`"
    )
    await query.answer()

# --- SCHEDULED MOVIE UPDATES ---
async def scheduled_movie_updates(client: Client):
    """Send scheduled movie updates to groups"""
    while True:
        try:
            await asyncio.sleep(6 * 3600)
            
            groups = await get_all_groups()
            
            for group_id in groups:
                try:
                    group_data = await get_group(group_id)
                    if not group_data or not group_data.get("active", True):
                        continue
                    
                    # Get dynamic movie info
                    keywords = ["Avengers", "Batman", "Spider", "Iron", "Mission", "Fast", "Harry"]
                    random_query = random.choice(keywords)
                    movie_info = await MovieBotUtils.get_omdb_info(random_query)
                    
                    if "Movie Information" in movie_info:
                        update_text = f"""
🎬 **DAILY MOVIE UPDATE** 🎬

{movie_info}

💡 **Tip:** Use `/request` command to request this movie!

Happy Watching! 🍿
"""
                    else:
                        update_text = """
🎬 **DAILY MOVIE UPDATE** 🎬

🌟 **Trending Now:**
1. Kalki 2898 AD
2. Pushpa 2 The Rule
3. Jawan
4. Animal
5. Gadar 2

🎯 **Today's Recommendation:**
Watch **Kalki 2898 AD** for an epic sci-fi experience!

💡 **Tip:** Use proper format when requesting movies.

Happy Watching! 🍿
"""
                    
                    await client.send_message(group_id, update_text)
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"Scheduled update error: {e}")
            await asyncio.sleep(60)
