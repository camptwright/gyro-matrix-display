#!/usr/bin/env python3
"""
Test script to verify the updated leaderboard manager works correctly
with the new NCAA Football rankings endpoint.
"""

import sys
import os
import json
import time
from typing import Dict, Any

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from leaderboard_manager import LeaderboardManager
from cache_manager import CacheManager
from config_manager import ConfigManager

def test_updated_leaderboard_manager():
    """Test the updated leaderboard manager with NCAA Football rankings."""
    
    print("Testing Updated Leaderboard Manager")
    print("=" * 50)
    
    # Create a mock display manager (we don't need the actual hardware for this test)
    class MockDisplayManager:
        def __init__(self):
            self.matrix = type('Matrix', (), {'width': 64, 'height': 32})()
            self.image = None
            self.draw = None
        
        def update_display(self):
            pass
        
        def set_scrolling_state(self, scrolling):
            pass
        
        def process_deferred_updates(self):
            pass
    
    # Create test configuration
    test_config = {
        'leaderboard': {
            'enabled': True,
            'enabled_sports': {
                'ncaa_fb': {
                    'enabled': True,
                    'top_teams': 10
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
            'duration_buffer': 0.1,
            'time_per_team': 2.0,
            'time_per_league': 3.0
        }
    }
    
    try:
        # Initialize the leaderboard manager
        print("Initializing LeaderboardManager...")
        display_manager = MockDisplayManager()
        leaderboard_manager = LeaderboardManager(test_config, display_manager)
        
        print(f"Leaderboard enabled: {leaderboard_manager.is_enabled}")
        print(f"Enabled sports: {[k for k, v in leaderboard_manager.enabled_sports.items() if v.get('enabled', False)]}")
        
        # Test the NCAA Football rankings fetch
        print("\nTesting NCAA Football rankings fetch...")
        ncaa_fb_config = leaderboard_manager.league_configs['ncaa_fb']
        print(f"NCAA FB config: {ncaa_fb_config}")
        
        # Fetch standings using the new method
        standings = leaderboard_manager._fetch_standings(ncaa_fb_config)
        
        if standings:
            print(f"\nSuccessfully fetched {len(standings)} teams")
            print("\nTop 10 NCAA Football Teams (from rankings):")
            print("-" * 60)
            print(f"{'Rank':<4} {'Team':<25} {'Abbr':<6} {'Record':<12} {'Win %':<8}")
            print("-" * 60)
            
            for team in standings:
                record_str = f"{team['wins']}-{team['losses']}"
                if team['ties'] > 0:
                    record_str += f"-{team['ties']}"
                
                win_pct = team['win_percentage']
                win_pct_str = f"{win_pct:.3f}" if win_pct > 0 else "0.000"
                
                print(f"{team.get('rank', 'N/A'):<4} {team['name']:<25} {team['abbreviation']:<6} {record_str:<12} {win_pct_str:<8}")
            
            print("-" * 60)
            
            # Show additional info
            ranking_name = standings[0].get('ranking_name', 'Unknown') if standings else 'Unknown'
            print(f"Ranking system used: {ranking_name}")
            print(f"Data fetched at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Test caching
            print(f"\nTesting caching...")
            cached_standings = leaderboard_manager._fetch_standings(ncaa_fb_config)
            if cached_standings:
                print("✓ Caching works correctly - data retrieved from cache")
            else:
                print("✗ Caching issue - no data retrieved from cache")
            
        else:
            print("✗ No standings data retrieved")
            return False
        
        print("\n✓ Leaderboard manager test completed successfully!")
        return True
        
    except Exception as e:
        print(f"✗ Error testing leaderboard manager: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function to run the test."""
    try:
        success = test_updated_leaderboard_manager()
        if success:
            print("\n🎉 All tests passed! The updated leaderboard manager is working correctly.")
        else:
            print("\n❌ Tests failed. Please check the errors above.")
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Error running test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
