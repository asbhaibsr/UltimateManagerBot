import re
import aiohttp
import asyncio
import difflib
import random
from config import Config
from typing import Optional
from urllib.parse import quote

try:
    import g4f
    G4F_AVAILABLE = True
except:
    G4F_AVAILABLE = False

# ===================== RANDOM MESSAGE BANKS =====================

JUNK_WARNINGS = [
    "Arre yaar {name}, seedha movie ka naam likh na! '{junk}' kisliye likha? 😅",
    "Bhai {name}, kuch zyada hi likh diya tune. '{junk}' hatake dobara try kar! 🙈",
    "{name} bhai, format galat hai. '{junk}' ki zaroorat nahi thi yahan. Sahi format use karo! 😤",
    "Oye {name}! '{junk}' wala word hatao aur sirf movie/series ka naam likho. Simple hai! 🎬",
    "Dekh {name}, hum samajh gaye tujhe movie chahiye. Par '{junk}' likhneki zaroorat nahi. Sahi likho! 😊",
    "{name}, chill karo! Sirf naam likho bhai. '{junk}' add mat karo. 🍿",
    "Ugh {name}! '{junk}' kyun? Seedha naam likho, bot search kar lega! 🤖",
]

LINK_WARNINGS = [
    "🚫 {name} bhai, links dalne ki koshish ki? Yahan allowed nahi hai!",
    "❌ Oye {name}! Link mat bhej. Group rules follow karo yaar.",
    "⚠️ {name}, link diya tune? Warning {count}/{limit}. Dobara mat karna!",
    "🔗 {name} bhai link send kiya? Yahan nahi chalega. {count}/{limit} warning.",
]

ABUSE_WARNINGS = [
    "🤬 {name}! Gaali? Seedha ban karwa loge. Warning {count}/{limit}.",
    "😤 Oye {name}, zubaan sambhalo. Warning {count}/{limit}.",
    "🚫 {name} bhai, abusive language? {count}/{limit} warnings. Careful raho!",
]

SIMPLE_CORRECTIONS = [
    "Arrey {name} bhai! 🎬\n\nTune likha: *{original}*\nSahi format: *{correct}*\n\nBas naam likho, aur kuch nahi! 😄",
    "Oi {name}! 👋\n\nYe sahi format hai:\n✅ *{correct}*\n\n'{original}' se kaise search karega bot? 😅",
    "Dekh {name} 🍿\n\nGalat: ❌ *{original}*\nSahi: ✅ *{correct}*\n\nThoda dhyan rakh bhai!",
    "Bhai {name}! 😊\n\nSeedha naam likhte hain:\n*{correct}*\n\n'{original}' thoda zyada ho gaya!",
]

ADVANCED_FOUND = [
    "Mil gayi {name} bhai! 🎉 *{original}* ke badle yeh dekho:",
    "Ha ha! {name}, '{original}' likhke dhundh raha tha? Le bhai, yeh raha:",
    "Arrey {name}, *{original}* ki jagah yeh chahiye tha na tujhe? 🍿",
]

ADVANCED_NOT_FOUND = [
    "Yaar {name}, '{original}' se kuch nahi mila. Sahi naam likhke try kar!",
    "Hmm {name}, '{original}'? Nahi mila bhai. Spelling check karke dobara bhej!",
    "Oye {name}! '{original}' kuch samajh nahi aaya. Sahi naam kya hai? 🤔",
]

AI_THINKING = [
    "Soch raha hoon... 🤔",
    "Ek sec, dekh raha hoon 👀",
    "Hmm interesting! Zaraa soochne do 🧠",
    "AI brain chal raha hai... ⚡",
]

# ===================== MAIN UTILS CLASS =====================

