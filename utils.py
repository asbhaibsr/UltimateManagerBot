import re
import aiohttp
import asyncio
from config import Config
from pyrogram.types import ChatPermissions

class MovieBotUtils:
    @staticmethod
    async def get_ai_response(query: str) -> str:
        """AI Response logic (Simulated for speed)"""
        # Fast response without blocking
        return f"🤖 AI Response: {query} \n(AI features are limited in this fix to improve speed)"

    @staticmethod
    async def get_omdb_info(movie_name: str) -> str:
        """Get movie info using AIOHTTP (Non-blocking/Fast)"""
        try:
            url = f"http://www.omdbapi.com/?t={movie_name}&apikey={Config.OMDB_API_KEY}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()
            
            if data.get("Response") == "True":
                return (f"🎬 **{data.get('Title')} ({data.get('Year')})**\n"
                        f"⭐ Rating: {data.get('imdbRating')}/10\n"
                        f"🎭 Genre: {data.get('Genre')}")
            return None
        except Exception as e:
            return None

    @staticmethod
    def check_message_quality(text: str) -> str:
        """
        Returns: 'CLEAN', 'JUNK', or 'IGNORE'
        """
        text_lower = text.lower().strip()
        
        # 1. Junk Words List (Agar ye dikhe to DELETE)
        junk_words = [
            "dedo", "chahiye", "link", "bhej", "send", "pls", "please", "plz", 
            "lunch", "dinner", "do", "kardo", "chaiye", "download", "dowanload",
            "karo", "bhai", "yaar", "yar", "movie", "series", "hd", "480p", "720p", "1080p"
        ]
        
        # Check if text contains any junk word exactly
        words_in_text = text_lower.split()
        for word in junk_words:
            if word in words_in_text:
                return "JUNK" # Delete this
            
            # Check for attached words like "dedo." or "plz,"
            for w in words_in_text:
                if word in w and len(w) < len(word) + 3: 
                    return "JUNK"

        # 2. Strict Format Check (Regex)
        # Accepted formats: 
        # "Name" OR "Name Year" OR "Name S01" OR "Name S01 E01"
        # Sirf alphanumeric characters aur thode symbols allow karenge
        
        clean_pattern = r'^[a-zA-Z0-9\s\-\:\']+(\s\d{4}|\sS\d{2}|\sS\d{2}\s?E\d{2})?$'
        
        if re.match(clean_pattern, text, re.IGNORECASE):
            return "CLEAN" # Allow this
            
        # Agar na junk hai, na clean format hai (e.g. random chat), to IGNORE
        return "IGNORE"

    @staticmethod
    def extract_movie_name(text: str):
        """Extract clean movie name"""
        return text.strip()

    @staticmethod
    async def auto_delete_message(client, message, delay=300):
        """Auto delete message after delay"""
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except:
            pass
