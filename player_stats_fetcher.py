"""
Player stats fetcher for fantasy mode
Fetches player statistics using ESPN API (primary implementation)
Supports NFL, NBA, and NHL

Uses ESPN's public API to fetch last game stats for players.
"""

import logging
import requests
import json
import os
from typing import Dict, Any, Optional, Tuple, List, Union
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# API-Sports configuration
# Note: api.api-sports.io domain does not resolve (NXDOMAIN)
# API-Sports may only be available through RapidAPI with different endpoints
# For now, we'll rely on ESPN fallback
API_SPORTS_BASE_URL = "https://api.api-sports.io/v3"  # This domain doesn't exist
API_SPORTS_AVAILABLE = False
API_SPORTS_KEY = None

# Try to load API key from config
try:
    # Get script directory (same approach as matrix_display_controller.py)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config', 'config.json')
    secrets_path = os.path.join(script_dir, 'config', 'config_secrets.json')
    
    logger.debug(f"Looking for config files in: {script_dir}")
    logger.debug(f"Config path: {config_path}")
    logger.debug(f"Secrets path: {secrets_path}")
    
    # Try secrets file first
    if os.path.exists(secrets_path):
        logger.debug(f"Found secrets file: {secrets_path}")
        with open(secrets_path, 'r') as f:
            secrets = json.load(f)
            logger.debug(f"Secrets file keys: {list(secrets.keys())}")
            
            # Check for api_sports key
            if 'api_sports' in secrets:
                logger.debug(f"Found 'api_sports' in secrets: {secrets['api_sports']}")
                if isinstance(secrets['api_sports'], dict) and 'api_key' in secrets['api_sports']:
                    API_SPORTS_KEY = secrets['api_sports']['api_key']
                    if API_SPORTS_KEY and API_SPORTS_KEY != 'YOUR_API_KEY_HERE':
                        API_SPORTS_AVAILABLE = True
                        logger.info("API-Sports key loaded from secrets file")
                    else:
                        logger.warning("API-Sports key found but appears to be placeholder value")
                else:
                    logger.warning(f"'api_sports' exists but 'api_key' not found. Structure: {secrets['api_sports']}")
            else:
                logger.debug("'api_sports' key not found in secrets file")
    
    # Fallback to main config
    if not API_SPORTS_AVAILABLE and os.path.exists(config_path):
        logger.debug(f"Trying main config file: {config_path}")
        with open(config_path, 'r') as f:
            config = json.load(f)
            if 'api_sports' in config:
                if isinstance(config['api_sports'], dict) and 'api_key' in config.get('api_sports', {}):
                    API_SPORTS_KEY = config['api_sports']['api_key']
                    if API_SPORTS_KEY and API_SPORTS_KEY != 'YOUR_API_KEY_HERE':
                        API_SPORTS_AVAILABLE = True
                        logger.info("API-Sports key loaded from config file")
    
    if not API_SPORTS_AVAILABLE:
        logger.warning("API-Sports key not found. Add 'api_sports': {'api_key': 'YOUR_KEY'} to config_secrets.json")
        logger.warning("Get free API key at: https://api-sports.io/ (100 requests/day free)")
        logger.warning(f"Expected structure: {{'api_sports': {{'api_key': 'your_key_here'}}}}")
        logger.warning("NOTE: api.api-sports.io domain does not resolve. API-Sports may require RapidAPI access.")
        logger.warning("Using ESPN API fallback for player stats.")
except Exception as e:
    logger.warning(f"Error loading API-Sports key: {e}", exc_info=True)


def fetch_player_stats(player_name: str, team_abbr: str, sport: str = 'nfl') -> Optional[Dict[str, Any]]:
    """
    Fetch player stats for NFL, NBA, or NHL using API-Sports (primary) or ESPN API (fallback)
    
    Args:
        player_name: Player name (e.g., "Patrick Mahomes", "LeBron James", "Connor McDavid")
        team_abbr: Team abbreviation (e.g., "KC", "LAL", "EDM")
        sport: Sport type - 'nfl', 'nba', or 'nhl'
        
    Returns:
        Dictionary with player stats or None if not found
    """
    sport = sport.lower()
    
    # Use ESPN API (API-Sports domain doesn't resolve)
    logger.debug(f"Using ESPN API for {sport} player stats")
    if sport == 'nfl':
        return fetch_nfl_player_stats_espn(player_name, team_abbr)
    elif sport == 'nba':
        return fetch_nba_player_stats_espn(player_name, team_abbr)
    elif sport == 'nhl':
        return fetch_nhl_player_stats_espn(player_name, team_abbr)
    else:
        logger.warning(f"Unsupported sport: {sport}. Supported: nfl, nba, nhl")
        return None


# ==================== API-Sports Implementation ====================

