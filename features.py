# features.py - UPDATED WITH MOVIE DETAILS

import re
import asyncio
from typing import Tuple, Optional, Dict
from fuzzywuzzy import fuzz
import aiohttp
from bs4 import BeautifulSoup

class FeatureManager:
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
    
    @staticmethod
    async def check_spelling_correction(query: str) -> Dict:
        try:
            # Clean query first
            clean_query = ' '.join([word.capitalize() for word in query.split()])
            
            # Wikipedia API
            wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={clean_query}&format=json"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(wiki_url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('query', {}).get('search'):
                            result = data['query']['search'][0]
                            title = result.get('title', clean_query)
                            ratio = fuzz.ratio(query.lower(), title.lower())
                            
                            # Only suggest if confidence is low
                            if ratio < 85 and ratio > 50:
                                return {
                                    'original': query,
                                    'suggested': title,
                                    'confidence': ratio,
                                    'needs_correction': True,
                                    'source': 'wikipedia'
                                }
            
            # If Wikipedia fails, check OMDb API (free)
            omdb_url = f"http://www.omdbapi.com/?apikey=free&t={clean_query}&plot=short"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(omdb_url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('Response') == 'True':
                            title = data.get('Title', clean_query)
                            ratio = fuzz.ratio(query.lower(), title.lower())
                            
                            if ratio < 85 and ratio > 50:
                                return {
                                    'original': query,
                                    'suggested': title,
                                    'confidence': ratio,
                                    'needs_correction': True,
                                    'source': 'omdb'
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
        common_words = ['download', 'full', 'hd', 'movie', 'film']
        for word in common_words:
            base_name = base_name.replace(word, '').strip()
        
        suggested = f"{base_name} Season 1" if base_name else "Season 1"
        return True, suggested
    
    @staticmethod
    async def clean_movie_request(text: str) -> str:
        phrases_to_remove = [
            'movie de do', 'movie chahiye', 'movie dena', 'film do',
            'please send', 'please share', 'link chahiye', 'download',
            'de do bhai', 'bhejo bhai', 'do yaar', 'ka link', 'ki link'
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
    
    @staticmethod
    async def get_movie_details(movie_name: str) -> Dict:
        """Get movie details from OMDb API"""
        try:
            clean_name = movie_name.replace(' ', '+')
            omdb_url = f"http://www.omdbapi.com/?apikey=free&t={clean_name}&plot=short"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(omdb_url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('Response') == 'True':
                            return {
                                'success': True,
                                'title': data.get('Title', movie_name),
                                'year': data.get('Year', 'N/A'),
                                'rating': data.get('imdbRating', 'N/A'),
                                'duration': data.get('Runtime', 'N/A'),
                                'genre': data.get('Genre', 'N/A'),
                                'director': data.get('Director', 'N/A'),
                                'plot': data.get('Plot', 'No description available.'),
                                'poster': data.get('Poster', ''),
                                'actors': data.get('Actors', 'N/A'),
                                'language': data.get('Language', 'N/A')
                            }
            
            # Fallback to Wikipedia
            wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exintro&explaintext&titles={clean_name}&format=json"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(wiki_url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pages = data.get('query', {}).get('pages', {})
                        for page_id, page_data in pages.items():
                            if page_id != '-1':
                                extract = page_data.get('extract', '')
                                if extract:
                                    # Get first paragraph
                                    paragraphs = extract.split('\n')
                                    plot = paragraphs[0] if paragraphs else 'No description available.'
                                    
                                    return {
                                        'success': True,
                                        'title': page_data.get('title', movie_name),
                                        'plot': plot[:500] + '...' if len(plot) > 500 else plot,
                                        'year': 'N/A',
                                        'rating': 'N/A',
                                        'duration': 'N/A',
                                        'genre': 'N/A',
                                        'director': 'N/A',
                                        'source': 'wikipedia'
                                    }
            
            return {
                'success': False,
                'title': movie_name,
                'message': 'Details not found. Try searching on @asfilter_bot'
            }
            
        except Exception as e:
            return {
                'success': False,
                'title': movie_name,
                'message': f'Error fetching details: {str(e)}'
            }

feature_manager = FeatureManager()
