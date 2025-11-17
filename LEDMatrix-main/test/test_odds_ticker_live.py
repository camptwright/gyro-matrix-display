#!/usr/bin/env python3
"""
Test script to verify odds ticker live game functionality.
"""

import sys
import os
import json
import requests
from datetime import datetime, timezone

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from odds_ticker_manager import OddsTickerManager
from display_manager import DisplayManager
from cache_manager import CacheManager
from config_manager import ConfigManager

def test_live_game_detection():
    """Test that the odds ticker can detect live games."""
    print("Testing live game detection in odds ticker...")
    
    # Create a minimal config for testing
    config = {
        'odds_ticker': {
            'enabled': True,
            'enabled_leagues': ['mlb', 'nfl', 'nba'],
            'show_favorite_teams_only': False,
            'max_games_per_league': 3,
            'show_odds_only': False,
            'update_interval': 300,
            'scroll_speed': 2,
            'scroll_delay': 0.05,
            'display_duration': 30,
            'future_fetch_days': 1,
            'loop': True,
            'show_channel_logos': True,
            'broadcast_logo_height_ratio': 0.8,
            'broadcast_logo_max_width_ratio': 0.8,
            'request_timeout': 30,
            'dynamic_duration': True,
            'min_duration': 30,
            'max_duration': 300,
            'duration_buffer': 0.1
        },
        'timezone': 'UTC',
        'mlb': {
            'enabled': True,
            'favorite_teams': []
        },
        'nfl_scoreboard': {
            'enabled': True,
            'favorite_teams': []
        },
        'nba_scoreboard': {
            'enabled': True,
            'favorite_teams': []
        }
    }
    
    # Create mock display manager
    class MockDisplayManager:
        def __init__(self):
            self.matrix = MockMatrix()
            self.image = None
            self.draw = None
            
        def update_display(self):
            pass
            
        def is_currently_scrolling(self):
            return False
            
        def set_scrolling_state(self, state):
            pass
            
        def defer_update(self, func, priority=0):
            pass
            
        def process_deferred_updates(self):
            pass
    
    class MockMatrix:
        def __init__(self):
            self.width = 128
            self.height = 32
    
    # Create managers
    display_manager = MockDisplayManager()
    cache_manager = CacheManager()
    config_manager = ConfigManager()
    
    # Create odds ticker manager
    odds_ticker = OddsTickerManager(config, display_manager)
    
    # Test fetching games
    print("Fetching games...")
    games = odds_ticker._fetch_upcoming_games()
    
    print(f"Found {len(games)} total games")
    
    # Check for live games
    live_games = [game for game in games if game.get('status_state') == 'in']
    scheduled_games = [game for game in games if game.get('status_state') != 'in']
    
    print(f"Live games: {len(live_games)}")
    print(f"Scheduled games: {len(scheduled_games)}")
    
    # Display live games
    for i, game in enumerate(live_games[:3]):  # Show first 3 live games
        print(f"\nLive Game {i+1}:")
        print(f"  Teams: {game['away_team']} @ {game['home_team']}")
        print(f"  Status: {game.get('status')} (State: {game.get('status_state')})")
        
        live_info = game.get('live_info')
        if live_info:
            print(f"  Score: {live_info.get('away_score', 0)} - {live_info.get('home_score', 0)}")
            print(f"  Period: {live_info.get('period', 'N/A')}")
            print(f"  Clock: {live_info.get('clock', 'N/A')}")
            print(f"  Detail: {live_info.get('detail', 'N/A')}")
            
            # Sport-specific info
            sport = None
            for league_key, league_config in odds_ticker.league_configs.items():
                if league_config.get('logo_dir') == game.get('logo_dir'):
                    sport = league_config.get('sport')
                    break
            
            if sport == 'baseball':
                print(f"  Inning: {live_info.get('inning_half', 'N/A')} {live_info.get('inning', 'N/A')}")
                print(f"  Count: {live_info.get('balls', 0)}-{live_info.get('strikes', 0)}")
                print(f"  Outs: {live_info.get('outs', 0)}")
                print(f"  Bases: {live_info.get('bases_occupied', [])}")
            elif sport == 'football':
                print(f"  Quarter: {live_info.get('quarter', 'N/A')}")
                print(f"  Down: {live_info.get('down', 'N/A')} & {live_info.get('distance', 'N/A')}")
                print(f"  Yard Line: {live_info.get('yard_line', 'N/A')}")
                print(f"  Possession: {live_info.get('possession', 'N/A')}")
            elif sport == 'basketball':
                print(f"  Quarter: {live_info.get('quarter', 'N/A')}")
                print(f"  Time: {live_info.get('time_remaining', 'N/A')}")
                print(f"  Possession: {live_info.get('possession', 'N/A')}")
            elif sport == 'hockey':
                print(f"  Period: {live_info.get('period', 'N/A')}")
                print(f"  Time: {live_info.get('time_remaining', 'N/A')}")
                print(f"  Power Play: {live_info.get('power_play', False)}")
        else:
            print("  No live info available")
    
    # Test formatting
    print("\nTesting text formatting...")
    for game in live_games[:2]:  # Test first 2 live games
        formatted_text = odds_ticker._format_odds_text(game)
        print(f"Formatted text: {formatted_text}")
    
    # Test image creation
    print("\nTesting image creation...")
    if games:
        try:
            odds_ticker.games_data = games[:3]  # Use first 3 games
            odds_ticker._create_ticker_image()
            if odds_ticker.ticker_image:
                print(f"Successfully created ticker image: {odds_ticker.ticker_image.size}")
            else:
                print("Failed to create ticker image")
        except Exception as e:
            print(f"Error creating ticker image: {e}")
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_live_game_detection()
