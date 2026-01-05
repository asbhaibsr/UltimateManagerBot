import asyncio
import re
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, 
    InlineKeyboardButton, CallbackQuery
)
from cinemagoer import IMDb
from fuzzywuzzy import fuzz, process
from config import Config
from database import db

ia = IMDb()

class MovieChecker:
    """AI-powered movie name checker"""
    
    @staticmethod
    async def extract_query(text):
        """Extract clean movie name from user message"""
        # Remove common hindi/english phrases
        remove_patterns = [
            r'(de do|do|give me|bhejo|chahiye|chaiye|movie|series|film|webseries|web series|download|hd|full)',
            r'(720p|1080p|4k|bluray|dvdrip|brrip|hindi|english|dubbed|subtitles)',
            r'(please|plz|pls|kripya|krpya|send|share|link)',
            r'[!@#$%^&*()_+\-=\[\]{};:"\\|,.<>/?]'
        ]
        
        clean_text = text.lower()
        for pattern in remove_patterns:
            clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE)
        
        # Remove extra spaces
        clean_text = ' '.join(clean_text.split())
        
        # Check for year
        year_match = re.search(r'(19|20)\d{2}', clean_text)
        year = year_match.group() if year_match else ""
        
        # Remove year from text
        if year:
            clean_text = clean_text.replace(year, '').strip()
        
        return clean_text.strip(), year
    
    @staticmethod
    async def check_spelling(query):
        """Check and correct spelling using AI"""
        try:
            # First try TMDB API
            async with aiohttp.ClientSession() as session:
                url = f"https://api.themoviedb.org/3/search/multi?api_key={Config.TMDB_API_KEY}&query={query}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('results'):
                            result = data['results'][0]
                            title = result.get('title') or result.get('name')
                            if title:
                                ratio = fuzz.ratio(query.lower(), title.lower())
                                return {
                                    'original': query,
                                    'corrected': title,
                                    'year': result.get('release_date', '')[:4] if result.get('release_date') else '',
                                    'type': result.get('media_type'),
                                    'confidence': ratio,
                                    'is_correct': ratio > 85
                                }
            
            # Fallback to IMDb
            movies = ia.search_movie(query)
            if movies:
                movie = movies[0]
                ia.update(movie)
                title = movie.get('title', query)
                ratio = fuzz.ratio(query.lower(), title.lower())
                
                return {
                    'original': query,
                    'corrected': title,
                    'year': str(movie.get('year', '')) if movie.get('year') else '',
                    'type': movie.get('kind', 'movie'),
                    'confidence': ratio,
                    'is_correct': ratio > 85
                }
            
            return {'original': query, 'is_correct': True}
            
        except Exception as e:
            print(f"Spell check error: {e}")
            return {'original': query, 'is_correct': True}
    
    @staticmethod
    async def check_season_required(query):
        """Check if season number is needed"""
        series_keywords = ['season', 'série', 'serie', 'web series', 'webseries', 'tv series', 'tv']
        
        # Check if it's a series
        for keyword in series_keywords:
            if keyword in query.lower():
                # Check if season number is present
                if not re.search(r'S\d+|Season\s*\d+', query, re.IGNORECASE):
                    return True
        
        return False
    
    @staticmethod
    async def get_movie_details(title):
        """Get movie details for sending to user"""
        try:
            # Try TMDB first
            async with aiohttp.ClientSession() as session:
                url = f"https://api.themoviedb.org/3/search/movie?api_key={Config.TMDB_API_KEY}&query={title}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('results'):
                            movie = data['results'][0]
                            return {
                                'title': movie.get('title', title),
                                'year': movie.get('release_date', '')[:4] if movie.get('release_date') else 'N/A',
                                'rating': movie.get('vote_average', 'N/A'),
                                'overview': movie.get('overview', 'No description available'),
                                'poster': f"https://image.tmdb.org/t/p/w500{movie.get('poster_path')}" if movie.get('poster_path') else None
                            }
            
            # Fallback to IMDb
            movies = ia.search_movie(title)
            if movies:
                movie = movies[0]
                ia.update(movie)
                
                return {
                    'title': movie.get('title', title),
                    'year': str(movie.get('year', 'N/A')),
                    'rating': str(movie.get('rating', 'N/A')),
                    'overview': movie.get('plot outline', 'No description available')[:300] + "...",
                    'poster': movie.get('cover url')
                }
            
            return None
            
        except Exception as e:
            print(f"Details error: {e}")
            return None

