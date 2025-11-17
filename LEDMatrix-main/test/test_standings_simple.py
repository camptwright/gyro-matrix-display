#!/usr/bin/env python3
"""
Simple test script to verify the ESPN standings endpoints work correctly.
"""

import requests
import json

def test_nfl_standings():
    """Test NFL standings endpoint with corrected parsing."""
    print("\n=== Testing NFL Standings ===")
    
    url = "https://site.api.espn.com/apis/v2/sports/football/nfl/standings"
    params = {
        'season': 2025,
        'level': 1,
        'sort': 'winpercent:desc,gamesbehind:asc'
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        print(f"✓ Successfully fetched NFL standings")
        
        # Check for direct standings data
        if 'standings' in data and 'entries' in data['standings']:
            standings_data = data['standings']['entries']
            print(f"  Found {len(standings_data)} teams in direct standings")
            
            # Show top 5 teams
            print(f"  Top 5 teams:")
            for i, entry in enumerate(standings_data[:5]):
                team_data = entry.get('team', {})
                team_name = team_data.get('displayName', 'Unknown')
                team_abbr = team_data.get('abbreviation', 'Unknown')
                
                # Get record
                wins = 0
                losses = 0
                ties = 0
                win_percentage = 0.0
                
                for stat in entry.get('stats', []):
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
                
                record = f"{wins}-{losses}" if ties == 0 else f"{wins}-{losses}-{ties}"
                print(f"    {i+1}. {team_name} ({team_abbr}): {record} ({win_percentage:.3f})")
            
            return True
        else:
            print("  ✗ No direct standings data found")
            return False
        
    except Exception as e:
        print(f"✗ Error testing NFL standings: {e}")
        return False

def test_mlb_standings():
    """Test MLB standings endpoint with corrected parsing."""
    print("\n=== Testing MLB Standings ===")
    
    url = "https://site.api.espn.com/apis/v2/sports/baseball/mlb/standings"
    params = {
        'season': 2025,
        'level': 1,
        'sort': 'winpercent:desc,gamesbehind:asc'
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        print(f"✓ Successfully fetched MLB standings")
        
        # Check for direct standings data
        if 'standings' in data and 'entries' in data['standings']:
            standings_data = data['standings']['entries']
            print(f"  Found {len(standings_data)} teams in direct standings")
            
            # Show top 5 teams
            print(f"  Top 5 teams:")
            for i, entry in enumerate(standings_data[:5]):
                team_data = entry.get('team', {})
                team_name = team_data.get('displayName', 'Unknown')
                team_abbr = team_data.get('abbreviation', 'Unknown')
                
                # Get record
                wins = 0
                losses = 0
                ties = 0
                win_percentage = 0.0
                
                for stat in entry.get('stats', []):
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
                
                record = f"{wins}-{losses}" if ties == 0 else f"{wins}-{losses}-{ties}"
                print(f"    {i+1}. {team_name} ({team_abbr}): {record} ({win_percentage:.3f})")
            
            return True
        else:
            print("  ✗ No direct standings data found")
            return False
        
    except Exception as e:
        print(f"✗ Error testing MLB standings: {e}")
        return False

def test_nhl_standings():
    """Test NHL standings endpoint with corrected parsing."""
    print("\n=== Testing NHL Standings ===")
    
    url = "https://site.api.espn.com/apis/v2/sports/hockey/nhl/standings"
    params = {
        'season': 2025,
        'level': 1,
        'sort': 'winpercent:desc,gamesbehind:asc'
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        print(f"✓ Successfully fetched NHL standings")
        
        # Check for direct standings data
        if 'standings' in data and 'entries' in data['standings']:
            standings_data = data['standings']['entries']
            print(f"  Found {len(standings_data)} teams in direct standings")
            
            # Show top 5 teams
            print(f"  Top 5 teams:")
            for i, entry in enumerate(standings_data[:5]):
                team_data = entry.get('team', {})
                team_name = team_data.get('displayName', 'Unknown')
                team_abbr = team_data.get('abbreviation', 'Unknown')
                
                # Get record with NHL-specific parsing
                wins = 0
                losses = 0
                ties = 0
                win_percentage = 0.0
                games_played = 0
                
                # First pass: collect all stat values
                for stat in entry.get('stats', []):
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
                    # NHL specific stats
                    elif stat_type == 'overtimelosses':
                        ties = int(stat_value)  # NHL uses overtime losses as ties
                    elif stat_type == 'gamesplayed':
                        games_played = float(stat_value)
                
                # Second pass: calculate win percentage for NHL if not already set
                if win_percentage == 0.0 and games_played > 0:
                    win_percentage = wins / games_played
                
                record = f"{wins}-{losses}" if ties == 0 else f"{wins}-{losses}-{ties}"
                print(f"    {i+1}. {team_name} ({team_abbr}): {record} ({win_percentage:.3f})")
            
            return True
        else:
            print("  ✗ No direct standings data found")
            return False
        
    except Exception as e:
        print(f"✗ Error testing NHL standings: {e}")
        return False

def test_ncaa_baseball_standings():
    """Test NCAA Baseball standings endpoint with corrected parsing."""
    print("\n=== Testing NCAA Baseball Standings ===")
    
    url = "https://site.api.espn.com/apis/v2/sports/baseball/college-baseball/standings"
    params = {
        'season': 2025,
        'level': 1,
        'sort': 'winpercent:desc,gamesbehind:asc'
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        print(f"✓ Successfully fetched NCAA Baseball standings")
        
        # Check for direct standings data
        if 'standings' in data and 'entries' in data['standings']:
            standings_data = data['standings']['entries']
            print(f"  Found {len(standings_data)} teams in direct standings")
            
            # Show top 5 teams
            print(f"  Top 5 teams:")
            for i, entry in enumerate(standings_data[:5]):
                team_data = entry.get('team', {})
                team_name = team_data.get('displayName', 'Unknown')
                team_abbr = team_data.get('abbreviation', 'Unknown')
                
                # Get record
                wins = 0
                losses = 0
                ties = 0
                win_percentage = 0.0
                
                for stat in entry.get('stats', []):
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
                
                record = f"{wins}-{losses}" if ties == 0 else f"{wins}-{losses}-{ties}"
                print(f"    {i+1}. {team_name} ({team_abbr}): {record} ({win_percentage:.3f})")
            
            return True
        else:
            print("  ✗ No direct standings data found")
            return False
        
    except Exception as e:
        print(f"✗ Error testing NCAA Baseball standings: {e}")
        return False

def main():
    """Main function to run all tests."""
    print("ESPN Standings Endpoints Test (Corrected)")
    print("=" * 50)
    
    results = []
    
    # Test individual endpoints
    results.append(test_nfl_standings())
    results.append(test_mlb_standings())
    results.append(test_nhl_standings())
    results.append(test_ncaa_baseball_standings())
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed!")
        return True
    else:
        print("✗ Some tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
