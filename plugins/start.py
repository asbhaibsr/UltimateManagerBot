#  start.py

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from config import Config
from database import db

@Client.on_message(filters.command("start"))
async def start_command(client, message: Message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    
    # Add user to database
    await db.add_user(user_id, name, message.from_user.username)
    
    # Welcome message with buttons
    welcome_text = f"""
👋 **Hello {name}!**

Welcome to **Movie Filter Bot** 🤖

I can help you:
✅ Find movie details
✅ Correct movie spellings
✅ Auto-filter movies in groups
✅ Force join system
✅ And much more!

Add me to your group and make me admin to get started!
    """
    
    buttons = [
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true")],
        [
            InlineKeyboardButton("📖 Help", callback_data="help_main"),
            InlineKeyboardButton("🌟 Premium", callback_data="premium_info")
        ],
        [InlineKeyboardButton("📞 Contact", url="https://t.me/asbhaibsr")]
    ]
    
    await message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex(r"^help_main$"))
async def help_main(client, callback):
    help_text = """
**🤖 Bot Commands Guide**

**📌 Admin Commands:**
/connect - Connect bot to group
/settings - Group settings
/stats - Bot statistics
/broadcast - Broadcast message (Owner only)

**🔍 Movie Commands:**
/search [movie] - Search movie
/moviedetails [movie] - Get movie details
/request [movie] - Request a movie

**⚙️ Group Commands:**
/linkfsub [channel_id] - Setup force join
/fsubstatus - Check force join status
/autodelete [minutes] - Set auto delete time

**👤 User Commands:**
/start - Start the bot
/help - Show this help
/font [text] - Convert text to stylish fonts

**🔧 Setup Instructions:**
1. Add bot to group
2. Make bot admin
3. Use /connect in group
4. Configure settings
    """
    
    buttons = [
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")],
        [InlineKeyboardButton("🌟 Premium Features", callback_data="premium_info")]
    ]
    
    await callback.message.edit_text(
        help_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex(r"^premium_info$"))
async def premium_info(client, callback):
    premium_text = f"""
**🌟 Premium Features**

**✅ Benefits:**
• No broadcast messages
• Priority support
• Custom welcome messages
• Advanced spell check
• Unlimited movie requests
• Auto-delete files feature
• Detailed analytics

**💰 Pricing:**
• 1 Month - ₹{Config.PREMIUM_PRICE_PER_MONTH}
• 2 Months - ₹{Config.PREMIUM_PRICE_PER_MONTH * 2}
• 3 Months - ₹{Config.PREMIUM_PRICE_PER_MONTH * 3}
• Each additional month +₹{Config.PREMIUM_PRICE_PER_MONTH}

**💳 Payment Methods:**
• UPI
• Paytm
• PhonePe

**📞 Contact for Premium:**
@asbhaibsr
    """
    
    buttons = [
        [InlineKeyboardButton("💳 Buy Premium", url="https://t.me/asbhaibsr")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
    ]
    
    await callback.message.edit_text(
        premium_text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^back_to_start$"))
async def back_to_start(client, callback):
    await start_command(client, callback.message)
