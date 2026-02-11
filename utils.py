import re
import aiohttp
import asyncio
import g4f
import difflib
import random
from config import Config
from typing import Optional
from urllib.parse import quote
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class MovieBotUtils:
    
    # --- 1. BIO PROTECTION REGEX ---
    @staticmethod
    def check_bio_safety(bio: str) -> bool:
        """Returns False if bio contains links or usernames"""
        if not bio: return True
        bio_lower = bio.lower()
        
        # Regex for Links and Usernames
        unsafe_pattern = r'(https?://|www\.|t\.me/|telegram\.me/|\.com|\.net|\.org|@[\w_]+)'
        
        if re.search(unsafe_pattern, bio_lower):
            return False
        return True

    # --- 2. GOOGLE SEARCH (FIXED - Working without API) ---
    @staticmethod
    async def get_google_search(query: str):
        """Fetch Top 5 Google Results using multiple fallback methods"""
        
        # Method 1: DuckDuckGo HTML API (Reliable, no API key)
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        
                        # Extract results with improved regex
                        results = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)">([^<]+)</a>', text)
                        
                        if results:
                            formatted_results = []
                            for href, title in results[:5]:
                                # Clean HTML entities
                                title = title.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', "'")
                                formatted_results.append((href, title))
                            return formatted_results
        except Exception as e:
            print(f"DDG Search Error: {e}")
        
        # Method 2: Brave Search (Free, no API key)
        try:
            url = f"https://search.brave.com/search?q={quote(query)}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        
                        # Extract results
                        results = re.findall(r'<a data-testid="result-title-a" href="([^"]+)".*?<span[^>]*>([^<]+)</span>', text, re.DOTALL)
                        
                        if results:
                            formatted_results = []
                            for href, title in results[:5]:
                                if href.startswith('http'):
                                    formatted_results.append((href, title.strip()))
                            return formatted_results
        except Exception as e:
            print(f"Brave Search Error: {e}")
        
        # Method 3: Simple fallback to Google frontend (might work sometimes)
        try:
            url = f"https://www.google.com/search?q={quote(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "en-US,en;q=0.9"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        
                        # Extract results
                        results = re.findall(r'<a href="/url\?q=([^&"]+)[^>]*><br><h3[^>]*>([^<]+)</h3>', text)
                        
                        if results:
                            formatted_results = []
                            for href, title in results[:5]:
                                if href.startswith('http'):
                                    formatted_results.append((href, title))
                            return formatted_results
        except Exception as e:
            print(f"Google Frontend Error: {e}")
        
        # No results found
        return []

    # --- 3. ANIME SEARCH (Jikan API) ---
    @staticmethod
    async def get_anime_info(query: str):
        """Fetch Anime Info from Jikan API"""
        try:
            url = f"https://api.jikan.moe/v4/anime?q={quote(query)}&limit=1"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('data') and len(data['data']) > 0:
                            anime = data['data'][0]
                            return {
                                "title": anime['title'],
                                "score": anime.get('score', 'N/A'),
                                "episodes": anime.get('episodes', 'Unknown'),
                                "url": anime['url'],
                                "synopsis": anime.get('synopsis', 'No details available.')[:200] + "..." if anime.get('synopsis') else "No synopsis available."
                            }
        except Exception as e:
            print(f"Anime API Error: {e}")
        return None

    # --- 4. MOVIE/SERIES FORMAT VALIDATION ---
    @staticmethod
    def validate_movie_format(text: str) -> dict:
        text_lower = text.lower().strip()
        
        # Junk words list - NO HARDCODED MOVIE NAMES
        junk_words_list = [
            "dedo", "chahiye", "chaiye", "season", "bhejo", "send", "kardo", "karo", "do",
            "plz", "pls", "please", "request", "mujhe", "mereko", "koi", "link", 
            "download", "movie", "film", "series", "full", "hd", "480p", "720p", "1080p", 
            "webseries", "episode", "dubbed", "hindi", "english", "tamil", "telugu",
            "dual", "audio", "print", "org", "movies", "dena", "admin", "yaar", 
            "upload", "uploded", "zaldi", "fast", "bro", "bhai", "sir", "hello", "hi"
        ]
        
        # Check for junk words
        found_junk = []
        words = text_lower.split()
        
        # Language detection
        languages = {'hindi', 'english', 'tamil', 'telugu', 'malayalam', 'kannada', 'marathi', 'punjabi'}
        detected_lang = ""
        
        # Clean Text Generation
        clean_words = []
        for word in words:
            clean_w = re.sub(r'[^\w]', '', word)
            
            if clean_w in junk_words_list:
                if clean_w not in found_junk:
                    found_junk.append(clean_w)
            elif clean_w in languages:
                detected_lang = clean_w.title()
            else:
                # Keep only words that might be movie title (minimum 2 chars)
                if len(clean_w) >= 2 or clean_w.isdigit():
                    clean_words.append(word)
                
        clean_text = " ".join(clean_words).title()
        
        # Format with language if detected
        if detected_lang and clean_text:
            correct_format = f"{clean_text} [{detected_lang}]"
        else:
            correct_format = clean_text

        return {
            'is_valid': len(found_junk) == 0,
            'found_junk': found_junk,
            'clean_name': clean_text,
            'correct_format': correct_format,
            'search_query': clean_text.replace(" ", "+")
        }
    
    # --- 5. OMDb INFO (FULLY DYNAMIC) ---
    @staticmethod
    async def get_omdb_info(movie_name: str) -> str:
        """Get movie info using OMDb - NO HARDCODED MOVIES"""
        if not Config.OMDB_API_KEY:
            return "❌ **OMDb API Key Missing**\n\nPlease set OMDB_API_KEY in config."
            
        try:
            url = f"http://www.omdbapi.com/?t={quote(movie_name)}&apikey={Config.OMDB_API_KEY}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
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
                
                # Shorten plot if too long
                if len(plot) > 200:
                    plot = plot[:200] + "..."
                
                # Format rating with star
                rating_star = "⭐" if rating != "N/A" else ""
                
                response_lines = [
                    "🎬 **Movie Information** 🎬",
                    "",
                    f"📝 **Title:** {title}",
                    f"📅 **Year:** {year}",
                    f"{rating_star} **IMDb:** {rating}/10" if rating != "N/A" else "📊 **IMDb:** N/A",
                    f"🎭 **Genre:** {genre}",
                    f"🎬 **Director:** {director}",
                    f"👥 **Cast:** {actors}",
                    f"📖 **Plot:** {plot}",
                    "",
                    f"🔗 **IMDb:** https://www.imdb.com/title/{data.get('imdbID', '')}/",
                    "",
                    "_Enjoy watching! 🍿_"
                ]
                
                return "\n".join(response_lines)
            else:
                return f"❌ **Movie Not Found**\n\nCouldn't find '{movie_name}' on IMDb.\nPlease check the spelling and try again."
                
        except asyncio.TimeoutError:
            return "❌ **OMDb Service Timeout**\n\nServer didn't respond. Please try again later."
        except Exception as e:
            print(f"OMDb Error: {e}")
            return "❌ **OMDb Service Unavailable**\n\nPlease try again later."
    
    # --- 6. RANDOM MOVIE FROM OMDb (FULLY DYNAMIC) ---
    @staticmethod
    async def get_random_movie():
        """Get a random movie from OMDb - NO HARDCODING"""
        if not Config.OMDB_API_KEY:
            return None
            
        # Random IMDb IDs (popular movies)
        random_ids = [
            "tt1375666",  # Inception
            "tt0816692",  # Interstellar
            "tt0468569",  # The Dark Knight
            "tt0111161",  # Shawshank Redemption
            "tt0109830",  # Forrest Gump
            "tt0137523",  # Fight Club
            "tt0120737",  # LOTR
            "tt0910970",  # Wall-E
            "tt4154796",  # Avengers Endgame
            "tt7286456"   # Joker
        ]
        
        import random
        movie_id = random.choice(random_ids)
        
        try:
            url = f"http://www.omdbapi.com/?i={movie_id}&apikey={Config.OMDB_API_KEY}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
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
    
    # --- 7. AI RESPONSE ---
    @staticmethod
    async def get_ai_response(query: str, context: str = "") -> str:
        """Get AI response"""
        try:
            # Check if server is busy
            if random.random() < 0.05:  # 5% chance
                return "🤖 **AI Server Processing**\n\nPlease wait a moment and try again! ⏳"
            
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
            
            if context:
                prompt = f"Context: {context}\n\n{prompt}"
            
            response = await g4f.ChatCompletion.create_async(
                model=Config.G4F_MODEL,
                messages=[{"role": "user", "content": prompt}],
                timeout=25
            )
            
            if not response or not response.strip():
                return "🤖 **AI Response**\n\nI'm thinking... Ask me about movies! 🎬"
            
            formatted_response = f"🤖 **AI Response**\n\n{response.strip()}"
            return formatted_response
            
        except Exception as e:
            print(f"AI Error: {e}")
            return "🤖 **AI Service Busy**\n\nPlease try again in a few moments! ⏳"
    
    # --- 8. MESSAGE QUALITY CHECK ---
    @staticmethod
    def check_message_quality(text: str) -> str:
        """Returns: 'CLEAN', 'JUNK', 'LINK', 'ABUSE', or 'IGNORE'"""
        text_lower = text.lower().strip()
        
        # Link Detection
        link_patterns = [
            r't\.me/', r'telegram\.me/', r'http://', r'https://', 
            r'www\.', r'\.com', r'\.in', r'\.net', r'\.org',
            r'joinchat', r'bit\.ly', r'tinyurl', r'goo\.gl'
        ]
        for pattern in link_patterns:
            if re.search(pattern, text_lower):
                return "LINK"
        
        # Abuse Words
        abuse_words = [
            "mc", "bc", "bkl", "mkl", "chutiya", "kutta", "kamina", "fuck", 
            "bitch", "sex", "porn", "randi", "gand", "lund", "bhosda", 
            "madarchod", "behenchod", "harami", "ullu", "gadha", "bewakuf",
            "idiot", "stupid", "moron", "lauda", "chut", "gaand", "bsdk",
            "bhadwa", "chodu", "gandu", "lavde", "rand", "kutti"
        ]
        
        words = text_lower.split()
        for word in abuse_words:
            if word in words:
                return "ABUSE"
        
        # Junk Words - Short messages that are just spam
        if len(words) == 1 and words[0] in ["hi", "hello", "hey", "hii", "helloo", "good", "morning", "night"]:
            return "IGNORE"
        
        return "CLEAN"
    
    # --- 9. AUTO DELETE ---
    @staticmethod
    async def auto_delete_message(client, message, delay: int = Config.AUTO_DELETE_TIME):
        await asyncio.sleep(delay)
        try:
            await client.delete_messages(message.chat.id, message.id)
        except:
            pass
    
    # --- 10. BROADCAST ---
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
