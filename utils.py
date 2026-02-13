import re
import aiohttp
import asyncio
import random
import datetime
import io
import time
import hashlib
import json
from typing import Optional, Dict, List, Tuple, Any
from urllib.parse import quote
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant, FloodWait
from config import Config
from database import get_spelling_cache, set_spelling_cache
import logging

logger = logging.getLogger(__name__)


class MovieBotUtils:
    """
    Movie Helper Bot - Advanced Utils Class
    All helper functions with caching and error handling
    """
    
    # Cache dictionaries
    _google_cache = {}
    _movie_cache = {}
    _ai_cache = {}
    _omdb_cache = {}
    _anime_cache = {}
    _translation_cache = {}
    
    # Constants
    CACHE_TTL = 300  # 5 minutes default
    MAX_RETRIES = 3
    
    # --- 1. BIO PROTECTION (ADVANCED) ---
    @staticmethod
    def check_bio_safety_deep(bio: str) -> Dict:
        """
        Deep bio scan for security threats
        Returns dict with safety score and issues
        """
        if not bio or not bio.strip():
            return {"safe": True, "issues": [], "score": 100, "message": "✅ Bio safe hai!"}
        
        bio_lower = bio.lower()
        issues = []
        score = 100
        detected_items = []
        
        # Comprehensive link patterns
        link_patterns = [
            (r'https?://\S+', "🔗 HTTP Link"),
            (r'www\.\S+', "🌐 WWW Link"),
            (r't\.me/\S+', "📢 Telegram Link"),
            (r'telegram\.me/\S+', "📢 Telegram Link"),
            (r'@\w+', "📛 Username"),
            (r'bit\.ly/\S+', "🔗 Short URL"),
            (r'tinyurl\.com/\S+', "🔗 Short URL"),
            (r'instagram\.com/\S+', "📷 Instagram"),
            (r'youtube\.com/\S+', "🎥 YouTube"),
            (r'youtu\.be/\S+', "🎥 YouTube"),
            (r'facebook\.com/\S+', "📘 Facebook"),
            (r'twitter\.com/\S+', "🐦 Twitter"),
            (r'x\.com/\S+', "🐦 X/Twitter"),
            (r'discord\.gg/\S+', "💬 Discord"),
            (r'whatsapp\.com/\S+', "📱 WhatsApp"),
        ]
        
        for pattern, label in link_patterns:
            if re.search(pattern, bio_lower):
                if label not in issues:
                    issues.append(label)
                    score -= 20
        
        # Promotion keywords
        promo_words = [
            'join', 'subscribe', 'follow', 'channel', 'group', 'free', 'earn',
            'income', 'money', 'cash', 'refer', 'bonus', 'promotion', 'paid',
            'premium', 'exclusive', '🔥', '💥', '🎁', '💰', '💸', '🚀'
        ]
        
        for word in promo_words:
            if re.search(r'\b' + re.escape(word) + r'\b', bio_lower):
                if "📢 Promotion" not in issues:
                    issues.append("📢 Promotion")
                    score -= 15
                break
        
        # Spam detection
        if len(bio) > 150:
            issues.append("📝 Too Long Bio")
            score -= 10
        
        # Emoji spam
        emoji_count = len(re.findall(r'[^\w\s]', bio))
        if emoji_count > 10:
            issues.append("😊 Emoji Spam")
            score -= 5
        
        # HTML/JS injection attempts
        if re.search(r'<script|javascript:|onclick=|onerror=', bio_lower):
            issues.append("⚠️ Suspicious Code")
            score -= 50
        
        # Ensure score doesn't go below 0
        score = max(0, score)
        
        return {
            "safe": score >= 70,
            "issues": issues,
            "score": score,
            "message": MovieBotUtils._get_bio_message(issues, score),
            "detected": detected_items
        }
    
    @staticmethod
    def _get_bio_message(issues: List[str], score: int) -> str:
        """Generate bio warning message"""
        if score >= 70:
            if issues:
                return f"⚠️ **Warning:** Bio mein `{', '.join(issues[:2])}` hai. Please hatao!"
            return "✅ Bio safe hai!"
        
        if score < 40:
            return f"🚨 **DANGER!** Bio mein `{', '.join(issues)}` mila. Immediate action required!"
        
        return f"⚠️ Bio mein `{', '.join(issues)}` hai. Remove karo warna action hoga!"
    
    # --- 2. WELCOME STICKER CREATOR (ENHANCED) ---
    @staticmethod
    async def create_welcome_sticker(
        user_photo_bytes: bytes, 
        group_name: str, 
        bot_name: str,
        user_name: str,
        is_premium: bool = False
    ) -> Optional[io.BytesIO]:
        """
        Create beautiful welcome sticker with user's photo
        Returns BytesIO object or None
        """
        try:
            # Open and process image
            img = Image.open(io.BytesIO(user_photo_bytes)).convert("RGBA")
            img = img.resize((512, 512), Image.Resampling.LANCZOS)
            
            # Create circular mask
            mask = Image.new('L', (512, 512), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, 512, 512), fill=255)
            
            # Apply mask
            output = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
            output.paste(img, (0, 0), mask)
            
            # Add decorative elements
            draw = ImageDraw.Draw(output)
            
            # Premium border or normal border
            if is_premium:
                # Gold gradient border for premium
                for i in range(0, 20, 2):
                    draw.ellipse(
                        (i, i, 511 - i, 511 - i), 
                        outline=(255, 215, 0, 255 - i * 10), 
                        width=2
                    )
            else:
                # Simple border
                draw.ellipse((0, 0, 511, 511), outline=(255, 215, 0), width=12)
                draw.ellipse((6, 6, 505, 505), outline=(255, 255, 255), width=6)
            
            # Load fonts (try multiple options)
            try:
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
                font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 25)
            except:
                try:
                    font_large = ImageFont.truetype("arial.ttf", 40)
                    font_medium = ImageFont.truetype("arial.ttf", 30)
                    font_small = ImageFont.truetype("arial.ttf", 25)
                except:
                    font_large = ImageFont.load_default()
                    font_medium = font_large
                    font_small = font_large
            
            # Shorten names if too long
            short_group = group_name[:20] + ".." if len(group_name) > 20 else group_name
            short_user = user_name[:15] + ".." if len(user_name) > 15 else user_name
            
            # Add semi-transparent background for text
            text_bg = Image.new('RGBA', (512, 150), (0, 0, 0, 180))
            output.paste(text_bg, (0, 362), text_bg)
            
            # Add text
            draw.text((256, 390), f"👋 Welcome", 
                     fill=(255, 215, 0), anchor="mm", font=font_medium)
            
            draw.text((256, 430), f"{short_user}", 
                     fill=(255, 255, 255), anchor="mm", font=font_large)
            
            draw.text((256, 480), f"to {short_group}", 
                     fill=(200, 200, 200), anchor="mm", font=font_small)
            
            if is_premium:
                draw.text((450, 50), "⭐ PREMIUM", 
                         fill=(255, 215, 0), anchor="mm", font=font_small)
            
            # Save to bytes
            img_bytes = io.BytesIO()
            output.save(img_bytes, format="PNG", optimize=True)
            img_bytes.seek(0)
            
            return img_bytes
            
        except Exception as e:
            logger.error(f"Sticker creation error: {e}")
            return None
    
    # --- 3. ADMIN MENTIONS (ENHANCED) ---
    @staticmethod
    async def get_admin_mentions(client, chat_id: int, max_mentions: int = 5) -> str:
        """
        Get formatted admin mentions with proper tags
        """
        mentions = []
        
        try:
            # Add owner first
            try:
                owner = await client.get_users(Config.OWNER_ID)
                mentions.append(f"👑 [{owner.first_name}](tg://user?id={Config.OWNER_ID})")
            except:
                mentions.append("👑 **Owner**")
            
            # Get group admins
            admin_count = 0
            async for member in client.get_chat_members(chat_id, filter="administrators"):
                if not member.user.is_bot and member.user.id != Config.OWNER_ID:
                    if admin_count < max_mentions - 1:
                        name = member.user.first_name[:15]
                        mentions.append(f"🛡️ [{name}](tg://user?id={member.user.id})")
                        admin_count += 1
            
        except Exception as e:
            logger.error(f"Admin fetch error: {e}")
        
        if not mentions:
            return "👑 **Admins**"
        
        return "\n".join(mentions)
    
    # --- 4. MOVIE FORMAT VALIDATION (ULTIMATE) ---
    @staticmethod
    def validate_movie_format_advanced(text: str) -> Dict:
        """
        Advanced movie name validation and cleaning
        Returns dict with clean name and formatting suggestions
        """
        original = text
        text_lower = text.lower().strip()
        
        # Remove command prefixes
        text_lower = re.sub(r'^/request\s+', '', text_lower)
        text_lower = re.sub(r'^#request\s+', '', text_lower)
        
        # Extract year (4 digits)
        year_match = re.search(r'\b(19|20)\d{2}\b', text_lower)
        year = year_match.group(0) if year_match else None
        if year:
            text_lower = re.sub(r'\b' + year + r'\b', '', text_lower).strip()
        
        # Season/Episode detection
        season_patterns = [
            (r'season\s*(\d+)', 'S{:02d}'),
            (r's(\d{1,2})', 'S{:02d}'),
            (r'episode\s*(\d+)', 'E{:02d}'),
            (r'ep\s*(\d+)', 'E{:02d}'),
            (r'e(\d{1,2})', 'E{:02d}'),
            (r'part\s*(\d+)', 'Part {}'),
            (r'chapter\s*(\d+)', 'Ch.{}')
        ]
        
        session_info = ""
        clean_text = text_lower
        
        for pattern, fmt in season_patterns:
            match = re.search(pattern, clean_text)
            if match:
                num = int(match.group(1))
                session_info = fmt.format(num)
                clean_text = re.sub(pattern, '', clean_text).strip()
                break
        
        # Language detection
        languages = {
            'hindi': '🎬 Hindi', 'english': '🎬 English', 'tamil': '🎬 Tamil',
            'telugu': '🎬 Telugu', 'malayalam': '🎬 Malayalam', 'kannada': '🎬 Kannada',
            'punjabi': '🎬 Punjabi', 'bengali': '🎬 Bengali', 'marathi': '🎬 Marathi',
            'gujarati': '🎬 Gujarati', 'urdu': '🎬 Urdu', 'bhojpuri': '🎬 Bhojpuri',
            'dubbed': '🎬 Dubbed', 'dual audio': '🎬 Dual Audio'
        }
        
        detected_lang = ""
        for lang, display in languages.items():
            if lang in clean_text:
                detected_lang = display
                clean_text = clean_text.replace(lang, '').strip()
                break
        
        # Quality tags
        quality_patterns = [
            r'\b(720p|1080p|2160p|4k|480p|360p)\b',
            r'\b(hd|full hd|uhd|bluray|webrip|hdtv|dvdrip|cam|hdts)\b'
        ]
        
        quality = ""
        for pattern in quality_patterns:
            match = re.search(pattern, clean_text)
            if match:
                quality = match.group(0).upper()
                clean_text = re.sub(pattern, '', clean_text).strip()
                break
        
        # Junk words removal
        junk_words = [
            'dedo', 'chahiye', 'chaiye', 'bhejo', 'send', 'kardo', 'karo', 'do',
            'plz', 'pls', 'please', 'request', 'mujhe', 'mereko', 'koi', 'link',
            'download', 'movie', 'film', 'series', 'full', 'hd', 'file', 'video',
            'bro', 'bhai', 'sir', 'admin', 'yaar', 'dost', 'need', 'want',
            'provide', 'share', 'upload', 'give', 'send me', 'available'
        ]
        
        found_junk = []
        words = clean_text.split()
        clean_words = []
        
        for word in words:
            clean_w = re.sub(r'[^\w\s]', '', word)
            if clean_w in junk_words:
                if clean_w not in found_junk:
                    found_junk.append(clean_w)
            elif len(clean_w) >= 2 or (clean_w.isdigit() and len(clean_w) <= 4):
                clean_words.append(word)
        
        # Construct clean name
        movie_name = " ".join(clean_words).strip()
        if not movie_name:
            movie_name = original[:50]
        
        # Build correct format
        format_parts = []
        format_parts.append(movie_name.title())
        if year:
            format_parts.append(f"({year})")
        if session_info:
            format_parts.append(session_info)
        if detected_lang:
            format_parts.append(detected_lang)
        if quality:
            format_parts.append(quality)
        
        correct_format = " ".join(format_parts)
        
        return {
            'is_valid': len(found_junk) == 0,
            'found_junk': found_junk,
            'clean_name': movie_name,
            'correct_format': correct_format,
            'year': year,
            'session_info': session_info,
            'language': detected_lang,
            'quality': quality
        }
    
    # --- 5. OMDb MOVIE INFO (WITH CACHE) ---
    @staticmethod
    async def get_omdb_info(movie_name: str, detailed: bool = False) -> str:
        """
        Get movie info from OMDb API with caching
        """
        if not Config.OMDB_API_KEY:
            return "❌ **OMDb API key missing!** Contact @asbhai_bsr"
        
        cache_key = f"omdb_{movie_name.lower()}"
        
        # Check cache
        cached = await get_spelling_cache(cache_key)
        if cached:
            return cached
        
        for attempt in range(MovieBotUtils.MAX_RETRIES):
            try:
                url = f"http://www.omdbapi.com/?t={quote(movie_name)}&apikey={Config.OMDB_API_KEY}"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                
                if data.get("Response") == "True":
                    title = data.get("Title", "N/A")
                    year = data.get("Year", "N/A")
                    rated = data.get("Rated", "N/A")
                    released = data.get("Released", "N/A")
                    runtime = data.get("Runtime", "N/A")
                    genre = data.get("Genre", "N/A")
                    director = data.get("Director", "N/A")
                    writer = data.get("Writer", "N/A")
                    actors = data.get("Actors", "N/A")
                    plot = data.get("Plot", "N/A")
                    language = data.get("Language", "N/A")
                    country = data.get("Country", "N/A")
                    awards = data.get("Awards", "N/A")
                    imdb_rating = data.get("imdbRating", "N/A")
                    imdb_votes = data.get("imdbVotes", "N/A")
                    box_office = data.get("BoxOffice", "N/A")
                    
                    # Format rating stars
                    stars = ""
                    if imdb_rating != "N/A":
                        try:
                            rating_float = float(imdb_rating)
                            stars = "⭐" * max(1, min(5, int(rating_float // 2)))
                        except:
                            stars = ""
                    
                    if detailed:
                        response = (
                            f"🎬 **{title}** ({year})\n\n"
                            f"⭐ **IMDb:** {imdb_rating}/10 {stars}\n"
                            f"📊 **Votes:** {imdb_votes}\n"
                            f"🎭 **Genre:** {genre}\n"
                            f"🎬 **Director:** {director}\n"
                            f"👥 **Cast:** {actors[:100]}...\n"
                            f"📝 **Plot:** {plot[:150]}...\n"
                            f"🌍 **Language:** {language}\n"
                            f"💰 **Box Office:** {box_office}\n"
                            f"🏆 **Awards:** {awards[:50] if awards != 'N/A' else 'N/A'}"
                        )
                    else:
                        response = (
                            f"🎬 **Movie Found!**\n\n"
                            f"📽️ **{title}** ({year})\n"
                            f"{stars} **IMDb:** {imdb_rating}/10\n"
                            f"🎭 **Genre:** {genre}\n"
                            f"📝 **Story:** {plot[:100]}...\n\n"
                            f"✅ **Sahi naam:** `{title}`"
                        )
                    
                    # Cache for 6 hours
                    await set_spelling_cache(cache_key, response, 21600)
                    return response
                else:
                    return f"❌ **'{movie_name}'** ye movie OMDb mein nahi mili!\nSpelling check karo ya kuch aur try karo."
                    
            except asyncio.TimeoutError:
                if attempt == MovieBotUtils.MAX_RETRIES - 1:
                    return "❌ **OMDb timeout!** Thodi der baad try karo."
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"OMDb error: {e}")
                if attempt == MovieBotUtils.MAX_RETRIES - 1:
                    return "❌ **OMDb error!** Please try again later."
                await asyncio.sleep(1)
        
        return "❌ **Service unavailable!** Please try later."
    
    # --- 6. GOOGLE SEARCH (MULTI-SOURCE) ---
    @staticmethod
    async def get_google_search(query: str, max_results: int = 5) -> List[Tuple[str, str]]:
        """
        Google search with multiple fallback sources
        """
        cache_key = f"google_{hashlib.md5(query.lower().encode()).hexdigest()}"
        
        # Check cache
        if cache_key in MovieBotUtils._google_cache:
            cache_time, results = MovieBotUtils._google_cache[cache_key]
            if (datetime.datetime.now() - cache_time).seconds < 600:
                return results[:max_results]
        
        # Try multiple search engines
        sources = [
            MovieBotUtils._search_duckduckgo,
            MovieBotUtils._search_google_html,
            MovieBotUtils._search_bing
        ]
        
        for search_func in sources:
            try:
                results = await search_func(query)
                if results and len(results) > 0:
                    MovieBotUtils._google_cache[cache_key] = (datetime.datetime.now(), results)
                    return results[:max_results]
            except Exception as e:
                logger.error(f"Search error with {search_func.__name__}: {e}")
                continue
        
        return []
    
    @staticmethod
    async def _search_duckduckgo(query: str) -> List[Tuple[str, str]]:
        """DuckDuckGo HTML search"""
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=8) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        # Extract results
                        results = re.findall(
                            r'<a rel="nofollow" class="result__a" href="([^"]+)">([^<]+)</a>',
                            text
                        )
                        
                        formatted = []
                        for href, title in results:
                            title = title.replace('&amp;', '&').replace('&quot;', '"')
                            title = re.sub(r'<[^>]+>', '', title)
                            formatted.append((href, title))
                        
                        return formatted
        except:
            return []
    
    @staticmethod
    async def _search_google_html(query: str) -> List[Tuple[str, str]]:
        """Google HTML search (basic)"""
        try:
            url = f"https://www.google.com/search?q={quote(query)}&num=10"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=8) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        # Simple extraction
                        results = re.findall(
                            r'<a href="(/url\?q=[^"]+)"[^>]*><h3[^>]*>([^<]+)</h3>',
                            text
                        )
                        
                        formatted = []
                        for href, title in results[:5]:
                            # Clean Google redirect URL
                            match = re.search(r'q=([^&]+)', href)
                            if match:
                                clean_url = match.group(1)
                                formatted.append((clean_url, title))
                        
                        return formatted
        except:
            return []
    
    @staticmethod
    async def _search_bing(query: str) -> List[Tuple[str, str]]:
        """Bing HTML search"""
        try:
            url = f"https://www.bing.com/search?q={quote(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=8) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        # Extract results
                        results = re.findall(
                            r'<a href="([^"]+)"[^>]*><h2[^>]*>([^<]+)</h2>',
                            text
                        )
                        
                        formatted = []
                        for href, title in results[:5]:
                            if href.startswith('http'):
                                formatted.append((href, title))
                        
                        return formatted
        except:
            return []
    
    # --- 7. AI RESPONSE (ENHANCED) ---
    @staticmethod
    async def get_ai_response(query: str, context: str = "") -> str:
        """
        Get AI response with context and caching
        """
        cache_key = f"ai_{hashlib.md5((context + query).lower().encode()).hexdigest()}"
        
        # Check cache
        if cache_key in MovieBotUtils._ai_cache:
            cache_time, response = MovieBotUtils._ai_cache[cache_key]
            if (datetime.datetime.now() - cache_time).seconds < 300:
                return response
        
        try:
            import g4f
            
            # Build prompt based on context
            if context:
                prompt = f"""Context: {context}
User: {query}
You are a helpful Indian movie expert. Reply in Hinglish with emojis. Keep it short (3-4 lines)."""
            else:
                prompt = f"""User: {query}
You are a friendly Indian movie expert. Reply in Hinglish with emojis. Keep it short (3-4 lines). Be helpful and engaging."""
            
            response = await g4f.ChatCompletion.create_async(
                model=Config.G4F_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful Indian movie expert who replies in Hinglish with emojis."},
                    {"role": "user", "content": prompt}
                ],
                timeout=15
            )
            
            if response and response.strip():
                formatted = f"🤖 **BOT:**\n\n{response.strip()}"
                MovieBotUtils._ai_cache[cache_key] = (datetime.datetime.now(), formatted)
                return formatted
            
        except Exception as e:
            logger.error(f"AI Error: {e}")
        
        # Fallback responses
        fallbacks = [
            "🤖 **BOT:**\n\nArey yaar, abhi thoda busy hoon! ⏳ 2 minute baad try karo!",
            "🤖 **BOT:**\n\nMujhe laga samajh gaya but nahi samjha 😅 Thoda easy bolo!",
            "🤖 **BOT:**\n\nNetwork issue hai, thodi der mein baat karte hain! 📱",
            "🤖 **BOT:**\n\nMain soch raha hoon... 🤔 Kuch aur pucho?",
            "🤖 **BOT:**\n\nSorry yaar, yeh sawal samajh nahi aaya! Hindi mein pucho?"
        ]
        
        return random.choice(fallbacks)
    
    # --- 8. ANIME SEARCH (JIKAN API) ---
    @staticmethod
    async def get_anime_info(query: str) -> Optional[Dict]:
        """
        Get anime info from Jikan API (MyAnimeList)
        """
        cache_key = f"anime_{hashlib.md5(query.lower().encode()).hexdigest()}"
        
        # Check cache
        if cache_key in MovieBotUtils._anime_cache:
            cache_time, data = MovieBotUtils._anime_cache[cache_key]
            if (datetime.datetime.now() - cache_time).seconds < 3600:
                return data
        
        try:
            url = f"https://api.jikan.moe/v4/anime?q={quote(query)}&limit=1"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=8) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        if data.get('data') and len(data['data']) > 0:
                            anime = data['data'][0]
                            
                            # Format synopsis
                            synopsis = anime.get('synopsis', 'No synopsis available.')
                            if synopsis and len(synopsis) > 200:
                                synopsis = synopsis[:200] + "..."
                            
                            result = {
                                "title": anime['title'],
                                "title_japanese": anime.get('title_japanese', ''),
                                "score": anime.get('score', 'N/A'),
                                "scored_by": anime.get('scored_by', 0),
                                "rank": anime.get('rank', 'N/A'),
                                "popularity": anime.get('popularity', 'N/A'),
                                "members": anime.get('members', 0),
                                "favorites": anime.get('favorites', 0),
                                "episodes": anime.get('episodes', 'Unknown'),
                                "status": anime.get('status', 'Unknown'),
                                "aired": anime.get('aired', {}).get('string', 'Unknown'),
                                "duration": anime.get('duration', 'Unknown'),
                                "rating": anime.get('rating', 'Unknown'),
                                "genres": [g['name'] for g in anime.get('genres', [])],
                                "studios": [s['name'] for s in anime.get('studios', [])],
                                "source": anime.get('source', 'Unknown'),
                                "url": anime['url'],
                                "image_url": anime.get('images', {}).get('jpg', {}).get('image_url', ''),
                                "synopsis": synopsis
                            }
                            
                            # Cache for 1 hour
                            MovieBotUtils._anime_cache[cache_key] = (datetime.datetime.now(), result)
                            return result
        except Exception as e:
            logger.error(f"Anime search error: {e}")
        
        return None
    
    # --- 9. MESSAGE QUALITY CHECK ---
    @staticmethod
    def check_message_quality(text: str) -> str:
        """
        Check message quality (LINK, ABUSE, SPAM, CLEAN)
        """
        if not text:
            return "CLEAN"
        
        text_lower = text.lower().strip()
        
        # Link detection
        link_patterns = [
            r't\.me/\S+', r'http://', r'https://', r'www\.',
            r'\.com\b', r'\.in\b', r'\.net\b', r'\.org\b',
            r'bit\.ly/\S+', r'tinyurl\.com/\S+', r'telegram\.me/\S+'
        ]
        
        for pattern in link_patterns:
            if re.search(pattern, text_lower):
                return "LINK"
        
        # Abuse words (extended list)
        abuse_words = [
            'mc', 'bc', 'bkl', 'mkl', 'chutiya', 'kutta', 'fuck', 'bitch',
            'gand', 'lund', 'madarchod', 'behenchod', 'bsdk', 'gandu',
            'randi', 'bhosdike', 'lauda', 'chodu', 'kamine', 'harami',
            'motherfucker', 'asshole', 'dick', 'pussy', 'sex', 'xxx'
        ]
        
        words = text_lower.split()
        for word in abuse_words:
            if word in words or word in text_lower:
                return "ABUSE"
        
        # Spam detection (repeated messages)
        if len(text) > 500:
            return "SPAM"
        
        # Repeated characters
        if re.search(r'(.)\1{10,}', text):
            return "SPAM"
        
        return "CLEAN"
    
    # --- 10. AUTO DELETE WITH FLOOD WAIT HANDLING ---
    @staticmethod
    async def auto_delete_message(client, message, delay: int = 30):
        """
        Delete message after delay with flood wait handling
        """
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await message.delete()
            except:
                pass
        except:
            pass
    
    # --- 11. FORCE SUBSCRIBE CHECK ---
    @staticmethod
    async def check_fsub_member(client, channel_id: int, user_id: int) -> bool:
        """
        Check if user is member of channel
        """
        try:
            member = await client.get_chat_member(channel_id, user_id)
            return member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]
        except UserNotParticipant:
            return False
        except Exception as e:
            logger.error(f"FSub check error: {e}")
            return False
    
    # --- 12. PROGRESS BAR ---
    @staticmethod
    def get_progress_bar(current: int, total: int, length: int = 10) -> str:
        """
        Generate progress bar
        """
        if total == 0:
            return "░" * length + " 0%"
        
        filled = int(current * length / total)
        bar = "█" * filled + "░" * (length - filled)
        percent = int(current * 100 / total)
        return f"{bar} {percent}%"
    
    # --- 13. TEXT FORMATTING ---
    @staticmethod
    def format_number(num: int) -> str:
        """
        Format number with K, M suffixes
        """
        if num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num/1_000:.1f}K"
        return str(num)
    
    @staticmethod
    def format_time(seconds: int) -> str:
        """
        Format seconds to readable time
        """
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours}h"
        else:
            days = seconds // 86400
            return f"{days}d"
    
    # --- 14. CACHE CLEANUP ---
    @staticmethod
    def clean_cache():
        """
        Clean expired cache entries
        """
        now = datetime.datetime.now()
        
        # Clean Google cache
        expired = []
        for key, (cache_time, _) in MovieBotUtils._google_cache.items():
            if (now - cache_time).seconds > 600:
                expired.append(key)
        for key in expired:
            del MovieBotUtils._google_cache[key]
        
        # Clean AI cache
        expired = []
        for key, (cache_time, _) in MovieBotUtils._ai_cache.items():
            if (now - cache_time).seconds > 300:
                expired.append(key)
        for key in expired:
            del MovieBotUtils._ai_cache[key]
        
        # Clean OMDb cache (handled by database)
        
        logger.info(f"Cache cleaned: {len(expired)} items removed")
    
    # --- 15. RANDOM MOVIE OF THE DAY ---
    @staticmethod
    async def get_random_movie() -> Optional[Dict]:
        """
        Get random movie for Movie of the Day
        """
        # List of popular movies
        popular_movies = [
            "Inception", "The Dark Knight", "Interstellar", "Avengers Endgame",
            "3 Idiots", "Dangal", "PK", "Bahubali", "KGF", "RRR",
            "Titanic", "Avatar", "Joker", "The Matrix", "Pulp Fiction",
            "Shawshank Redemption", "Godfather", "The Lion King", "Frozen",
            "Spider-Man No Way Home", "Top Gun Maverick", "Oppenheimer"
        ]
        
        movie = random.choice(popular_movies)
        
        if Config.OMDB_API_KEY:
            try:
                url = f"http://www.omdbapi.com/?t={quote(movie)}&apikey={Config.OMDB_API_KEY}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=8) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            if data.get("Response") == "True":
                                return {
                                    "title": data.get("Title", movie),
                                    "year": data.get("Year", "N/A"),
                                    "rating": data.get("imdbRating", "N/A"),
                                    "genre": data.get("Genre", "N/A"),
                                    "plot": data.get("Plot", "N/A")[:100] + "..."
                                }
            except:
                pass
        
        # Fallback
        return {
            "title": movie,
            "year": "N/A",
            "rating": "N/A",
            "genre": "N/A",
            "plot": "Check this movie!"
        }
    
    # --- 16. TRANSLATION (HINGLISH TO ENGLISH/HINDI) ---
    @staticmethod
    async def translate_text(text: str, target_lang: str = "en") -> str:
        """
        Simple translation using free API
        """
        cache_key = f"trans_{hashlib.md5((text + target_lang).encode()).hexdigest()}"
        
        if cache_key in MovieBotUtils._translation_cache:
            cache_time, result = MovieBotUtils._translation_cache[cache_key]
            if (datetime.datetime.now() - cache_time).seconds < 3600:
                return result
        
        try:
            # Using LibreTranslate (free)
            url = "https://libretranslate.de/translate"
            payload = {
                "q": text,
                "source": "auto",
                "target": target_lang,
                "format": "text"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=8) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result = data.get("translatedText", text)
                        MovieBotUtils._translation_cache[cache_key] = (datetime.datetime.now(), result)
                        return result
        except:
            pass
        
        return text
    
    # --- 17. RATE LIMITING ---
    _rate_limit = {}
    
    @staticmethod
    def check_rate_limit(user_id: int, action: str, limit: int = 5, period: int = 60) -> bool:
        """
        Check if user is rate limited
        Returns True if allowed, False if limited
        """
        key = f"{user_id}_{action}"
        now = time.time()
        
        if key in MovieBotUtils._rate_limit:
            count, first_time = MovieBotUtils._rate_limit[key]
            
            if now - first_time < period:
                if count >= limit:
                    return False
                else:
                    MovieBotUtils._rate_limit[key] = (count + 1, first_time)
            else:
                MovieBotUtils._rate_limit[key] = (1, now)
        else:
            MovieBotUtils._rate_limit[key] = (1, now)
        
        return True
    
    # --- 18. CLEAN RATE LIMITS ---
    @staticmethod
    def clean_rate_limits():
        """
        Clean expired rate limits
        """
        now = time.time()
        expired = []
        
        for key, (_, first_time) in MovieBotUtils._rate_limit.items():
            if now - first_time > 300:  # 5 minutes
                expired.append(key)
        
        for key in expired:
            del MovieBotUtils._rate_limit[key]
    
    # --- 19. EXTRACT MEDIA INFO ---
    @staticmethod
    def extract_media_info(message) -> Dict:
        """
        Extract media info from message
        """
        info = {
            "type": "text",
            "file_id": None,
            "file_size": 0,
            "duration": 0,
            "caption": message.caption or ""
        }
        
        if message.photo:
            info["type"] = "photo"
            info["file_id"] = message.photo.file_id
            info["file_size"] = message.photo.file_size
        
        elif message.video:
            info["type"] = "video"
            info["file_id"] = message.video.file_id
            info["file_size"] = message.video.file_size
            info["duration"] = message.video.duration
            info["mime_type"] = message.video.mime_type
        
        elif message.document:
            info["type"] = "document"
            info["file_id"] = message.document.file_id
            info["file_size"] = message.document.file_size
            info["mime_type"] = message.document.mime_type
            info["file_name"] = message.document.file_name
        
        elif message.audio:
            info["type"] = "audio"
            info["file_id"] = message.audio.file_id
            info["file_size"] = message.audio.file_size
            info["duration"] = message.audio.duration
            info["performer"] = message.audio.performer
            info["title"] = message.audio.title
        
        elif message.voice:
            info["type"] = "voice"
            info["file_id"] = message.voice.file_id
            info["file_size"] = message.voice.file_size
            info["duration"] = message.voice.duration
        
        elif message.sticker:
            info["type"] = "sticker"
            info["file_id"] = message.sticker.file_id
            info["file_size"] = message.sticker.file_size
            info["emoji"] = message.sticker.emoji
        
        return info
    
    # --- 20. BUTTON MAKER ---
    @staticmethod
    def make_buttons(buttons_data: List[List[Tuple[str, str]]], prefix: str = "") -> InlineKeyboardMarkup:
        """
        Create inline keyboard buttons
        buttons_data: List of rows, each row is list of (text, callback_data)
        """
        keyboard = []
        
        for row in buttons_data:
            buttons = []
            for text, data in row:
                if prefix:
                    data = f"{prefix}_{data}"
                buttons.append(InlineKeyboardButton(text, callback_data=data))
            keyboard.append(buttons)
        
        return InlineKeyboardMarkup(keyboard)
