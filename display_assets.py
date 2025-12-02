"""
Asset loader for matrix display
Handles logos, icons, and images
"""

import os
import logging
from PIL import Image
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class AssetLoader:
    """Load and manage display assets"""
    
    def __init__(self, assets_dir: str = "assets"):
        self.assets_dir = assets_dir
        self.logo_cache = {}
        
    def get_sport_logo(self, sport_id: str, team_abbr: str = None) -> Optional[Image.Image]:
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

