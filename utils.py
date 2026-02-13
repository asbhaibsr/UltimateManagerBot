import re
import aiohttp
import asyncio
import g4f
import random
import datetime
import io
import time
from config import Config
from urllib.parse import quote
from PIL import Image, ImageDraw, ImageFont
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant, ChatAdminRequired
from database import get_spelling_cache, set_spelling_cache, is_fsub_verified, add_fsub_verified


class MovieBotUtils:
    """
    Movie Helper Bot - Utils Class
    All advanced functions with Indian style messages
    """
    
    # --- CACHE SYSTEM ---
    _google_cache = {}
    _movie_cache = {}
    _ai_cache = {}
    _fsub_check_cache = {}  # ✅ NAYA: FSUB check cache
    
    # --- 1. BIO PROTECTION (SMARTDEV LOGIC) ---
    @staticmethod
    def check_bio_safety_deep(bio: str) -> dict:
        """Bio scan - links, username, promotion detect karega"""
        if not bio:
            return {"safe": True, "issues": [], "score": 100}
        
        bio_lower = bio.lower()
        issues = []
        score = 100
        
        # Link patterns
        link_patterns = [
            r'https?://\S+', r'www\.\S+', r't\.me/\S+', r'telegram\.me/\S+',
            r'\.com\b', r'\.in\b', r'\.net\b', r'\.org\b',
            r'bit\.ly/\S+', r'tinyurl\.com/\S+'
        ]
        
        for pattern in link_patterns:
            if re.search(pattern, bio_lower):
                issues.append("🔗 Link")
                score -= 30
                break
        
        # Username
        if re.search(r'@[\w_]+', bio_lower):
            issues.append("📛 Username")
            score -= 25
        
        # Promotion words
        promo_words = ['join', 'subscribe', 'follow', 'channel', 'group', 'free']
        for word in promo_words:
            if re.search(r'\b' + word + r'\b', bio_lower):
                issues.append("📢 Promotion")
                score -= 15
                break
        
        return {
            "safe": score >= 70,
            "issues": issues,
            "score": score,
            "message": MovieBotUtils._get_bio_message(issues, score)
        }
    
    @staticmethod
    def _get_bio_message(issues, score):
        """Bio warning message in Hinglish"""
        if score >= 70:
            return "✅ Bio safe hai, koi problem nahi!"
        
        issues_text = ", ".join(issues) if issues else "Link/Username"
        
        if score < 40:
            return f"🚨 **DANGER!** Bio mein `{issues_text}` mila. Bahut risky hai!"
        else:
            return f"⚠️ **Warning:** Bio mein `{issues_text}` hai. Please hatao warna action hoga!"
    
    # --- 2. ADVANCED WELCOME STICKER (FIXED) ---
    @staticmethod
    async def create_welcome_sticker(user_photo_bytes, group_name, bot_name, user_name):
        """User ki DP ke saath welcome sticker banaye"""
        try:
            # Resize image
            img = Image.open(io.BytesIO(user_photo_bytes)).convert("RGBA")
            img = img.resize((512, 512), Image.Resampling.LANCZOS)
            
            # Circular mask
            mask = Image.new('L', (512, 512), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, 512, 512), fill=255)
            
            # Apply mask
            output = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
            output.paste(img, (0, 0), mask)
            
            # Border
            draw = ImageDraw.Draw(output)
            draw.ellipse((0, 0, 511, 511), outline=(255, 215, 0), width=12)  # Gold border
            draw.ellipse((6, 6, 505, 505), outline=(255, 255, 255), width=6)  # White inner
            
            # Try to load font, fallback to default
            try:
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
            except:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # Text
            short_group = group_name[:20] + ".." if len(group_name) > 20 else group_name
            
            # Name
            draw.text((256, 380), f"👋 {user_name[:15]}", 
                     fill=(255, 255, 255), anchor="mm", font=font_large)
            
            # Welcome message
            draw.text((256, 440), f"Welcome to", 
                     fill=(200, 200, 200), anchor="mm", font=font_small)
            
            draw.text((256, 490), f"{short_group}", 
                     fill=(255, 215, 0), anchor="mm", font=font_large)
            
            # Save
            img_bytes = io.BytesIO()
            output.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            
            return img_bytes
            
        except Exception as e:
            print(f"Sticker Error: {e}")
            return None
    
    # --- 3. ADMIN MENTIONS (LIVE FETCH) ---
    @staticmethod
    async def get_admin_mentions(client, chat_id):
        """Live admin fetch - proper tagging ke liye"""
        mentions = []
        
        try:
            # Owner first
            try:
                owner = await client.get_users(Config.OWNER_ID)
                mentions.append(f"👑 **{owner.first_name}**")
            except:
                mentions.append("👑 **Owner**")
            
            # Group admins
            async for member in client.get_chat_members(chat_id, filter="administrators"):
                if not member.user.is_bot:
                    if member.user.id != Config.OWNER_ID:
                        name = member.user.first_name[:15]
                        mentions.append(f"🛡️ **{name}**")
            
        except Exception as e:
            print(f"Admin fetch error: {e}")
        
        if not mentions:
            return "👑 **Admins**"
        
        return "\n".join(mentions[:5])  # Max 5 admins
    
    # --- 4. MOVIE FORMAT VALIDATION (BEST) ---
    @staticmethod
    def validate_movie_format_advanced(text: str) -> dict:
        """Movie name clean karo, junk words hatao, format do"""
        text_lower = text.lower().strip()
        original = text
        
        # Season/Episode detect
        session_patterns = [
            (r'season\s*(\d+)', 'S{:02d}'),
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
        
        # Language detect
        languages = {
            'hindi': '🎬 Hindi', 'english': '🎬 English', 'tamil': '🎬 Tamil',
            'telugu': '🎬 Telugu', 'malayalam': '🎬 Malayalam', 'kannada': '🎬 Kannada',
            'punjabi': '🎬 Punjabi', 'bengali': '🎬 Bengali'
        }
        
        detected_lang = ""
        for lang, display in languages.items():
            if lang in clean_text:
                detected_lang = display
                clean_text = clean_text.replace(lang, '').strip()
                break
        
        # Junk words
        junk_words = [
            "dedo", "chahiye", "chaiye", "bhejo", "send", "kardo", "karo", "do",
            "plz", "pls", "please", "request", "mujhe", "mereko", "koi", "link",
            "download", "movie", "film", "series", "full", "hd", "720p", "1080p",
            "dubbed", "dual", "audio", "bro", "bhai", "sir", "admin", "yaar"
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
        
        # Format
        correct_format = movie_name.title()
        if session_info:
            correct_format += f" {session_info}"
        if detected_lang:
            correct_format += f" {detected_lang}"
        
        return {
            'is_valid': len(found_junk) == 0,
            'found_junk': found_junk,
            'clean_name': movie_name,
            'correct_format': correct_format,
            'session_info': session_info,
            'language': detected_lang
        }
    
    # --- 5. OMDb MOVIE INFO ---
    @staticmethod
    async def get_omdb_info(movie_name: str) -> str:
        """OMDb se movie info lao with cache"""
        if not Config.OMDB_API_KEY:
            return "❌ **Sorry!** OMDb API key nahi mil rahi.\nOwner se contact karo @asbhai_bsr"
        
        # Cache check
        cached = await get_spelling_cache(f"omdb_{movie_name}")
        if cached:
            return cached
        
        try:
            url = f"http://www.omdbapi.com/?t={quote(movie_name)}&apikey={Config.OMDB_API_KEY}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=8) as resp:
                    if resp.status == 200:
                        data = await resp.json()
            
            if data.get("Response") == "True":
                title = data.get("Title", "N/A")
                year = data.get("Year", "N/A")
                rating = data.get("imdbRating", "N/A")
                genre = data.get("Genre", "N/A")
                plot = data.get("Plot", "N/A")
                
                if len(plot) > 100:
                    plot = plot[:100] + "..."
                
                stars = "⭐" * max(1, min(5, int(float(rating) // 2))) if rating != "N/A" else ""
                
                response = (
                    f"🎬 **Movie Found!**\n\n"
                    f"📽️ **{title}** ({year})\n"
                    f"{stars} **IMDb:** {rating}/10\n"
                    f"🎭 **Genre:** {genre}\n"
                    f"📝 **Story:** {plot}\n\n"
                    f"✅ **Sahi naam:** `{title}`"
                )
                
                await set_spelling_cache(f"omdb_{movie_name}", response)
                return response
            else:
                return f"❌ **'{movie_name}'** ye movie OMDb mein nahi mili!\nSpelling check karo ya kuch aur try karo."
                
        except Exception as e:
            return "❌ **OMDb busy hai!** Thodi der baad try karo."
    
    # --- 6. GOOGLE SEARCH ---
    @staticmethod
    async def get_google_search(query: str):
        """Google search with fallback"""
        cache_key = f"google_{query.lower()}"
        
        # Cache check
        if cache_key in MovieBotUtils._google_cache:
            cache_time, results = MovieBotUtils._google_cache[cache_key]
            if (datetime.datetime.now() - cache_time).seconds < 600:
                return results
        
        # Try multiple sources
        results = await MovieBotUtils._search_duckduckgo(query)
        
        if results:
            MovieBotUtils._google_cache[cache_key] = (datetime.datetime.now(), results)
            return results
        
        return []
    
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
                        
                        formatted = []
                        for href, title in results[:5]:
                            title = title.replace('&amp;', '&').replace('&quot;', '"')
                            formatted.append((href, title))
                        return formatted
        except:
            return None
    
    # --- 7. AI RESPONSE ---
    @staticmethod
    async def get_ai_response(query: str) -> str:
        """AI se Hinglish mein reply"""
        cache_key = f"ai_{query.lower()}"
        
        # Cache check
        if cache_key in MovieBotUtils._ai_cache:
            cache_time, response = MovieBotUtils._ai_cache[cache_key]
            if (datetime.datetime.now() - cache_time).seconds < 300:
                return response
        
        try:
            prompt = f"""User ne pucha: '{query}'. 
            Tum ek friendly Indian movie expert ho.
            Hinglish mein jawab do, emojis use karo.
            Short aur simple rakho, max 3-4 lines.
            Helpful bano, agar pata nahi toh bolo 'sorry yaar yeh nahi pata'."""
            
            response = await g4f.ChatCompletion.create_async(
                model=Config.G4F_MODEL,
                messages=[{"role": "user", "content": prompt}],
                timeout=10
            )
            
            if response and response.strip():
                formatted = f"🤖 **BOT:**\n\n{response.strip()}"
                MovieBotUtils._ai_cache[cache_key] = (datetime.datetime.now(), formatted)
                return formatted
            
        except Exception as e:
            print(f"AI Error: {e}")
        
        return (
            "🤖 **BOT:**\n\n"
            "Arey yaar, abhi thoda busy hoon! ⏳\n"
            "2 minute baad try karo, phir baat karte hain! 😊"
        )
    
    # --- 8. ANIME SEARCH ---
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
                            synopsis = anime.get('synopsis', 'No synopsis.')
                            if len(synopsis) > 100:
                                synopsis = synopsis[:100] + "..."
                            
                            return {
                                "title": anime['title'],
                                "score": anime.get('score', 'N/A'),
                                "episodes": anime.get('episodes', 'Unknown'),
                                "url": anime['url'],
                                "synopsis": synopsis
                            }
        except:
            pass
        return None
    
    # --- 9. MESSAGE QUALITY CHECK ---
    @staticmethod
    def check_message_quality(text: str) -> str:
        """Link/Abuse detect karo"""
        text_lower = text.lower().strip()
        
        # Links
        link_patterns = [
            r't\.me/', r'http://', r'https://', r'www\.',
            r'\.com\b', r'\.in\b', r'\.net\b', r'\.org\b'
        ]
        for pattern in link_patterns:
            if re.search(pattern, text_lower):
                return "LINK"
        
        # Abuse words
        abuse_words = [
            "mc", "bc", "bkl", "mkl", "chutiya", "kutta", "fuck", "bitch",
            "gand", "lund", "madarchod", "behenchod", "bsdk", "gandu"
        ]
        
        words = text_lower.split()
        for word in abuse_words:
            if word in words:
                return "ABUSE"
        
        return "CLEAN"
    
    # --- 10. AUTO DELETE ---
    @staticmethod
    async def auto_delete_message(client, message, delay=30):
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except:
            pass
    
    # --- 11. CHECK FSUB MEMBER (✅ UPDATED WITH CACHE) ---
    @staticmethod
    async def check_fsub_member(client, channel_id, user_id):
        """Check if user is member - with cache and database verification"""
        cache_key = f"fsub_{channel_id}_{user_id}"
        
        # Memory cache check (5 minutes)
        if cache_key in MovieBotUtils._fsub_check_cache:
            cache_time, result = MovieBotUtils._fsub_check_cache[cache_key]
            if (datetime.datetime.now() - cache_time).seconds < 300:  # 5 min
                return result
        
        # Telegram se check
        try:
            member = await client.get_chat_member(channel_id, user_id)
            result = member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]
            
            # Cache store
            MovieBotUtils._fsub_check_cache[cache_key] = (datetime.datetime.now(), result)
            
            # Clean cache if too big
            if len(MovieBotUtils._fsub_check_cache) > 1000:
                MovieBotUtils.clean_cache()
            
            return result
            
        except UserNotParticipant:
            MovieBotUtils._fsub_check_cache[cache_key] = (datetime.datetime.now(), False)
            return False
        except Exception as e:
            print(f"FSUB Check Error: {e}")
            return False
    
    # --- 12. PROGRESS BAR ---
    @staticmethod
    def get_progress_bar(current, total, length=10):
        filled = int(current * length / total)
        bar = "█" * filled + "░" * (length - filled)
        percent = int(current * 100 / total)
        return f"{bar} {percent}%"
    
    # --- 13. CLEAN CACHE (✅ UPDATED) ---
    @staticmethod
    def clean_cache():
        now = datetime.datetime.now()
        
        # Google cache
        expired = []
        for key, (cache_time, _) in MovieBotUtils._google_cache.items():
            if (now - cache_time).seconds > 600:
                expired.append(key)
        for key in expired:
            del MovieBotUtils._google_cache[key]
        
        # AI cache
        expired = []
        for key, (cache_time, _) in MovieBotUtils._ai_cache.items():
            if (now - cache_time).seconds > 300:
                expired.append(key)
        for key in expired:
            del MovieBotUtils._ai_cache[key]
        
        # FSUB cache
        expired = []
        for key, (cache_time, _) in MovieBotUtils._fsub_check_cache.items():
            if (now - cache_time).seconds > 300:
                expired.append(key)
        for key in expired:
            del MovieBotUtils._fsub_check_cache[key]
    
    # --- 14. RANDOM MOVIE ---
    @staticmethod
    async def get_random_movie():
        """Random movie for MOTD"""
        movies = [
            "Inception", "The Dark Knight", "Interstellar", "3 Idiots", 
            "Dangal", "KGF", "RRR", "Jawan", "Pathaan", "Animal",
            "Avengers Endgame", "Titanic", "The Matrix", "Shawshank Redemption"
        ]
        movie = random.choice(movies)
        
        # Try OMDb
        info = await MovieBotUtils.get_omdb_info(movie)
        if "not found" not in info.lower():
            return {
                "title": movie,
                "year": "N/A",
                "genre": "N/A",
                "rating": "N/A"
            }
        return None
    
    # --- 15. FORCE SUBSCRIBE VERIFICATION (✅ NAYA) ---
    @staticmethod
    async def verify_and_unmute(client, chat_id, user_id, channel_id):
        """Verify karo aur unmute karo agar channel joined hai"""
        is_joined = await MovieBotUtils.check_fsub_member(client, channel_id, user_id)
        
        if is_joined:
            try:
                # Database mein mark karo
                await add_fsub_verified(chat_id, user_id)
                
                # Unmute
                await client.restrict_chat_member(
                    chat_id, user_id,
                    ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True
                    )
                )
                return True
            except Exception as e:
                print(f"Unmute Error: {e}")
        return False
    
    # --- 16. FORCE SUBSCRIBE MESSAGE (✅ NAYA) ---
    @staticmethod
    def get_fsub_message(settings, user_name, channel_title, channel_link):
        """Custom force subscribe message"""
        msg_template = settings.get("fsub_welcome_msg", 
            "🔒 **Group Locked!**\n\nHello {name}! 👋\n\nIs group mein message karne ke liye pehle hamara **channel join karna hoga**:\n\n📢 **{channel}**\n\n✅ Channel join karo\n✅ \"I've Joined\" button dabao\n✅ Phir message kar sakoge\n\n_Join karne ke baad auto-unmute ho jaoge!_ 🎉")
        
        return msg_template.replace("{name}", user_name).replace("{channel}", channel_title)
