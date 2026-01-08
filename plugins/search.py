import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from imdb import Cinemagoer
from utils import format_movie_info, extract_movie_name
from database import db

ia = Cinemagoer()

@Client.on_message(filters.command("search"))
async def search_cmd(client, message):
    """Search for movies"""
    if len(message.command) < 2:
        await message.reply("Please provide movie name!\nExample: `/search Avengers Endgame`")
        return
    
    query = " ".join(message.command[1:])
    movie_name = extract_movie_name(query)
    
    m = await message.reply(f"🔍 Searching for **{movie_name}**...")
    
    try:
        results = ia.search_movie(movie_name)
        if not results:
            await m.edit("❌ No movie found with that name.")
            return
        
        # Get top 5 results
        top_results = results[:5]
        
        text = f"🎬 **Search Results for:** `{movie_name}`\n\n"
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
            InlineKeyboardButton("🔍 Search More", url=f"https://www.imdb.com/find?q={movie_name}"),
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
async def movie_details_cmd(client, message):
    """Get movie details"""
    if len(message.command) < 2:
        await message.reply("Please provide movie name!\nExample: `/moviedetails Avengers Endgame`")
        return
    
    query = " ".join(message.command[1:])
    movie_name = extract_movie_name(query)
    
    m = await message.reply(f"🔍 Getting details for **{movie_name}**...")
    
    try:
        results = ia.search_movie(movie_name)
        if not results:
            await m.edit("❌ No movie found with that name.")
            return
        
        movie = results[0]
        ia.update(movie)
        
        # Format movie info
        info = format_movie_info(movie)
        photo = movie.get('full-size cover url')
        
        # Create buttons
        buttons = [
            [
                InlineKeyboardButton("📺 Trailer", url=f"https://www.youtube.com/results?search_query={movie['title']}+trailer"),
                InlineKeyboardButton("⭐ IMDb", url=f"https://www.imdb.com/title/tt{movie.movieID}")
            ],
            [InlineKeyboardButton("🔍 Search Another", callback_data="search_another")]
        ]
        
        if photo:
            await message.reply_photo(
                photo,
                caption=info,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            await m.delete()
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
                await asyncio.sleep(300)  # 5 minutes
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
        info = format_movie_info(movie)
        photo = movie.get('full-size cover url')
        
        buttons = [
            [
                InlineKeyboardButton("📺 Trailer", url=f"https://www.youtube.com/results?search_query={movie['title']}+trailer"),
                InlineKeyboardButton("⭐ IMDb", url=f"https://www.imdb.com/title/tt{movie.movieID}")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_search")]
        ]
        
        if photo:
            await callback.message.reply_photo(
                photo,
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
