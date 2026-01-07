import re
import asyncio
from typing import Tuple, Optional, Dict, List
import aiohttp
from bs4 import BeautifulSoup
from imdb import Cinemagoer
from fuzzywuzzy import fuzz

class FeatureManager:
    def __init__(self):
        self.ia = Cinemagoer()
    
    # ========== MOVIE SEARCH AND DETAILS ==========
    async def get_poster(self, query, bulk=False, id=False, file=None):
        """Get movie poster and details from IMDb"""
        if not id:
            # Clean query
            query = (query.strip()).lower()
            title = query
            
            # Extract year from query
            year = re.findall(r'[1-2]\d{3}$', query, re.IGNORECASE)
            
            if year:
                year = year[0]
                title = (query.replace(year, "")).strip()
            elif file is not None:
                year = re.findall(r'[1-2]\d{3}', file)
                if year:
                    year = year[0]
            else:
                year = None
            
            # Search on IMDb
            movieid = self.ia.search_movie(title.lower(), results=10)
            
            if not movieid:
                return None
            
            # Filter by year if provided
            if year:
                filtered = list(filter(lambda k: str(k.get('year')) == str(year), movieid))
                if not filtered:
                    filtered = movieid
            else:
                filtered = movieid
            
            # Filter by kind
            movieid = list(filter(lambda k: k.get('kind') in ['movie', 'tv series'], filtered))
            
            if not movieid:
                movieid = filtered
                
            if bulk:
                return movieid
                
            movieid = movieid[0].movieID
        else:
            movieid = query
        
        # Get movie details
        movie = self.ia.get_movie(movieid)
        
        # Format movie details
        return {
            'title': movie.get('title', 'N/A'),
            'year': movie.get('year', 'N/A'),
            'rating': str(movie.get("rating", 'N/A')),
            'genres': movie.get("genres", ['N/A']),
            'poster': movie.get('full-size cover url'),
            'plot': movie.get('plot outline') or (movie.get('plot')[:500] + '...' if movie.get('plot') else 'No plot available'),
            'imdb_id': movieid,
            'url': f'https://www.imdb.com/title/tt{movieid}',
            'kind': movie.get('kind', 'movie'),
            'cast': [person.get('name') for person in movie.get('cast', [])[:5]] if movie.get('cast') else [],
            'directors': [director.get('name') for director in movie.get('directors', [])] if movie.get('directors') else [],
            'runtimes': movie.get('runtimes', ['N/A'])[0] if movie.get('runtimes') else 'N/A'
        }
    
    async def search_movies(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search movies and return multiple results"""
        try:
            # Clean query
            query = query.strip()
            
            # Extract year if present
            year_match = re.search(r'(19|20)\d{2}', query)
            year = year_match.group() if year_match else None
            
            # Remove year from query for search
            search_query = re.sub(r'(19|20)\d{2}', '', query).strip()
            
            # Search on IMDb
            search_results = self.ia.search_movie(search_query, results=max_results)
            
            if not search_results:
                return []
            
            results = []
            for movie in search_results:
                try:
                    # Filter by type
                    if movie.get('kind') not in ['movie', 'tv series']:
                        continue
                    
                    # Filter by year if specified
                    if year and str(movie.get('year')) != str(year):
                        continue
                    
                    results.append({
                        'title': movie.get('title', 'Unknown'),
                        'year': movie.get('year', 'N/A'),
                        'imdb_id': movie.movieID,
                        'kind': movie.get('kind', 'movie')
                    })
                except:
                    continue
                
                if len(results) >= max_results:
                    break
            
            return results
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    async def get_movie_details(self, movie_name: str) -> Dict:
        """Get detailed movie information"""
        try:
            # Get movie details
            movie_data = await self.get_poster(movie_name)
            
            if not movie_data:
                return {
                    'success': False,
                    'title': movie_name,
                    'message': 'Movie not found. Please try a different name.'
                }
            
            # Format details text with proper Markdown
            title = movie_data.get('title', movie_name)
            year = movie_data.get('year', 'N/A')
            rating = movie_data.get('rating', 'N/A')
            genres = ", ".join(movie_data.get('genres', ['N/A']))
            runtime = movie_data.get('runtimes', 'N/A')
            plot = movie_data.get('plot', 'No description available.')
            
            cast = movie_data.get('cast', [])
            directors = movie_data.get('directors', [])
            
            details_text = f"""<b>🎬 {title} ({year})</b>

<b>⭐ Rating:</b> {rating}/10
<b>🎭 Genres:</b> {genres}
<b>⏳ Runtime:</b> {runtime}
<b>🎬 Director:</b> {', '.join(directors) if directors else 'N/A'}
<b>👥 Cast:</b> {', '.join(cast[:3]) if cast else 'N/A'}

<b>📖 Plot:</b>
{plot}

<b>🔗 IMDb:</b> https://www.imdb.com/title/tt{movie_data.get('imdb_id')}/
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
                'poster': movie_data.get('poster'),
                'imdb_id': movie_data.get('imdb_id'),
                'text': details_text,
                'kind': movie_data.get('kind', 'movie')
            }
            
        except Exception as e:
            return {
                'success': False,
                'title': movie_name,
                'message': f'Error fetching details: {str(e)}'
            }
    
    # ========== SPELLING CORRECTION ==========
    async def check_spelling_correction(self, query: str) -> Dict:
        try:
            clean_query = ' '.join([word.capitalize() for word in query.split()])
            
            # Search on IMDb first
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
            
            # Google search fallback
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                url = f'https://www.google.com/search?q={clean_query.replace(" ", "+")}+movie'
                
                async with session.get(url, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        soup = BeautifulSoup(await resp.text(), 'html.parser')
                        
                        # Look for movie titles in search results
                        titles = soup.find_all('h3')
                        for title_element in titles:
                            title_text = title_element.get_text()
                            if 'movie' in title_text.lower() or 'film' in title_text.lower():
                                ratio = fuzz.ratio(query.lower(), title_text.lower())
                                if ratio < 85 and ratio > 50:
                                    return {
                                        'original': query,
                                        'suggested': title_text,
                                        'confidence': ratio,
                                        'needs_correction': True,
                                        'source': 'google'
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
    
    # ========== SEASON DETECTION ==========
    @staticmethod
    async def check_season_requirement(text: str) -> Tuple[bool, str]:
        series_keywords = ['season', 'series', 'web series', 'webseries', 
                          'tv series', 'tv', 'série', 'serie', 's']
        
        text_lower = text.lower()
        is_series = any(keyword in text_lower for keyword in series_keywords)
        
        if not is_series:
            return False, ""
        
        # Check if season is already specified
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
        common_words = ['download', 'full', 'hd', 'movie', 'film', 'de', 'do', 
                       'bhai', 'send', 'chahiye', 'please', 'plz']
        for word in common_words:
            base_name = base_name.replace(word, '').strip()
        
        # Check for season number
        season_match = re.search(r'(s|season)\s*(\d+)', text_lower, re.IGNORECASE)
        if season_match:
            season_num = season_match.group(2)
            suggested = f"{base_name} Season {season_num}" if base_name else f"Season {season_num}"
        else:
            suggested = f"{base_name} Season 1" if base_name else "Season 1"
        
        return True, suggested
    
    # ========== TEXT CLEANING ==========
    @staticmethod
    async def clean_movie_request(text: str) -> str:
        phrases_to_remove = [
            'movie de do', 'movie chahiye', 'movie dena', 'film do',
            'please send', 'please share', 'link chahiye', 'download',
            'de do bhai', 'bhejo bhai', 'do yaar', 'ka link', 'ki link',
            'bhai', 'bro', 'please', 'plz', 'send me', 'give me',
            'upload', 'upload karo', 'share karo', 'dena hai'
        ]
        
        clean_text = text.lower()
        for phrase in phrases_to_remove:
            clean_text = clean_text.replace(phrase, '')
        
        clean_text = ' '.join(clean_text.split())
        
        # Capitalize properly
        words = clean_text.split()
        capitalized_words = []
        
        for i, word in enumerate(words):
            if i == 0 or len(word) > 2:
                capitalized_words.append(word.capitalize())
            else:
                capitalized_words.append(word.lower())
        
        return ' '.join(capitalized_words)
    
    # ========== FILE INFO EXTRACTION ==========
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
    
    # ========== EXTRACT MOVIE NAME ==========
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

feature_manager = FeatureManager()
