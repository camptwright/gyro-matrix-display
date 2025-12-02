"""
Simple sports score fetcher
Fetches scores from ESPN API or similar free APIs
"""

import requests
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def fetch_espn_scores(sport: str, league_id: str = None) -> List[Dict[str, Any]]:
    """
    Fetch sports scores from ESPN API
    
    Args:
        sport: Sport name (e.g., 'nba', 'nfl', 'mlb', 'nhl')
        league_id: Optional league/team ID
        
    Returns:
        List of game dictionaries with scores
    """
    try:
        # Handle None or empty sport
        if not sport:
            logger.error("Sport is None or empty")
            return []
        
        # ESPN API endpoint (free, no key required)
        base_url = "https://site.api.espn.com/apis/site/v2/sports"
        
        sport_map = {
            'nba': 'basketball/nba',
            'nfl': 'football/nfl',
            'mlb': 'baseball/mlb',
            'nhl': 'hockey/nhl',
            'ncaaf': 'football/college-football',
            'ncaab': 'basketball/mens-college-basketball',
            'ncaam': 'basketball/mens-college-basketball',  # NCAAM is same as NCAAB
            'NFL': 'football/nfl',  # Handle uppercase
            'NBA': 'basketball/nba',
            'MLB': 'baseball/mlb',
            'NHL': 'hockey/nhl',
            'NCAAM': 'basketball/mens-college-basketball'
        }
        
        # Convert to string and lowercase for lookup
        sport_str = str(sport).lower()
        sport_path = sport_map.get(sport_str, f'basketball/{sport_str}')
        url = f"{base_url}/{sport_path}/scoreboard"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        games = []
        for event in data.get('events', []):
            competition = event.get('competitions', [{}])[0]
            competitors = competition.get('competitors', [])
            
            if len(competitors) >= 2:
                home = competitors[0] if competitors[0].get('homeAway') == 'home' else competitors[1]
                away = competitors[1] if competitors[0].get('homeAway') == 'home' else competitors[0]
                
                # Get scores - try different paths
                home_score = home.get('score', '0')
                away_score = away.get('score', '0')
                
                # If scores are None or empty, try alternative paths
                if not home_score or home_score == '0':
                    home_score = str(competition.get('competitors', [{}])[0].get('score', 0))
                if not away_score or away_score == '0':
                    away_score = str(competition.get('competitors', [{}])[1].get('score', 0))
                
                # Extract status information
                status = event.get('status', {})
                status_type = status.get('type', {})
                status_desc = status_type.get('description', '')
                status_id = status_type.get('id', '')
                
                # Get date/time information
                date_str = event.get('date', '')
                
                # Get period/clock information for live games
                period_info = competition.get('period', {})
                period_num = period_info.get('number', 0)
                clock = period_info.get('displayClock', '')
                
                # Determine game state - check both status_id and status_desc
                status_id_upper = status_id.upper() if status_id else ''
                status_desc_upper = status_desc.upper() if status_desc else ''
                
                is_final = (status_id_upper in ['STATUS_FINAL', 'STATUS_FINAL_OVERTIME'] or 
                           'FINAL' in status_id_upper or 'FINAL' in status_desc_upper)
                is_live = (status_id_upper in ['STATUS_IN_PROGRESS', 'STATUS_HALFTIME', 'STATUS_DELAYED'] or
                          'IN_PROGRESS' in status_id_upper or 'HALFTIME' in status_id_upper or
                          'LIVE' in status_desc_upper or 'IN PROGRESS' in status_desc_upper)
                is_scheduled = (status_id_upper in ['STATUS_SCHEDULED', 'STATUS_PRE'] or
                               'SCHEDULED' in status_id_upper or 'PRE' in status_id_upper or
                               'SCHEDULED' in status_desc_upper)
                
                # Format period name based on sport
                period_name = ''
                if period_num > 0:
                    if sport_str in ['nfl', 'ncaaf']:
                        period_name = 'Q' + str(period_num) if period_num <= 4 else 'OT'
                    elif sport_str in ['nba', 'ncaab']:
                        period_name = 'Q' + str(period_num) if period_num <= 4 else 'OT'
                    elif sport_str == 'mlb':
                        period_name = str(period_num) + 'IN'
                    elif sport_str == 'nhl':
                        period_name = str(period_num) + 'P'
                    else:
                        period_name = 'P' + str(period_num)
                
                game = {
                    'home_team': home.get('team', {}).get('abbreviation', home.get('team', {}).get('displayName', 'HOME')),
                    'away_team': away.get('team', {}).get('abbreviation', away.get('team', {}).get('displayName', 'AWAY')),
                    'home_score': home_score if home_score else '0',
                    'away_score': away_score if away_score else '0',
                    'status': status_desc,
                    'status_id': status_id,
                    'period': period_num,
                    'period_name': period_name,
                    'clock': clock,
                    'date': date_str,
                    'is_final': is_final,
                    'is_live': is_live,
                    'is_scheduled': is_scheduled
                }
                games.append(game)
        
        return games
        
    except Exception as e:
        logger.error(f"Error fetching ESPN scores for {sport}: {e}")
        return []


def fetch_simple_scores(sport: str) -> List[Dict[str, Any]]:
    """
    Simple fallback score fetcher
    Returns mock data if API fails
    """
    # Mock data for testing
    mock_games = [
        {
            'home_team': 'TEAM1',
            'away_team': 'TEAM2',
            'home_score': 0,
            'away_score': 0,
            'status': 'Scheduled',
            'period': 0
        }
    ]
    return mock_games
