import asyncio
import g4f
from config import Config
import requests
import re
from typing import Tuple, Optional

class MovieBotUtils:
    @staticmethod
    async def get_ai_response(query: str) -> str:
        """Get AI response in Hinglish"""
        try:
            # Check if query is about movies
            movie_keywords = ["movie", "film", "series", "web series", "show", "episode", 
                            "imdb", "rating", "cast", "director", "review", "download",
                            "watch", "stream", "ott", "netflix", "amazon", "hotstar"]
            
            is_movie_query = any(keyword in query.lower() for keyword in movie_keywords)
            
            if is_movie_query:
                prompt = f"""User is asking about: '{query}'
                
                Provide information in this format:
                🎬 **Movie/Series Info:**
                📝 **Name:** [Movie/Series Name]
                📅 **Year:** [Release Year]
                ⭐ **Rating:** [IMDb/Other Rating]
                🎭 **Genre:** [Genre]
                🎥 **Type:** [Movie/Web Series/TV Show]
                🌐 **IMDb:** [IMDb Link if available]
                
                Add a short review or description in cute Hinglish. Use emojis! 😊
                
                If you don't have specific info, give general advice about the movie."""
            else:
                prompt = f"""User says: '{query}'
                
                Reply as a friendly, cute Indian girl in short Hinglish sentences. 
                Be helpful and use emojis! 😊"""
            
            # Try g4f for AI response
            response = await g4f.ChatCompletion.create_async(
                model=Config.G4F_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            
            # If response is empty, try OMDb fallback for movie queries
            if not response.strip() and is_movie_query:
                movie_name = query.split('movie')[0].split('film')[0].strip()
                if movie_name:
                    response = await MovieBotUtils.get_omdb_info(movie_name)
            
            return response if response.strip() else "Sorry yaar, main samjhi nahi! 😅 Phirse pucho na..."
            
        except Exception as e:
            print(f"AI Error: {e}")
            return "Oops! Kuch error aa gaya. Thodi der baad try karo! 😅"
    
    @staticmethod
    async def get_omdb_info(movie_name: str) -> str:
        """Get movie info from OMDb API"""
        try:
            url = f"http://www.omdbapi.com/?t={movie_name}&apikey={Config.OMDB_API_KEY}"
            response = requests.get(url)
            data = response.json()
            
            if data.get("Response") == "True":
                title = data.get("Title", "N/A")
                year = data.get("Year", "N/A")
                rating = data.get("imdbRating", "N/A")
                genre = data.get("Genre", "N/A")
                imdb_id = data.get("imdbID", "")
                imdb_link = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else "N/A"
                
                return f"""🎬 **Movie Info:**
📝 **Name:** {title}
📅 **Year:** {year}
⭐ **IMDb Rating:** {rating}/10
🎭 **Genre:** {genre}
🌐 **IMDb Link:** {imdb_link if imdb_id else "Not Available"}

Mast movie hai yaar! Dekhna mat chhodo! 😍"""
            return "Movie not found on OMDb! 😕"
        except:
            return "OMDb API error! 📡"
    
    @staticmethod
    def extract_movie_name(text: str) -> Optional[str]:
        """Extract movie/series name from text"""
        # Remove common extra words
        text = text.lower()
        remove_words = ["dedo", "chahiye", "link", "download", "movie", "film", 
                       "ka", "ki", "ke", "ko", "hai", "please", "plz", "de"]
        
        for word in remove_words:
            text = text.replace(word, "")
        
        # Clean up multiple spaces
        text = ' '.join(text.split())
        
        # Pattern for series: "Mirzapur S01 E01 Hindi"
        series_pattern = r'([A-Za-z]+)\s*(?:S\d+\s*E\d+)?\s*(?:Hindi|English)?'
        match = re.match(series_pattern, text, re.IGNORECASE)
        
        if match and len(match.group(1)) > 2:
            return match.group(1).title()
        
        # Pattern for movies: "Avatar 2022"
        movie_pattern = r'([A-Za-z\s]+)\s*(?:\d{4})?'
        match = re.match(movie_pattern, text.strip())
        
        if match and len(match.group(1).strip()) > 2:
            return match.group(1).strip().title()
        
        return None
    
    @staticmethod
    async def auto_delete_message(client, message, delay: int = Config.AUTO_DELETE_TIME):
        """Auto delete message after delay"""
        await asyncio.sleep(delay)
        try:
            await client.delete_messages(message.chat.id, message.id)
        except:
            pass
    
    @staticmethod
    async def broadcast_messages(client, chat_ids, message_text, delay: float = Config.BROADCAST_DELAY):
        """Broadcast messages with delay to avoid flood"""
        success = 0
        failed = 0
        
        for chat_id in chat_ids:
            try:
                await client.send_message(chat_id, message_text)
                success += 1
                await asyncio.sleep(delay)  # Delay between messages
            except Exception as e:
                print(f"Failed to send to {chat_id}: {e}")
                failed += 1
        
        return success, failed
