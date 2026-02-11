import asyncio
import datetime
import random
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus
from config import Config
from database import *
from utils import MovieBotUtils

# ================ MOVIE OF THE DAY (FULLY DYNAMIC - NO HARDCODING) ================
@app.on_message(filters.command(["movieoftheday", "motd"]))
async def movie_of_the_day(client: Client, message: Message):
    """Fully dynamic Movie of the Day using OMDb only"""
    
    if not Config.OMDB_API_KEY:
        await message.reply_text("❌ **OMDb API Key Missing**\n\nPlease set OMDB_API_KEY in config.")
        return
    
    msg = await message.reply_text("🎬 **Fetching Movie of the Day...**")
    
    # Get random movie from OMDb
    movie = await MovieBotUtils.get_random_movie()
    
    if movie:
        motd_text = f"""
🎬 **MOVIE OF THE DAY** 🎬

🌟 **{movie['title']} ({movie['year']})**
🎭 **Genre:** {movie['genre']}
⭐ **IMDb Rating:** {movie['rating']}/10

📅 **Featured:** {datetime.datetime.now().strftime('%d %B %Y')}

💡 **Tip:** Use `/request {movie['title']}` to request this movie!

Happy Watching! 🍿
"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Request This Movie", switch_inline_query_current_chat=f"/request {movie['title']}")]
        ])
        
        await msg.edit_text(motd_text, reply_markup=buttons)
    else:
        await msg.edit_text(
            "❌ **Could not fetch Movie of the Day**\n\n"
            "Please try again later or check OMDb API key."
        )

# ================ GROUP STATISTICS ================
@app.on_message(filters.command(["groupstats", "ginfo"]) & filters.group)
async def group_statistics(client: Client, message: Message):
    """Show group statistics"""
    try:
        chat = await client.get_chat(message.chat.id)
        member_count = await client.get_chat_members_count(message.chat.id)
        
        admin_count = 0
        bot_count = 0
        
        async for member in client.get_chat_members(message.chat.id):
            if member.user.is_bot:
                bot_count += 1
            if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                if not member.user.is_bot:
                    admin_count += 1
        
        stats_text = f"""
📊 **GROUP STATISTICS**

🏷️ **Name:** {chat.title}
👥 **Total Members:** {member_count}
👑 **Admins:** {admin_count}
🤖 **Bots:** {bot_count}
👤 **Active Users:** {member_count - bot_count}

🆔 **Group ID:** `{message.chat.id}`

⚡ **Bot Features:**
• Spelling Check: ✅
• Auto Accept: {await get_auto_accept(message.chat.id)}
• AI Chat: {await get_settings(message.chat.id)}.get("ai_chat_on", False)
"""
        
        await message.reply_text(stats_text)
        
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")

# ================ AUTO DELETE COMMAND MESSAGES ================
@app.on_message(filters.command([
    "start", "help", "settings", "addfsub", "stats", "ai", 
    "request", "ping", "id", "google", "anime", "cleanjoin", "setwelcome"
]) & filters.group)
async def auto_delete_commands(client: Client, message: Message):
    """Auto delete command messages"""
    asyncio.create_task(MovieBotUtils.auto_delete_message(client, message, 300))

# ================ CHANNEL ID HANDLER ================
@app.on_message(filters.private & filters.regex(r'^-100\d+$'))
async def handle_channel_id(client: Client, message: Message):
    """Handle channel ID for auto accept setup"""
    channel_id = int(message.text.strip())
    user_id = message.from_user.id
    
    try:
        chat = await client.get_chat(channel_id)
        
        # Check if user is admin
        member = await client.get_chat_member(channel_id, user_id)
        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await message.reply_text(f"❌ **You are not admin in {chat.title}!**")
            return
        
        # Check if bot is admin
        try:
            bot_member = await client.get_chat_member(channel_id, (await client.get_me()).id)
            if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                await message.reply_text(f"❌ **I'm not admin in {chat.title}!**")
                return
        except:
            await message.reply_text(f"❌ **I'm not in {chat.title}!**")
            return
        
        # Enable auto accept
        await set_auto_accept(channel_id, True)
        
        await message.reply_text(
            f"✅ **Auto Accept Enabled!**\n\n"
            f"**Channel:** {chat.title}\n"
            f"**ID:** `{channel_id}`\n\n"
            f"I will now auto-approve join requests."
        )
        
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")

# ================ PREMIUM STATS ================
@app.on_message(filters.command("premiumstats") & filters.user(Config.OWNER_ID))
async def premium_stats_cmd(client: Client, message: Message):
    """Show premium groups"""
    count = 0
    premium_list = []
    all_groups = await get_all_groups()
    
    for g in all_groups:
        if await check_is_premium(g):
            count += 1
            try:
                chat = await client.get_chat(g)
                premium_list.append(f"• {chat.title} (`{g}`)")
            except:
                premium_list.append(f"• Unknown (`{g}`)")
    
    text = f"**💎 Premium Groups:** {count}\n\n"
    if premium_list:
        text += "\n".join(premium_list[:10])
        if len(premium_list) > 10:
            text += f"\n\n...and {len(premium_list) - 10} more"
    else:
        text += "No premium groups yet."
    
    await message.reply_text(text)