class ForceSubHandler:
    """Handle Force Subscribe functionality"""
    
    @staticmethod
    async def check_user(client: Client, chat_id: int, user_id: int):
        """Check if user has joined required channels"""
        channels = await db.get_fsub(chat_id)
        
        if not channels:
            return True
        
        for channel in channels:
            try:
                member = await client.get_chat_member(channel, user_id)
                if member.status in ['left', 'kicked']:
                    return False, channel
            except:
                return False, channel
        
        return True, None
    
    @staticmethod
    async def send_fsub_message(client: Client, chat_id: int, user_id: int, channel: str):
        """Send FSub message with button"""
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{channel.replace('@', '')}"),
            InlineKeyboardButton("✅ Done", callback_data=f"fsub_verify_{user_id}")
        ]])
        
        message = await client.send_message(
            chat_id=chat_id,
            text=f"**🚫 ACCESS DENIED!**\n\n"
                 f"@{user_id}, You must join our channel first!\n"
                 f"Channel: @{channel}\n\n"
                 f"👉 Join the channel and click **DONE** button",
            reply_markup=keyboard
        )
        
        # Auto delete after 1 minute
        await asyncio.sleep(Config.FSUB_CHECK_TIME)
        try:
            await message.delete()
        except:
            pass

class ForceJoinHandler:
    """Handle Force Join Group functionality"""
    
    @staticmethod
    async def check_force_join(client: Client, chat_id: int, user_id: int):
        """Check if user needs to add members"""
        count = await db.get_force_join(chat_id)
        
        if count == 0:
            return True
        
        # Check if already verified
        if await db.is_verified(chat_id, user_id):
            return True
        
        return False, count
    
    @staticmethod
    async def send_force_join_message(client: Client, chat_id: int, user_id: int, count: int):
        """Send force join message"""
        invite_link = await client.export_chat_invite_link(chat_id)
        
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("➕ Add Members", url=invite_link),
            InlineKeyboardButton("✅ Verify", callback_data=f"fjoin_verify_{user_id}")
        ]])
        
        message = await client.send_message(
            chat_id=chat_id,
            text=f"**👥 GROUP MEMBERS REQUIRED!**\n\n"
                 f"@{user_id}, you need to add **{count} members** to this group before posting!\n\n"
                 f"**Steps:**\n"
                 f"1. Add {count} members using above button\n"
                 f"2. Click VERIFY button\n"
                 f"3. Start posting!\n\n"
                 f"⚠️ Members must stay in group for verification",
            reply_markup=keyboard
        )
        
        # Mute user temporarily
        try:
            await client.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False)
            )
        except:
            pass
        
        return message

class BroadcastHandler:
    """Handle broadcasting messages"""
    
    @staticmethod
    async def send_broadcast(client: Client, message: Message):
        """Broadcast message to all users"""
        users = await db.get_all_users()
        total = len(users)
        success = 0
        failed = 0
        
        progress_msg = await message.reply(f"📢 Broadcasting started...\nTotal: {total} users")
        
        for user in users:
            try:
                if user.get('blocked', False):
                    continue
                    
                await message.copy(user['user_id'])
                success += 1
                
                # To avoid flood
                if success % 100 == 0:
                    await asyncio.sleep(2)
                    
            except Exception as e:
                failed += 1
                # Mark as blocked if user blocked bot
                if "blocked" in str(e).lower():
                    await db.db.users.update_one(
                        {"user_id": user['user_id']},
                        {"$set": {"blocked": True}}
                    )
        
        await progress_msg.edit(
            f"✅ **Broadcast Complete!**\n\n"
            f"📊 **Statistics:**\n"
            f"• ✅ Success: {success}\n"
            f"• ❌ Failed: {failed}\n"
            f"• 📊 Total: {total}\n"
            f"• 🚫 Blocked: {total - success - failed}"
        )

# Create instances
movie_checker = MovieChecker()
fsub_handler = ForceSubHandler()
fjoin_handler = ForceJoinHandler()
broadcast_handler = BroadcastHandler()
