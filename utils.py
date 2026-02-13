# utils.py - Movie Helper Bot Utilities File
# Updated with Welcome Image, OMDb Data, Admin Mentions, and Daily Limit System

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
from pyrogram.errors import UserNotParticipant
from database import get_spelling_cache, set_spelling_cache


class MovieBotUtils:
    """
    Movie Helper Bot - Utils Class
    All advanced functions with Indian style messages
    """
    
    # --- CACHE SYSTEM ---
    _google_cache = {}
    _movie_cache = {}
    _ai_cache = {}
    
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
    
    # --- 2. ADVANCED WELCOME IMAGE (UPDATED) ---
    @staticmethod
    async def create_welcome_image(user_name, user_id, profile_pic_bytes, group_name):
        """Tumhara Custom Dark Design - Welcome Image with DP and Details"""
        try:
            def make_image():
                # --- 1. Canvas Setup ---
                W, H = 800, 400
                background_color = (15, 15, 25) 
                background = Image.new('RGB', (W, H), color=background_color)
                draw = ImageDraw.Draw(background)

                # --- 2. Watermark ---
                watermark_layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
                draw_watermark = ImageDraw.Draw(watermark_layer)
                big_text = "Asbhaibsr Bots"
                
                try:
                    font_big = ImageFont.truetype("arial.ttf", 110) 
                except:
                    font_big = ImageFont.load_default()

                bbox = draw_watermark.textbbox((0, 0), big_text, font=font_big)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x_pos = (W - text_width) // 2
                y_pos = (H - text_height) // 2
                
                draw_watermark.text((x_pos, y_pos), big_text, fill=(45, 45, 60, 150), font=font_big)
                watermark_layer = watermark_layer.rotate(10, resample=Image.BICUBIC, center=(W//2, H//2))
                background.paste(watermark_layer, (0, 0), watermark_layer)

                # --- 3. User PFP ---
                pfp_size = 200
                if profile_pic_bytes:
                    try:
                        pfp = Image.open(io.BytesIO(profile_pic_bytes)).convert("RGBA").resize((pfp_size, pfp_size))
                        mask = Image.new('L', (pfp_size, pfp_size), 0)
                        draw_mask = ImageDraw.Draw(mask)
                        draw_mask.ellipse((0, 0, pfp_size, pfp_size), fill=255)
                        
                        # White Border
                        border_size = 210
                        border_pos = 45
                        draw.ellipse((border_pos, border_pos, border_pos + border_size, border_pos + border_size), fill=(255, 255, 255))
                        background.paste(pfp, (50, 50), mask)
                    except:
                        draw.ellipse((50, 50, 250, 250), fill=(100, 100, 100))
                else:
                    draw.ellipse((50, 50, 250, 250), fill=(100, 100, 100))

                # --- 4. Text Details ---
                try:
                    font_header = ImageFont.truetype("arial.ttf", 50)
                    font_sub = ImageFont.truetype("arial.ttf", 35)
                except:
                    font_header = ImageFont.load_default()
                    font_sub = ImageFont.load_default()

                start_x = 300 
                draw.text((start_x, 60), f"🤖 {Config.BOT_USERNAME}", fill="#FFD700", font=font_header)
                draw.text((start_x, 130), f"📢 Group: {group_name[:15]}..", fill="#00FFFF", font=font_sub)
                draw.text((start_x, 180), f"👤 Name: {user_name[:20]}", fill="white", font=font_sub)
                draw.text((start_x, 230), f"🆔 ID: {user_id}", fill="#90EE90", font=font_sub)

                output = io.BytesIO()
                background.save(output, format="PNG")
                output.seek(0)
                return output

            # Async Run
            return await asyncio.get_event_loop().run_in_executor(None, make_image)
            
        except Exception as e:
            print(f"Image Error: {e}")
            return None
    
    # --- 3. ADMIN MENTIONS (LIVE FETCH - PROPER TAGGING) ---
    @staticmethod
    async def get_admin_mentions(client, chat_id):
        """Live admin fetch with proper tg://user?id= tagging"""
        mentions = []
        
        try:
            async for member in client.get_chat_members(chat_id, filter=ChatMemberStatus.ADMINISTRATOR):
                if not member.user.is_bot:
                    # Proper tag format - ALWAYS WORKS
                    mentions.append(f"<a href='tg://user?id={member.user.id}'>👮 {member.user.first_name}</a>")
            
            if not mentions:
                return "👮 Admins"
            
            return ", ".join(mentions[:5])
            
        except Exception as e:
            print(f"Admin fetch error: {e}")
            return "👮 Admins"
    
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
    
    # --- 5. OMDb MOVIE INFO (DATA MODE) ---
    @staticmethod
    async def get_omdb_info(movie_name: str):
        """OMDb se data lao dict format mein - NOT TEXT"""
        if not Config.OMDB_API_KEY:
            return None
        
        try:
            url = f"http://www.omdbapi.com/?t={quote(movie_name)}&apikey={Config.OMDB_API_KEY}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("Response") == "True":
                            return {
                                "found": True,
                                "title": data.get("Title", "N/A"),
                                "year": data.get("Year", "N/A"),
                                "rating": data.get("imdbRating", "N/A"),
                                "genre": data.get("Genre", "N/A"),
                                "plot": data.get("Plot", "N/A")[:150],
                                "poster": data.get("Poster", None)
                            }
        except Exception as e:
            print(f"OMDb Error: {e}")
            pass
        return {"found": False}
    
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
    
    # --- 11. CHECK FSUB MEMBER ---
    @staticmethod
    async def check_fsub_member(client, channel_id, user_id):
        try:
            member = await client.get_chat_member(channel_id, user_id)
            return member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]
        except UserNotParticipant:
            return False
        except:
            return False
    
    # --- 12. PROGRESS BAR ---
    @staticmethod
    def get_progress_bar(current, total, length=10):
        filled = int(current * length / total)
        bar = "█" * filled + "░" * (length - filled)
        percent = int(current * 100 / total)
        return f"{bar} {percent}%"
    
    # --- 13. CLEAN CACHE ---
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
