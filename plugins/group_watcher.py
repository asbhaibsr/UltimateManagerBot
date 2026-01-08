# plugins/group_watcher.py

import asyncio
import re
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from utils import check_movie_spelling, extract_movie_name, format_movie_info, get_movie_details
from config import Config

@Client.on_chat_member_updated()
async def welcome_new_member(client, chat_member_updated):
    """Welcome new members"""
    if chat_member_updated.new_chat_member and chat_member_updated.new_chat_member.status == enums.ChatMemberStatus.MEMBER:
        group = await db.get_group(chat_member_updated.chat.id)
        if not group or not group["settings"].get("welcome"):
            return
        
        user = chat_member_updated.new_chat_member.user
        welcome_text = f"""
👋 Welcome {user.mention} to {chat_member_updated.chat.title}!

🎬 This group uses Movie Filter Bot for:
• Movie spell check
• Movie details
• Force join system
• Auto file management

Type `/help` for commands!
        """
        
        try:
            await client.send_message(
                chat_member_updated.chat.id,
                welcome_text,
                reply_to_message_id=chat_member_updated.message_id
            )
        except:
            pass

@Client.on_message(filters.group & filters.text & ~filters.command(["start", "help", "connect", "settings", "search", "moviedetails", "request", "autodelete", "linkfsub", "fsubstatus"]))
async def group_text_handler(client, message):
    """Handle group messages for spell check - FIXED"""
    if not message.text or len(message.text.strip()) < 3:
        return
    
    group = await db.get_group(message.chat.id)
    if not group or not group["settings"].get("spell_check"):
        return
    
    # Update stats
    await db.update_group_stats(message.chat.id, "total_messages")
    
    # Check if message looks like movie request
    text_lower = message.text.lower()
    movie_keywords = ['movie', 'film', 'series', 'season', 'episode', 'download', 'watch', 'please', 'send']
    
    if any(keyword in text_lower for keyword in movie_keywords) and len(text_lower) > 5:
        # Spell check - FIXED AWAIT ISSUE
        correct_name, year, status = await check_movie_spelling(message.text)
        
        if status == "correct" and correct_name:
            # If correct, provide details
            try:
                movie_data = await get_movie_details(correct_name)
                if movie_data:
                    info = format_movie_info(movie_data)
                    poster = movie_data.get("poster")
                    
                    buttons = [
                        [InlineKeyboardButton("🎬 Get This Movie", url=f"https://t.me/asfilter_bot?start={correct_name.replace(' ', '+')}")]
                    ]
                    
                    if poster:
                        sent = await message.reply_photo(
                            poster,
                            caption=info[:1024],  # Telegram limit
                            reply_to_message_id=message.id,
                            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
                        )
                    else:
                        sent = await message.reply(
                            info[:4096],  # Telegram limit
                            reply_to_message_id=message.id,
                            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
                        )
                    
                    # Auto delete after 5 minutes
                    if group["settings"].get("auto_delete_files"):
                        await asyncio.sleep(300)
                        try:
                            await sent.delete()
                        except:
                            pass
            except Exception as e:
                print(f"Movie details error: {e}")
        
        elif status in ["suggest", "ai_corrected", "ai_suggest"] and correct_name:
            # FIXED: Now correct_name is string, not coroutine
            suggestion_text = f"""
❌ **Possible Spelling Mistake!**

👤 **User:** {message.from_user.mention}
📝 **You typed:** {message.text[:50]}...

✅ **Did you mean:** {correct_name} ({year if year != 'N/A' else ''})

💡 **Tip:** Type only movie name without extra words like "send", "link", "dedo", etc.
            """
            
            sent = await message.reply(
                suggestion_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 Search This", callback_data=f"search_{correct_name.replace(' ', '_')}")]
                ])
            )
            
            # Auto delete after 30 seconds
            await asyncio.sleep(30)
            try:
                await sent.delete()
            except:
                pass

# ... rest of the code remains same ...
