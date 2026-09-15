"""
Simple sports score fetcher
Fetches scores from ESPN API or similar free APIs
"""

import requests
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

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
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # For NCAAM, use date parameter with limit/groups to get all today's games
        # For other sports, use simple default URL
        if sport_str in ['ncaam', 'ncaab']:
            today = datetime.now()
            today_str = today.strftime('%Y%m%d')
            params = {
                'limit': '500',
                'groups': '50',
                'dates': today_str
            }
            url = f"{base_url}/{sport_path}/scoreboard"
            logger.debug(f"Fetching NCAAM games for {today_str} with limit=500, groups=50")
        else:
            url = f"{base_url}/{sport_path}/scoreboard"
            params = {}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
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
                
                # Extract status information - check both event.status and competition.status
                event_status = event.get('status', {})
                comp_status = competition.get('status', {})
                # Prefer competition.status if available, fallback to event.status
                status = comp_status if comp_status else event_status
                
                status_type = status.get('type', {})
                status_desc = status_type.get('description', '')
                # ESPN's status.type.id is a bare numeric string ("1", "2",
                # "3"...), never one of the STATUS_* constants below - the
                # actual constant name lives in status.type.name (confirmed
                # live: {"id": "2", "name": "STATUS_IN_PROGRESS", ...}).
                # Reading .id here meant every `status_id_upper in
                # ['STATUS_...']` check below could never match; classification
                # only ever worked by accident, via the status_desc_upper
                # fallback text ("In Progress"/"Final") not covering every
                # state - Halftime/Delayed games have no such fallback and
                # were silently misclassified as neither live nor final.
                status_id = status_type.get('name', '') or status_type.get('id', '')
                
                # Get date/time information
                date_str = event.get('date', '')
                
                # Get period/clock information for live games from status object
                period_num = status.get('period', 0)
                clock = status.get('displayClock', '')
                # Also try to get shortDetail for better period display
                status_detail = status_type.get('detail', '')
                status_short_detail = status_type.get('shortDetail', '')
                
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
                # Use shortDetail if available (e.g., "4th", "OT", "2nd Half", "Halftime")
                period_name = ''
                if status_short_detail:
                    period_name = status_short_detail
                elif period_num > 0:
                    if sport_str in ['nfl', 'ncaaf']:
                        if period_num <= 4:
                            period_name = f"{period_num}{'st' if period_num == 1 else 'nd' if period_num == 2 else 'rd' if period_num == 3 else 'th'}"
                        else:
                            period_name = 'OT'
                    elif sport_str in ['nba']:
                        if period_num <= 4:
                            period_name = f"Q{period_num}"
                        else:
                            period_name = 'OT'
                    elif sport_str in ['ncaab', 'ncaam']:
                        # College basketball uses halves, not quarters
                        if period_num == 1:
                            period_name = '1st Half'
                        elif period_num == 2:
                            period_name = '2nd Half'
                        else:
                            period_name = 'OT'
                    elif sport_str == 'mlb':
                        period_name = f"{period_num}IN"
                    elif sport_str == 'nhl':
                        period_name = f"{period_num}P"
                    else:
                        period_name = f"P{period_num}"
                
                # Extract logo URLs from team data if available
                # ESPN API structure can vary: team.logos[0].href, team.logo, or team.links[].href
                home_team_data = home.get('team', {})
                away_team_data = away.get('team', {})
                
                # Try multiple paths for logo URL
                home_logo_url = ''
                # Try team.logos array first (most common)
                if home_team_data.get('logos') and len(home_team_data.get('logos', [])) > 0:
                    # Try first logo's href
                    home_logo_url = home_team_data.get('logos', [{}])[0].get('href', '')
                    # If not found, try the logo itself
                    if not home_logo_url:
                        home_logo_url = home_team_data.get('logos', [{}])[0].get('logo', '')
                # Fallback to direct logo field
                if not home_logo_url and home_team_data.get('logo'):
                    home_logo_url = home_team_data.get('logo')
                
                away_logo_url = ''
                # Try team.logos array first (most common)
                if away_team_data.get('logos') and len(away_team_data.get('logos', [])) > 0:
                    # Try first logo's href
                    away_logo_url = away_team_data.get('logos', [{}])[0].get('href', '')
                    # If not found, try the logo itself
                    if not away_logo_url:
                        away_logo_url = away_team_data.get('logos', [{}])[0].get('logo', '')
                # Fallback to direct logo field
                if not away_logo_url and away_team_data.get('logo'):
                    away_logo_url = away_team_data.get('logo')
                
                # Log if we found logo URLs (for debugging)
                if home_logo_url:
                    logger.debug(f"Found home logo URL for {home_team_data.get('abbreviation', 'UNKNOWN')}: {home_logo_url}")
                else:
                    logger.debug(f"No logo URL found in API response for {home_team_data.get('abbreviation', 'UNKNOWN')} - team data keys: {list(home_team_data.keys())}")
                if away_logo_url:
                    logger.debug(f"Found away logo URL for {away_team_data.get('abbreviation', 'UNKNOWN')}: {away_logo_url}")
                else:
                    logger.debug(f"No logo URL found in API response for {away_team_data.get('abbreviation', 'UNKNOWN')} - team data keys: {list(away_team_data.keys())}")
                
                game = {
                    'home_team': home_team_data.get('abbreviation', home_team_data.get('displayName', 'HOME')),
                    'away_team': away_team_data.get('abbreviation', away_team_data.get('displayName', 'AWAY')),
                    'home_score': home_score if home_score else '0',
                    'away_score': away_score if away_score else '0',
                    'home_logo_url': home_logo_url,
                    'away_logo_url': away_logo_url,
                    'status': status_desc,
                    'status_id': status_id,
                    'status_detail': status_detail,
                    'status_short_detail': status_short_detail,
                    'period': period_num,
                    'period_name': period_name,
                    'clock': clock,
                    'date': date_str,
                    'is_final': is_final,
                    'is_live': is_live,
                    'is_scheduled': is_scheduled
                }
                games.append(game)
        
        # Sort games: live first, then scheduled, then finished
        def sort_key(game):
            # Priority: 0 = live, 1 = scheduled, 2 = finished
            if game.get('is_live', False):
                return (0, game.get('period', 0), game.get('clock', ''))  # Live games sorted by period, then clock
            elif game.get('is_scheduled', False):
                return (1, game.get('date', ''))  # Scheduled games sorted by date/time
            else:
                return (2, game.get('date', ''))  # Finished games sorted by date/time
        
        games.sort(key=sort_key)
        
        # Log sorting results
        live_count = sum(1 for g in games if g.get('is_live', False))
        scheduled_count = sum(1 for g in games if g.get('is_scheduled', False))
        finished_count = sum(1 for g in games if g.get('is_final', False))
        logger.info(f"Fetched {len(games)} games for {sport} - {live_count} live, {scheduled_count} scheduled, {finished_count} finished")
        
        return games
        
    except Exception as e:
        logger.error(f"Error fetching ESPN scores for {sport}: {e}")
        return []


