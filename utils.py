import re
import aiohttp
import asyncio
import g4f
import difflib
from config import Config
from typing import Optional
from urllib.parse import quote
# Ye line add ki gayi hai error fix karne ke liye:
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class MovieBotUtils:
    
    # --- MOVIE/SERIES FORMAT VALIDATION (UPDATED) ---
    @staticmethod
    def validate_movie_format(text: str) -> dict:
        text_lower = text.lower().strip()
        
        # 1. Junk words ki list define karo
        junk_words_list = [
            "dedo", "chahiye", "chaiye", "mangta", "bhej", "send", "kardo", "karo", "do",
            "plz", "pls", "please", "request", "mujhe", "mereko", "koi", "link", 
            "download", "movie", "film", "series", "full", "hd", "480p", "720p", "1080p", 
            "hindi", "english", "dubbed", "bhai", "bro", "sir", "admin", "yaar",
            "upload", "fast", "urgent", "now", "online", "watch"
        ]
        
        # 2. Check karo user ne kon se junk words use kiye
        found_junk = []
        words = text_lower.split()
        
        # Language detect (Simple logic)
        languages = {'hindi', 'english', 'tamil', 'telugu', 'malayalam', 'kannada', 'marathi'}
        detected_lang = ""
        
        # Clean Text Generation
        clean_words = []
        for word in words:
            # Punctuation htao check karne ke liye
            clean_w = re.sub(r'[^\w]', '', word)
            
            if clean_w in junk_words_list:
                if clean_w not in found_junk:
                    found_junk.append(clean_w)
            elif clean_w in languages:
                detected_lang = clean_w.title()
            else:
                clean_words.append(word)
                
        clean_text = " ".join(clean_words).title()
        
        # Format banao
        if detected_lang:
            correct_format = f"{clean_text} [{detected_lang}]"
        else:
            correct_format = clean_text

        # Return dict me 'found_junk' add kiya hai
        return {
            'is_valid': len(found_junk) == 0, # Agar junk mila to invalid
            'found_junk': found_junk,         # Ye list bot use karega message me
            'clean_name': clean_text,
            'correct_format': correct_format,
            'search_query': clean_text.replace(" ", "+")
        }
    
    # --- CREATE FORMATTED MESSAGE ---
    @staticmethod
    def create_format_message(user_name: str, original_text: str, validation_result: dict, group_username: str = "") -> tuple:
        """Returns (message_text, keyboard_markup)"""
        
        # Create main message
        lines = [
            "╔══════════════════════════╗",
            "  ✨ **FORMAT CORRECTION** ✨",
            "╚══════════════════════════╝",
            "",
            f"👤 **User:** {user_name}",
            f"❌ **Wrong Format:** `{original_text}`",
            f"✅ **Correct Format:** {validation_result['correct_format']}",
            "",
            "📌 **Format Rules:**",
            "• Movie: **Movie Name (Year) [Language]**",
            "• Series: **Series Name S01 E01 (Year) [Language]**",
            "",
            "🔍 **Examples:**",
            "• `kalki 2024 hindi` → **Kalki (2024) [Hindi]**",
            "• `stranger things s01 e01` → **Stranger Things S01 E01**",
            ""
        ]
        
        message_text = "\n".join(lines)
        
        # Create search button with proper link
        if group_username:
            # Remove @ if present
            group_name = group_username.replace('@', '')
            search_query = validation_result['search_query']
            search_url = f"https://t.me/{group_name}?start={search_query}"
            
            buttons = [
                [InlineKeyboardButton("🔍 Search Again", url=search_url)],
                [InlineKeyboardButton("📋 Copy Format", callback_data=f"copy_{validation_result['clean_name']}")]
            ]
        else:
            buttons = [
                [InlineKeyboardButton("📋 Copy Format", callback_data=f"copy_{validation_result['clean_name']}")]
            ]
        
        return message_text, InlineKeyboardMarkup(buttons)
    
    # --- AI RESPONSE (UPDATED) ---
    @staticmethod
    async def get_ai_response(query: str, context: str = "") -> str:
        """Get AI response with better handling"""
        try:
            # Check if server is busy
            import random
            if random.random() < 0.1:  # 10% chance of simulated busy
                return "🤖 **AI Server Busy**\n\nPlease try again in a few moments! ⏳"
            
            movie_keywords = ["movie", "film", "series", "web series", "show", "episode", 
                            "imdb", "rating", "cast", "director", "review", "download",
                            "watch", "stream", "ott", "netflix", "amazon", "hotstar"]
            
            is_movie_query = any(keyword in query.lower() for keyword in movie_keywords)
            
            if is_movie_query:
                prompt = f"""User is asking about: '{query}'. 
                Provide Movie/Series Name, Year, Rating, Genre and a short review in Hinglish with emojis.
                Keep it under 150 words."""
            else:
                prompt = f"""User says: '{query}'. 
                Reply as a helpful assistant in Hinglish with emojis.
                Keep it friendly and under 100 words."""
            
            # Add context if available
            if context:
                prompt = f"Context: {context}\n\n{prompt}"
            
            response = await g4f.ChatCompletion.create_async(
                model=Config.G4F_MODEL,
                messages=[{"role": "user", "content": prompt}],
                timeout=30
            )
            
            if not response.strip():
                if is_movie_query:
                    return "🎬 **Movie Information**\n\nSorry, couldn't fetch details right now. Please try the official IMDB website for accurate information! 📡"
                else:
                    return "🤖 **AI Response**\n\nHmm, let me think... Actually, why don't you ask me about movies? I'm great at that! 🍿"
            
            # Format response nicely
            formatted_response = f"🤖 **AI Response**\n\n{response.strip()}\n\n✨ *Powered by Movie Helper Bot*"
            return formatted_response
            
        except Exception as e:
            print(f"AI Error: {e}")
            return "🤖 **AI Server Busy**\n\nOur AI is currently processing many requests. Please try again in a few minutes! ⏳"
    
    # --- OMDb INFO ---
    @staticmethod
    async def get_omdb_info(movie_name: str) -> str:
        """Get movie info using OMDb"""
        try:
            url = f"http://www.omdbapi.com/?t={quote(movie_name)}&apikey={Config.OMDB_API_KEY}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    data = await resp.json()
            
            if data.get("Response") == "True":
                title = data.get("Title", "N/A")
                year = data.get("Year", "N/A")
                rating = data.get("imdbRating", "N/A")
                genre = data.get("Genre", "N/A")
                plot = data.get("Plot", "N/A")[:150]
                
                response_lines = [
                    "🎬 **Movie Information** 🎬",
                    "",
                    f"📝 **Title:** {title}",
                    f"📅 **Year:** {year}",
                    f"⭐ **Rating:** {rating}/10",
                    f"🎭 **Genre:** {genre}",
                    f"📖 **Plot:** {plot}...",
                    "",
                    f"🔗 **IMDb:** https://www.imdb.com/title/{data.get('imdbID', '')}/",
                    "",
                    "_Enjoy watching! 🍿_"
                ]
                
                return "\n".join(response_lines)
            return "❌ **Movie Not Found**\n\nSorry, couldn't find details for this movie on IMDb."
        except:
            return "❌ **IMDb Service Unavailable**\n\nPlease check the movie name and try again later."
    
    # --- MESSAGE QUALITY CHECK (UPDATED) ---
    @staticmethod
    def check_message_quality(text: str) -> str:
        """
        Returns: 'CLEAN', 'JUNK', 'LINK', 'ABUSE', or 'IGNORE'
        """
        text_lower = text.lower().strip()
        
        # A. 🔗 LINK DETECTION
        link_patterns = [
            r't\.me/', r'telegram\.me/', r'http://', r'https://', 
            r'www\.', r'\.com', r'\.in', r'\.net', r'\.org', r'\.io',
            r'joinchat', r'bit\.ly', r'tinyurl', r'goo\.gl', r'shorturl'
        ]
        for pattern in link_patterns:
            if re.search(pattern, text_lower):
                return "LINK"
        
        # B. 🤬 ABUSE WORDS
        abuse_words = [
            "mc", "bc", "bkl", "mkl", "chutiya", "kutta", "kamina", "fuck", 
            "bitch", "sex", "porn", "randi", "gand", "lund", "bhosda", 
            "madarchod", "behenchod", "harami", "ullu", "gadha", "bewakuf",
            "idiot", "stupid", "moron", "lauda", "chut", "gaand", "bsdk",
            "bhadwa", "chodu", "gandu", "lavde", "rand", "kutti", "kamina",
            "gandu", "motherfucker", "asshole", "bastard", "bloody", "damn"
        ]
        
        words = text_lower.split()
        for word in abuse_words:
            if word in words:
                return "ABUSE"
        
        # C. 🚫 JUNK WORDS
        junk_words = [
            "dedo", "chahiye", "chaiye", "mangta", "bhej", "send", "kardo", 
            "karo", "do", "plz", "pls", "please", "request", "link", "download", 
            "downlod", "movie", "film", "series", "season", "episode", "hd", 
            "480p", "720p", "1080p", "bhai", "bro", "sir", "admin", "yaar", 
            "hello", "hi", "hey", "lunch", "dinner", "mujhe", "mereko", "koi",
            "full", "complete", "part", "version", "print", "quality", "bluray",
            "webdl", "torrent", "magnet", "subtitle", "dual", "audio", "dubbed"
        ]
        
        for word in junk_words:
            if word in words:
                for w in words:
                    clean_w = w.strip('.,!?;:')
                    if clean_w == word:
                        return "JUNK"
        
        # D. ✅ CLEAN FORMAT
        clean_pattern = r'^[a-zA-Z0-9\s\-\:\'\&]+(?:\s\d{4})?(?:\s?[Ss]\d{1,2})?(?:\s?[Ee]\d{1,2})?$'
        if re.match(clean_pattern, text, re.IGNORECASE):
            return "CLEAN"
        
        return "IGNORE"
    
    # --- SPELLING SUGGESTION ---
    @staticmethod
    def get_spelling_suggestion(user_text: str, movie_list: list) -> Optional[str]:
        """Suggest correct spelling"""
        matches = difflib.get_close_matches(user_text, movie_list, n=1, cutoff=0.5)
        if matches:
            return matches[0]
        return None
    
    # --- EXTRACT CLEAN NAME ---
    @staticmethod
    def extract_movie_name(text: str) -> str:
        """Extract clean movie/series name"""
        text = text.lower()
        
        # Remove common words
        remove_words = [
            "download", "movie", "film", "series", "link", "dedo", "chahiye", 
            "plz", "pls", "bhai", "season", "episode", "full", "hd", "hindi", 
            "english", "dual", "dubbed", "request", "send", "give", "me", 
            "please", "want", "need", "looking", "for", "ka", "ki", "ke"
        ]
        
        for word in remove_words:
            text = text.replace(word, "")
        
        # Clean up
        text = re.sub(r'[^\w\s]', '', text)
        text = ' '.join(text.split())
        
        if len(text) > 1:
            return text.title()
        return ""
    
    # --- SYSTEM UTILS ---
    @staticmethod
    async def auto_delete_message(client, message, delay: int = Config.AUTO_DELETE_TIME):
        await asyncio.sleep(delay)
        try:
            await client.delete_messages(message.chat.id, message.id)
        except:
            pass
    
    @staticmethod
    async def broadcast_messages(client, chat_ids, message_text, delay: float = Config.BROADCAST_DELAY):
        success = 0
        failed = 0
        for chat_id in chat_ids:
            try:
                await client.send_message(chat_id, message_text)
                success += 1
                await asyncio.sleep(delay)
            except Exception as e:
                failed += 1
        return success, failed
    
    # --- MOVIE DATABASE ---
    @staticmethod
    def get_movie_suggestions():
        return [
            "Pushpa 2 The Rule 2024",
            "Kalki 2898 AD",
            "Jawan 2023",
            "Pathaan 2023",
            "Animal 2023",
            "Gadar 2 2023",
            "OMG 2 2023",
            "Mission Impossible 2023",
            "Oppenheimer 2023",
            "Barbie 2023",
            "Spider-Man Across The Spider-Verse",
            "The Kerala Story 2023",
            "Vikram Vedha 2022",
            "Brahmastra 2022",
            "RRR 2022",
            "KGF Chapter 2 2022",
            "83 2021",
            "Sooryavanshi 2021",
            "Tenet 2020",
            "Avengers Endgame 2019"
        ]
