#!/usr/bin/env python3
"""
Test script for the LeaderboardManager
"""

import sys
import os
import json
import logging

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from leaderboard_manager import LeaderboardManager
from display_manager import DisplayManager
from config_manager import ConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_leaderboard_manager():
    """Test the leaderboard manager functionality."""
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    # Enable leaderboard and some sports for testing
    config['leaderboard'] = {
        'enabled': True,
        'enabled_sports': {
            'nfl': {
                'enabled': True,
                'top_teams': 5
            },
            'nba': {
                'enabled': True,
                'top_teams': 5
            },
            'mlb': {
                'enabled': True,
                'top_teams': 5
            }
        },
        'update_interval': 3600,
        'scroll_speed': 2,
        'scroll_delay': 0.05,
        'display_duration': 60,
        'loop': True,
        'request_timeout': 30,
        'dynamic_duration': True,
        'min_duration': 30,
        'max_duration': 300,
        'duration_buffer': 0.1
    }
    
    # Initialize display manager (this will be a mock for testing)
    display_manager = DisplayManager(config)
    
    # Initialize leaderboard manager
    leaderboard_manager = LeaderboardManager(config, display_manager)
    
    print("Testing LeaderboardManager...")
    print(f"Enabled: {leaderboard_manager.is_enabled}")
    print(f"Enabled sports: {[k for k, v in leaderboard_manager.league_configs.items() if v['enabled']]}")
    
    # Test fetching standings
    print("\nFetching standings...")
    leaderboard_manager.update()
    
    print(f"Number of leagues with data: {len(leaderboard_manager.leaderboard_data)}")
    
    for league_data in leaderboard_manager.leaderboard_data:
        league = league_data['league']
        teams = league_data['teams']
        print(f"\n{league.upper()}:")
        for i, team in enumerate(teams[:5]):  # Show top 5
            record = f"{team['wins']}-{team['losses']}"
            if 'ties' in team:
                record += f"-{team['ties']}"
            print(f"  {i+1}. {team['abbreviation']} {record}")
    
    # Test image creation
    print("\nCreating leaderboard image...")
    if leaderboard_manager.leaderboard_data:
        leaderboard_manager._create_leaderboard_image()
        if leaderboard_manager.leaderboard_image:
            print(f"Image created successfully: {leaderboard_manager.leaderboard_image.size}")
            print(f"Dynamic duration: {leaderboard_manager.dynamic_duration:.1f}s")
        else:
            print("Failed to create image")
    else:
        print("No data available to create image")

if __name__ == "__main__":
    test_leaderboard_manager()
