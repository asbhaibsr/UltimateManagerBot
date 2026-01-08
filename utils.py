#  utils.py

import re
from aiohttp import web
from fuzzywuzzy import process
from imdb import Cinemagoer

ia = Cinemagoer()

# --- Koyeb Health Check Server ---
async def web_server():
    async def handle_home(request):
        return web.Response(text="Bot is Running and Healthy!", status=200)

    app = web.Application()
    app.add_routes([web.get('/', handle_home)])
    return app

# --- Spelling Logic ---
# Words to remove before searching
IGNORE_WORDS = [
    "movie", "film", "dedo", "dena", "link", "download", "webseries", 
    "season", "episode", "chahiye", "send", "hd", "480p", "720p", "1080p", 
    "hindi", "dubbed", "plz", "pls", "sir", "bhai", "bro"
]

def clean_text(text):
    text = text.lower()
    for word in IGNORE_WORDS:
        text = text.replace(word, "")
    # Remove special chars but keep spaces
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    return text.strip()

def check_movie_spelling(query):
    cleaned_query = clean_text(query)
    if not cleaned_query:
        return None, None

    # Search IMDb
    try:
        results = ia.search_movie(cleaned_query)
        if not results:
            return None, "No results"
        
        # Get top match
        top_match = results[0]['title']
        
        # Fuzzy Match Ratio
        ratio = process.extractOne(cleaned_query, [top_match])[1]
        
        if ratio >= 85: # High match -> Correct Spelling
            return top_match, "correct"
        else: # Low match -> Suggestion
            return top_match, "wrong"
    except Exception as e:
        print(f"Error in spell check: {e}")
        return None, "error"
