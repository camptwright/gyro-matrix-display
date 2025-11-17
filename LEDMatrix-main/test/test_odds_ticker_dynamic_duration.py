#!/usr/bin/env python3
"""
Test script for debugging OddsTickerManager dynamic duration calculation
"""

import sys
import os
import time
import logging

# Add the parent directory to the Python path so we can import from src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.display_manager import DisplayManager
from src.config_manager import ConfigManager
from src.odds_ticker_manager import OddsTickerManager

# Configure logging to show debug information
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d - %(levelname)s:%(name)s:%(message)s',
    datefmt='%H:%M:%S'
)

def test_dynamic_duration():
    """Test the dynamic duration calculation for odds ticker."""
    print("Testing OddsTickerManager Dynamic Duration...")
    
    try:
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Initialize display manager
        display_manager = DisplayManager(config)
        
        # Initialize odds ticker
        odds_ticker = OddsTickerManager(config, display_manager)
        
        print(f"Odds ticker enabled: {odds_ticker.is_enabled}")
        print(f"Dynamic duration enabled: {odds_ticker.dynamic_duration_enabled}")
        print(f"Min duration: {odds_ticker.min_duration}s")
        print(f"Max duration: {odds_ticker.max_duration}s")
        print(f"Duration buffer: {odds_ticker.duration_buffer}")
        print(f"Scroll speed: {odds_ticker.scroll_speed}")
        print(f"Scroll delay: {odds_ticker.scroll_delay}")
        print(f"Display width: {display_manager.matrix.width}")
        
        if not odds_ticker.is_enabled:
            print("Odds ticker is disabled in config. Enabling for test...")
            odds_ticker.is_enabled = True
        
        # Temporarily disable favorite teams filter for testing
        print("Temporarily disabling favorite teams filter to test display...")
        original_show_favorite = odds_ticker.show_favorite_teams_only
        odds_ticker.show_favorite_teams_only = False
        
        # Update odds ticker data
        print("\nUpdating odds ticker data...")
        odds_ticker.update()
        
        print(f"Found {len(odds_ticker.games_data)} games")
        
        if odds_ticker.games_data:
            print("\nSample game data:")
            for i, game in enumerate(odds_ticker.games_data[:3]):  # Show first 3 games
                print(f"  Game {i+1}: {game.get('away_team', 'Unknown')} @ {game.get('home_team', 'Unknown')}")
                print(f"    Time: {game.get('start_time', 'Unknown')}")
                print(f"    League: {game.get('league', 'Unknown')}")
                print(f"    Sport: {game.get('sport', 'Unknown')}")
                if game.get('odds'):
                    print(f"    Has odds: Yes")
                else:
                    print(f"    Has odds: No")
                print(f"    Available keys: {list(game.keys())}")
                print()
            
            # Check dynamic duration calculation
            print("\nDynamic Duration Analysis:")
            print(f"Total scroll width: {odds_ticker.total_scroll_width}px")
            print(f"Calculated dynamic duration: {odds_ticker.dynamic_duration}s")
            
            # Calculate expected duration manually
            display_width = display_manager.matrix.width
            total_scroll_distance = display_width + odds_ticker.total_scroll_width
            frames_needed = total_scroll_distance / odds_ticker.scroll_speed
            total_time = frames_needed * odds_ticker.scroll_delay
            buffer_time = total_time * odds_ticker.duration_buffer
            calculated_duration = int(total_time + buffer_time)
            
            print(f"\nManual calculation:")
            print(f"  Display width: {display_width}px")
            print(f"  Content width: {odds_ticker.total_scroll_width}px")
            print(f"  Total scroll distance: {total_scroll_distance}px")
            print(f"  Frames needed: {frames_needed:.1f}")
            print(f"  Base time: {total_time:.2f}s")
            print(f"  Buffer time: {buffer_time:.2f}s ({odds_ticker.duration_buffer*100}%)")
            print(f"  Calculated duration: {calculated_duration}s")
            
            # Test display for a few iterations
            print(f"\nTesting display for 10 iterations...")
            for i in range(10):
                print(f"  Display iteration {i+1} starting...")
                odds_ticker.display()
                print(f"  Display iteration {i+1} complete - scroll position: {odds_ticker.scroll_position}")
                time.sleep(1)
        
        else:
            print("No games found even with favorite teams filter disabled.")
            
        # Restore original setting
        odds_ticker.show_favorite_teams_only = original_show_favorite
        
        # Cleanup
        display_manager.cleanup()
        print("\nTest completed successfully!")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dynamic_duration()
