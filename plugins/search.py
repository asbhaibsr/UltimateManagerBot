import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from imdb import Cinemagoer
from utils import get_movie_details_from_apis, format_movie_info, extract_movie_name, get_movie_poster
from database import db
from config import Config

ia = Cinemagoer()

@Client.on_message(filters.command("search"))
async def search_cmd(client, message: Message):
    """Search for movies"""
    if len(message.command) < 2:
        await message.reply("Please provide movie name!\nExample: /search Avengers Endgame")
        return
    
    query = " ".join(message.command[1:])
    movie_name = extract_movie_name(query)
    
    if not movie_name:
        await message.reply("Please enter a valid movie name!")
        return
    
    m = await message.reply(f"🔍 Searching for {movie_name}...")
    
    try:
        results = ia.search_movie(movie_name)
        
        if not results:
            # If no results found, provide search link
            search_url = f"{Config.SEARCH_BOT_URL}?start={movie_name.replace(' ', '%20')}"
            
            text = f"""
🎬 **Movie Search**

Sorry, I couldn't find **"{movie_name}"** in my database.

🔍 **Search on our bot:**
[Click here to search]({search_url})

💡 **Tips:**
• Check the spelling
• Try the full movie name
• Or use our dedicated search bot
            """
            
            buttons = [
                [InlineKeyboardButton("🔍 Search on Bot", url=search_url)],
                [InlineKeyboardButton("❌ Close", callback_data="close_msg")]
            ]
            
            await m.edit(
                text,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=False
            )
            return
        
        # Get top 5 results
        top_results = results[:5]
        
        text = f"🎬 **Search Results for:** {movie_name}\n\n"
        buttons = []
        
        for idx, movie in enumerate(top_results, 1):
            title = movie['title']
            year = movie.get('year', 'N/A')
            movie_id = movie.movieID
            
            text += f"{idx}. **{title}** ({year})\n"
            
            buttons.append([
                InlineKeyboardButton(
                    f"{idx}. {title[:20]}...",
                    callback_data=f"movie_details_{movie_id}"
                )
            ])
        
        buttons.append([
            InlineKeyboardButton("🔍 Search More", url=f"https://www.imdb.com/find?q={movie_name.replace(' ', '+')}"),
            InlineKeyboardButton("❌ Close", callback_data="close_msg")
        ])
        
        await m.edit(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
        
    except Exception as e:
        await m.edit(f"❌ Error: {str(e)}")

@Client.on_message(filters.command("moviedetails"))
async def movie_details_cmd(client, message: Message):
    """Get movie details"""
    if len(message.command) < 2:
        await message.reply("Please provide movie name!\nExample: /moviedetails Avengers Endgame")
        return
    
    query = " ".join(message.command[1:])
    movie_name = extract_movie_name(query)
    
    if not movie_name:
        await message.reply("Please enter a valid movie name!")
        return
    
    m = await message.reply(f"🔍 Getting details for {movie_name}...")
    
    try:
        # Get movie details from APIs
        movie_data = await get_movie_details_from_apis(movie_name)
        
        if not movie_data:
            # If no details found, provide search link
            search_url = f"{Config.SEARCH_BOT_URL}?start={movie_name.replace(' ', '%20')}"
            
            text = f"""
🎬 **Movie Details**

Sorry, I couldn't find details for **"{movie_name}"**.

🔍 **Search on our bot:**
[Click here to search]({search_url})

You can find the movie on our dedicated bot with better search capabilities.
            """
            
            buttons = [
                [InlineKeyboardButton("🔍 Search on Bot", url=search_url)],
                [InlineKeyboardButton("🎬 Try Another", callback_data="search_another")]
            ]
            
            await m.edit(
                text,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=False
            )
            return
        
        # Format movie info
        info = format_movie_info(movie_data)
        
        # Get poster
        poster_url = await get_movie_poster(movie_name)
        
        # Create buttons with bot link
        buttons = [
            [
                InlineKeyboardButton("📺 Trailer", url=f"https://www.youtube.com/results?search_query={movie_data['title'].replace(' ', '+')}+trailer"),
                InlineKeyboardButton("⭐ IMDb", url=f"https://www.imdb.com/title/tt{movie_data.get('imdb_id', '')}")
            ],
            [
                InlineKeyboardButton("🔍 Search More Movies", url=Config.SEARCH_BOT_URL),
                InlineKeyboardButton("🔙 Back", callback_data="back_to_search")
            ]
        ]
        
        if poster_url:
            try:
                await message.reply_photo(
                    poster_url,
                    caption=info,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                await m.delete()
            except:
                # If photo fails, send text
                await m.edit(
                    info,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=True
                )
        else:
            await m.edit(
                info,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=True
            )
        
        # Auto delete for groups
        if message.chat.type != "private":
            group = await db.get_group(message.chat.id)
            if group and group["settings"].get("auto_delete_files"):
                delete_after = group["settings"].get("delete_after_minutes", 5)
                await asyncio.sleep(delete_after * 60)
                try:
                    await m.delete()
                except:
                    pass
                
    except Exception as e:
        await m.edit(f"❌ Error: {str(e)}")

@Client.on_callback_query(filters.regex(r"^movie_details_"))
async def movie_details_callback(client, callback):
    """Handle movie details from callback"""
    movie_id = callback.data.split("_")[2]
    
    try:
        movie = ia.get_movie(movie_id)
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
        
        info = format_movie_info(movie_data)
        poster = movie.get('full-size cover url') or movie.get('cover url')
        
        buttons = [
            [
                InlineKeyboardButton("📺 Trailer", url=f"https://www.youtube.com/results?search_query={movie['title'].replace(' ', '+')}+trailer"),
                InlineKeyboardButton("⭐ IMDb", url=f"https://www.imdb.com/title/tt{movie.movieID}")
            ],
            [
                InlineKeyboardButton("🔍 Search More", url=Config.SEARCH_BOT_URL),
                InlineKeyboardButton("🔙 Back", callback_data="back_to_search")
            ]
        ]
        
        if poster:
            await callback.message.reply_photo(
                poster,
                caption=info,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await callback.message.reply(
                info,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
        await callback.answer("Details sent!")
        
    except Exception as e:
        await callback.answer(f"Error: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^(close_msg|back_to_search|search_another)$"))
async def close_message(client, callback):
    """Close or go back"""
    await callback.message.delete()
    await callback.answer()
