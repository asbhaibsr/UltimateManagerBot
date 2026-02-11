import re
import aiohttp
import asyncio
import g4f
import random
import datetime
import io
from config import Config
from urllib.parse import quote
from PIL import Image, ImageDraw, ImageFont
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus  # <-- Ye Missing tha
from pyrogram.errors import UserNotParticipant # <-- Ye bhi Missing tha
from database import get_spelling_cache, set_spelling_cache

class MovieBotUtils:
    
    # --- CACHE SYSTEM ---
    _google_cache = {}
    _movie_cache = {}
    _ai_cache = {}
    
    # --- 1. BIO PROTECTION DEEP SCAN ---
    @staticmethod
    def check_bio_safety_deep(bio: str) -> dict:
        """Deep scan bio - returns detailed report"""
        if not bio:
            return {"safe": True, "issues": [], "score": 100}
        
        bio_lower = bio.lower()
        issues = []
        score = 100
        
        # Check for links
        link_patterns = [
            r'https?://\S+', r'www\.\S+', r't\.me/\S+', r'telegram\.me/\S+',
            r'\.com\b', r'\.in\b', r'\.net\b', r'\.org\b', r'\.io\b',
            r'bit\.ly/\S+', r'tinyurl\.com/\S+', r'goo\.gl/\S+'
        ]
        
        for pattern in link_patterns:
            if re.search(pattern, bio_lower):
                issues.append("link_detected")
                score -= 30
                break
        
        # Check for usernames
        if re.search(r'@[\w_]+', bio_lower):
            issues.append("username_detected")
            score -= 25
        
        # Check for promotion words
        promo_words = ['join', 'subscribe', 'follow', 'channel', 'group', 'update', 'news', 
                      'latest', 'free', 'click', 'link', 'visit', 'buy', 'purchase', 'offer']
        
        for word in promo_words:
            if re.search(r'\b' + word + r'\b', bio_lower):
                issues.append("promotion_detected")
                score -= 10
                break
        
        # Check for contact info
        contact_patterns = [r'\+\d{10,}', r'\d{10,}', r'whatsapp', r'call', r'contact']
        for pattern in contact_patterns:
            if re.search(pattern, bio_lower):
                issues.append("contact_detected")
                score -= 15
                break
        
        # Check for banned words
        banned_words = ['admin', 'moderator', 'owner', 'creator', 'hack', 'crack', 'paid']
        for word in banned_words:
            if re.search(r'\b' + word + r'\b', bio_lower):
                issues.append("banned_word")
                score -= 20
                break
        
        # Check bio length (too long might be promotion)
        if len(bio) > 150:
            issues.append("long_bio")
            score -= 5
        
        return {
            "safe": score >= 70,
            "issues": issues,
            "score": score,
            "bio_preview": bio[:50] + "..." if len(bio) > 50 else bio
        }
    
    # --- 2. GOOGLE SEARCH WITH CACHE ---
    @staticmethod
    async def get_google_search(query: str):
        """Fast Google search with cache"""
        cache_key = f"google_{query.lower()}"
        
        if cache_key in MovieBotUtils._google_cache:
            cache_time, results = MovieBotUtils._google_cache[cache_key]
            if (datetime.datetime.now() - cache_time).seconds < 600:
                return results
        
        # Try multiple search engines in parallel
        tasks = [
            MovieBotUtils._search_duckduckgo(query),
            MovieBotUtils._search_brave(query)
        ]
        
        results = None
        for completed in asyncio.as_completed(tasks, timeout=5):
            try:
                res = await completed
                if res:
                    results = res
                    break
            except:
                continue
        
        if results:
            MovieBotUtils._google_cache[cache_key] = (datetime.datetime.now(), results)
            if len(MovieBotUtils._google_cache) > Config.MAX_CACHE_SIZE:
                oldest = min(MovieBotUtils._google_cache.keys(), 
                           key=lambda k: MovieBotUtils._google_cache[k][0])
                del MovieBotUtils._google_cache[oldest]
        
        return results or []
    
    @staticmethod
    async def _search_duckduckgo(query):
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=8) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        results = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)">([^<]+)</a>', text)
                        if results:
                            formatted = []
                            for href, title in results[:5]:
                                title = title.replace('&amp;', '&').replace('&quot;', '"')
                                formatted.append((href, title))
                            return formatted
        except:
            return None
    
    @staticmethod
    async def _search_brave(query):
        try:
            url = f"https://search.brave.com/search?q={quote(query)}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=8) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        results = re.findall(r'<a data-testid="result-title-a" href="([^"]+)".*?<span[^>]*>([^<]+)</span>', text, re.DOTALL)
                        if results:
                            formatted = []
                            for href, title in results[:5]:
                                if href.startswith('http'):
                                    formatted.append((href, title.strip()))
                            return formatted
        except:
            return None
    
    # --- 3. ANIME SEARCH ---
    @staticmethod
    async def get_anime_info(query: str):
        try:
            url = f"https://api.jikan.moe/v4/anime?q={quote(query)}&limit=1"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=8) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('data') and len(data['data']) > 0:
                            anime = data['data'][0]
                            return {
                                "title": anime['title'],
                                "score": anime.get('score', 'N/A'),
                                "episodes": anime.get('episodes', 'Unknown'),
                                "url": anime['url'],
                                "synopsis": anime.get('synopsis', 'No details.')[:150] + "..." if anime.get('synopsis') else "No synopsis."
                            }
        except:
            pass
        return None
    
    # --- 4. MOVIE FORMAT VALIDATION (ADVANCED) ---
    @staticmethod
    def validate_movie_format_advanced(text: str) -> dict:
        """Advanced movie format validation with session detection"""
        text_lower = text.lower().strip()
        original = text
        
        # Session/Season detection
        session_patterns = [
            (r'season\s*(\d+)', 'S{:02d}'),
            (r's[e]?[e]?[s]?[i]?[o]?[n]?\s*(\d+)', 'S{:02d}'),
            (r's(\d{1,2})', 'S{:02d}'),
            (r'episode\s*(\d+)', 'E{:02d}'),
            (r'ep\s*(\d+)', 'E{:02d}'),
            (r'e(\d{1,2})', 'E{:02d}')
        ]
        
        session_info = ""
        clean_text = text_lower
        
        for pattern, fmt in session_patterns:
            match = re.search(pattern, text_lower)
            if match:
                num = int(match.group(1))
                session_info = fmt.format(num)
                clean_text = re.sub(pattern, '', clean_text).strip()
                break
        
        # Language detection
        languages = {'hindi', 'english', 'tamil', 'telugu', 'malayalam', 'kannada', 
                    'punjabi', 'bengali', 'gujarati', 'marathi'}
        detected_lang = ""
        
        for lang in languages:
            if lang in clean_text:
                detected_lang = lang.title()
                clean_text = clean_text.replace(lang, '').strip()
                break
        
        # Remove junk words
        junk_words = [
            "dedo", "chahiye", "chaiye", "bhejo", "send", "kardo", "karo", "do",
            "plz", "pls", "please", "request", "mujhe", "mereko", "koi", "link", 
            "download", "movie", "film", "series", "full", "hd", "480p", "720p", 
            "1080p", "webseries", "episode", "dubbed", "dual", "audio", "print",
            "org", "movies", "dena", "admin", "yaar", "upload", "uploded", "zaldi",
            "fast", "bro", "bhai", "sir", "hello", "hi", "movie", "film"
        ]
        
        found_junk = []
        words = clean_text.split()
        clean_words = []
        
        for word in words:
            clean_w = re.sub(r'[^\w]', '', word)
            if clean_w in junk_words:
                if clean_w not in found_junk:
                    found_junk.append(clean_w)
            elif len(clean_w) >= 2 or clean_w.isdigit():
                clean_words.append(word)
        
        movie_name = " ".join(clean_words).strip()
        
        if not movie_name:
            movie_name = original[:30]
        
        # Format correctly
        correct_format = movie_name.title()
        if session_info:
            correct_format += f" {session_info}"
        if detected_lang:
            correct_format += f" [{detected_lang}]"
        
        return {
            'is_valid': len(found_junk) == 0,
            'found_junk': found_junk,
            'clean_name': movie_name,
            'correct_format': correct_format,
            'session_info': session_info,
            'language': detected_lang,
            'search_query': movie_name.replace(" ", "+")
        }
    
    # --- 5. OMDb INFO WITH CACHE ---
    @staticmethod
    async def get_omdb_info(movie_name: str) -> str:
        """Get movie info from OMDb with caching"""
        if not Config.OMDB_API_KEY:
            return "❌ OMDb API Key Missing!"
        
        # Check cache
        cached = await get_spelling_cache(f"omdb_{movie_name}")
        if cached:
            return cached
        
        try:
            url = f"http://www.omdbapi.com/?t={quote(movie_name)}&apikey={Config.OMDB_API_KEY}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
            
            if data.get("Response") == "True":
                title = data.get("Title", "N/A")
                year = data.get("Year", "N/A")
                rating = data.get("imdbRating", "N/A")
                genre = data.get("Genre", "N/A")
                plot = data.get("Plot", "N/A")
                director = data.get("Director", "N/A")
                actors = data.get("Actors", "N/A")
                
                if len(plot) > 150:
                    plot = plot[:150] + "..."
                
                rating_star = "⭐" if rating != "N/A" else ""
                
                response = (
                    f"🎬 **Movie Info**\n\n"
                    f"📝 **Title:** {title}\n"
                    f"📅 **Year:** {year}\n"
                    f"{rating_star} **IMDb:** {rating}/10\n"
                    f"🎭 **Genre:** {genre}\n"
                    f"🎬 **Director:** {director}\n"
                    f"👥 **Cast:** {actors[:50]}...\n"
                    f"📖 **Plot:** {plot}\n\n"
                    f"✨ **Correct Name:** `{title}`"
                )
                
                await set_spelling_cache(f"omdb_{movie_name}", response)
                return response
            else:
                return f"❌ '{movie_name}' not found on IMDb"
                
        except Exception as e:
            return "❌ OMDb service busy, try again later"
    
    # --- 6. RANDOM MOVIE ---
    @staticmethod
    async def get_random_movie():
        if not Config.OMDB_API_KEY:
            return None
        
        random_ids = [
            "tt1375666", "tt0816692", "tt0468569", "tt0111161", "tt0109830",
            "tt0137523", "tt0120737", "tt0910970", "tt4154796", "tt7286456",
            "tt2560142", "tt0944947", "tt0903747", "tt1475582", "tt2356777"
        ]
        
        movie_id = random.choice(random_ids)
        
        try:
            url = f"http://www.omdbapi.com/?i={movie_id}&apikey={Config.OMDB_API_KEY}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
            if data.get("Response") == "True":
                return {
                    "title": data.get("Title", "Unknown"),
                    "year": data.get("Year", "N/A"),
                    "genre": data.get("Genre", "N/A"),
                    "rating": data.get("imdbRating", "N/A")
                }
        except:
            pass
        
        return None
    
    # --- 7. AI RESPONSE WITH CACHE ---
    @staticmethod
    async def get_ai_response(query: str, context: str = "") -> str:
        """Fast AI response with caching"""
        cache_key = f"ai_{query.lower()}"
        
        if cache_key in MovieBotUtils._ai_cache:
            cache_time, response = MovieBotUtils._ai_cache[cache_key]
            if (datetime.datetime.now() - cache_time).seconds < 300:
                return response
        
        try:
            movie_keywords = ["movie", "film", "series", "web series", "show", "episode", 
                            "imdb", "rating", "cast", "director", "review", "ott"]
            
            is_movie = any(k in query.lower() for k in movie_keywords)
            
            if is_movie:
                prompt = f"""User asked: '{query}'. Reply in Hinglish with emojis, max 100 words. 
                Give movie/series name, year, rating if known, and short review. Be friendly!"""
            else:
                prompt = f"""User said: '{query}'. Reply in casual Hinglish with emojis, max 60 words. 
                Be helpful and friendly, like a friend chatting!"""
            
            response = await g4f.ChatCompletion.create_async(
                model=Config.G4F_MODEL,
                messages=[{"role": "user", "content": prompt}],
                timeout=12
            )
            
            if response and response.strip():
                formatted = f"🤖 **Bhai**\n\n{response.strip()}"
                MovieBotUtils._ai_cache[cache_key] = (datetime.datetime.now(), formatted)
                return formatted
            else:
                return "🤖 **Bhai**\n\nKuch technical dikkat aa rahi hai, thodi der baad try kar bro! ⏳"
                
        except Exception as e:
            return "🤖 **Bhai**\n\nAI server thoda busy hai, 2 min baad try kar! 🎬"
    
    # --- 8. MESSAGE QUALITY CHECK ---
    @staticmethod
    def check_message_quality(text: str) -> str:
        text_lower = text.lower().strip()
        
        # Link Detection
        link_patterns = [
            r't\.me/', r'telegram\.me/', r'http://', r'https://', 
            r'www\.', r'\.com\b', r'\.in\b', r'\.net\b', r'\.org\b',
            r'joinchat', r'bit\.ly', r'tinyurl', r'goo\.gl'
        ]
        for pattern in link_patterns:
            if re.search(pattern, text_lower):
                return "LINK"
        
        # Abuse Words
        abuse_words = [
            "mc", "bc", "bkl", "mkl", "chutiya", "kutta", "kamina", "fuck", 
            "bitch", "randi", "gand", "lund", "bhosda", "madarchod", "behenchod",
            "harami", "ullu", "gadha", "bewakuf", "idiot", "stupid", "moron",
            "lauda", "chut", "gaand", "bsdk", "bhadwa", "chodu", "gandu", "lavde"
        ]
        
        words = text_lower.split()
        for word in abuse_words:
            if word in words:
                return "ABUSE"
        
        return "CLEAN"
    
    # --- 9. AUTO DELETE ---
    @staticmethod
    async def auto_delete_message(client, message, delay: int = Config.AUTO_DELETE_TIME):
        await asyncio.sleep(delay)
        try:
            await client.delete_messages(message.chat.id, message.id)
        except:
            pass
    
    # --- 10. CREATE WELCOME STICKER WITH DP (FIXED - NO FONT DEPENDENCY) ---
    @staticmethod
    async def create_welcome_sticker(user_photo_bytes, group_name, bot_name):
        """Create welcome sticker with user DP and group name - FIXED for Linux servers"""
        try:
            img = Image.open(io.BytesIO(user_photo_bytes)).convert("RGBA")
            img = img.resize((512, 512), Image.Resampling.LANCZOS)
            
            # Create circular mask
            mask = Image.new('L', (512, 512), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, 512, 512), fill=255)
            
            # Apply mask
            output = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
            output.paste(img, (0, 0), mask)
            
            # Add border
            draw = ImageDraw.Draw(output)
            draw.ellipse((0, 0, 511, 511), outline=(255, 255, 255), width=5)
            
            # --- FONT FIX FOR LINUX SERVERS ---
            # Linux servers (Koyeb/Railway) mein arial.ttf nahi hota
            # Isliye default font use karo aur text size adjust karo
            try:
                # Default font - ye sab servers par available hai
                font = ImageFont.load_default()
                font_small = ImageFont.load_default()
            except:
                # Agar font load nahi hua to bina text ke sticker bhejo
                img_bytes = io.BytesIO()
                output.save(img_bytes, format="PNG")
                img_bytes.seek(0)
                return img_bytes
            # --- FONT FIX END ---
            
            # Text drawing with default font (coordinates adjusted)
            # Group name - trim if too long
            short_group = group_name[:15] + ".." if len(group_name) > 15 else group_name
            draw.text((256, 460), f"Welcome to {short_group}", 
                     fill=(255, 255, 255), anchor="mm", font=font)
            draw.text((256, 490), f"@{bot_name}", 
                     fill=(200, 200, 200), anchor="mm", font=font_small)
            
            img_bytes = io.BytesIO()
            output.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            
            return img_bytes
        except Exception as e:
            print(f"Sticker Error: {e}")
            return None
    
    # --- 11. GET ADMIN MENTIONS ---
    @staticmethod
    async def get_admin_mentions(client, chat_id, limit=5):
        """Get admin mentions for tagging"""
        mentions = []
        try:
            async for member in client.get_chat_members(chat_id, filter="administrators"):
                if not member.user.is_bot and member.user.id != Config.OWNER_ID:
                    mentions.append(f"👑 {member.user.mention}")
                    if len(mentions) >= limit:
                        break
        except:
            pass
        
        if not mentions:
            return "👑 **Admins**"
        
        return "\n".join(mentions)
    
    # --- 12. PROGRESS BAR ---
    @staticmethod
    def get_progress_bar(current, total, length=10):
        """Create progress bar for broadcasts"""
        filled = int(current * length / total)
        bar = "█" * filled + "░" * (length - filled)
        percentage = int(current * 100 / total)
        return f"{bar} {percentage}%"
    
    # --- 13. CHECK FSUB MEMBER ---
    @staticmethod
    async def check_fsub_member(client, channel_id, user_id):
        """Check if user is member of channel - with error handling"""
        try:
            member = await client.get_chat_member(channel_id, user_id)
            return member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED, ChatMemberStatus.KICKED]
        except UserNotParticipant:
            return False
        except Exception:
            return False
    
    # --- 14. CLEAN CACHE ---
    @staticmethod
    def clean_cache():
        """Clean expired cache"""
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