class MovieBotUtils:

    # --- FORMAT VALIDATION ---
    @staticmethod
    def validate_movie_format(text: str) -> dict:
        text_lower = text.lower().strip()

        junk_words_list = [
            "dedo", "chahiye", "chaiye", "season", "bhejo", "send", "kardo", "karo", "do",
            "plz", "pls", "please", "request", "mujhe", "mereko", "koi", "link",
            "download", "movie", "film", "series", "full", "hd", "480p", "720p", "1080p",
            "webseries", "episode", "dubbed", "episod", "movies", "dena", "admin", "yaar",
            "upload", "uploded", "zaldi", "seassion", "post", "watch", "bhai", "bro",
            "sir", "please", "abhi", "jaldi", "chahie", "milega", "nahi"
        ]

        languages = {'hindi', 'english', 'tamil', 'telugu', 'malayalam', 'kannada', 'marathi', 'punjabi'}

        words = text_lower.split()
        found_junk = []
        detected_lang = ""
        clean_words = []

        for word in words:
            clean_w = re.sub(r'[^\w]', '', word)
            if clean_w in junk_words_list:
                if clean_w not in found_junk:
                    found_junk.append(clean_w)
            elif clean_w in languages:
                detected_lang = clean_w.title()
            else:
                clean_words.append(word)

        clean_text = " ".join(clean_words).title()
        correct_format = f"{clean_text} [{detected_lang}]" if detected_lang else clean_text

        return {
            'is_valid': len(found_junk) == 0,
            'found_junk': found_junk,
            'clean_name': clean_text,
            'correct_format': correct_format,
            'search_query': clean_text.replace(" ", "+")
        }

    # --- MESSAGE QUALITY CHECK ---
    @staticmethod
    def check_message_quality(text: str) -> str:
        text_lower = text.lower().strip()

        # Link detection
        link_patterns = [
            r't\.me/', r'telegram\.me/', r'http://', r'https://',
            r'www\.', r'\.com', r'\.in', r'\.net', r'\.org', r'\.io',
            r'joinchat', r'bit\.ly', r'tinyurl'
        ]
        for p in link_patterns:
            if re.search(p, text_lower):
                return "LINK"

        # Abuse detection
        abuse_words = [
            "mc", "bc", "bkl", "chutiya", "kutta", "fuck", "bitch", "porn",
            "randi", "gand", "lund", "bhosda", "madarchod", "behenchod", "harami",
            "bsdk", "gandu", "lavde", "motherfucker", "asshole", "bastard"
        ]
        words = text_lower.split()
        for word in abuse_words:
            if word in words:
                return "ABUSE"

        # Junk detection
        junk_words = [
            "dedo", "chahiye", "chaiye", "mangta", "bhej", "send", "kardo",
            "karo", "plz", "pls", "please", "request", "link", "download",
            "downlod", "movie", "film", "series", "season", "episode", "hd",
            "480p", "720p", "1080p", "bhai", "bro", "sir", "admin", "yaar",
            "mujhe", "mereko", "full", "dubbed", "dena", "chahie", "milega"
        ]
        for word in junk_words:
            clean_words = [re.sub(r'[^\w]', '', w) for w in words]
            if word in clean_words:
                return "JUNK"

        # Clean format check
        clean_pattern = r'^[a-zA-Z0-9\s\-\:\'\&\.]+(?:\s\d{4})?(?:\s?[Ss]\d{1,2})?(?:\s?[Ee][Pp]?\d{1,2})?$'
        if re.match(clean_pattern, text, re.IGNORECASE):
            return "CLEAN"

        return "IGNORE"

    # --- RANDOM MESSAGE GENERATORS ---
    @staticmethod
    def get_junk_warning(name: str, junk: str, original: str, correct: str) -> str:
        msg = random.choice(SIMPLE_CORRECTIONS)
        return msg.format(name=name, original=original, correct=correct, junk=junk)

    @staticmethod
    def get_link_warning(name: str, count: int, limit: int) -> str:
        msg = random.choice(LINK_WARNINGS)
        return msg.format(name=name, count=count, limit=limit)

    @staticmethod
    def get_abuse_warning(name: str, count: int, limit: int) -> str:
        msg = random.choice(ABUSE_WARNINGS)
        return msg.format(name=name, count=count, limit=limit)

    @staticmethod
    def get_advanced_found_msg(name: str, original: str) -> str:
        msg = random.choice(ADVANCED_FOUND)
        return msg.format(name=name, original=original)

    @staticmethod
    def get_advanced_not_found_msg(name: str, original: str) -> str:
        msg = random.choice(ADVANCED_NOT_FOUND)
        return msg.format(name=name, original=original)

    @staticmethod
    def get_ai_thinking() -> str:
        return random.choice(AI_THINKING)

    # --- OMDb INFO (WITH PHOTO) ---
    @staticmethod
    async def get_omdb_info(movie_name: str) -> dict:
        """Returns dict with text and poster_url"""
        try:
            url = f"http://www.omdbapi.com/?t={quote(movie_name)}&apikey={Config.OMDB_API_KEY}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()

            if data.get("Response") == "True":
                title = data.get("Title", "N/A")
                year = data.get("Year", "N/A")
                rating = data.get("imdbRating", "N/A")
                genre = data.get("Genre", "N/A")
                plot = data.get("Plot", "N/A")[:200]
                director = data.get("Director", "N/A")
                cast = data.get("Actors", "N/A")
                language = data.get("Language", "N/A")
                runtime = data.get("Runtime", "N/A")
                poster = data.get("Poster", "")
                imdb_id = data.get("imdbID", "")

                stars = ""
                try:
                    r = float(rating)
                    stars = "⭐" * int(r / 2) + ("½" if r % 2 >= 1 else "")
                except:
                    stars = "⭐"

                text = (
                    f"🎬 **{title}** ({year})\n\n"
                    f"⭐ **Rating:** {rating}/10 {stars}\n"
                    f"🎭 **Genre:** {genre}\n"
                    f"🗣 **Language:** {language}\n"
                    f"⏱ **Runtime:** {runtime}\n"
                    f"🎬 **Director:** {director}\n"
                    f"👥 **Cast:** {cast}\n\n"
                    f"📖 **Story:**\n_{plot}_\n\n"
                    f"🔗 [IMDb Link](https://www.imdb.com/title/{imdb_id}/)"
                )

                return {
                    "found": True,
                    "text": text,
                    "poster": poster if poster and poster != "N/A" else None,
                    "title": title
                }

            return {"found": False, "text": "", "poster": None, "title": ""}
        except Exception as e:
            return {"found": False, "text": "", "poster": None, "title": ""}

    # --- AI RESPONSE ---
    @staticmethod
    async def get_ai_response(query: str, context: str = "") -> str:
        if not G4F_AVAILABLE:
            return "🤖 AI abhi available nahi hai. Baad mein try karo!"

        try:
            movie_keywords = ["movie", "film", "series", "show", "episode", "imdb",
                              "rating", "cast", "director", "review", "download",
                              "watch", "stream", "netflix", "amazon", "hotstar", "recommend"]

            is_movie_query = any(k in query.lower() for k in movie_keywords)

            if is_movie_query:
                prompt = (
                    f"User ne poocha: '{query}'\n\n"
                    f"Ek helpful movie/series assistant ki tarah Hinglish mein jawab do. "
                    f"Emojis use karo. Movie details, rating, genre, short review do. "
                    f"150 words ke andar rakho."
                )
            else:
                prompt = (
                    f"User ne kaha: '{query}'\n\n"
                    f"Ek friendly assistant ki tarah Hinglish mein jawab do. "
                    f"Natural aur casual raho jaise dost baat karta hai. "
                    f"Emojis use karo. 100 words mein jawab do."
                )

            if context:
                prompt = f"Context: {context}\n\n{prompt}"

            response = await g4f.ChatCompletion.create_async(
                model=Config.G4F_MODEL,
                messages=[{"role": "user", "content": prompt}],
                timeout=Config.AI_TIMEOUT
            )

            if response and response.strip():
                return f"🤖 {response.strip()}"

            return "Hmm, kuch samajh nahi aaya mujhe. Dobara try karo! 😅"

        except Exception as e:
            return "🤖 AI server thoda busy hai abhi. 2 minute baad try karo! ⏳"

    # --- AUTO DELETE ---
    @staticmethod
    async def auto_delete_message(client, message, delay: int = Config.AUTO_DELETE_TIME):
        await asyncio.sleep(delay)
        try:
            await client.delete_messages(message.chat.id, message.id)
        except:
            pass

    # --- SPELLING SUGGESTION ---
    @staticmethod
    def get_spelling_suggestion(user_text: str, movie_list: list) -> Optional[str]:
        matches = difflib.get_close_matches(user_text, movie_list, n=1, cutoff=0.5)
        return matches[0] if matches else None
