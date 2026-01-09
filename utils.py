import re
import asyncio
import aiohttp
import json
import logging
from typing import Tuple, Optional
from fuzzywuzzy import process
from imdb import Cinemagoer

logger = logging.getLogger(__name__)

ia = Cinemagoer()

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
    
    for word in IGNORE_WORDS:
        text = re.sub(rf'\b{word}\b', '', text)
    
    text = re.sub(r'[^a-zA-Z0-9\s\-\.]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def extract_movie_name(text):
    """Extract movie name from query"""
    cleaned = clean_movie_query(text)
    
    if not cleaned:
        return ""
    
    season_match = re.search(r'(.+?)\s+s(\d+)\s*e(\d+)', cleaned, re.IGNORECASE) or \
                   re.search(r'(.+?)\s+season\s*(\d+)', cleaned, re.IGNORECASE)
    
    if season_match:
        base_name = season_match.group(1).strip()
        season_num = season_match.group(2) if len(season_match.groups()) > 1 else season_match.group(2)
        return f"{base_name} S{season_num.zfill(2)}" if season_num else base_name
    
    year_match = re.search(r'(.+?)\s+\((\d{4})\)', cleaned) or \
                 re.search(r'(.+?)\s+(\d{4})', cleaned)
    
    if year_match:
        return year_match.group(1).strip()
    
    return cleaned

async def check_movie_spelling(query: str) -> Tuple[Optional[str], Optional[str], str]:
    """Check and correct movie spelling using multiple sources"""
    movie_name = extract_movie_name(query)
    
    if not movie_name or len(movie_name) < 2:
        return None, None, "invalid"
    
    try:
        # Try IMDb first
        results = ia.search_movie(movie_name)
        
        if results:
            top_match = results[0]['title']
            year = str(results[0].get('year', 'N/A'))
            
            ratio = process.extractOne(movie_name, [top_match])[1]
            
            if ratio >= 80:
                return top_match, year, "correct"
            else:
                return top_match, year, "suggest"
        
        # Try OMDb API
        omdb_result = await search_omdb(movie_name)
        if omdb_result:
            return omdb_result[0], omdb_result[1], "omdb_found"
        
        # Try TMDB
        tmdb_result = await search_tmdb(movie_name)
        if tmdb_result:
            return tmdb_result[0], tmdb_result[1], "tmdb_found"
            
        return None, None, "no_results"
        
    except Exception as e:
        logger.error(f"Spell check error: {e}")
        return None, None, "error"

async def search_omdb(query: str) -> Optional[Tuple[str, str]]:
    """Search movie using OMDb API"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://www.omdbapi.com/?apikey=6ed172d8&s={query}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("Search"):
                        movie = data["Search"][0]
                        return movie["Title"], movie.get("Year", "N/A")
    except Exception as e:
        logger.error(f"OMDb search error: {e}")
    return None

async def search_tmdb(query: str) -> Optional[Tuple[str, str]]:
    """Search movie using TMDB API"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.themoviedb.org/3/search/movie?api_key=e547e17d4e91f3e62a571655cd1ccaff&query={query}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("results"):
                        movie = data["results"][0]
                        return movie["title"], movie.get("release_date", "").split("-")[0] if movie.get("release_date") else "N/A"
    except Exception as e:
        logger.error(f"TMDB search error: {e}")
    return None

async def get_movie_details_from_apis(movie_name: str):
    """Get movie details from multiple APIs"""
    details = {}
    
    try:
        # Try IMDb
        results = ia.search_movie(movie_name)
        if results:
            movie = results[0]
            ia.update(movie)
            
            details = {
                "title": movie.get('title', 'N/A'),
                "year": movie.get('year', 'N/A'),
                "rating": movie.get('rating', 'N/A'),
                "genres": ', '.join(movie.get('genres', [])),
                "plot": movie.get('plot outline', movie.get('plot', ['No plot available.'])),
                "poster": movie.get('full-size cover url') or movie.get('cover url'),
                "imdb_id": movie.movieID,
                "source": "imdb"
            }
            
            if isinstance(details["plot"], list):
                details["plot"] = details["plot"][0] if details["plot"] else 'No plot available.'
            
            return details
    except Exception as e:
        logger.error(f"IMDb details error: {e}")
    
    try:
        # Try OMDb
        async with aiohttp.ClientSession() as session:
            url = f"http://www.omdbapi.com/?apikey=6ed172d8&t={movie_name}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("Response") == "True":
                        details = {
                            "title": data.get("Title", "N/A"),
                            "year": data.get("Year", "N/A"),
                            "rating": data.get("imdbRating", "N/A"),
                            "genres": data.get("Genre", "N/A"),
                            "plot": data.get("Plot", "No plot available."),
                            "poster": data.get("Poster"),
                            "imdb_id": data.get("imdbID", "").replace("tt", ""),
                            "source": "omdb"
                        }
                        return details
    except Exception as e:
        logger.error(f"OMDb details error: {e}")
    
    return None

def format_movie_info(movie_data):
    """Format movie information for display"""
    if not movie_data:
        return "No information available."
    
    title = movie_data.get("title", "N/A")
    year = movie_data.get("year", "N/A")
    rating = movie_data.get("rating", "N/A")
    genres = movie_data.get("genres", "N/A")
    plot = movie_data.get("plot", "No plot available.")
    
    if len(plot) > 300:
        plot = plot[:300] + "..."
    
    imdb_id = movie_data.get("imdb_id", "")
    imdb_url = f"https://www.imdb.com/title/tt{imdb_id}" if imdb_id else "https://www.imdb.com"
    
    info = f"""🎬 **{title}** ({year})

⭐ **Rating:** {rating}/10
🎭 **Genres:** {genres}
📖 **Plot:** {plot}

🔗 **IMDb:** {imdb_url}"""
    
    return info

async def get_movie_poster(movie_name):
    """Get movie poster URL"""
    try:
        details = await get_movie_details_from_apis(movie_name)
        if details and details.get("poster"):
            return details["poster"]
    except Exception as e:
        logger.error(f"Poster error: {e}")
    return None
