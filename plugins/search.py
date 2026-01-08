# plugins/search.py

import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from utils import get_movie_details, format_movie_info, extract_movie_name
from database import db
from config import Config

@Client.on_message(filters.command("search"))
async def search_cmd(client, message: Message):
    """Search for movies"""
    if len(message.command) < 2:
        await message.reply("Please provide movie name!\nExample: `/search Avengers Endgame`")
        return
    
    query = " ".join(message.command[1:])
    movie_name = extract_movie_name(query)
    
    if not movie_name:
        await message.reply("Please enter a valid movie name!")
        return
    
    m = await message.reply(f"🔍 Searching for **{movie_name}**...")
    
    try:
        # Get movie details
        movie_data = await get_movie_details(movie_name)
        
        if not movie_data:
            # If no movie found, show search link
            search_url = f"{Config.SEARCH_BOT_URL}{movie_name.replace(' ', '+')}"
            
            response_text = f"❌ **No movie found with that name.**\n\n"
            response_text += f"🔍 **Try searching here:**\n"
            response_text += f"👉 [Click to search '{movie_name}'](https://t.me/asfilter_bot?start={movie_name.replace(' ', '+')})\n\n"
            response_text += f"💡 **Tips:**\n"
            response_text += f"• Check spelling\n• Use correct year\n• Try full title"
            
            buttons = [
                [InlineKeyboardButton("🔍 Search Here", url=f"https://t.me/asfilter_bot?start={movie_name.replace(' ', '+')}")],
                [InlineKeyboardButton("🎬 Try Another", callback_data="search_again")]
            ]
            
            await m.edit(
                response_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=False
            )
            return
        
        # Format movie info
        info = format_movie_info(movie_data)
        poster = movie_data.get("poster")
        
        # Create buttons
        buttons = [
            [
                InlineKeyboardButton("🎬 More Info", url=movie_data.get("imdb_url", "https://www.imdb.com")),
                InlineKeyboardButton("🔍 Search Bot", url=f"https://t.me/asfilter_bot?start={movie_name.replace(' ', '+')}")
            ]
        ]
        
        if poster:
            try:
                await message.reply_photo(
                    poster,
                    caption=info,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                await m.delete()
            except:
                await m.edit(
                    info,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=False
                )
        else:
            await m.edit(
                info,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=False
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

@Client.on_message(filters.command("moviedetails"))
async def movie_details_cmd(client, message: Message):
    """Get movie details"""
    if len(message.command) < 2:
        await message.reply("Please provide movie name!\nExample: `/moviedetails Avengers Endgame`")
        return
    
    query = " ".join(message.command[1:])
    movie_name = extract_movie_name(query)
    
    if not movie_name:
        await message.reply("Please enter a valid movie name!")
        return
    
    m = await message.reply(f"🔍 Getting details for **{movie_name}**...")
    
    try:
        # Get movie details
        movie_data = await get_movie_details(movie_name)
        
        if not movie_data:
            # If no movie found, show search link
            search_url = f"{Config.SEARCH_BOT_URL}{movie_name.replace(' ', '+')}"
            
            response_text = f"❌ **No movie found with that name.**\n\n"
            response_text += f"🔍 **Try searching here:**\n"
            response_text += f"👉 [Click to search '{movie_name}'](https://t.me/asfilter_bot?start={movie_name.replace(' ', '+')})\n\n"
            response_text += f"💡 **Tips:**\n"
            response_text += f"• Check spelling\n• Use correct year\n• Try full title"
            
            buttons = [
                [InlineKeyboardButton("🔍 Search Here", url=f"https://t.me/asfilter_bot?start={movie_name.replace(' ', '+')}")],
                [InlineKeyboardButton("🎬 Try Another", callback_data="search_again")]
            ]
            
            await m.edit(
                response_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=False
            )
            return
        
        # Format movie info
        info = format_movie_info(movie_data)
        poster = movie_data.get("poster")
        
        # Create buttons with your bot link
        buttons = [
            [
                InlineKeyboardButton("🎬 More Info", url=movie_data.get("imdb_url", "https://www.imdb.com")),
                InlineKeyboardButton("🔍 Search Bot", url=f"https://t.me/asfilter_bot?start={movie_name.replace(' ', '+')}")
            ],
            [InlineKeyboardButton("🤖 Get This Movie", url=f"https://t.me/{Config.BOT_USERNAME}?start={movie_name.replace(' ', '+')}")]
        ]
        
        if poster:
            try:
                await message.reply_photo(
                    poster,
                    caption=info,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                await m.delete()
            except:
                await m.edit(
                    info,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=False
                )
        else:
            await m.edit(
                info,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=False
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

@Client.on_callback_query(filters.regex(r"^search_again$"))
async def search_again_callback(client, callback):
    """Handle search again callback"""
    await callback.message.edit_text(
        "🔍 **Search Movies**\n\n"
        "Type: `/search Movie Name`\n"
        "Example: `/search Kill 2024`\n\n"
        "Or use: `/moviedetails Movie Name` for details."
    )
    await callback.answer()
