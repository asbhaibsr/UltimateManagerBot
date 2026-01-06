import re
import asyncio
from typing import Tuple, Optional, Dict
from fuzzywuzzy import fuzz
import aiohttp
from bs4 import BeautifulSoup
from imdb import IMDb

class FeatureManager:
    def __init__(self):
        self.ia = IMDb()
    
    @staticmethod
    async def extract_movie_name(text: str) -> Tuple[str, str]:
        remove_patterns = [
            r'(de do|do|give me|bhejo|chahiye|chaiye|movie|series|film|webseries|web series|download|hd|full)',
            r'(720p|1080p|4k|bluray|dvdrip|brrip|hindi|english|dubbed|subtitles)',
            r'(please|plz|pls|kripya|krpya|send|share|link|dena|do|chahiye|bhejo)',
            r'(bhai|bro|dude|yaar|sir|madam|ji|jee|please)',
            r'[!@#$%^&*()_+\-=\[\]{};:"\\|,.<>/?]'
        ]
        
        text_lower = text.lower()
        
        for pattern in remove_patterns:
            text_lower = re.sub(pattern, '', text_lower, flags=re.IGNORECASE)
        
        clean_text = ' '.join(text_lower.split())
        
        year_match = re.search(r'(19|20)\d{2}', clean_text)
        year = year_match.group() if year_match else ""
        
        if year:
            clean_text = clean_text.replace(year, '').strip()
        
        return clean_text.strip(), year
    
    async def check_spelling_correction(self, query: str) -> Dict:
        try:
            # Clean query first
            clean_query = ' '.join([word.capitalize() for word in query.split()])
            
            # IMDb search for exact match
            search_results = self.ia.search_movie(clean_query)
            if search_results:
                movie = search_results[0]
                title = movie.get('title', clean_query)
                ratio = fuzz.ratio(query.lower(), title.lower())
                
                if ratio < 85 and ratio > 50:
                    return {
                        'original': query,
                        'suggested': title,
                        'confidence': ratio,
                        'needs_correction': True,
                        'source': 'imdb'
                    }
            
            # Wikipedia API fallback
            wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={clean_query}&format=json"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(wiki_url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('query', {}).get('search'):
                            result = data['query']['search'][0]
                            title = result.get('title', clean_query)
                            ratio = fuzz.ratio(query.lower(), title.lower())
                            
                            if ratio < 85 and ratio > 50:
                                return {
                                    'original': query,
                                    'suggested': title,
                                    'confidence': ratio,
                                    'needs_correction': True,
                                    'source': 'wikipedia'
                                }
            
            return {
                'original': query,
                'suggested': clean_query,
                'confidence': 100,
                'needs_correction': False,
                'source': 'none'
            }
            
        except Exception as e:
            return {
                'original': query,
                'suggested': query,
                'confidence': 100,
                'needs_correction': False,
                'source': 'error'
            }
    
    @staticmethod
    async def check_season_requirement(text: str) -> Tuple[bool, str]:
        series_keywords = ['season', 'série', 'serie', 'web series', 'webseries', 
                          'tv series', 'tv', 'series', 's']
        
        text_lower = text.lower()
        is_series = any(keyword in text_lower for keyword in series_keywords)
        
        if not is_series:
            return False, ""
        
        season_patterns = [
            r'S\d+',
            r'Season\s*\d+',
            r'S\.\d+',
            r's\d+',
            r'season\s*\d+',
            r'\s\d+st\s',
            r'\s\d+nd\s',
            r'\s\d+rd\s',
            r'\s\d+th\s'
        ]
        
        for pattern in season_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False, ""
        
        # Extract base name
        base_name = text_lower
        for keyword in series_keywords:
            base_name = base_name.replace(keyword, '').strip()
        
        # Remove common words
        common_words = ['download', 'full', 'hd', 'movie', 'film', 'de', 'do', 'bhai', 'send']
        for word in common_words:
            base_name = base_name.replace(word, '').strip()
        
        # Check if season format exists (like s01, s1, season 1)
        season_match = re.search(r'(s|season)(\d+)', text_lower, re.IGNORECASE)
        if season_match:
            season_num = season_match.group(2)
            suggested = f"{base_name} Season {season_num}"
        else:
            suggested = f"{base_name} Season 1" if base_name else "Season 1"
        
        return True, suggested
    
    @staticmethod
    async def clean_movie_request(text: str) -> str:
        phrases_to_remove = [
            'movie de do', 'movie chahiye', 'movie dena', 'film do',
            'please send', 'please share', 'link chahiye', 'download',
            'de do bhai', 'bhejo bhai', 'do yaar', 'ka link', 'ki link',
            'bhai', 'bro', 'please', 'plz'
        ]
        
        clean_text = text.lower()
        for phrase in phrases_to_remove:
            clean_text = clean_text.replace(phrase, '')
        
        clean_text = ' '.join(clean_text.split())
        words = clean_text.split()
        capitalized_words = []
        
        for i, word in enumerate(words):
            if i == 0 or len(word) > 2:
                capitalized_words.append(word.capitalize())
            else:
                capitalized_words.append(word.lower())
        
        return ' '.join(capitalized_words)
    
    @staticmethod
    async def extract_file_info(message) -> Optional[Dict]:
        if message.document:
            return {
                'type': 'document',
                'file_id': message.document.file_id,
                'file_name': message.document.file_name,
                'file_size': message.document.file_size,
                'mime_type': message.document.mime_type
            }
        elif message.video:
            return {
                'type': 'video',
                'file_id': message.video.file_id,
                'file_name': getattr(message.video, 'file_name', 'video.mp4'),
                'file_size': message.video.file_size,
                'duration': message.video.duration,
                'mime_type': getattr(message.video, 'mime_type', 'video/mp4')
            }
        elif message.photo:
            return {
                'type': 'photo',
                'file_id': message.photo.file_id,
                'file_size': message.photo.file_size
            }
        elif message.audio:
            return {
                'type': 'audio',
                'file_id': message.audio.file_id,
                'file_name': getattr(message.audio, 'file_name', 'audio.mp3'),
                'file_size': message.audio.file_size,
                'duration': message.audio.duration,
                'mime_type': getattr(message.audio, 'mime_type', 'audio/mpeg')
            }
        
        return None
    
    async def get_movie_details(self, movie_name: str) -> Dict:
        """Get movie details from IMDb"""
        try:
            # Search movie
            search_results = self.ia.search_movie(movie_name)
            
            if not search_results:
                return {
                    'success': False,
                    'title': movie_name,
                    'message': 'Movie not found on IMDb. Try different name.'
                }
            
            # Get first result
            movie = search_results[0]
            self.ia.update(movie)
            
            # Extract details
            title = movie.get('title', movie_name)
            year = movie.get('year', 'N/A')
            rating = movie.get('rating', 'N/A')
            genres = ", ".join(movie.get('genres', ['N/A']))
            runtime = movie.get('runtimes', ['N/A'])[0] + " min" if movie.get('runtimes') else 'N/A'
            
            # Get plot (try different sources)
            plot = 'No description available.'
            if movie.get('plot outline'):
                plot = movie.get('plot outline')
            elif movie.get('plot'):
                plots = movie.get('plot')
                if plots and len(plots) > 0:
                    plot = plots[0]
            
            # Truncate plot if too long
            if len(plot) > 500:
                plot = plot[:500] + "..."
            
            # Get poster URL
            poster = None
            if movie.get('full-size cover url'):
                poster = movie.get('full-size cover url')
            elif movie.get('cover url'):
                poster = movie.get('cover url')
            
            # Get cast (first 3)
            cast = []
            if movie.get('cast'):
                for person in movie.get('cast')[:3]:
                    cast.append(person.get('name'))
            
            # Get directors
            directors = []
            if movie.get('directors'):
                for director in movie.get('directors'):
                    directors.append(director.get('name'))
            
            details_text = f"""
🎬 **{title}** ({year})

⭐ **Rating:** {rating}/10
🎭 **Genres:** {genres}
⏳ **Runtime:** {runtime}
🎬 **Director:** {', '.join(directors) if directors else 'N/A'}
👥 **Cast:** {', '.join(cast) if cast else 'N/A'}

📖 **Plot:**
{plot}

🔗 **IMDb:** https://www.imdb.com/title/tt{movie.movieID}/
"""
            
            return {
                'success': True,
                'title': title,
                'year': year,
                'rating': rating,
                'genre': genres,
                'duration': runtime,
                'director': ', '.join(directors) if directors else 'N/A',
                'plot': plot,
                'poster': poster,
                'imdb_id': movie.movieID,
                'text': details_text
            }
            
        except Exception as e:
            return {
                'success': False,
                'title': movie_name,
                'message': f'Error: {str(e)}'
            }

feature_manager = FeatureManager()