def fetch_nfl_player_stats_api_sports(player_name: str, team_abbr: str = None) -> Optional[Dict[str, Any]]:
    """Fetch NFL player stats using API-Sports"""
    try:
        logger.info(f"Fetching NFL stats via API-Sports for: {player_name}, team: {team_abbr}")
        
        headers = {
            'x-apisports-key': API_SPORTS_KEY,
            'x-rapidapi-key': API_SPORTS_KEY  # Some endpoints may use this
        }
        
        # Step 1: Get team ID from abbreviation
        team_id = None
        if team_abbr:
            team_id = _get_team_id_api_sports('nfl', team_abbr, headers)
            if team_id:
                logger.debug(f"Found team ID {team_id} for {team_abbr}")
        
        # Step 2: Search for player
        player_id = None
        url = f"{API_SPORTS_BASE_URL}/nfl/players"
        params = {'search': player_name}
        if team_id:
            params['team'] = team_id
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        players = data.get('response', [])
        if players:
            # Find best match
            player_name_lower = player_name.lower()
            for player in players:
                full_name = f"{player.get('firstname', '')} {player.get('lastname', '')}".lower()
                if player_name_lower in full_name or full_name in player_name_lower:
                    player_id = player.get('id')
                    logger.info(f"Found player ID {player_id}: {player.get('firstname')} {player.get('lastname')}")
                    break
        
        if not player_id:
            logger.warning(f"Player {player_name} not found in API-Sports")
            return None
        
        # Step 3: Get player statistics
        current_year = datetime.now().year
        season_year = current_year if datetime.now().month >= 9 else current_year - 1
        
        stats_url = f"{API_SPORTS_BASE_URL}/nfl/players/statistics"
        stats_params = {'player': player_id, 'season': season_year}
        
        stats_response = requests.get(stats_url, headers=headers, params=stats_params, timeout=10)
        stats_response.raise_for_status()
        stats_data = stats_response.json()
        
        # Extract stats from response
        stats_list = stats_data.get('response', [])
        if not stats_list:
            logger.warning(f"No stats found for player {player_id} in season {season_year}")
            return None
        
        # Get most recent game stats or season totals
        latest_game = stats_list[0] if stats_list else {}
        game_stats = latest_game.get('statistics', [{}])[0] if latest_game.get('statistics') else {}
        
        result = {
            'name': f"{latest_game.get('player', {}).get('firstname', '')} {latest_game.get('player', {}).get('lastname', '')}",
            'team': team_abbr.upper() if team_abbr else '',
        }
        
        # Extract NFL stats
        if 'passing' in game_stats:
            passing = game_stats['passing']
            result['passing_yards'] = int(passing.get('yards', 0) or 0)
            result['passing_tds'] = int(passing.get('touchdowns', 0) or 0)
        
        if 'rushing' in game_stats:
            rushing = game_stats['rushing']
            result['rushing_yards'] = int(rushing.get('yards', 0) or 0)
            result['rushing_tds'] = int(rushing.get('touchdowns', 0) or 0)
        
        if 'receiving' in game_stats:
            receiving = game_stats['receiving']
            result['receptions'] = int(receiving.get('receptions', 0) or 0)
            result['receiving_yards'] = int(receiving.get('yards', 0) or 0)
            result['receiving_tds'] = int(receiving.get('touchdowns', 0) or 0)
        
        logger.info(f"Successfully fetched NFL stats: {result}")
        return result
        
    except requests.exceptions.ConnectionError as e:
        # DNS resolution errors, network issues, etc.
        error_msg = str(e)
        if "Name or service not known" in error_msg or "Failed to resolve" in error_msg:
            logger.warning(f"API-Sports DNS resolution failed for 'api.api-sports.io'. Check internet connection and DNS settings.")
            logger.warning(f"Falling back to ESPN API. Error: {e}")
        else:
            logger.warning(f"API-Sports connection error: {e}")
        raise  # Re-raise to trigger ESPN fallback
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logger.warning("API-Sports rate limit exceeded (100 requests/day free tier)")
        else:
            logger.warning(f"API-Sports HTTP error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching NFL stats from API-Sports: {e}", exc_info=True)
        # For DNS/connection errors, re-raise to trigger ESPN fallback
        if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
            raise
        return None


def fetch_nba_player_stats_api_sports(player_name: str, team_abbr: str = None) -> Optional[Dict[str, Any]]:
    """Fetch NBA player stats using API-Sports"""
    try:
        logger.info(f"Fetching NBA stats via API-Sports for: {player_name}, team: {team_abbr}")
        
        headers = {
            'x-apisports-key': API_SPORTS_KEY,
            'x-rapidapi-key': API_SPORTS_KEY  # Some endpoints may use this
        }
        
        # Get team ID
        team_id = None
        if team_abbr:
            team_id = _get_team_id_api_sports('nba', team_abbr, headers)
        
        # Search for player
        url = f"{API_SPORTS_BASE_URL}/nba/players"
        params = {'search': player_name}
        if team_id:
            params['team'] = team_id
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        players = data.get('response', [])
        if not players:
            return None
        
        player = players[0]
        player_id = player.get('id')
        
        # Get statistics
        current_year = datetime.now().year
        season_year = current_year if datetime.now().month >= 10 else current_year - 1
        
        stats_url = f"{API_SPORTS_BASE_URL}/nba/players/statistics"
        stats_params = {'player': player_id, 'season': season_year}
        
        stats_response = requests.get(stats_url, headers=headers, params=stats_params, timeout=10)
        stats_response.raise_for_status()
        stats_data = stats_response.json()
        
        stats_list = stats_data.get('response', [])
        if not stats_list:
            return None
        
        latest_game = stats_list[0] if stats_list else {}
        game_stats = latest_game.get('statistics', [{}])[0] if latest_game.get('statistics') else {}
        
        result = {
            'name': f"{player.get('firstname', '')} {player.get('lastname', '')}",
            'team': team_abbr.upper() if team_abbr else '',
            'points': float(game_stats.get('points', 0) or 0),
            'rebounds': float(game_stats.get('totReb', 0) or 0),
            'assists': float(game_stats.get('assists', 0) or 0),
        }
        
        # Calculate FG%
        fg_made = game_stats.get('fgm', 0) or 0
        fg_attempted = game_stats.get('fga', 0) or 0
        if fg_attempted > 0:
            result['fg_percent'] = round((fg_made / fg_attempted) * 100, 1)
        
        logger.info(f"Successfully fetched NBA stats: {result}")
        return result
        
    except requests.exceptions.ConnectionError as e:
        error_msg = str(e)
        if "Name or service not known" in error_msg or "Failed to resolve" in error_msg:
            logger.warning(f"API-Sports DNS resolution failed. Falling back to ESPN API.")
        else:
            logger.warning(f"API-Sports connection error: {e}")
        raise  # Re-raise to trigger ESPN fallback
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logger.warning("API-Sports rate limit exceeded (100 requests/day free tier)")
        else:
            logger.warning(f"API-Sports HTTP error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching NBA stats from API-Sports: {e}", exc_info=True)
        # For DNS/connection errors, re-raise to trigger ESPN fallback
        if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
            raise
        return None


