"""
Simple weather data fetcher
Uses OpenWeatherMap API
"""

import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def fetch_weather(city: str, state: str, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Fetch weather data from OpenWeatherMap
    
    Args:
        city: City name
        state: State/Country code
        api_key: OpenWeatherMap API key
        
    Returns:
        Dictionary with weather data or None
    """
    try:
        if not api_key or api_key == "your_openweathermap_api_key":
            return None
            
        # Build location string
        location = f"{city},{state},US" if len(state) == 2 else f"{city},{state}"
        
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            'q': location,
            'appid': api_key,
            'units': 'imperial'  # Fahrenheit
        }
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        # Get sunrise/sunset times to determine day/night
        sys_time = data.get('sys', {})
        sunrise = sys_time.get('sunrise', 0)
        sunset = sys_time.get('sunset', 0)
        current_time = data.get('dt', 0)  # Current time from API
        
        # Determine if it's day or night
        is_day = True
        if sunrise and sunset and current_time:
            is_day = sunrise <= current_time <= sunset
        
        return {
            'city': city,
            'temp': round(data.get('main', {}).get('temp', 0)),
            'feels_like': round(data.get('main', {}).get('feels_like', 0)),
            'condition': data.get('weather', [{}])[0].get('main', 'Unknown'),
            'description': data.get('weather', [{}])[0].get('description', ''),
            'humidity': data.get('main', {}).get('humidity', 0),
            'wind_speed': round(data.get('wind', {}).get('speed', 0)),
            'is_day': is_day,
            'sunrise': sunrise,
            'sunset': sunset
        }
        
    except Exception as e:
        logger.error(f"Error fetching weather for {city}, {state}: {e}")
        return None

