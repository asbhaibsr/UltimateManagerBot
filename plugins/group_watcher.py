import asyncio
import re
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from database import db
from utils import check_movie_spelling, extract_movie_name
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

@Client.on_message(filters.group & filters.text & ~filters.command(["start", "help", "connect", "settings", "search", "moviedetails", "request", "autodelete", "linkfsub", "fsubstatus", "stats", "broadcast", "addpremium"]))
async def group_text_handler(client, message: Message):
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
    movie_keywords = ['movie', 'film', 'series', 'season', 'episode', 'download', 'watch', 'dekho', 'dekhna']
    
    if any(keyword in text_lower for keyword in movie_keywords) and len(text_lower) > 5:
        # Spell check - FIXED: await the async function
        correct_name, year, status = await check_movie_spelling(message.text)
        
        if status in ["suggest", "omdb_found", "tmdb_found"] and correct_name:
            # Only suggest, don't delete
            suggestion_text = f"""
🎬 **Spelling Suggestion**

👤 **User:** {message.from_user.mention}
❌ **You typed:** `{message.text[:50]}{'...' if len(message.text) > 50 else ''}`

✅ **Did you mean:** **{correct_name}** ({year if year != 'N/A' else ''})

💡 **Tip:** Use `/search {correct_name}` for better results
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

@Client.on_message(filters.group & (filters.command("request") | filters.regex(r'^#request')))
async def request_handler(client, message: Message):
    """Handle movie requests"""
    group = await db.get_group(message.chat.id)
    if not group:
        return
    
    # Extract query
    if message.text.startswith("/request"):
        query = message.text.replace("/request", "").strip()
    else:
        query = message.text.replace("#request", "").strip()
    
    if not query or len(query) < 2:
        await message.reply("Please provide movie name!\nExample: /request Avengers Endgame")
        return
    
    # Clean the query
    movie_name = extract_movie_name(query)
    
    if not movie_name:
        await message.reply("Please enter a valid movie name!")
        return
    
    # Save request to database
    await db.add_request(message.from_user.id, message.chat.id, movie_name)
    
    # Notify group
    text = f"""
📩 **New Movie Request!**

🎬 **Movie:** {movie_name}
👤 **Requested by:** {message.from_user.mention}
👥 **Group:** {message.chat.title}

✅ Request saved! The admin will process it soon.
    """
    
    # Tag owner if available
    owner_id = group.get("owner_id")
    owner_mention = ""
    if owner_id:
        try:
            owner = await client.get_users(owner_id)
            owner_mention = f"\n👑 **Group Owner:** {owner.mention}"
        except:
            pass
    
    await message.reply(text + owner_mention)
    
    # Notify owner in private
    try:
        if owner_id:
            await client.send_message(
                owner_id,
                f"📥 New movie request in {message.chat.title}\n\n"
                f"🎬 Movie: {movie_name}\n"
                f"👤 User: {message.from_user.mention}\n"
                f"💬 Message: {message.link}"
            )
    except:
        pass

@Client.on_callback_query(filters.regex(r"^search_"))
async def search_callback(client, callback):
    """Handle search from callback"""
    movie_name = callback.data.split("_", 1)[1].replace('_', ' ')
    
    try:
        from imdb import Cinemagoer
        ia = Cinemagoer()
        results = ia.search_movie(movie_name)
        
        if results:
            movie = results[0]
            movie_data = {
                "title": movie.get('title', 'N/A'),
                "year": movie.get('year', 'N/A'),
                "rating": movie.get('rating', 'N/A'),
                "genres": ', '.join(movie.get('genres', [])),
                "plot": movie.get('plot outline', movie.get('plot', ['No plot available.'])),
                "imdb_id": movie.movieID
            }
            
            if isinstance(movie_data["plot"], list):
                movie_data["plot"] = movie_data["plot"][0] if movie_data["plot"] else 'No plot available.'
            
            from utils import format_movie_info
            info = format_movie_info(movie_data)
            poster = movie.get('full-size cover url')
            
            buttons = [
                [
                    InlineKeyboardButton("🔍 Search More", url=Config.SEARCH_BOT_URL),
                    InlineKeyboardButton("❌ Close", callback_data="close_msg")
                ]
            ]
            
            if poster:
                await callback.message.reply_photo(poster, caption=info, reply_markup=InlineKeyboardMarkup(buttons))
            else:
                await callback.message.reply(info, reply_markup=InlineKeyboardMarkup(buttons))
            
            await callback.answer("Search completed!")
        else:
            search_url = f"{Config.SEARCH_BOT_URL}?start={movie_name.replace(' ', '%20')}"
            buttons = [[InlineKeyboardButton("🔍 Search on Bot", url=search_url)]]
            await callback.message.reply(
                f"No results found for **{movie_name}**. Try searching on our dedicated bot:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            await callback.answer("No results found!")
    except Exception as e:
        await callback.answer(f"Error searching: {str(e)}", show_alert=True)
