import re
import aiohttp
import asyncio
import g4f
import difflib
from config import Config
from typing import Optional

class MovieBotUtils:
    
    # --- 1. AI FUNCTION (SMART RESPONSE) ---
    @staticmethod
    async def get_ai_response(query: str) -> str:
        """Get AI response in Hinglish"""
        try:
            movie_keywords = ["movie", "film", "series", "web series", "show", "episode", 
                            "imdb", "rating", "cast", "director", "review", "download",
                            "watch", "stream", "ott", "netflix", "amazon", "hotstar"]
            
            is_movie_query = any(keyword in query.lower() for keyword in movie_keywords)
            
            if is_movie_query:
                prompt = f"""User is asking about: '{query}'. Provide Movie Name, Year, Rating, Genre and a cute Hinglish review with emojis."""
            else:
                prompt = f"""User says: '{query}'. Reply as a cute Indian girl in Hinglish with emojis."""
            
            response = await g4f.ChatCompletion.create_async(
                model=Config.G4F_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            
            # Fallback to OMDb if G4F fails or empty
            if not response.strip() and is_movie_query:
                movie_name = query.split('movie')[0].split('film')[0].strip()
                if movie_name:
                    response = await MovieBotUtils.get_omdb_info(movie_name)
            
            return response if response.strip() else "Sorry yaar, samajh nahi aaya! 😅"
        except Exception as e:
            print(f"AI Error: {e}")
            return "Server busy hai, baad me try karna! 😅"

    @staticmethod
    async def get_omdb_info(movie_name: str) -> str:
        """Get movie info using OMDb"""
        try:
            url = f"http://www.omdbapi.com/?t={movie_name}&apikey={Config.OMDB_API_KEY}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()
            
            if data.get("Response") == "True":
                return f"""🎬 **Movie Info:**
📝 **Name:** {data.get("Title")}
📅 **Year:** {data.get("Year")}
⭐ **Rating:** {data.get("imdbRating")}/10
🎭 **Genre:** {data.get("Genre")}
🌐 **Link:** https://www.imdb.com/title/{data.get("imdbID")}/

Mast movie hai! 😍"""
            return "Movie details nahi mili! 😕"
        except:
            return "OMDb API Error! 📡"

    # --- 2. ADVANCED MESSAGE CHECKER (SECURITY++) ---
    @staticmethod
    def check_message_quality(text: str) -> str:
        """
        Returns: 'CLEAN', 'JUNK', 'LINK', 'ABUSE', or 'IGNORE'
        """
        text_lower = text.lower().strip()
        
        # A. 🔗 LINK DETECTION (Security)
        link_patterns = [
            r't\.me/', r'telegram\.me/', r'http://', r'https://', 
            r'www\.', r'\.com', r'\.in', r'\.net', r'\.org', r'joinchat'
        ]
        for pattern in link_patterns:
            if re.search(pattern, text_lower):
                return "LINK"

        # B. 🤬 BAD WORDS (Abuse Filter)
        bad_words = ["mc", "bc", "bkl", "mkl", "chutiya", "kutta", "kamina", "fuck", "bitch", "sex", "porn", "randi", "gand"]
        tokens = text_lower.split()
        for word in bad_words:
            if word in tokens:
                return "ABUSE"

        # C. 🚫 JUNK WORDS
        junk_words = [
            "dedo", "chahiye", "chaiye", "mangta", "bhej", "send", "kardo", "karo", "do",
            "plz", "pls", "please", "request", "link", "download", "downlod",
            "movie", "film", "series", "season", "episode", "hd", "480p", "720p",
            "bhai", "bro", "sir", "admin", "yaar", "hello", "hi", "lunch", "dinner"
        ]
        
        for word in junk_words:
            if word in tokens:
                return "JUNK"
            # Check for hidden junk (e.g., "link.")
            for w in tokens:
                clean_w = w.replace('.', '').replace(',', '')
                if clean_w == word:
                    return "JUNK"

        # D. ✅ CLEAN FORMAT CHECK (Strict)
        clean_pattern = r'^[a-zA-Z0-9\s\-\:\']+(\s\d{4})?(\s?S\d{1,2})?(\s?E\d{1,2})?$'
        if re.match(clean_pattern, text, re.IGNORECASE):
            return "CLEAN"
            
        return "IGNORE"

    # --- 3. SPELLING SUGGESTER (SMART FEATURE) ---
    @staticmethod
    def get_spelling_suggestion(user_text: str, movie_list: list) -> Optional[str]:
        """User='Iron Mn' -> Returns='Iron Man'"""
        matches = difflib.get_close_matches(user_text, movie_list, n=1, cutoff=0.6)
        if matches:
            return matches[0]
        return None

    # --- 4. EXTRACT NAME ---
    @staticmethod
    def extract_movie_name(text: str) -> Optional[str]:
        text = text.lower()
        remove_words = ["download", "movie", "film", "series", "link", "dedo", "chahiye", 
                       "plz", "pls", "bhai", "season", "episode", "full", "hd", "hindi", "dual"]
        for word in remove_words:
            text = text.replace(word, "")
        
        text = ' '.join(text.split())
        
        # Logic for S01/Year extraction
        series_match = re.search(r'(.+?)\s*(?:s\d+|e\d+)', text, re.IGNORECASE)
        if series_match: return series_match.group(1).strip().title()
            
        movie_match = re.search(r'(.+?)\s*\d{4}', text)
        if movie_match: return movie_match.group(1).strip().title()
            
        if len(text) > 1: return text.title()
        return None

    # --- 5. SYSTEM UTILS ---
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
