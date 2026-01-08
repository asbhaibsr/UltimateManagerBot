# utils.py

import re
import asyncio
import aiohttp
import nest_asyncio
from aiohttp import web
from fuzzywuzzy import process
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Apply nest_asyncio to fix event loop issues
nest_asyncio.apply()

# --- Koyeb Health Check Server ---
async def web_server():
    async def handle_home(request):
        return web.Response(text="Bot is Running and Healthy!", status=200)

    app = web.Application()
    app.add_routes([web.get('/', handle_home)])
    return app

# --- Spelling Logic ---
IGNORE_WORDS = [
    "movie", "film", "dedo", "dena", "link", "download", "webseries", 
    "season", "episode", "chahiye", "send", "hd", "480p", "720p", "1080p", 
    "hindi", "dubbed", "plz", "pls", "please", "sir", "bhai", "bro", 
    "yaar", "bhejo", "bhej", "koi", "ka", "ki", "hai", "hain", "do"
]

def clean_movie_query(text):
    """Clean movie query by removing unnecessary words"""
    if not text:
        return ""
    
    text = text.lower()
    
    # Remove common request patterns
    patterns = [
        r'please send me (.+?) movie',
        r'send me (.+?) movie',
        r'movie (.+?) please',
        r'please give (.+?) movie',
        r'give me (.+?) movie',
        r'(.+?) movie dedo',
        r'(.+?) movie send',
        r'(.+?) movie link',
        r'(.+?) movie chahiye',
        r'movie (.+?) dedo',
        r'movie (.+?) send',
        r'movie (.+?) link'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            text = match.group(1)
            break
    
    # Remove ignore words
    for word in IGNORE_WORDS:
        text = re.sub(rf'\b{word}\b', '', text)
    
    # Remove special characters but keep spaces and numbers
    text = re.sub(r'[^a-zA-Z0-9\s\-\.]', '', text)
    
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def extract_movie_name(text):
    """Extract movie name from query"""
    cleaned = clean_movie_query(text)
    
    if not cleaned:
        return ""
    
    # Check for season pattern (S01, S02, etc)
    season_match = re.search(r'(.+?)\s+s(\d+)\s*e(\d+)', cleaned, re.IGNORECASE) or \
                   re.search(r'(.+?)\s+season\s*(\d+)', cleaned, re.IGNORECASE)
    
    if season_match:
        base_name = season_match.group(1).strip()
        season_num = season_match.group(2) if len(season_match.groups()) > 1 else season_match.group(2)
        return f"{base_name} S{season_num.zfill(2)}" if season_num else base_name
    
    # Check for year pattern
    year_match = re.search(r'(.+?)\s+\((\d{4})\)', cleaned) or \
                 re.search(r'(.+?)\s+(\d{4})', cleaned)
    
    if year_match:
        return year_match.group(1).strip()
    
    return cleaned

async def check_movie_spelling(query):
    """Check and correct movie spelling using multiple sources"""
    movie_name = extract_movie_name(query)
    
    if not movie_name or len(movie_name) < 2:
        return None, None, None
    
    try:
        # Try TMDB API
        corrected_name = await search_tmdb_movie(movie_name)
        
        if corrected_name:
            return corrected_name, "N/A", "correct"
        
        # Try OMDb API
        corrected_name = await search_omdb_movie(movie_name)
        
        if corrected_name:
            return corrected_name, "N/A", "correct"
        
        # If API fails, use simple fuzzy matching
        return movie_name, "N/A", "suggest"
        
    except Exception as e:
        logger.error(f"Spell check error: {e}")
        return None, None, "error"

async def search_tmdb_movie(query):
    """Search movie using TMDB API"""
    try:
        url = f"https://api.themoviedb.org/3/search/movie"
        params = {
            "api_key": "e547e17d4e91f3e62a571655cd1ccaff",
            "query": query,
            "language": "en-US",
            "page": 1
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("results") and len(data["results"]) > 0:
                        return data["results"][0]["title"]
    except Exception as e:
        logger.error(f"TMDB search error: {e}")
    
    return None

async def search_omdb_movie(query):
    """Search movie using OMDb API"""
    try:
        url = f"http://www.omdbapi.com/"
        params = {
            "apikey": "6ed172d8",
            "s": query,
            "type": "movie"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("Search") and len(data["Search"]) > 0:
                        return data["Search"][0]["Title"]
    except Exception as e:
        logger.error(f"OMDb search error: {e}")
    
    return None

async def get_movie_details(movie_name):
    """Get movie details from multiple APIs"""
    try:
        # Try OMDb first
        details = await get_omdb_details(movie_name)
        if details:
            return details
        
        # Try TMDB
        details = await get_tmdb_details(movie_name)
        if details:
            return details
            
        return None
    except Exception as e:
        logger.error(f"Movie details error: {e}")
        return None

async def get_omdb_details(movie_name):
    """Get movie details from OMDb"""
    try:
        url = f"http://www.omdbapi.com/"
        params = {
            "apikey": "6ed172d8",
            "t": movie_name,
            "plot": "short"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("Response") == "True":
                        return {
                            "title": data.get("Title", "N/A"),
                            "year": data.get("Year", "N/A"),
                            "rating": data.get("imdbRating", "N/A"),
                            "genre": data.get("Genre", "N/A"),
                            "plot": data.get("Plot", "No plot available."),
                            "poster": data.get("Poster"),
                            "imdb_id": data.get("imdbID"),
                            "imdb_url": f"https://www.imdb.com/title/{data.get('imdbID')}" if data.get("imdbID") else None
                        }
    except Exception as e:
        logger.error(f"OMDb details error: {e}")
    
    return None

async def get_tmdb_details(movie_name):
    """Get movie details from TMDB"""
    try:
        # First search for movie
        search_url = f"https://api.themoviedb.org/3/search/movie"
        search_params = {
            "api_key": "e547e17d4e91f3e62a571655cd1ccaff",
            "query": movie_name,
            "language": "en-US",
            "page": 1
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=search_params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("results") and len(data["results"]) > 0:
                        movie_id = data["results"][0]["id"]
                        
                        # Get details
                        details_url = f"https://api.themoviedb.org/3/movie/{movie_id}"
                        details_params = {
                            "api_key": "e547e17d4e91f3e62a571655cd1ccaff",
                            "language": "en-US"
                        }
                        
                        async with session.get(details_url, params=details_params) as details_response:
                            if details_response.status == 200:
                                details_data = await details_response.json()
                                
                                # Get poster
                                poster_path = details_data.get("poster_path")
                                poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
                                
                                return {
                                    "title": details_data.get("title", "N/A"),
                                    "year": details_data.get("release_date", "N/A")[:4] if details_data.get("release_date") else "N/A",
                                    "rating": str(details_data.get("vote_average", "N/A")),
                                    "genre": ", ".join([g["name"] for g in details_data.get("genres", [])]),
                                    "plot": details_data.get("overview", "No plot available."),
                                    "poster": poster_url,
                                    "imdb_id": details_data.get("imdb_id"),
                                    "imdb_url": f"https://www.imdb.com/title/{details_data.get('imdb_id')}" if details_data.get("imdb_id") else f"https://www.themoviedb.org/movie/{movie_id}"
                                }
    except Exception as e:
        logger.error(f"TMDB details error: {e}")
    
    return None

def format_movie_info(movie_data):
    """Format movie information for display"""
    if not movie_data:
        return "No information available."
    
    title = movie_data.get('title', 'N/A')
    year = movie_data.get('year', 'N/A')
    rating = movie_data.get('rating', 'N/A')
    genre = movie_data.get('genre', 'N/A')
    plot = movie_data.get('plot', 'No plot available.')
    
    # Truncate plot
    if len(plot) > 300:
        plot = plot[:300] + "..."
    
    imdb_url = movie_data.get('imdb_url', 'https://www.imdb.com/')
    
    info = f"""🎬 **{title}** ({year})

⭐ **Rating:** {rating}/10
🎭 **Genres:** {genre}

📖 **Plot:**
{plot}

🔗 **More Info:** {imdb_url}"""
    
    return info
