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
            wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&format=json"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(wiki_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('query', {}).get('search'):
                            result = data['query']['search'][0]
                            title = result.get('title', query)
                            ratio = fuzz.ratio(query.lower(), title.lower())
                            
                            return {
                                'original': query,
                                'suggested': title,
                                'confidence': ratio,
                                'needs_correction': ratio < 85 and ratio > 50,
                                'source': 'wikipedia'
                            }
            
            ddg_url = f"https://api.duckduckgo.com/?q={query}+movie&format=json"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(ddg_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('Heading'):
                            title = data['Heading']
                            ratio = fuzz.ratio(query.lower(), title.lower())
                            
                            return {
                                'original': query,
                                'suggested': title,
                                'confidence': ratio,
                                'needs_correction': ratio < 85 and ratio > 50,
                                'source': 'duckduckgo'
                            }
            
            return {
                'original': query,
                'suggested': query,
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
        
        base_name = text_lower
        for keyword in series_keywords:
            base_name = base_name.replace(keyword, '').strip()
        
        suggested = f"{base_name} S01" if base_name else "S01"
        return True, suggested
    
    @staticmethod
    async def clean_movie_request(text: str) -> str:
        phrases_to_remove = [
            'movie de do', 'movie chahiye', 'movie dena', 'film do',
            'please send', 'please share', 'link chahiye', 'download',
            'de do bhai', 'bhejo bhai', 'do yaar'
        ]
        
        clean_text = text
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

feature_manager = FeatureManager()
