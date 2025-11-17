#!/usr/bin/env python3
"""
Test script to verify the standings fetching logic works correctly.
This tests the core functionality without requiring the full LED matrix setup.
"""

import requests
import json
import time
from typing import Dict, Any, List

def fetch_standings_data(league_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fetch standings data from ESPN API using the standings endpoint."""
    league_key = league_config['league']
    
    try:
        print(f"Fetching fresh standings data for {league_key}")
        
        # Build the standings URL with query parameters
        standings_url = league_config['standings_url']
        params = {
            'season': league_config.get('season', 2024),
            'level': league_config.get('level', 1),
            'sort': league_config.get('sort', 'winpercent:desc,gamesbehind:asc')
        }
        
        print(f"Fetching standings from: {standings_url} with params: {params}")
        
        response = requests.get(standings_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        standings = []
        
        # Parse the standings data structure
        # Check if we have direct standings data or children (divisions/conferences)
        if 'standings' in data and 'entries' in data['standings']:
            # Direct standings data (e.g., NFL overall standings)
            standings_data = data['standings']['entries']
            print(f"Processing direct standings data with {len(standings_data)} teams")
            
            for entry in standings_data:
                team_data = entry.get('team', {})
                stats = entry.get('stats', [])
                
                team_name = team_data.get('displayName', 'Unknown')
                team_abbr = team_data.get('abbreviation', 'Unknown')
                
                # Extract record from stats
                wins = 0
                losses = 0
                ties = 0
                win_percentage = 0.0
                
                for stat in stats:
                    stat_type = stat.get('type', '')
                    stat_value = stat.get('value', 0)
                    
                    if stat_type == 'wins':
                        wins = int(stat_value)
                    elif stat_type == 'losses':
                        losses = int(stat_value)
                    elif stat_type == 'ties':
                        ties = int(stat_value)
                    elif stat_type == 'winpercent':
                        win_percentage = float(stat_value)
                
                # Create record summary
                if ties > 0:
                    record_summary = f"{wins}-{losses}-{ties}"
                else:
                    record_summary = f"{wins}-{losses}"
                
                standings.append({
                    'name': team_name,
                    'abbreviation': team_abbr,
                    'wins': wins,
                    'losses': losses,
                    'ties': ties,
                    'win_percentage': win_percentage,
                    'record_summary': record_summary,
                    'division': 'Overall'
                })
        
        elif 'children' in data:
            # Children structure (divisions/conferences)
            children = data.get('children', [])
            print(f"Processing {len(children)} divisions/conferences")
            
            for child in children:
                child_name = child.get('displayName', 'Unknown')
                print(f"Processing {child_name}")
                
                standings_data = child.get('standings', {}).get('entries', [])
                
                for entry in standings_data:
                    team_data = entry.get('team', {})
                    stats = entry.get('stats', [])
                    
                    team_name = team_data.get('displayName', 'Unknown')
                    team_abbr = team_data.get('abbreviation', 'Unknown')
                    
                    # Extract record from stats
                    wins = 0
                    losses = 0
                    ties = 0
                    win_percentage = 0.0
                    
                    for stat in stats:
                        stat_type = stat.get('type', '')
                        stat_value = stat.get('value', 0)
                        
                        if stat_type == 'wins':
                            wins = int(stat_value)
                        elif stat_type == 'losses':
                            losses = int(stat_value)
                        elif stat_type == 'ties':
                            ties = int(stat_value)
                        elif stat_type == 'winpercent':
                            win_percentage = float(stat_value)
                    
                    # Create record summary
                    if ties > 0:
                        record_summary = f"{wins}-{losses}-{ties}"
                    else:
                        record_summary = f"{wins}-{losses}"
                    
                    standings.append({
                        'name': team_name,
                        'abbreviation': team_abbr,
                        'wins': wins,
                        'losses': losses,
                        'ties': ties,
                        'win_percentage': win_percentage,
                        'record_summary': record_summary,
                        'division': child_name
                    })
        else:
            print(f"No standings or children data found for {league_key}")
            return []
        
        # Sort by win percentage (descending) and limit to top teams
        standings.sort(key=lambda x: x['win_percentage'], reverse=True)
        top_teams = standings[:league_config['top_teams']]
        
        print(f"Fetched and processed {len(top_teams)} teams for {league_key} standings")
        return top_teams
        
    except Exception as e:
        print(f"Error fetching standings for {league_key}: {e}")
        return []

def test_standings_fetch():
    """Test the standings fetching functionality."""
    print("Testing Standings Fetching Logic")
    print("=" * 50)
    
    # Test configurations
    test_configs = [
        {
            'name': 'NFL',
            'config': {
                'league': 'nfl',
                'standings_url': 'https://site.api.espn.com/apis/v2/sports/football/nfl/standings',
                'top_teams': 5,
                'season': 2025,
                'level': 1,
                'sort': 'winpercent:desc,gamesbehind:asc'
            }
        },
        {
            'name': 'MLB',
            'config': {
                'league': 'mlb',
                'standings_url': 'https://site.api.espn.com/apis/v2/sports/baseball/mlb/standings',
                'top_teams': 5,
                'season': 2025,
                'level': 1,
                'sort': 'winpercent:desc,gamesbehind:asc'
            }
        },
        {
            'name': 'NHL',
            'config': {
                'league': 'nhl',
                'standings_url': 'https://site.api.espn.com/apis/v2/sports/hockey/nhl/standings',
                'top_teams': 5,
                'season': 2025,
                'level': 1,
                'sort': 'winpercent:desc,gamesbehind:asc'
            }
        },
        {
            'name': 'NCAA Baseball',
            'config': {
                'league': 'college-baseball',
                'standings_url': 'https://site.api.espn.com/apis/v2/sports/baseball/college-baseball/standings',
                'top_teams': 5,
                'season': 2025,
                'level': 1,
                'sort': 'winpercent:desc,gamesbehind:asc'
            }
        }
    ]
    
    results = []
    
    for test_config in test_configs:
        print(f"\n--- Testing {test_config['name']} ---")
        
        standings = fetch_standings_data(test_config['config'])
        
        if standings:
            print(f"✓ Successfully fetched {len(standings)} teams")
            print(f"Top {len(standings)} teams:")
            for i, team in enumerate(standings):
                print(f"  {i+1}. {team['name']} ({team['abbreviation']}): {team['record_summary']} ({team['win_percentage']:.3f})")
            results.append(True)
        else:
            print(f"✗ Failed to fetch standings for {test_config['name']}")
            results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All standings fetch tests passed!")
        return True
    else:
        print("✗ Some tests failed!")
        return False

if __name__ == "__main__":
    success = test_standings_fetch()
    exit(0 if success else 1)
