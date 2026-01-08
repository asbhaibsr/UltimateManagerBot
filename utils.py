#  utils.py

import re
import asyncio
from aiohttp import web
from fuzzywuzzy import process
from imdb import Cinemagoer
import g4f
from datetime import datetime

ia = Cinemagoer()

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

def check_movie_spelling(query):
    """Check and correct movie spelling using multiple sources"""
    movie_name = extract_movie_name(query)
    
    if not movie_name or len(movie_name) < 2:
        return None, None, None
    
    try:
        # Try IMDb first
        results = ia.search_movie(movie_name)
        
        if results:
            top_match = results[0]['title']
            year = results[0].get('year', 'N/A')
            
            # Fuzzy match
            ratio = process.extractOne(movie_name, [top_match])[1]
            
            if ratio >= 80:
                return top_match, year, "correct"
            else:
                # Try AI correction
                try:
                    ai_corrected = correct_with_ai(movie_name)
                    if ai_corrected and ai_corrected != movie_name:
                        return ai_corrected, year, "ai_corrected"
                except:
                    pass
                
                return top_match, year, "suggest"
        
        # If IMDb fails, try AI
        ai_result = correct_with_ai(movie_name)
        if ai_result:
            return ai_result, "N/A", "ai_suggest"
            
        return None, None, "no_results"
        
    except Exception as e:
        print(f"Spell check error: {e}")
        return None, None, "error"

def correct_with_ai(query):
    """Correct movie name using AI (g4f)"""
    try:
        response = g4f.ChatCompletion.create(
            model=g4f.models.gpt_35_turbo,
            messages=[{
                "role": "user", 
                "content": f"What is the correct title for this movie/show: '{query}'? Return only the correct title."
            }],
            timeout=10
        )
        if response and len(response.strip()) > 3:
            return response.strip()
    except Exception as e:
        print(f"AI correction error: {e}")
    
    return None

def format_movie_info(movie_data):
    """Format movie information for display"""
    if not movie_data:
        return "No information available."
    
    title = movie_data.get('title', 'N/A')
    year = movie_data.get('year', 'N/A')
    rating = movie_data.get('rating', 'N/A')
    genres = ', '.join(movie_data.get('genres', []))
    plot = movie_data.get('plot outline', 'No plot available.')
    
    # Truncate plot
    if len(plot) > 300:
        plot = plot[:300] + "..."
    
    info = f"""🎬 **{title}** ({year})
⭐ **Rating:** {rating}/10
🎭 **Genres:** {genres}
📖 **Plot:** {plot}

🔗 **IMDb:** https://www.imdb.com/title/tt{movie_data.movieID}"""
    
    return info