def fetch_nhl_player_stats_api_sports(player_name: str, team_abbr: str = None) -> Optional[Dict[str, Any]]:
    """Fetch NHL player stats using API-Sports"""
    try:
        logger.info(f"Fetching NHL stats via API-Sports for: {player_name}, team: {team_abbr}")
        
        headers = {
            'x-apisports-key': API_SPORTS_KEY,
            'x-rapidapi-key': API_SPORTS_KEY  # Some endpoints may use this
        }
        
        # Get team ID
        team_id = None
        if team_abbr:
            team_id = _get_team_id_api_sports('nhl', team_abbr, headers)
        
        # Search for player
        url = f"{API_SPORTS_BASE_URL}/nhl/players"
        params = {'search': player_name}
        if team_id:
            params['team'] = team_id
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        players = data.get('response', [])
        if not players:
            return None
        
        player = players[0]
        player_id = player.get('id')
        
        # Get statistics
        current_year = datetime.now().year
        season_year = current_year if datetime.now().month >= 10 else current_year - 1
        
        stats_url = f"{API_SPORTS_BASE_URL}/nhl/players/statistics"
        stats_params = {'player': player_id, 'season': season_year}
        
        stats_response = requests.get(stats_url, headers=headers, params=stats_params, timeout=10)
        stats_response.raise_for_status()
        stats_data = stats_response.json()
        
        stats_list = stats_data.get('response', [])
        if not stats_list:
            return None
        
        latest_game = stats_list[0] if stats_list else {}
        game_stats = latest_game.get('statistics', [{}])[0] if latest_game.get('statistics') else {}
        
        result = {
            'name': f"{player.get('firstname', '')} {player.get('lastname', '')}",
            'team': team_abbr.upper() if team_abbr else '',
            'goals': int(game_stats.get('goals', 0) or 0),
            'assists': int(game_stats.get('assists', 0) or 0),
            'points': int((game_stats.get('goals', 0) or 0) + (game_stats.get('assists', 0) or 0)),
        }
        
        logger.info(f"Successfully fetched NHL stats: {result}")
        return result
        
    except requests.exceptions.ConnectionError as e:
        error_msg = str(e)
        if "Name or service not known" in error_msg or "Failed to resolve" in error_msg:
            logger.warning(f"API-Sports DNS resolution failed. Falling back to ESPN API.")
        else:
            logger.warning(f"API-Sports connection error: {e}")
        raise  # Re-raise to trigger ESPN fallback
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logger.warning("API-Sports rate limit exceeded (100 requests/day free tier)")
        else:
            logger.warning(f"API-Sports HTTP error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching NHL stats from API-Sports: {e}", exc_info=True)
        # For DNS/connection errors, re-raise to trigger ESPN fallback
        if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
            raise
        return None


def _get_team_id_api_sports(sport: str, team_abbr: str, headers: Dict) -> Optional[int]:
    """Get team ID from API-Sports using team abbreviation"""
    try:
        url = f"{API_SPORTS_BASE_URL}/{sport}/teams"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        teams = data.get('response', [])
        team_abbr_upper = team_abbr.upper()
        
        for team in teams:
            if team.get('code', '').upper() == team_abbr_upper or team.get('name', '').upper() == team_abbr_upper:
                return team.get('id')
        
        return None
    except Exception as e:
        logger.debug(f"Error getting team ID from API-Sports: {e}")
        return None


# ==================== ESPN API Implementation ====================
# Based on espn_player_last_game.py

LEAGUE_CONFIG = {
    "nfl": {"sport": "football", "league": "nfl"},
    "nba": {"sport": "basketball", "league": "nba"},
    "nhl": {"sport": "hockey", "league": "nhl"},
}


def _get_league_config(league: str) -> Dict[str, str]:
    league = league.lower()
    if league not in LEAGUE_CONFIG:
        raise ValueError(f"Unsupported league '{league}'. Use nfl, nba, or nhl.")
    return LEAGUE_CONFIG[league]


def _normalize_team_string(s: str) -> str:
    """Uppercase, letters+digits only, no spaces/punctuation."""
    return "".join(ch for ch in s.upper() if ch.isalnum())


def _team_matches(team_info: Dict[str, Any], user_team_input: str) -> bool:
    """Match team by abbreviation, full name, or nickname."""
    if not user_team_input:
        return False

    q_raw = user_team_input.strip().upper()
    q_norm = _normalize_team_string(user_team_input)

    candidates = [
        team_info.get("abbreviation") or "",
        team_info.get("shortDisplayName") or "",
        team_info.get("displayName") or "",
        team_info.get("name") or "",
        team_info.get("nickname") or "",
    ]

    for cand in candidates:
        if not cand:
            continue
        c_raw = cand.upper()
        c_norm = _normalize_team_string(cand)

        if q_raw == c_raw or q_norm == c_norm:
            return True
        if q_norm and q_norm in c_norm:
            return True

    return False


