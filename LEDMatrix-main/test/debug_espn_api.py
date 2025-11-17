#!/usr/bin/env python3
"""
Debug script to examine ESPN API response structure
"""

import requests
import json

def debug_espn_api():
    """Debug ESPN API responses."""
    
    # Test different endpoints
    test_endpoints = [
        {
            'name': 'NFL Standings',
            'url': 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/standings'
        },
        {
            'name': 'NFL Teams',
            'url': 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams'
        },
        {
            'name': 'NFL Scoreboard',
            'url': 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'
        },
        {
            'name': 'NBA Teams',
            'url': 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams'
        },
        {
            'name': 'MLB Teams',
            'url': 'https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/teams'
        }
    ]
    
    for endpoint in test_endpoints:
        print(f"\n{'='*50}")
        print(f"Testing {endpoint['name']}")
        print(f"URL: {endpoint['url']}")
        print('='*50)
        
        try:
            response = requests.get(endpoint['url'], timeout=30)
            response.raise_for_status()
            data = response.json()
            
            print(f"Response status: {response.status_code}")
            print(f"Response keys: {list(data.keys())}")
            
            # Print a sample of the response
            if 'sports' in data:
                sports = data['sports']
                print(f"Sports found: {len(sports)}")
                if sports:
                    leagues = sports[0].get('leagues', [])
                    print(f"Leagues found: {len(leagues)}")
                    if leagues:
                        teams = leagues[0].get('teams', [])
                        print(f"Teams found: {len(teams)}")
                        if teams:
                            print("Sample team data:")
                            sample_team = teams[0]
                            print(f"  Team: {sample_team.get('team', {}).get('name', 'Unknown')}")
                            print(f"  Abbreviation: {sample_team.get('team', {}).get('abbreviation', 'Unknown')}")
                            stats = sample_team.get('stats', [])
                            print(f"  Stats found: {len(stats)}")
                            for stat in stats[:3]:  # Show first 3 stats
                                print(f"    {stat.get('name', 'Unknown')}: {stat.get('value', 'Unknown')}")
            
            elif 'groups' in data:
                groups = data['groups']
                print(f"Groups found: {len(groups)}")
                if groups:
                    print("Sample group data:")
                    print(json.dumps(groups[0], indent=2)[:500] + "...")
            
            else:
                print("Sample response data:")
                print(json.dumps(data, indent=2)[:500] + "...")
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    debug_espn_api()
