#  plugins/search.py

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from imdb import Cinemagoer

ia = Cinemagoer()

@Client.on_message(filters.command("search"))
async def search_cmd(client, message):
    query = " ".join(message.command[1:])
    if not query:
        return await message.reply("Give movie name.")
        
    btn = [[InlineKeyboardButton("Search Here", url=f"https://t.me/asfilter_bot?start={query}")]]
    await message.reply(f"Click below to search for **{query}**", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_message(filters.command("moviedetails"))
async def movie_details(client, message):
    query = " ".join(message.command[1:])
    if not query: return
    
    m = await message.reply("Searching...")
    try:
        results = ia.search_movie(query)
        if not results:
            return await m.edit("No movie found.")
            
        movie = results[0]
        ia.update(movie)
        
        txt = (
            f"🎬 **{movie.get('title')}**\n"
            f"📅 Year: {movie.get('year')}\n"
            f"⭐ Rating: {movie.get('rating')}\n"
            f"🎭 Genres: {', '.join(movie.get('genres', []))}\n"
            f"📝 Plot: {movie.get('plot outline', 'N/A')[:200]}..."
        )
        
        # Send Poster if available
        if movie.get('full-size cover url'):
            await message.reply_photo(movie['full-size cover url'], caption=txt)
            await m.delete()
        else:
            await m.edit(txt)
            
    except Exception as e:
        await m.edit(f"Error: {e}")