def _find_latest_team_game_event(
    league: str,
    team_query: str,
    max_days_back: int = 30,
) -> Tuple[str, Dict[str, Any], str]:
    """Find the most recent game for a team and return (event_id, event_json, canonical_team_abbrev)."""
    cfg = _get_league_config(league)
    sport = cfg["sport"]
    league_code = cfg["league"]

    today = datetime.now(timezone.utc).date()

    for days_back in range(max_days_back + 1):
        target_date = today - timedelta(days=days_back)
        date_str = target_date.strftime("%Y%m%d")

        scoreboard_url = (
            f"https://site.api.espn.com/apis/site/v2/sports/"
            f"{sport}/{league_code}/scoreboard"
        )
        try:
            response = requests.get(scoreboard_url, params={"dates": date_str}, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.debug(f"Error fetching scoreboard for {date_str}: {e}")
            continue

        events = data.get("events", [])
        for event in events:
            # Skip future/pregame
            state = (
                event.get("status", {})
                .get("type", {})
                .get("state", "")
            )
            if state.lower() == "pre":
                continue

            competitions = event.get("competitions", [])
            if not competitions:
                continue

            comp = competitions[0]
            competitors = comp.get("competitors", [])

            for team in competitors:
                team_info = team.get("team", {}) or {}
                if _team_matches(team_info, team_query):
                    event_id = event.get("id")
                    if not event_id:
                        continue
                    canonical_abbrev = (team_info.get("abbreviation") or "").upper()
                    return str(event_id), event, canonical_abbrev

    raise ValueError(
        f"No in-progress or completed game found for team '{team_query}' "
        f"in the last {max_days_back} days."
    )


def _fetch_game_summary(league: str, event_id: str) -> Dict[str, Any]:
    """Fetch the game summary (includes boxscore) for the given event ID."""
    cfg = _get_league_config(league)
    sport = cfg["sport"]
    league_code = cfg["league"]

    summary_url = (
        f"http://site.api.espn.com/apis/site/v2/sports/"
        f"{sport}/{league_code}/summary"
    )
    response = requests.get(summary_url, params={"event": event_id}, timeout=10)
    response.raise_for_status()
    return response.json()


def _match_player_name(athlete: Dict[str, Any], player_name: str) -> bool:
    """Check if the ESPN athlete matches the desired player name."""
    name_lower = player_name.lower()
    candidates = [
        athlete.get("fullName"),
        athlete.get("displayName"),
        athlete.get("shortName"),
    ]
    for c in candidates:
        if c and c.lower() == name_lower:
            return True
    for c in candidates:
        if c and name_lower in c.lower():
            return True
    return False


def _find_player_stats_from_boxscore_players(
    boxscore: Dict[str, Any],
    player_name: str,
    team_abbrev: str
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract player stats from boxscore['players'] structure."""
    players_groups = boxscore.get("players", [])
    team_abbrev = team_abbrev.upper()

    for group in players_groups:
        team_info = group.get("team") or {}
        abbrev = (team_info.get("abbreviation") or "").upper()
        if abbrev != team_abbrev:
            continue

        statistics = group.get("statistics", [])
        combined_stats: Dict[str, Any] = {}
        athlete_info: Optional[Dict[str, Any]] = None

        for stat_group in statistics:
            labels = stat_group.get("labels") or stat_group.get("names") or []
            stat_group_name = (
                stat_group.get("name")
                or stat_group.get("type")
                or stat_group.get("displayName")
                or ""
            )
            athletes = stat_group.get("athletes", [])

            for entry in athletes:
                athlete = entry.get("athlete") or {}
                if not _match_player_name(athlete, player_name):
                    continue

                if athlete_info is None:
                    athlete_info = athlete

                values = entry.get("stats") or []
                for label, value in zip(labels, values):
                    key = str(label)
                    if key in combined_stats and stat_group_name:
                        key = f"{stat_group_name}_{key}"
                    combined_stats[key] = value

        if athlete_info is not None and combined_stats:
            return athlete_info, combined_stats

    raise ValueError(
        f"Could not find boxscore['players'] stats for '{player_name}' on team '{team_abbrev}'."
    )


def _extract_stats_from_node(node: Dict[str, Any]) -> Dict[str, Any]:
    """Generic fallback: Convert an ESPN stats/summary node into a dict."""
    stats: Dict[str, Any] = {}

    if "statistics" in node and isinstance(node["statistics"], list):
        for stat in node["statistics"]:
            if not isinstance(stat, dict):
                continue
            key = stat.get("abbreviation") or stat.get("name") or stat.get("label")
            value = stat.get("displayValue") or stat.get("value")
            if key and value is not None:
                stats[str(key)] = value

    if "stats" in node and isinstance(node["stats"], list):
        for stat in node["stats"]:
            if not isinstance(stat, dict):
                continue
            key = stat.get("abbreviation") or stat.get("name") or stat.get("label")
            value = stat.get("displayValue") or stat.get("value")
            if key and value is not None:
                stats[str(key)] = value

    return stats


def _match_team_abbrev_in_context(
    context: Dict[str, Any],
    team_abbrev: str
) -> bool:
    """Verify that the stat object belongs to the requested team."""
    team_abbrev = team_abbrev.upper()

    team = context.get("team")
    if isinstance(team, dict):
        abbrev = team.get("abbreviation") or team.get("shortDisplayName")
        if abbrev and abbrev.upper().startswith(team_abbrev):
            return True

    athlete = context.get("athlete")
    if isinstance(athlete, dict):
        team = athlete.get("team")
        if isinstance(team, dict):
            abbrev = team.get("abbreviation") or team.get("shortDisplayName")
            if abbrev and abbrev.upper().startswith(team_abbrev):
                return True

    return False


def _recursive_find_player_stats_generic(
    summary: Dict[str, Any],
    player_name: str,
    team_abbrev: str
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Generic recursive search as fallback."""
    matches: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []

    def traverse(obj: Any):
        if isinstance(obj, dict):
            if "athlete" in obj and isinstance(obj["athlete"], dict):
                athlete = obj["athlete"]
                if _match_player_name(athlete, player_name):
                    if _match_team_abbrev_in_context(obj, team_abbrev):
                        stats = _extract_stats_from_node(obj)
                        if stats:
                            matches.append((athlete, stats))

            for v in obj.values():
                traverse(v)

        elif isinstance(obj, list):
            for item in obj:
                traverse(item)

    root = summary.get("boxscore", summary)
    traverse(root)

    if not matches:
        raise ValueError(
            f"Could not find stats for '{player_name}' on team '{team_abbrev}'. (generic search)"
        )

    best_athlete, best_stats = max(matches, key=lambda x: len(x[1]))
    return best_athlete, best_stats


def _find_player_stats_in_summary(
    league: str,
    summary: Dict[str, Any],
    player_name: str,
    team_abbrev: str
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Main entry point to get player stats from a game summary."""
    boxscore = summary.get("boxscore", {})

    if "players" in boxscore:
        try:
            return _find_player_stats_from_boxscore_players(
                boxscore,
                player_name,
                team_abbrev,
            )
        except ValueError:
            pass

    return _recursive_find_player_stats_generic(
        summary,
        player_name,
        team_abbrev,
    )


def _convert_espn_stats_to_display_format(
    sport: str,
    stats: Dict[str, Any],
    athlete: Dict[str, Any]
) -> Dict[str, Any]:
    """Convert ESPN stats format to display controller format."""
    result = {
        'name': athlete.get('fullName') or athlete.get('displayName') or '',
        'team': '',
        'position': '',
    }
    
    # Get team and position from athlete
    team = athlete.get("team", {})
    if isinstance(team, dict):
        result['team'] = (team.get("abbreviation") or team.get("shortDisplayName") or "").upper()
    
    position = athlete.get("position", {})
    if isinstance(position, dict):
        result['position'] = position.get("abbreviation") or position.get("displayName") or ""
    
    if sport == 'nfl':
        # Map ESPN NFL stats to display format
        # Priority order: Passing > Rushing > Receiving (for ambiguous YDS/TD fields)
        # Passing stats
        if 'C/ATT' in stats:
            c_att = str(stats.get('C/ATT', '0/0')).split('/')
            result['passing_completions'] = int(c_att[0]) if len(c_att) > 0 and c_att[0].isdigit() else 0
            result['passing_attempts'] = int(c_att[1]) if len(c_att) > 1 and c_att[1].isdigit() else 0
            # If C/ATT exists, YDS without prefix is ALWAYS passing yards
            # (even if rushing_YDS or receiving_YDS also exist - those are separate fields)
            if 'YDS' in stats:
                result['passing_yards'] = int(stats.get('YDS', 0) or 0)
            # TD without prefix is ALWAYS passing TD when C/ATT exists
            # (even if rushing_TD or receiving_TD also exist - those are separate fields)
            if 'TD' in stats:
                result['passing_tds'] = int(stats.get('TD', 0) or 0)
        if 'INT' in stats:
            result['passing_ints'] = int(stats.get('INT', 0) or 0)
        if 'RTG' in stats:
            try:
                result['passing_rating'] = float(stats.get('RTG', 0) or 0)
            except (ValueError, TypeError):
                pass
        
        # Rushing stats
        if 'CAR' in stats:
            result['rushing_attempts'] = int(stats.get('CAR', 0) or 0)
        if 'rushing_YDS' in stats:
            result['rushing_yards'] = int(stats.get('rushing_YDS', 0) or 0)
        elif 'YDS' in stats and 'CAR' in stats and 'C/ATT' not in stats:
            # YDS with CAR (regardless of REC) is rushing yards
            # This handles players like Bucky Irving who have both rushing and receiving stats
            result['rushing_yards'] = int(stats.get('YDS', 0) or 0)
        if 'rushing_TD' in stats:
            result['rushing_tds'] = int(stats.get('rushing_TD', 0) or 0)
        elif 'TD' in stats and 'CAR' in stats and 'C/ATT' not in stats:
            # TD with CAR (regardless of REC) is rushing TD
            result['rushing_tds'] = int(stats.get('TD', 0) or 0)
        
        # Receiving stats
        if 'REC' in stats:
            result['receptions'] = int(stats.get('REC', 0) or 0)
        if 'receiving_YDS' in stats:
            result['receiving_yards'] = int(stats.get('receiving_YDS', 0) or 0)
        elif 'YDS' in stats and 'REC' in stats and 'C/ATT' not in stats and 'CAR' not in stats:
            # YDS with REC but no C/ATT and no CAR is receiving yards
            # Only use YDS for receiving if CAR is not present (CAR takes priority)
            result['receiving_yards'] = int(stats.get('YDS', 0) or 0)
        if 'receiving_TD' in stats:
            result['receiving_tds'] = int(stats.get('receiving_TD', 0) or 0)
        if 'TGTS' in stats:
            result['targets'] = int(stats.get('TGTS', 0) or 0)
        
        # Fumbles
        if 'FUM' in stats or 'fumbles' in stats:
            result['fumbles'] = int(stats.get('FUM', stats.get('fumbles', 0)) or 0)
        if 'FUM_LOST' in stats or 'fumbles_lost' in stats:
            result['fumbles_lost'] = int(stats.get('FUM_LOST', stats.get('fumbles_lost', 0)) or 0)
        
        # Kicker stats
        if 'FG' in stats or 'field_goals' in stats:
            # Field goals might be in format "MADE/ATT" or separate fields
            fg_str = str(stats.get('FG', stats.get('field_goals', '0/0')) or '0/0')
            if '/' in fg_str:
                fg_parts = fg_str.split('/')
                result['fg_made'] = int(fg_parts[0]) if len(fg_parts) > 0 and fg_parts[0].isdigit() else 0
                result['fg_attempted'] = int(fg_parts[1]) if len(fg_parts) > 1 and fg_parts[1].isdigit() else 0
            else:
                result['fg_made'] = int(fg_str) if fg_str.isdigit() else 0
        if 'XP' in stats or 'extra_points' in stats or 'PAT' in stats:
            xp_str = str(stats.get('XP', stats.get('PAT', stats.get('extra_points', '0/0'))) or '0/0')
            if '/' in xp_str:
                xp_parts = xp_str.split('/')
                result['xp_made'] = int(xp_parts[0]) if len(xp_parts) > 0 and xp_parts[0].isdigit() else 0
                result['xp_attempted'] = int(xp_parts[1]) if len(xp_parts) > 1 and xp_parts[1].isdigit() else 0
            else:
                result['xp_made'] = int(xp_str) if xp_str.isdigit() else 0
        if 'LNG' in stats or 'long' in stats or 'longest' in stats:
            result['fg_long'] = int(stats.get('LNG', stats.get('long', stats.get('longest', 0))) or 0)
    
    elif sport == 'nba':
        # Map ESPN NBA stats to display format
        if 'PTS' in stats or 'points' in stats:
            result['points'] = float(stats.get('PTS', stats.get('points', 0)) or 0)
        
        # Field goals made/attempted - check multiple formats
        # ESPN returns "FG" as "9-13" format, also check for FGM/FGA separately and FGM-A format
        fg_parsed = False
        
        # Check for "FG" field first (ESPN's primary format: "9-13")
        # ESPN uses "FG" key with value like "9-13" (made-attempted)
        if 'FG' in stats and 'fg_made' not in result:
            fg_str = str(stats.get('FG', '0-0') or '0-0')
            if '-' in fg_str:
                fg_parts = fg_str.split('-')
                if len(fg_parts) >= 2:
                    try:
                        result['fg_made'] = int(fg_parts[0].strip())
                        result['fg_attempted'] = int(fg_parts[1].strip())
                        fg_parsed = True
                    except (ValueError, IndexError):
                        pass
            elif '/' in fg_str:
                fg_parts = fg_str.split('/')
                if len(fg_parts) >= 2:
                    try:
                        result['fg_made'] = int(fg_parts[0].strip())
                        result['fg_attempted'] = int(fg_parts[1].strip())
                        fg_parsed = True
                    except (ValueError, IndexError):
                        pass
        
        # Check for FGM-A format (alternative format)
        if not fg_parsed and 'FGM-A' in stats:
            fgm_a_str = str(stats.get('FGM-A', '0-0') or '0-0')
            if '-' in fgm_a_str:
                fgm_a_parts = fgm_a_str.split('-')
                if len(fgm_a_parts) >= 2:
                    try:
                        result['fg_made'] = int(fgm_a_parts[0])
                        result['fg_attempted'] = int(fgm_a_parts[1])
                        fg_parsed = True
                    except (ValueError, IndexError):
                        pass
        
        # Check for separate FGM and FGA fields
        if not fg_parsed:
            if 'FGM' in stats or 'fgm' in stats:
                try:
                    result['fg_made'] = int(stats.get('FGM', stats.get('fgm', 0)) or 0)
                except (ValueError, TypeError):
                    pass
            if 'FGA' in stats or 'fga' in stats:
                try:
                    result['fg_attempted'] = int(stats.get('FGA', stats.get('fga', 0)) or 0)
                except (ValueError, TypeError):
                    pass
        
        if 'REB' in stats or 'rebounds' in stats:
            result['rebounds'] = float(stats.get('REB', stats.get('rebounds', 0)) or 0)
        if 'AST' in stats or 'assists' in stats:
            result['assists'] = float(stats.get('AST', stats.get('assists', 0)) or 0)
        if 'BLK' in stats or 'blocks' in stats or 'BLKS' in stats:
            result['blocks'] = float(stats.get('BLK', stats.get('BLKS', stats.get('blocks', 0))) or 0)
        if 'STL' in stats or 'steals' in stats or 'STLS' in stats:
            result['steals'] = float(stats.get('STL', stats.get('STLS', stats.get('steals', 0))) or 0)
        if 'TO' in stats or 'turnovers' in stats or 'TOS' in stats:
            result['turnovers'] = float(stats.get('TO', stats.get('TOS', stats.get('turnovers', 0))) or 0)
        if 'PF' in stats or 'personal_fouls' in stats:
            result['personal_fouls'] = float(stats.get('PF', stats.get('personal_fouls', 0)) or 0)
        if '+/-' in stats or 'plus_minus' in stats or 'PM' in stats:
            pm_str = str(stats.get('+/-', stats.get('PM', stats.get('plus_minus', '0'))) or '0')
            try:
                result['plus_minus'] = int(pm_str)
            except ValueError:
                result['plus_minus'] = 0
        if 'FG%' in stats or 'FG_PCT' in stats:
            fg_pct_str = str(stats.get('FG%', stats.get('FG_PCT', '0')) or '0').rstrip('%')
            try:
                result['fg_pct'] = float(fg_pct_str)
            except ValueError:
                result['fg_pct'] = 0.0
    
    elif sport == 'nhl':
        # Map ESPN NHL stats to display format
        if 'G' in stats or 'goals' in stats:
            result['goals'] = int(stats.get('G', stats.get('goals', 0)) or 0)
        if 'A' in stats or 'assists' in stats:
            result['assists'] = int(stats.get('A', stats.get('assists', 0)) or 0)
        if 'G' in stats or 'A' in stats:
            goals = int(stats.get('G', stats.get('goals', 0)) or 0)
            assists = int(stats.get('A', stats.get('assists', 0)) or 0)
            result['points'] = goals + assists
        if 'S' in stats or 'shots' in stats or 'SOG' in stats:
            result['shots'] = int(stats.get('S', stats.get('SOG', stats.get('shots', 0))) or 0)
        if '+/-' in stats or 'plus_minus' in stats or 'PM' in stats:
            pm_str = str(stats.get('+/-', stats.get('PM', stats.get('plus_minus', '0'))) or '0')
            try:
                result['plus_minus'] = int(pm_str)
            except ValueError:
                result['plus_minus'] = 0
        if 'BS' in stats or 'blocks' in stats or 'BLK' in stats:
            result['blocks'] = int(stats.get('BS', stats.get('BLK', stats.get('blocks', 0))) or 0)
        if 'HIT' in stats or 'hits' in stats:
            result['hits'] = int(stats.get('HIT', stats.get('hits', 0)) or 0)
        if 'PIM' in stats or 'penalty_minutes' in stats:
            result['penalty_minutes'] = int(stats.get('PIM', stats.get('penalty_minutes', 0)) or 0)
        if 'TOI' in stats or 'time_on_ice' in stats:
            toi_str = str(stats.get('TOI', stats.get('time_on_ice', '0:00')) or '0:00')
            result['time_on_ice'] = toi_str
        if 'SV%' in stats or 'save_pct' in stats:
            sv_pct_str = str(stats.get('SV%', stats.get('save_pct', '0')) or '0').rstrip('%')
            try:
                result['save_pct'] = float(sv_pct_str)
            except ValueError:
                result['save_pct'] = 0.0
        if 'GAA' in stats or 'gaa' in stats:
            try:
                result['gaa'] = float(stats.get('GAA', stats.get('gaa', 0)) or 0)
            except ValueError:
                result['gaa'] = 0.0
        # Goalie stats
        if 'W' in stats or 'wins' in stats:
            result['wins'] = int(stats.get('W', stats.get('wins', 0)) or 0)
        if 'GA' in stats or 'goals_against' in stats:
            result['goals_against'] = int(stats.get('GA', stats.get('goals_against', 0)) or 0)
        if 'SV' in stats or 'saves' in stats:
            result['saves'] = int(stats.get('SV', stats.get('saves', 0)) or 0)
        if 'SO' in stats or 'shutouts' in stats:
            result['shutouts'] = int(stats.get('SO', stats.get('shutouts', 0)) or 0)
    
    return result


def _get_game_matchup(event: Dict[str, Any], team_abbrev: str) -> str:
    """Extract game matchup (e.g., 'TB vs. ARI') from event data"""
    try:
        competitions = event.get("competitions", [])
        if not competitions:
            return team_abbrev
        
        comp = competitions[0]
        competitors = comp.get("competitors", [])
        
        team_abbrev_upper = team_abbrev.upper()
        away_abbrev = ""
        home_abbrev = ""
        
        for team in competitors:
            team_info = team.get("team", {}) or {}
            abbrev = (team_info.get("abbreviation") or "").upper()
            is_home = team.get("homeAway", "").lower() == "home"
            
            if abbrev == team_abbrev_upper:
                if is_home:
                    home_abbrev = abbrev
                else:
                    away_abbrev = abbrev
            else:
                if is_home:
                    home_abbrev = abbrev
                else:
                    away_abbrev = abbrev
        
        if away_abbrev and home_abbrev:
            return f"{away_abbrev} vs. {home_abbrev}"
        elif away_abbrev or home_abbrev:
            return away_abbrev or home_abbrev
        else:
            return team_abbrev
    except Exception as e:
        logger.debug(f"Error getting game matchup: {e}")
        return team_abbrev


def fetch_nfl_player_stats_espn(player_name: str, team_abbr: str = None) -> Optional[Dict[str, Any]]:
    """Fetch NFL player stats using ESPN API - gets last game stats"""
    try:
        logger.info(f"Fetching NFL stats via ESPN for: {player_name}, team: {team_abbr}")
        
        if not team_abbr:
            logger.warning("No team abbreviation provided for ESPN search")
            return None
        
        # Find latest game for team
        event_id, event, canonical_abbrev = _find_latest_team_game_event('nfl', team_abbr)
        logger.debug(f"Found event {event_id} for team {canonical_abbrev}")
        
        # Fetch game summary
        summary = _fetch_game_summary('nfl', event_id)
        
        # Find player stats in summary
        athlete, stats = _find_player_stats_in_summary('nfl', summary, player_name, canonical_abbrev)
        
        # Convert to display format
        result = _convert_espn_stats_to_display_format('nfl', stats, athlete)
        result['team'] = canonical_abbrev
        result['game_matchup'] = _get_game_matchup(event, canonical_abbrev)
        
        logger.info(f"Successfully fetched NFL stats: {result}")
        return result
        
    except ValueError as e:
        logger.warning(f"Could not find stats: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching NFL stats from ESPN: {e}", exc_info=True)
        return None


def fetch_nba_player_stats_espn(player_name: str, team_abbr: str = None) -> Optional[Dict[str, Any]]:
    """Fetch NBA player stats using ESPN API - gets last game stats"""
    try:
        logger.info(f"Fetching NBA stats via ESPN for: {player_name}, team: {team_abbr}")
        
        if not team_abbr:
            logger.warning("No team abbreviation provided for ESPN search")
            return None
        
        # Find latest game for team
        event_id, event, canonical_abbrev = _find_latest_team_game_event('nba', team_abbr)
        logger.debug(f"Found event {event_id} for team {canonical_abbrev}")
        
        # Fetch game summary
        summary = _fetch_game_summary('nba', event_id)
        
        # Find player stats in summary
        athlete, stats = _find_player_stats_in_summary('nba', summary, player_name, canonical_abbrev)
        
        # Convert to display format
        result = _convert_espn_stats_to_display_format('nba', stats, athlete)
        result['team'] = canonical_abbrev
        result['game_matchup'] = _get_game_matchup(event, canonical_abbrev)
        
        logger.info(f"Successfully fetched NBA stats: {result}")
        return result
        
    except ValueError as e:
        logger.warning(f"Could not find stats: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching NBA stats from ESPN: {e}", exc_info=True)
        return None


def fetch_nhl_player_stats_espn(player_name: str, team_abbr: str = None) -> Optional[Dict[str, Any]]:
    """Fetch NHL player stats using ESPN API - gets last game stats"""
    try:
        logger.info(f"Fetching NHL stats via ESPN for: {player_name}, team: {team_abbr}")
        
        if not team_abbr:
            logger.warning("No team abbreviation provided for ESPN search")
            return None
        
        # Find latest game for team
        event_id, event, canonical_abbrev = _find_latest_team_game_event('nhl', team_abbr)
        logger.debug(f"Found event {event_id} for team {canonical_abbrev}")
        
        # Fetch game summary
        summary = _fetch_game_summary('nhl', event_id)
        
        # Find player stats in summary
        athlete, stats = _find_player_stats_in_summary('nhl', summary, player_name, canonical_abbrev)
        
        # Convert to display format
        result = _convert_espn_stats_to_display_format('nhl', stats, athlete)
        result['team'] = canonical_abbrev
        result['game_matchup'] = _get_game_matchup(event, canonical_abbrev)
        
        logger.info(f"Successfully fetched NHL stats: {result}")
        return result
        
    except ValueError as e:
        logger.warning(f"Could not find stats: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching NHL stats from ESPN: {e}", exc_info=True)
        return None


def _get_nfl_team_id_espn(team_abbr: str, base_url: str, headers: Dict) -> Optional[str]:
    """Get ESPN team ID from team abbreviation"""
    try:
        url = f"{base_url}/teams"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        team_abbr_upper = team_abbr.upper()
        for sport in data.get('sports', []):
            for league in sport.get('leagues', []):
                for team_group in league.get('teams', []):
                    team_entry = team_group.get('team')
                    if team_entry and isinstance(team_entry, dict):
                        if team_entry.get('abbreviation', '').upper() == team_abbr_upper:
                            return team_entry.get('id')
        return None
    except Exception as e:
        logger.debug(f"Error fetching NFL team list from ESPN: {e}")
        return None


def _search_player_in_team_roster_espn(
    base_url: str, headers: Dict, team_id: str, player_name: str, team_abbr: str = None
) -> Optional[Dict[str, Any]]:
    """Search for player in team roster (ESPN)"""
    try:
        url = f"{base_url}/teams/{team_id}/roster"
        logger.debug(f"Fetching ESPN roster from {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        player_name_lower = player_name.lower()
        name_parts = player_name_lower.split()
        first_name = name_parts[0] if name_parts else ''
        last_name = name_parts[-1] if len(name_parts) > 1 else ''
        
        total_players = 0
        for athlete_group in data.get('athletes', []):
            items = athlete_group.get('items', [])
            total_players += len(items)
            for athlete in items:
                full_name = athlete.get('fullName', '').lower()
                
                # Flexible name matching
                if (player_name_lower in full_name or 
                    (first_name and first_name in full_name and last_name and last_name in full_name)):
                    logger.info(f"Found player match: {athlete.get('fullName')} (searching for: {player_name})")
                    return {
                        'name': athlete.get('fullName', player_name),
                        'team': team_abbr.upper() if team_abbr else '',
                        'position': athlete.get('position', {}).get('abbreviation', '') if isinstance(athlete.get('position'), dict) else '',
                        'note': 'Player found in roster (ESPN API does not provide individual game stats)'
                    }
        
        logger.debug(f"Player {player_name} not found in roster of {total_players} players")
        # Log some sample names for debugging
        if total_players > 0:
            sample_names = []
            for athlete_group in data.get('athletes', [])[:2]:
                for athlete in athlete_group.get('items', [])[:3]:
                    sample_names.append(athlete.get('fullName', 'N/A'))
            logger.debug(f"Sample player names from roster: {sample_names[:5]}")
        
        return None
    except Exception as e:
        logger.warning(f"Error searching ESPN roster: {e}", exc_info=True)
        return None
