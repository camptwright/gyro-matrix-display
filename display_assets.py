"""
Asset loader for matrix display
Handles logos, icons, and images
"""

import os
import logging
import requests
from PIL import Image
from typing import Optional, Dict
from io import BytesIO

logger = logging.getLogger(__name__)


class AssetLoader:
    """Load and manage display assets"""
    
    def __init__(self, assets_dir: str = "assets"):
        self.assets_dir = assets_dir
        self.logo_cache = {}
        self.download_cache = {}  # Cache for download attempts to avoid repeated failures
        
    def get_sport_logo(self, sport_id: str, team_abbr: str = None, logo_url: str = None) -> Optional[Image.Image]:
        """Get sport or team logo"""
        try:
            # Map sport IDs to logo directories
            logo_dirs = {
                'nfl': 'sports/nfl_logos',
                'nba': 'sports/nba_logos',
                'mlb': 'sports/mlb_logos',
                'nhl': 'sports/nhl_logos',
                'ncaaf': 'sports/ncaa_logos',  # College football
                'ncaab': 'sports/ncaa_logos',   # College basketball
                'ncaa': 'sports/ncaa_logos',    # General NCAA
                'college-football': 'sports/ncaa_logos',
                'college-basketball': 'sports/ncaa_logos',
                'mens-college-basketball': 'sports/ncaa_logos'
            }
            
            # If team abbreviation provided, try team logo first
            if team_abbr:
                # Clean up team abbreviation (remove extra chars, ensure uppercase)
                team_abbr_clean = str(team_abbr).upper().strip()
                # Try full abbreviation first, then truncated
                team_variants = [team_abbr_clean, team_abbr_clean[:4], team_abbr_clean[:3]]
                
                # Try to find logo in appropriate directory
                logo_dir = None
                for sport, dir_path in logo_dirs.items():
                    if sport_id.lower() == sport.lower():
                        logo_dir = dir_path
                        break
                
                # If no exact match, try to guess from sport_id
                if not logo_dir:
                    sport_lower = sport_id.lower()
                    if 'ncaa' in sport_lower or 'college' in sport_lower:
                        logo_dir = 'sports/ncaa_logos'
                    elif 'football' in sport_lower and 'nfl' not in sport_lower:
                        logo_dir = 'sports/ncaa_logos'  # College football
                    else:
                        # Default to checking all directories
                        logo_dir = None
                
                if logo_dir:
                    # Try variants in the specific directory
                    for variant in team_variants:
                        logo_path = os.path.join(self.assets_dir, logo_dir, f"{variant}.png")
                        logger.debug(f"Trying logo path: {logo_path}")
                        if os.path.exists(logo_path):
                            if logo_path not in self.logo_cache:
                                try:
                                    img = Image.open(logo_path).convert('RGBA')  # Keep alpha channel
                                    self.logo_cache[logo_path] = img
                                    logger.info(f"Loaded team logo: {logo_path} for {team_abbr}")
                                    return self.logo_cache[logo_path]
                                except Exception as e:
                                    logger.error(f"Error loading logo {logo_path}: {e}")
                                    continue
                            else:
                                logger.info(f"Using cached logo: {logo_path}")
                                return self.logo_cache[logo_path]
                    # Logo not found locally, try to download from internet
                    # First try provided logo_url, then try generic download
                    logger.info(f"Logo not found locally for {team_abbr}, attempting to download from internet...")
                    downloaded_logo = None
                    if logo_url:
                        logger.info(f"Trying to download from provided URL: {logo_url}")
                        downloaded_logo = self._download_logo_from_url(logo_url, team_abbr_clean, sport_id, logo_dir)
                    if not downloaded_logo:
                        logger.info(f"Trying generic download for {team_abbr} ({sport_id})")
                        downloaded_logo = self._download_team_logo(team_abbr_clean, sport_id, logo_dir)
                    if downloaded_logo:
                        logger.info(f"Successfully downloaded logo for {team_abbr}")
                        return downloaded_logo
                    else:
                        logger.warning(f"Failed to download logo for {team_abbr} from internet, falling back to conference logo")
                    
                    logger.warning(f"Logo not found for {team_abbr} in {logo_dir}, trying conference/league logo...")
                else:
                    # Try all directories as fallback
                    for sport, dir_path in logo_dirs.items():
                        for variant in team_variants:
                            logo_path = os.path.join(self.assets_dir, dir_path, f"{variant}.png")
                            if os.path.exists(logo_path):
                                if logo_path not in self.logo_cache:
                                    try:
                                        img = Image.open(logo_path).convert('RGBA')
                                        self.logo_cache[logo_path] = img
                                        logger.info(f"Loaded team logo (fallback): {logo_path} for {team_abbr}")
                                        return self.logo_cache[logo_path]
                                    except Exception as e:
                                        logger.error(f"Error loading logo {logo_path}: {e}")
                                        continue
                                else:
                                    return self.logo_cache[logo_path]
                    
                    # Try downloading if not found in any directory
                    downloaded_logo = None
                    if logo_url:
                        downloaded_logo = self._download_logo_from_url(logo_url, team_abbr_clean, sport_id, None)
                    if not downloaded_logo:
                        downloaded_logo = self._download_team_logo(team_abbr_clean, sport_id, None)
                    if downloaded_logo:
                        return downloaded_logo
                    
                    logger.warning(f"Logo not found for {team_abbr} in any directory, trying conference/league logo...")
                
                # Try conference logo for NCAA teams (fallback if team logo not found)
                if logo_dir and 'ncaa' in logo_dir.lower():
                    # Try to find conference logos (common conference names)
                    conference_names = ['SEC', 'BIG10', 'BIG12', 'ACC', 'PAC12', 'AAC', 'CUSA', 'MAC', 'MWC', 'SUNBELT', 'CONFERENCE']
                    for conf_name in conference_names:
                        conf_path = os.path.join(self.assets_dir, logo_dir, f"{conf_name}.png")
                        if os.path.exists(conf_path):
                            if conf_path not in self.logo_cache:
                                try:
                                    img = Image.open(conf_path).convert('RGBA')
                                    self.logo_cache[conf_path] = img
                                    logger.info(f"Using conference logo: {conf_path} for {team_abbr}")
                                    return self.logo_cache[conf_path]
                                except Exception as e:
                                    logger.error(f"Error loading conference logo {conf_path}: {e}")
                                    continue
                            else:
                                logger.info(f"Using cached conference logo: {conf_path}")
                                return self.logo_cache[conf_path]
                    
                    # Try Conference_Usa_Logo_300X300.png (the one we found)
                    conf_usa_path = os.path.join(self.assets_dir, logo_dir, "Conference_Usa_Logo_300X300.png")
                    if os.path.exists(conf_usa_path):
                        if conf_usa_path not in self.logo_cache:
                            try:
                                img = Image.open(conf_usa_path).convert('RGBA')
                                self.logo_cache[conf_usa_path] = img
                                logger.info(f"Using conference logo: {conf_usa_path} for {team_abbr}")
                                return self.logo_cache[conf_usa_path]
                            except Exception as e:
                                logger.error(f"Error loading conference logo {conf_usa_path}: {e}")
                        else:
                            logger.info(f"Using cached conference logo: {conf_usa_path}")
                            return self.logo_cache[conf_usa_path]
            
            # Fall back to league logo
            logo_dir = logo_dirs.get(sport_id.lower())
            if logo_dir:
                logo_path = os.path.join(self.assets_dir, logo_dir, f"{sport_id.upper()}.png")
                if os.path.exists(logo_path):
                    if logo_path not in self.logo_cache:
                        img = Image.open(logo_path).convert('RGBA')
                        self.logo_cache[logo_path] = img
                    return self.logo_cache[logo_path]
                    
        except Exception as e:
            logger.error(f"Could not load sport logo for {sport_id}/{team_abbr}: {e}")
        return None
    
    def _download_logo_from_url(self, logo_url: str, team_abbr: str, sport_id: str, logo_dir: Optional[str]) -> Optional[Image.Image]:
        """Download logo from a specific URL"""
        try:
            if not logo_url:
                return None
            logger.info(f"Downloading logo from provided URL: {logo_url}")
            response = requests.get(logo_url, timeout=5, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            logger.info(f"Response status: {response.status_code} for provided URL: {logo_url}")
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                logger.info(f"Content type: {content_type} for provided URL")
                if 'image' in content_type:
                    try:
                        img = Image.open(BytesIO(response.content)).convert('RGBA')
                        
                        # Save to local directory
                        if logo_dir:
                            os.makedirs(os.path.join(self.assets_dir, logo_dir), exist_ok=True)
                            save_path = os.path.join(self.assets_dir, logo_dir, f"{team_abbr}.png")
                        else:
                            default_dir = os.path.join(self.assets_dir, 'sports', 'ncaa_logos')
                            os.makedirs(default_dir, exist_ok=True)
                            save_path = os.path.join(default_dir, f"{team_abbr}.png")
                        
                        try:
                            img.save(save_path, 'PNG')
                            logger.info(f"Downloaded and saved logo for {team_abbr} from URL to {save_path}")
                        except Exception as save_error:
                            logger.warning(f"Could not save downloaded logo: {save_error}")
                        
                        self.logo_cache[save_path] = img
                        return img
                    except Exception as img_error:
                        logger.warning(f"Failed to parse image from provided URL {logo_url}: {img_error}")
                else:
                    logger.warning(f"Provided URL returned non-image content type: {content_type}")
            else:
                logger.warning(f"Provided URL returned status code {response.status_code}")
        except Exception as e:
            logger.warning(f"Error downloading logo from URL {logo_url}: {e}")
        return None
    
    def _download_team_logo(self, team_abbr: str, sport_id: str, logo_dir: Optional[str]) -> Optional[Image.Image]:
        """Download team logo from internet if not found locally"""
        try:
            # Skip if we've already tried to download this logo and failed
            cache_key = f"{sport_id}_{team_abbr}"
            if cache_key in self.download_cache:
                if self.download_cache[cache_key] is False:
                    logger.debug(f"Skipping download for {team_abbr} - previously failed")
                return None
            
            # Try multiple logo sources
            logo_urls = []
            
            # 1. ESPN API logo URL pattern
            # ESPN uses: https://a.espncdn.com/i/teamlogos/sports/league/team.png
            sport_map = {
                'nfl': ('nfl', '32'),
                'nba': ('nba', '32'),
                'mlb': ('mlb', '40'),
                'nhl': ('nhl', '40'),
                'ncaaf': ('ncaaf', '40'),
                'ncaab': ('ncaab', '40'),
                'ncaam': ('ncaab', '40'),
                'ncaa': ('ncaab', '40'),  # Add ncaa mapping
                'college-football': ('ncaaf', '40'),
                'college-basketball': ('ncaab', '40'),
                'mens-college-basketball': ('ncaab', '40')
            }
            
            sport_key, size = sport_map.get(sport_id.lower(), ('ncaab', '40'))
            espn_url = f"https://a.espncdn.com/i/teamlogos/{sport_key}/{size}/{team_abbr}.png"
            logo_urls.append(espn_url)
            
            # 2. Alternative ESPN URL pattern (sometimes uses different paths)
            espn_url2 = f"https://a.espncdn.com/i/teamlogos/{sport_key}/500/{team_abbr}.png"
            logo_urls.append(espn_url2)
            
            # 3. Try full team name variations for college teams
            if sport_id.lower() in ['ncaaf', 'ncaab', 'ncaam', 'ncaa']:
                # Try with full team name (might need to be lowercase or different format)
                espn_url3 = f"https://a.espncdn.com/i/teamlogos/ncaab/40/{team_abbr.lower()}.png"
                logo_urls.append(espn_url3)
            
            # 4. Try teamlogos.com (free logo service) - commented out as it may not work
            # teamlogos_url = f"https://www.teamlogos.com/logos/{team_abbr}.png"
            # logo_urls.append(teamlogos_url)
            
            # Try each URL
            for i, logo_url in enumerate(logo_urls, 1):
                try:
                    logger.info(f"Attempting to download logo from source {i}/{len(logo_urls)}: {logo_url}")
                    response = requests.get(logo_url, timeout=5, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    
                    logger.info(f"Response status: {response.status_code} for {logo_url}")
                    
                    if response.status_code == 200:
                        # Check if it's actually an image
                        content_type = response.headers.get('content-type', '')
                        logger.info(f"Content type: {content_type} for {logo_url}")
                        if 'image' in content_type:
                            # Verify it's actually a valid image by trying to open it
                            try:
                                img = Image.open(BytesIO(response.content)).convert('RGBA')
                                
                                # Save to local directory for future use
                                if logo_dir:
                                    os.makedirs(os.path.join(self.assets_dir, logo_dir), exist_ok=True)
                                    save_path = os.path.join(self.assets_dir, logo_dir, f"{team_abbr}.png")
                                else:
                                    # Default to ncaa_logos if no directory specified
                                    default_dir = os.path.join(self.assets_dir, 'sports', 'ncaa_logos')
                                    os.makedirs(default_dir, exist_ok=True)
                                    save_path = os.path.join(default_dir, f"{team_abbr}.png")
                                
                                try:
                                    img.save(save_path, 'PNG')
                                    logger.info(f"Downloaded and saved logo for {team_abbr} to {save_path}")
                                except Exception as save_error:
                                    logger.warning(f"Could not save downloaded logo: {save_error}")
                                
                                # Cache the image
                                self.logo_cache[save_path] = img
                                self.download_cache[cache_key] = True
                                return img
                            except Exception as img_error:
                                logger.warning(f"Failed to parse image from {logo_url}: {img_error}")
                                continue
                        else:
                            logger.warning(f"URL returned non-image content type: {content_type} for {logo_url}")
                    else:
                        logger.warning(f"URL returned status code {response.status_code} for {logo_url}")
                except requests.exceptions.RequestException as e:
                    logger.debug(f"Request exception for {logo_url}: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"Error processing downloaded logo from {logo_url}: {e}")
                    continue
            
            # Mark as failed to avoid repeated attempts
            self.download_cache[cache_key] = False
            logger.warning(f"Could not download logo for {team_abbr} from any of {len(logo_urls)} sources")
            return None
            
        except Exception as e:
            logger.debug(f"Error in _download_team_logo for {team_abbr}: {e}")
            return None
    
    def get_stock_icon(self, ticker: str) -> Optional[Image.Image]:
        """Get stock/crypto icon"""
        try:
            # Try crypto first
            crypto_path = os.path.join(self.assets_dir, "stocks", "crypto_icons", f"{ticker.upper()}.png")
            if os.path.exists(crypto_path):
                if crypto_path not in self.logo_cache:
                    img = Image.open(crypto_path).convert('RGB')
                    self.logo_cache[crypto_path] = img
                return self.logo_cache[crypto_path]
            
            # Try stock ticker
            ticker_path = os.path.join(self.assets_dir, "stocks", "ticker_icons", f"{ticker.upper()}.png")
            if os.path.exists(ticker_path):
                if ticker_path not in self.logo_cache:
                    img = Image.open(ticker_path).convert('RGB')
                    self.logo_cache[ticker_path] = img
                return self.logo_cache[ticker_path]
                
        except Exception as e:
            logger.debug(f"Could not load stock icon: {e}")
        return None
    
    def get_weather_icon(self, condition: str, is_day: bool = True) -> Optional[Image.Image]:
        """Get weather condition icon with time-based variants"""
        try:
            from datetime import datetime
            import pytz
            
            # Determine if it's day or night (default to is_day parameter, but can be overridden)
            condition_lower = condition.lower()
            
            # Map conditions to icon names with day/night variants
            condition_map = {
                'clear': 'clear-day' if is_day else 'clear-night',
                'clouds': 'cloudy',
                'rain': 'rain',
                'snow': 'snow',
                'thunderstorm': 'thunderstorms-day' if is_day else 'thunderstorms-night',
                'mist': 'mist',
                'fog': 'fog-day' if is_day else 'fog-night',
                'haze': 'haze-day' if is_day else 'haze-night',
                'dust': 'dust-day' if is_day else 'dust-night',
                'smoke': 'smoke',
                'overcast': 'overcast-day' if is_day else 'overcast-night',
                'partly-cloudy': 'partly-cloudy-day' if is_day else 'partly-cloudy-night',
                'extreme': 'extreme-day' if is_day else 'extreme-night'
            }
            
            # Try exact match first
            icon_name = condition_map.get(condition_lower)
            
            # If no exact match, try partial matches
            if not icon_name:
                if 'clear' in condition_lower:
                    icon_name = 'clear-day' if is_day else 'clear-night'
                elif 'cloud' in condition_lower:
                    if 'partly' in condition_lower:
                        icon_name = 'partly-cloudy-day' if is_day else 'partly-cloudy-night'
                    elif 'overcast' in condition_lower:
                        icon_name = 'overcast-day' if is_day else 'overcast-night'
                    else:
                        icon_name = 'cloudy'
                elif 'rain' in condition_lower:
                    icon_name = 'rain'
                elif 'snow' in condition_lower:
                    icon_name = 'snow'
                elif 'thunder' in condition_lower or 'storm' in condition_lower:
                    icon_name = 'thunderstorms-day' if is_day else 'thunderstorms-night'
                elif 'fog' in condition_lower:
                    icon_name = 'fog-day' if is_day else 'fog-night'
                elif 'mist' in condition_lower:
                    icon_name = 'mist'
                else:
                    icon_name = 'not-available'  # Fallback
            
            # Try the specific icon first
            icon_path = os.path.join(self.assets_dir, "weather", f"{icon_name}.png")
            if os.path.exists(icon_path):
                if icon_path not in self.logo_cache:
                    img = Image.open(icon_path).convert('RGB')
                    self.logo_cache[icon_path] = img
                return self.logo_cache[icon_path]
            
            # Fallback to generic version if day/night variant doesn't exist
            if '-day' in icon_name or '-night' in icon_name:
                generic_name = icon_name.replace('-day', '').replace('-night', '')
                generic_path = os.path.join(self.assets_dir, "weather", f"{generic_name}.png")
                if os.path.exists(generic_path):
                    if generic_path not in self.logo_cache:
                        img = Image.open(generic_path).convert('RGB')
                        self.logo_cache[generic_path] = img
                    return self.logo_cache[generic_path]
                
        except Exception as e:
            logger.debug(f"Could not load weather icon: {e}")
        return None

