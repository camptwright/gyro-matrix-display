#!/usr/bin/env python3
"""
Test script to demonstrate the graceful update system for scrolling displays.
This script shows how updates are deferred during scrolling periods to prevent lag.
"""

import time
import logging
import sys
import os

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging first
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d - %(levelname)s:%(name)s:%(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)

# Mock rgbmatrix module for testing on non-Raspberry Pi systems
try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
except ImportError:
    logger.info("rgbmatrix module not available, using mock for testing")
    
    class MockRGBMatrixOptions:
        def __init__(self):
            self.rows = 32
            self.cols = 64
            self.chain_length = 2
            self.parallel = 1
            self.hardware_mapping = 'adafruit-hat-pwm'
            self.brightness = 90
            self.pwm_bits = 10
            self.pwm_lsb_nanoseconds = 150
            self.led_rgb_sequence = 'RGB'
            self.pixel_mapper_config = ''
            self.row_address_type = 0
            self.multiplexing = 0
            self.disable_hardware_pulsing = False
            self.show_refresh_rate = False
            self.limit_refresh_rate_hz = 90
            self.gpio_slowdown = 2
    
    class MockRGBMatrix:
        def __init__(self, options=None):
            self.width = 128  # 64 * 2 chain length
            self.height = 32
            
        def CreateFrameCanvas(self):
            return MockCanvas()
            
        def SwapOnVSync(self, canvas, dont_wait=False):
            pass
            
        def Clear(self):
            pass
    
    class MockCanvas:
        def __init__(self):
            self.width = 128
            self.height = 32
            
        def SetImage(self, image):
            pass
            
        def Clear(self):
            pass
    
    RGBMatrix = MockRGBMatrix
    RGBMatrixOptions = MockRGBMatrixOptions

from src.display_manager import DisplayManager
from src.config_manager import ConfigManager

def simulate_scrolling_display(display_manager, duration=10):
    """Simulate a scrolling display for testing."""
    logger.info(f"Starting scrolling simulation for {duration} seconds")
    
    start_time = time.time()
    while time.time() - start_time < duration:
        # Signal that we're scrolling
        display_manager.set_scrolling_state(True)
        
        # Simulate some scrolling work
        time.sleep(0.1)
        
        # Every 2 seconds, try to defer an update
        if int(time.time() - start_time) % 2 == 0:
            logger.info("Attempting to defer an update during scrolling")
            display_manager.defer_update(
                lambda: logger.info("This update was deferred and executed later!"),
                priority=1
            )
    
    # Signal that scrolling has stopped
    display_manager.set_scrolling_state(False)
    logger.info("Scrolling simulation completed")

def test_graceful_updates():
    """Test the graceful update system."""
    logger.info("Testing graceful update system")
    
    # Load config
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    # Initialize display manager
    display_manager = DisplayManager(config, force_fallback=True)
    
    try:
        # Test 1: Defer updates during scrolling
        logger.info("=== Test 1: Defer updates during scrolling ===")
        
        # Add some deferred updates
        display_manager.defer_update(
            lambda: logger.info("Update 1: High priority update"),
            priority=1
        )
        display_manager.defer_update(
            lambda: logger.info("Update 2: Medium priority update"),
            priority=2
        )
        display_manager.defer_update(
            lambda: logger.info("Update 3: Low priority update"),
            priority=3
        )
        
        # Start scrolling simulation
        simulate_scrolling_display(display_manager, duration=5)
        
        # Check scrolling stats
        stats = display_manager.get_scrolling_stats()
        logger.info(f"Scrolling stats: {stats}")
        
        # Test 2: Process deferred updates when not scrolling
        logger.info("=== Test 2: Process deferred updates when not scrolling ===")
        
        # Process any remaining deferred updates
        display_manager.process_deferred_updates()
        
        # Test 3: Test inactivity threshold
        logger.info("=== Test 3: Test inactivity threshold ===")
        
        # Signal scrolling started
        display_manager.set_scrolling_state(True)
        logger.info(f"Is scrolling: {display_manager.is_currently_scrolling()}")
        
        # Wait longer than the inactivity threshold
        time.sleep(3)
        logger.info(f"Is scrolling after inactivity: {display_manager.is_currently_scrolling()}")
        
        # Test 4: Test priority ordering
        logger.info("=== Test 4: Test priority ordering ===")
        
        # Add updates in reverse priority order
        display_manager.defer_update(
            lambda: logger.info("Priority 3 update"),
            priority=3
        )
        display_manager.defer_update(
            lambda: logger.info("Priority 1 update"),
            priority=1
        )
        display_manager.defer_update(
            lambda: logger.info("Priority 2 update"),
            priority=2
        )
        
        # Process them (should execute in priority order: 1, 2, 3)
        display_manager.process_deferred_updates()
        
        logger.info("All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
    finally:
        # Cleanup
        display_manager.cleanup()

if __name__ == "__main__":
    test_graceful_updates()