def fetch_espn_scores_for_week(sport: str, week_offset: int = 0) -> List[Dict[str, Any]]:
    """
    Fetch sports scores from ESPN API for a specific week (for NFL/NCAAF)
    
    Args:
        sport: Sport name ('nfl' or 'ncaaf')
        week_offset: Week offset from current week (0 = current week, -1 = previous week, etc.)
        
    Returns:
        List of game dictionaries with scores
    """
    try:
        if not sport:
            logger.error("Sport is None or empty")
            return []
        
        sport_str = str(sport).lower()
        if sport_str not in ['nfl', 'ncaaf']:
            logger.warning(f"fetch_espn_scores_for_week called for {sport}, which may not support weeks")
        
        base_url = "https://site.api.espn.com/apis/site/v2/sports"
        
        sport_map = {
            'nfl': 'football/nfl',
            'ncaaf': 'football/college-football',
            'NFL': 'football/nfl',
            'NCAAF': 'football/college-football'
        }
        
        sport_path = sport_map.get(sport_str, f'football/{sport_str}')
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        url = f"{base_url}/{sport_path}/scoreboard"
        
        # Add week parameter if not current week (week_offset != 0)
        params = {}
        if week_offset != 0:
            # Calculate target week
            # For now, we'll use dates to approximate weeks
            # NFL/NCAAF weeks typically run Sun-Sat, but we'll use a 7-day range
            today = datetime.now()
            week_start = today + timedelta(days=week_offset * 7 - today.weekday())
            week_end = week_start + timedelta(days=6)
            # Use date range for the week
            params['dates'] = f"{week_start.strftime('%Y%m%d')}-{week_end.strftime('%Y%m%d')}"
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        games = []
        for event in data.get('events', []):
            competition = event.get('competitions', [{}])[0]
            competitors = competition.get('competitors', [])
            
            if len(competitors) >= 2:
                home = competitors[0] if competitors[0].get('homeAway') == 'home' else competitors[1]
                away = competitors[1] if competitors[0].get('homeAway') == 'home' else competitors[0]
                
                home_score = home.get('score', '0')
                away_score = away.get('score', '0')
                
                if not home_score or home_score == '0':
                    home_score = str(competition.get('competitors', [{}])[0].get('score', 0))
                if not away_score or away_score == '0':
                    away_score = str(competition.get('competitors', [{}])[1].get('score', 0))
                
                event_status = event.get('status', {})
                comp_status = competition.get('status', {})
                status = comp_status if comp_status else event_status
                
                status_type = status.get('type', {})
                status_desc = status_type.get('description', '')
                # ESPN's status.type.id is a bare numeric string ("1", "2",
                # "3"...), never one of the STATUS_* constants below - the
                # actual constant name lives in status.type.name (confirmed
                # live: {"id": "2", "name": "STATUS_IN_PROGRESS", ...}).
                # Reading .id here meant every `status_id_upper in
                # ['STATUS_...']` check below could never match; classification
                # only ever worked by accident, via the status_desc_upper
                # fallback text ("In Progress"/"Final") not covering every
                # state - Halftime/Delayed games have no such fallback and
                # were silently misclassified as neither live nor final.
                status_id = status_type.get('name', '') or status_type.get('id', '')
                
                date_str = event.get('date', '')
                
                period_num = status.get('period', 0)
                clock = status.get('displayClock', '')
                status_detail = status_type.get('detail', '')
                status_short_detail = status_type.get('shortDetail', '')
                
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
                
                period_name = ''
                if status_short_detail:
                    period_name = status_short_detail
                elif period_num > 0:
                    if sport_str in ['nfl', 'ncaaf']:
                        if period_num <= 4:
                            period_name = f"{period_num}{'st' if period_num == 1 else 'nd' if period_num == 2 else 'rd' if period_num == 3 else 'th'}"
                        else:
                            period_name = 'OT'
                
                home_team_data = home.get('team', {})
                away_team_data = away.get('team', {})
                
                home_logo_url = ''
                if home_team_data.get('logos') and len(home_team_data.get('logos', [])) > 0:
                    home_logo_url = home_team_data.get('logos', [{}])[0].get('href', '')
                    if not home_logo_url:
                        home_logo_url = home_team_data.get('logos', [{}])[0].get('logo', '')
                if not home_logo_url and home_team_data.get('logo'):
                    home_logo_url = home_team_data.get('logo')
                
                away_logo_url = ''
                if away_team_data.get('logos') and len(away_team_data.get('logos', [])) > 0:
                    away_logo_url = away_team_data.get('logos', [{}])[0].get('href', '')
                    if not away_logo_url:
                        away_logo_url = away_team_data.get('logos', [{}])[0].get('logo', '')
                if not away_logo_url and away_team_data.get('logo'):
                    away_logo_url = away_team_data.get('logo')
                
                game = {
                    'home_team': home_team_data.get('abbreviation', home_team_data.get('displayName', 'HOME')),
                    'away_team': away_team_data.get('abbreviation', away_team_data.get('displayName', 'AWAY')),
                    'home_score': home_score if home_score else '0',
                    'away_score': away_score if away_score else '0',
                    'home_logo_url': home_logo_url,
                    'away_logo_url': away_logo_url,
                    'status': status_desc,
                    'status_id': status_id,
                    'status_detail': status_detail,
                    'status_short_detail': status_short_detail,
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
        logger.debug(f"Error fetching games for {sport} week {week_offset}: {e}")
        return []


def fetch_ncaaf_games_with_week_iteration(team_abbr: str, max_weeks_back: int = 4) -> List[Dict[str, Any]]:
    """
    Fetch NCAAF games for a team, iterating through weeks until games are found
    
    Args:
        team_abbr: Team abbreviation to search for
        max_weeks_back: Maximum number of weeks to look back
        
    Returns:
        List of game dictionaries with scores
    """
    all_games = []
    team_abbr_upper = team_abbr.upper().strip()
    today = datetime.now()
    
    # Try current week first (Sun-Sat), then previous weeks
    for week_offset in range(0, -max_weeks_back - 1, -1):
        try:
            # Calculate week range (Sunday to Saturday)
            # Find the most recent Sunday (or today if it's Sunday)
            # weekday(): Monday=0, Tuesday=1, ..., Sunday=6
            # days_since_sunday: Sunday=0, Monday=1, ..., Saturday=6
            days_since_sunday = (today.weekday() + 1) % 7
            # Calculate the start of the current week (most recent Sunday)
            if days_since_sunday == 0:
                # Today is Sunday, this is the start of current week
                current_week_start = today
            else:
                # Go back to the most recent Sunday
                current_week_start = today - timedelta(days=days_since_sunday)
            
            # Apply week_offset (0 = current week, -1 = previous week, etc.)
            week_start = current_week_start + timedelta(days=week_offset * 7)
            week_end = week_start + timedelta(days=6)
            
            # Fetch games for this week using date range
            week_games = []
            for day_offset in range(7):
                target_date = week_start + timedelta(days=day_offset)
                date_str = target_date.strftime('%Y%m%d')
                day_games = fetch_espn_scores_for_date('ncaaf', date_str)
                week_games.extend(day_games)
            
            # Remove duplicates
            seen_games = set()
            unique_week_games = []
            for game in week_games:
                game_key = (
                    game.get('date', ''),
                    game.get('home_team', ''),
                    game.get('away_team', '')
                )
                if game_key not in seen_games:
                    seen_games.add(game_key)
                    unique_week_games.append(game)
            
            # Filter for games involving the team
            team_games = []
            for game in unique_week_games:
                away_team = game.get('away_team', '').upper().strip()
                home_team = game.get('home_team', '').upper().strip()
                if away_team == team_abbr_upper or home_team == team_abbr_upper:
                    team_games.append(game)
            
            if team_games:
                all_games.extend(team_games)
                logger.info(f"Found {len(team_games)} games for {team_abbr} in week starting {week_start.strftime('%Y-%m-%d')}")
                # If we found games, we can stop (we've found at least one game)
                # This ensures we get current week games if available, or the most recent past week with games
                break
            elif week_offset == 0:
                # No games in current week, continue to previous weeks
                logger.debug(f"No games found for {team_abbr} in current week, checking previous weeks...")
                continue
        except Exception as e:
            logger.debug(f"Error fetching NCAAF week {week_offset} for {team_abbr}: {e}")
            continue
    
    return all_games


def fetch_espn_scores_for_date_range(sport: str, days_back: int = 7, days_forward: int = 14) -> List[Dict[str, Any]]:
    """
    Fetch sports scores from ESPN API for a date range
    
    Args:
        sport: Sport name (e.g., 'nba', 'nfl', 'mlb', 'nhl')
        days_back: Number of days in the past to fetch
        days_forward: Number of days in the future to fetch
        
    Returns:
        List of game dictionaries with scores
    """
    all_games = []
    today = datetime.now()
    
    # Fetch games for each day in the range
    for day_offset in range(-days_back, days_forward + 1):
        target_date = today + timedelta(days=day_offset)
        date_str = target_date.strftime('%Y%m%d')
        
        try:
            # Use the existing fetch_espn_scores but with date parameter
            games = fetch_espn_scores_for_date(sport, date_str)
            if games:
                all_games.extend(games)
        except Exception as e:
            logger.debug(f"Error fetching games for {sport} on {date_str}: {e}")
            continue
    
    # Remove duplicates (same game might appear in multiple date queries)
    seen_games = set()
    unique_games = []
    for game in all_games:
        # Create a unique key: sport + date + home_team + away_team
        game_key = (
            game.get('date', ''),
            game.get('home_team', ''),
            game.get('away_team', '')
        )
        if game_key not in seen_games:
            seen_games.add(game_key)
            unique_games.append(game)
    
    logger.info(f"Fetched {len(unique_games)} unique games for {sport} across {days_back + days_forward + 1} days")
    return unique_games


def fetch_espn_scores_for_date(sport: str, date_str: str) -> List[Dict[str, Any]]:
    """
    Fetch sports scores from ESPN API for a specific date
    
    Args:
        sport: Sport name (e.g., 'nba', 'nfl', 'mlb', 'nhl')
        date_str: Date in YYYYMMDD format
        
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
            'ncaam': 'basketball/mens-college-basketball',
            'NFL': 'football/nfl',
            'NBA': 'basketball/nba',
            'MLB': 'baseball/mlb',
            'NHL': 'hockey/nhl',
            'NCAAM': 'basketball/mens-college-basketball'
        }
        
        # Convert to string and lowercase for lookup
        sport_str = str(sport).lower()
        sport_path = sport_map.get(sport_str, f'basketball/{sport_str}')
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        url = f"{base_url}/{sport_path}/scoreboard"
        
        # Add date parameter
        params = {'dates': date_str}
        
        # For NCAAM, also add limit and groups
        if sport_str in ['ncaam', 'ncaab']:
            params['limit'] = '500'
            params['groups'] = '50'
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        games = []
        for event in data.get('events', []):
            competition = event.get('competitions', [{}])[0]
            competitors = competition.get('competitors', [])
            
            if len(competitors) >= 2:
                home = competitors[0] if competitors[0].get('homeAway') == 'home' else competitors[1]
                away = competitors[1] if competitors[0].get('homeAway') == 'home' else competitors[0]
                
                # Get scores
                home_score = home.get('score', '0')
                away_score = away.get('score', '0')
                
                if not home_score or home_score == '0':
                    home_score = str(competition.get('competitors', [{}])[0].get('score', 0))
                if not away_score or away_score == '0':
                    away_score = str(competition.get('competitors', [{}])[1].get('score', 0))
                
                # Extract status information
                event_status = event.get('status', {})
                comp_status = competition.get('status', {})
                status = comp_status if comp_status else event_status
                
                status_type = status.get('type', {})
                status_desc = status_type.get('description', '')
                # ESPN's status.type.id is a bare numeric string ("1", "2",
                # "3"...), never one of the STATUS_* constants below - the
                # actual constant name lives in status.type.name (confirmed
                # live: {"id": "2", "name": "STATUS_IN_PROGRESS", ...}).
                # Reading .id here meant every `status_id_upper in
                # ['STATUS_...']` check below could never match; classification
                # only ever worked by accident, via the status_desc_upper
                # fallback text ("In Progress"/"Final") not covering every
                # state - Halftime/Delayed games have no such fallback and
                # were silently misclassified as neither live nor final.
                status_id = status_type.get('name', '') or status_type.get('id', '')
                
                date_str_game = event.get('date', '')
                
                period_num = status.get('period', 0)
                clock = status.get('displayClock', '')
                status_detail = status_type.get('detail', '')
                status_short_detail = status_type.get('shortDetail', '')
                
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
                
                # Format period name
                period_name = ''
                if status_short_detail:
                    period_name = status_short_detail
                elif period_num > 0:
                    if sport_str in ['nfl', 'ncaaf']:
                        if period_num <= 4:
                            period_name = f"{period_num}{'st' if period_num == 1 else 'nd' if period_num == 2 else 'rd' if period_num == 3 else 'th'}"
                        else:
                            period_name = 'OT'
                    elif sport_str in ['nba']:
                        if period_num <= 4:
                            period_name = f"Q{period_num}"
                        else:
                            period_name = 'OT'
                    elif sport_str in ['ncaab', 'ncaam']:
                        if period_num == 1:
                            period_name = '1st Half'
                        elif period_num == 2:
                            period_name = '2nd Half'
                        else:
                            period_name = 'OT'
                    elif sport_str == 'mlb':
                        period_name = f"{period_num}IN"
                    elif sport_str == 'nhl':
                        period_name = f"{period_num}P"
                    else:
                        period_name = f"P{period_num}"
                
                # Extract logo URLs
                home_team_data = home.get('team', {})
                away_team_data = away.get('team', {})
                
                home_logo_url = ''
                if home_team_data.get('logos') and len(home_team_data.get('logos', [])) > 0:
                    home_logo_url = home_team_data.get('logos', [{}])[0].get('href', '')
                    if not home_logo_url:
                        home_logo_url = home_team_data.get('logos', [{}])[0].get('logo', '')
                if not home_logo_url and home_team_data.get('logo'):
                    home_logo_url = home_team_data.get('logo')
                
                away_logo_url = ''
                if away_team_data.get('logos') and len(away_team_data.get('logos', [])) > 0:
                    away_logo_url = away_team_data.get('logos', [{}])[0].get('href', '')
                    if not away_logo_url:
                        away_logo_url = away_team_data.get('logos', [{}])[0].get('logo', '')
                if not away_logo_url and away_team_data.get('logo'):
                    away_logo_url = away_team_data.get('logo')
                
                game = {
                    'home_team': home_team_data.get('abbreviation', home_team_data.get('displayName', 'HOME')),
                    'away_team': away_team_data.get('abbreviation', away_team_data.get('displayName', 'AWAY')),
                    'home_score': home_score if home_score else '0',
                    'away_score': away_score if away_score else '0',
                    'home_logo_url': home_logo_url,
                    'away_logo_url': away_logo_url,
                    'status': status_desc,
                    'status_id': status_id,
                    'status_detail': status_detail,
                    'status_short_detail': status_short_detail,
                    'period': period_num,
                    'period_name': period_name,
                    'clock': clock,
                    'date': date_str_game,
                    'is_final': is_final,
                    'is_live': is_live,
                    'is_scheduled': is_scheduled
                }
                games.append(game)
        
        return games
        
    except Exception as e:
        logger.debug(f"Error fetching ESPN scores for {sport} on {date_str}: {e}")
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
