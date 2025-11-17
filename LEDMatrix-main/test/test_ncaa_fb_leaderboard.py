#!/usr/bin/env python3
"""
Test script to demonstrate NCAA Football leaderboard data gathering.
Shows the top 10 NCAA Football teams ranked by win percentage.
This script examines the actual ESPN API response structure to understand
how team records are provided in the teams endpoint.
"""

import sys
import os
import json
import time
import requests
from typing import Dict, Any, List, Optional

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cache_manager import CacheManager
from config_manager import ConfigManager

class NCAAFBLeaderboardTester:
    """Test class to demonstrate NCAA Football leaderboard data gathering."""
    
    def __init__(self):
        self.cache_manager = CacheManager()
        self.config_manager = ConfigManager()
        self.request_timeout = 30
        
        # NCAA Football configuration (matching the leaderboard manager)
        self.ncaa_fb_config = {
            'sport': 'football',
            'league': 'college-football',
            'teams_url': 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams',
            'top_teams': 10  # Show top 10 for this test
        }
    
    def examine_api_structure(self) -> None:
        """Examine the ESPN API response structure to understand available data."""
        print("Examining ESPN API response structure...")
        print("=" * 60)
        
        try:
            response = requests.get(self.ncaa_fb_config['teams_url'], timeout=self.request_timeout)
            response.raise_for_status()
            data = response.json()
            
            print(f"API Response Status: {response.status_code}")
            print(f"Response Keys: {list(data.keys())}")
            
            sports = data.get('sports', [])
            if sports:
                print(f"Sports found: {len(sports)}")
                sport = sports[0]
                print(f"Sport keys: {list(sport.keys())}")
                print(f"Sport name: {sport.get('name', 'Unknown')}")
                
                leagues = sport.get('leagues', [])
                if leagues:
                    print(f"Leagues found: {len(leagues)}")
                    league = leagues[0]
                    print(f"League keys: {list(league.keys())}")
                    print(f"League name: {league.get('name', 'Unknown')}")
                    
                    teams = league.get('teams', [])
                    if teams:
                        print(f"Teams found: {len(teams)}")
                        
                        # Examine first team structure
                        first_team = teams[0]
                        print(f"\nFirst team structure:")
                        print(f"Team keys: {list(first_team.keys())}")
                        
                        team_info = first_team.get('team', {})
                        print(f"Team info keys: {list(team_info.keys())}")
                        print(f"Team name: {team_info.get('name', 'Unknown')}")
                        print(f"Team abbreviation: {team_info.get('abbreviation', 'Unknown')}")
                        
                        # Check for record data
                        record = team_info.get('record', {})
                        print(f"Record keys: {list(record.keys())}")
                        
                        if record:
                            items = record.get('items', [])
                            print(f"Record items: {len(items)}")
                            if items:
                                print(f"First record item: {items[0]}")
                        
                        # Check for stats data
                        stats = team_info.get('stats', [])
                        print(f"Stats found: {len(stats)}")
                        if stats:
                            print("Available stats:")
                            for stat in stats[:5]:  # Show first 5 stats
                                print(f"  {stat.get('name', 'Unknown')}: {stat.get('value', 'Unknown')}")
                        
                        # Check for standings data
                        standings = first_team.get('standings', {})
                        print(f"Standings keys: {list(standings.keys())}")
                        
                        print(f"\nSample team data structure:")
                        print(json.dumps(first_team, indent=2)[:1000] + "...")
                        
        except Exception as e:
            print(f"Error examining API structure: {e}")
    
    def fetch_ncaa_fb_rankings_correct(self) -> List[Dict[str, Any]]:
        """Fetch NCAA Football rankings from ESPN API using the correct approach."""
        cache_key = "leaderboard_college-football-rankings"
        
        # Try to get cached data first
        cached_data = self.cache_manager.get_cached_data_with_strategy(cache_key, 'leaderboard')
        if cached_data:
            print("Using cached rankings data for NCAA Football")
            return cached_data.get('rankings', [])
        
        try:
            print("Fetching fresh rankings data for NCAA Football")
            rankings_url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/rankings"
            print(f"Rankings URL: {rankings_url}")
            
            # Get rankings data
            response = requests.get(rankings_url, timeout=self.request_timeout)
            response.raise_for_status()
            data = response.json()
            
            print(f"Available rankings: {[rank['name'] for rank in data.get('availableRankings', [])]}")
            print(f"Latest season: {data.get('latestSeason', {})}")
            print(f"Latest week: {data.get('latestWeek', {})}")
            
            rankings_data = data.get('rankings', [])
            if not rankings_data:
                print("No rankings data found")
                return []
            
            # Use the first ranking (usually AP Top 25)
            first_ranking = rankings_data[0]
            ranking_name = first_ranking.get('name', 'Unknown')
            ranking_type = first_ranking.get('type', 'Unknown')
            teams = first_ranking.get('ranks', [])
            
            print(f"Using ranking: {ranking_name} ({ranking_type})")
            print(f"Found {len(teams)} teams in ranking")
            
            standings = []
            
            # Process each team in the ranking
            for i, team_data in enumerate(teams):
                team_info = team_data.get('team', {})
                team_name = team_info.get('name', 'Unknown')
                team_abbr = team_info.get('abbreviation', 'Unknown')
                current_rank = team_data.get('current', 0)
                record_summary = team_data.get('recordSummary', '0-0')
                
                print(f"  {current_rank}. {team_name} ({team_abbr}): {record_summary}")
                
                # Parse the record string (e.g., "12-1", "8-4", "10-2-1")
                wins = 0
                losses = 0
                ties = 0
                win_percentage = 0
                
                try:
                    parts = record_summary.split('-')
                    if len(parts) >= 2:
                        wins = int(parts[0])
                        losses = int(parts[1])
                        if len(parts) == 3:
                            ties = int(parts[2])
                        
                        # Calculate win percentage
                        total_games = wins + losses + ties
                        win_percentage = wins / total_games if total_games > 0 else 0
                except (ValueError, IndexError):
                    print(f"    Could not parse record: {record_summary}")
                    continue
                
                standings.append({
                    'name': team_name,
                    'abbreviation': team_abbr,
                    'rank': current_rank,
                    'wins': wins,
                    'losses': losses,
                    'ties': ties,
                    'win_percentage': win_percentage,
                    'record_summary': record_summary,
                    'ranking_name': ranking_name
                })
            
            # Limit to top teams (they're already ranked)
            top_teams = standings[:self.ncaa_fb_config['top_teams']]
            
            # Cache the results
            cache_data = {
                'rankings': top_teams,
                'timestamp': time.time(),
                'league': 'college-football',
                'ranking_name': ranking_name
            }
            self.cache_manager.save_cache(cache_key, cache_data)
            
            print(f"Fetched and cached {len(top_teams)} teams for college-football")
            return top_teams
            
        except Exception as e:
            print(f"Error fetching rankings for college-football: {e}")
            return []
    
    def display_standings(self, standings: List[Dict[str, Any]]) -> None:
        """Display the standings in a formatted way."""
        if not standings:
            print("No standings data available")
            return
        
        ranking_name = standings[0].get('ranking_name', 'Unknown Ranking') if standings else 'Unknown'
        
        print("\n" + "="*80)
        print(f"NCAA FOOTBALL LEADERBOARD - TOP 10 TEAMS ({ranking_name})")
        print("="*80)
        print(f"{'Rank':<4} {'Team':<25} {'Abbr':<6} {'Record':<12} {'Win %':<8}")
        print("-"*80)
        
        for team in standings:
            record_str = f"{team['wins']}-{team['losses']}"
            if team['ties'] > 0:
                record_str += f"-{team['ties']}"
            
            win_pct = team['win_percentage']
            win_pct_str = f"{win_pct:.3f}" if win_pct > 0 else "0.000"
            
            print(f"{team['rank']:<4} {team['name']:<25} {team['abbreviation']:<6} {record_str:<12} {win_pct_str:<8}")
        
        print("="*80)
        print(f"Total teams processed: {len(standings)}")
        print(f"Data fetched at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def run_test(self) -> None:
        """Run the complete test."""
        print("NCAA Football Leaderboard Data Gathering Test")
        print("=" * 50)
        print("This test demonstrates how the leaderboard manager should gather data:")
        print("1. Fetches rankings from ESPN API rankings endpoint")
        print("2. Uses poll-based rankings (AP, Coaches, etc.) not win percentage")
        print("3. Gets team records from the ranking data")
        print("4. Displays top 10 teams with their poll rankings")
        print()
        
        print("\n" + "="*60)
        print("FETCHING RANKINGS DATA")
        print("="*60)
        
        # Fetch the rankings using the correct approach
        standings = self.fetch_ncaa_fb_rankings_correct()
        
        # Display the results
        self.display_standings(standings)
        
        # Show some additional info
        if standings:
            ranking_name = standings[0].get('ranking_name', 'Unknown')
            print(f"\nAdditional Information:")
            print(f"- API Endpoint: https://site.api.espn.com/apis/site/v2/sports/football/college-football/rankings")
            print(f"- Single API call fetches poll-based rankings")
            print(f"- Rankings are based on polls, not just win percentage")
            print(f"- Data is cached to avoid excessive API calls")
            print(f"- Using ranking: {ranking_name}")
            
            # Show the best team
            best_team = standings[0]
            print(f"\nCurrent #1 Team: {best_team['name']} ({best_team['abbreviation']})")
            print(f"Record: {best_team['wins']}-{best_team['losses']}{f'-{best_team['ties']}' if best_team['ties'] > 0 else ''}")
            print(f"Win Percentage: {best_team['win_percentage']:.3f}")
            print(f"Poll Ranking: #{best_team['rank']}")

def main():
    """Main function to run the test."""
    try:
        tester = NCAAFBLeaderboardTester()
        tester.run_test()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Error running test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
