#  plugins/group_watcher.py 

import asyncio
import re
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from utils import check_movie_spelling, extract_movie_name, format_movie_info
from config import Config
from imdb import Cinemagoer

ia = Cinemagoer()

@Client.on_chat_member_updated()
async def welcome_new_member(client, chat_member_updated):
    """Welcome new members"""
    if chat_member_updated.new_chat_member and chat_member_updated.new_chat_member.status == enums.ChatMemberStatus.MEMBER:
        group = await db.get_group(chat_member_updated.chat.id)
        if not group or not group["settings"].get("welcome"):
            return
        
        user = chat_member_updated.new_chat_member.user
        welcome_text = f"""
👋 Welcome {user.mention} to **{chat_member_updated.chat.title}**!

🎬 This group uses **Movie Filter Bot** for:
• Movie spell check
• Movie details
• Force join system
• Auto file management

Type /help for commands!
        """
        
        try:
            await client.send_message(
                chat_member_updated.chat.id,
                welcome_text,
                reply_to_message_id=chat_member_updated.message_id
            )
        except:
            pass

@Client.on_message(filters.group & filters.text & ~filters.command(["start", "help", "connect"]))
async def group_text_handler(client, message):
    """Handle group messages for spell check"""
    if not message.text or len(message.text.strip()) < 3:
        return
    
    group = await db.get_group(message.chat.id)
    if not group or not group["settings"].get("spell_check"):
        return
    
    # Update stats
    await db.update_group_stats(message.chat.id, "total_messages")
    
    # Check if message looks like movie request
    text_lower = message.text.lower()
    movie_keywords = ['movie', 'film', 'series', 'season', 'episode', 'download', 'watch']
    
    if any(keyword in text_lower for keyword in movie_keywords) and len(text_lower) > 5:
        # Spell check
        correct_name, year, status = check_movie_spelling(message.text)
        
        if status == "correct":
            # If correct, optionally provide details
            if "details" in text_lower or "info" in text_lower:
                try:
                    results = ia.search_movie(correct_name)
                    if results:
                        movie = results[0]
                        ia.update(movie)
                        
                        info = format_movie_info(movie)
                        photo = movie.get('full-size cover url')
                        
                        if photo:
                            sent = await message.reply_photo(
                                photo,
                                caption=info,
                                reply_to_message_id=message.id
                            )
                        else:
                            sent = await message.reply(
                                info,
                                reply_to_message_id=message.id
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
            # Delete wrong message and suggest correction
            try:
                await message.delete()
            except:
                pass
            
            suggestion_text = f"""
❌ **Possible Spelling Mistake!**

👤 **User:** {message.from_user.mention}
📝 **You typed:** `{message.text[:50]}...`

✅ **Did you mean:** **{correct_name}** ({year if year != 'N/A' else ''})

💡 **Tip:** Type only movie name without extra words like "send", "link", "dedo", etc.
            """
            
            sent = await message.reply(
                suggestion_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 Search This", callback_data=f"search_{correct_name}")]
                ])
            )
            
            # Auto delete after 30 seconds
            await asyncio.sleep(30)
            try:
                await sent.delete()
            except:
                pass

@Client.on_message(filters.group & (filters.command("request") | filters.regex(r'^#request')))
async def request_handler(client, message):
    """Handle movie requests"""
    group = await db.get_group(message.chat.id)
    if not group:
        return
    
    query = message.text.replace("/request", "").replace("#request", "").strip()
    if not query or len(query) < 2:
        await message.reply("Please provide movie name!\nExample: `/request Avengers Endgame`")
        return
    
    # Clean the query
    movie_name = extract_movie_name(query)
    
    # Save request to database
    await db.add_request(message.from_user.id, message.chat.id, movie_name)
    
    # Notify group
    text = f"""
📩 **New Movie Request!**

🎬 **Movie:** `{movie_name}`
👤 **Requested by:** {message.from_user.mention}
👥 **Group:** {message.chat.title}

✅ Request saved! The admin will process it soon.
    """
    
    # Tag owner if available
    owner_id = group.get("owner_id")
    if owner_id:
        try:
            owner = await client.get_users(owner_id)
            text += f"\n👑 **Group Owner:** {owner.mention}"
        except:
            pass
    
    await message.reply(text)
    
    # Notify owner in private
    try:
        if owner_id:
            await client.send_message(
                owner_id,
                f"📥 New movie request in {message.chat.title}\n"
                f"🎬 Movie: {movie_name}\n"
                f"👤 User: {message.from_user.mention}\n"
                f"💬 Message: {message.link}"
            )
    except:
        pass

@Client.on_callback_query(filters.regex(r"^search_"))
async def search_callback(client, callback):
    """Handle search from callback"""
    movie_name = callback.data.split("_", 1)[1]
    
    try:
        results = ia.search_movie(movie_name)
        if results:
            movie = results[0]
            ia.update(movie)
            
            info = format_movie_info(movie)
            photo = movie.get('full-size cover url')
            
            if photo:
                await callback.message.reply_photo(photo, caption=info)
            else:
                await callback.message.reply(info)
            
            await callback.answer("Search completed!")
        else:
            await callback.answer("No results found!", show_alert=True)
    except Exception as e:
        await callback.answer("Error searching!", show_alert=True)
