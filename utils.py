import re
import aiohttp
import asyncio
import g4f
import difflib
import logging
from config import Config
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class MovieBotUtils:
    
    # --- 1. ADVANCED FORMAT CHECKER (Movie vs Series) ---
    @staticmethod
    def check_movie_format(text: str) -> Tuple[str, Optional[str]]:
        """
        Returns: (format_type, corrected_name)
        format_type: 'MOVIE', 'SERIES', 'INVALID'
        """
        text_lower = text.lower().strip()
        
        # Common junk words to remove for checking
        junk_words = ["download", "movie", "film", "link", "dedo", "chahiye", 
                     "plz", "pls", "bhai", "full", "hd", "hindi", "dual", "480p", "720p", "1080p"]
        
        clean_text = text_lower
        for word in junk_words:
            clean_text = clean_text.replace(word, "")
        
        # Check for SERIES format (S01 E01 or Season Episode)
        series_patterns = [
            r'(.+?)\s*s\d{1,2}\s*e\d{1,2}',  # S01E01
            r'(.+?)\s*season\s*\d{1,2}\s*episode\s*\d{1,2}',  # Season 1 Episode 1
            r'(.+?)\s*s\d{1,2}',  # S01
            r'(.+?)\s*season\s*\d{1,2}',  # Season 1
        ]
        
        for pattern in series_patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                series_name = match.group(1).strip()
                # Extract season/episode numbers for formatting
                season_match = re.search(r's(\d{1,2})', clean_text, re.IGNORECASE)
                episode_match = re.search(r'e(\d{1,2})', clean_text, re.IGNORECASE)
                
                if season_match and episode_match:
                    formatted = f"{series_name.title()} S{season_match.group(1).zfill(2)} E{episode_match.group(1).zfill(2)}"
                elif season_match:
                    formatted = f"{series_name.title()} S{season_match.group(1).zfill(2)}"
                else:
                    formatted = f"{series_name.title()}"
                
                return "SERIES", formatted
        
        # Check for MOVIE format (Year optional)
        movie_pattern = r'^[a-zA-Z0-9\s\-\:\.\']+(\s\(\d{4}\))?$'
        if re.match(movie_pattern, text, re.IGNORECASE):
            # Extract movie name (remove year if present)
            movie_name = re.sub(r'\s*\(\d{4}\)', '', text).strip()
            return "MOVIE", movie_name.title()
        
        # Check for simple movie name (without year)
        if len(clean_text.split()) >= 1 and len(clean_text) > 2:
            return "MOVIE", clean_text.title()
        
        return "INVALID", None
    
    # --- 2. ADVANCED SPELLING CORRECTION (Multi-Source) ---
    @staticmethod
    async def advanced_spelling_correction(movie_name: str) -> Tuple[str, list]:
        """
        Get correct spelling from multiple sources
        Returns: (corrected_name, suggestions_list)
        """
        suggestions = []
        
        try:
            # Source 1: Local database suggestions
            local_matches = difflib.get_close_matches(
                movie_name, 
                MovieBotUtils.get_movie_suggestions(), 
                n=3, 
                cutoff=0.4
            )
            suggestions.extend(local_matches)
            
            # Source 2: OMDb API (if available)
            if Config.OMDB_API_KEY:
                try:
                    async with aiohttp.ClientSession() as session:
                        url = f"http://www.omdbapi.com/?s={movie_name}&apikey={Config.OMDB_API_KEY}"
                        async with session.get(url) as resp:
                            data = await resp.json()
                            
                            if data.get("Response") == "True":
                                for movie in data.get("Search", [])[:3]:
                                    title = movie.get("Title", "")
                                    if title and title.lower() != movie_name.lower():
                                        suggestions.append(title)
                except:
                    pass
            
            # Source 3: Google Search (simulated)
            # We'll use common movie database
            common_movies = MovieBotUtils.get_extended_movie_list()
            google_matches = difflib.get_close_matches(movie_name, common_movies, n=2, cutoff=0.5)
            suggestions.extend(google_matches)
            
            # Remove duplicates and original name
            suggestions = list(dict.fromkeys([s for s in suggestions if s.lower() != movie_name.lower()]))
            
            if suggestions:
                return suggestions[0], suggestions
            else:
                return movie_name, []
                
        except Exception as e:
            logger.error(f"Spelling Correction Error: {e}")
            return movie_name, []
    
    # --- 3. AI FUNCTION (with better error handling) ---
    @staticmethod
    async def get_ai_response(query: str) -> str:
        """Get AI response with better error handling"""
        try:
            # Check if query is too short
            if len(query.strip()) < 3:
                return "Please ask a longer question! 😊"
            
            movie_keywords = ["movie", "film", "series", "web series", "show", "episode", 
                            "imdb", "rating", "cast", "director", "review", "download",
                            "watch", "stream", "ott", "netflix", "amazon", "hotstar"]
            
            is_movie_query = any(keyword in query.lower() for keyword in movie_keywords)
            
            if is_movie_query:
                prompt = f"""User is asking about movies: '{query}'. 
                Provide Movie/Series Name, Year, Rating (if known), Genre and a cute Hinglish review with emojis.
                Keep it friendly and helpful."""
            else:
                prompt = f"""User says: '{query}'. 
                Reply as a cute helpful assistant in Hinglish with emojis. 
                Keep it short, sweet and friendly."""
            
            # Try multiple providers with timeout
            try:
                response = await asyncio.wait_for(
                    g4f.ChatCompletion.create_async(
                        model=Config.G4F_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                    ),
                    timeout=15
                )
                
                if response and len(response.strip()) > 10:
                    return response.strip()
                else:
                    raise Exception("Empty response")
                    
            except asyncio.TimeoutError:
                return "AI is taking too long to respond. Please try again later! ⏳"
            except Exception as e:
                logger.error(f"G4F Error: {e}")
                
                # Fallback to OMDb for movie queries
                if is_movie_query:
                    movie_name = query.split('movie')[0].split('film')[0].strip()[:30]
                    if movie_name:
                        return await MovieBotUtils.get_omdb_info_fallback(movie_name)
                
                return "I'm here to help! Try asking about movies or chat with me. 😊"
                
        except Exception as e:
            logger.error(f"AI Response Error: {e}")
            return "I'm currently busy helping others! Please try again in a moment. 🛠️"
    
    @staticmethod
    async def get_omdb_info_fallback(movie_name: str) -> str:
        """Simple OMDb fallback"""
        try:
            url = f"http://www.omdbapi.com/?t={movie_name}&apikey={Config.OMDB_API_KEY}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()
            
            if data.get("Response") == "True":
                title = data.get("Title", "N/A")
                year = data.get("Year", "N/A")
                rating = data.get("imdbRating", "N/A")
                genre = data.get("Genre", "N/A")
                
                return f"""🎬 **{title} ({year})**

⭐ **Rating:** {rating}/10
🎭 **Genre:** {genre}

_Yeh movie dekhne layak hai! 😍_
🎥 More: https://www.imdb.com/title/{data.get("imdbID")}/"""
            
            return f"❌ '{movie_name}' ki details nahi mili! Google par check karein. 🔍"
        except:
            return f"🎬 **{movie_name.title()}**\n\nKya aap is movie ke baare mein specific kuch puchna chahte hain? 😊"
    
    # --- 4. MESSAGE QUALITY CHECK (Updated) ---
    @staticmethod
    def check_message_quality(text: str) -> str:
        """
        Returns: 'CLEAN', 'JUNK', 'LINK', 'ABUSE', or 'IGNORE'
        """
        text_lower = text.lower().strip()
        
        # A. 🔗 LINK DETECTION
        link_patterns = [
            r't\.me/', r'telegram\.me/', r'http://', r'https://', 
            r'www\.', r'\.com', r'\.in', r'\.net', r'\.org', r'joinchat',
            r'bit\.ly', r'tinyurl', r'shorturl'
        ]
        for pattern in link_patterns:
            if re.search(pattern, text_lower):
                return "LINK"

        # B. 🤬 BAD WORDS
        bad_words = ["mc", "bc", "bkl", "mkl", "chutiya", "kutta", "kamina", 
                    "fuck", "bitch", "sex", "porn", "randi", "gand", "asshole",
                    "chut", "lund", "bhosdi", "madarchod", "behenchod"]
        
        tokens = text_lower.split()
        for word in bad_words:
            if word in tokens:
                return "ABUSE"

        # C. 🚫 JUNK WORDS (Reduced for better detection)
        junk_words = [
            "dedo", "chahiye", "mangta", "bhej", "send", "kardo", "karo",
            "plz", "pls", "please", "request", "link", "download", "downlod",
            "movie", "film", "series", "season", "episode"
        ]
        
        # Check if message is JUST junk words
        words = text_lower.split()
        junk_count = sum(1 for word in words if word in junk_words)
        
        if junk_count >= 2 or (len(words) <= 3 and junk_count >= 1):
            return "JUNK"
            
        return "IGNORE"
    
    # --- 5. EXTRACT NAME (Improved) ---
    @staticmethod
    def extract_content_name(text: str) -> Tuple[Optional[str], str]:
        """
        Extract name and type from message
        Returns: (name, type) where type can be 'movie', 'series', or 'unknown'
        """
        text_lower = text.lower()
        
        # Remove common request words
        remove_words = ["download", "movie", "film", "series", "link", "dedo", 
                       "chahiye", "plz", "pls", "bhai", "season", "episode", 
                       "full", "hd", "hindi", "dual", "please", "send", "mangta"]
        
        for word in remove_words:
            text_lower = text_lower.replace(word, "")
        
        text_lower = ' '.join(text_lower.split())
        
        # Check for series format first
        series_match = re.search(r'(.+?)\s*(?:s\d+|season\s*\d+)', text_lower, re.IGNORECASE)
        if series_match:
            return series_match.group(1).strip().title(), "series"
        
        # Check for movie with year
        movie_match = re.search(r'(.+?)\s*\d{4}', text_lower)
        if movie_match:
            return movie_match.group(1).strip().title(), "movie"
        
        # Just a name
        if len(text_lower) > 2:
            # Check if it looks like a movie/series name (has spaces or is capitalized)
            if ' ' in text_lower or text_lower[0].isupper():
                return text_lower.title(), "unknown"
        
        return None, "unknown"
    
    # --- 6. MOVIE DATABASE (Extended) ---
    @staticmethod
    def get_movie_suggestions():
        """Return list of popular movies for spelling suggestions"""
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
            "Avengers Endgame 2019",
            "3 Idiots 2009",
            "Dangal 2016",
            "Bahubali 2 2017",
            "Kabir Singh 2019",
            "War 2019"
        ]
    
    @staticmethod
    def get_extended_movie_list():
        """Extended list for better spelling correction"""
        return [
            "Pushpa 2", "Kalki", "Jawan", "Pathaan", "Animal", "Gadar 2",
            "OMG 2", "Mission Impossible", "Oppenheimer", "Barbie",
            "Spider-Man", "Kerala Story", "Vikram Vedha", "Brahmastra",
            "RRR", "KGF 2", "83", "Sooryavanshi", "Tenet", "Avengers",
            "3 Idiots", "Dangal", "Bahubali", "Kabir Singh", "War",
            "Shershaah", "Bhool Bhulaiyaa 2", "Drishyam 2", "Mughal-e-Azam",
            "Sholay", "DDLJ", "Kabhi Khushi Kabhie Gham", "Chennai Express",
            "Happy New Year", "Don", "Raees", "Sultan", "Tiger Zinda Hai",
            "Bajrangi Bhaijaan", "PK", "Lagaan", "Taare Zameen Par"
        ]
    
    # --- 7. SYSTEM UTILS ---
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
