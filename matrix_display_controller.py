#!/usr/bin/env python3
"""
Main Matrix Display Controller
Handles clock, sports, stocks/crypto, weather, and brightness modes
Optimized for Raspberry Pi 3B with Adafruit RGB Matrix Bonnet
"""

import time
import logging
import sys
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import pytz
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Try to import RGB matrix library
try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
    MATRIX_AVAILABLE = True
except ImportError:
    logger.warning("rgbmatrix library not available, using fallback mode")
    MATRIX_AVAILABLE = False
    RGBMatrix = None
    RGBMatrixOptions = None

from PIL import Image, ImageDraw, ImageFont

# Import managers from LEDMatrix example if available
# Note: These are optional - the system works with basic fallback displays if not available
MANAGERS_AVAILABLE = False
Clock = None
WeatherManager = None
StockManager = None
ConfigManager = None
CacheManager = None

# Try to import from LEDMatrix if installed separately
# You can install LEDMatrix separately if you want advanced features
try:
    from src.clock import Clock
    from src.weather_manager import WeatherManager
    from src.stock_manager import StockManager
    from src.config_manager import ConfigManager
    from src.cache_manager import CacheManager
    MANAGERS_AVAILABLE = True
    logger.info("LEDMatrix managers loaded successfully")
except (ImportError, SyntaxError, IndentationError) as e:
    logger.info(f"LEDMatrix managers not available - using basic fallback displays: {e}")
    MANAGERS_AVAILABLE = False

# Try to import music manager components
SkipModuleException = None
try:
    from src.music_manager import SkipModuleException
except (ImportError, SyntaxError, IndentationError):
    # SkipModuleException not available - will handle gracefully
    pass


class MatrixDisplay:
    """Low-level matrix display wrapper optimized for Pi 3B"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.matrix = None
        self.offscreen_canvas = None
        self.image = None
        self.draw = None
        self.brightness = config.get('brightness', 50)
        self._setup_matrix()
        self._load_fonts()
        
    def _setup_matrix(self):
        """Initialize RGB matrix with Pi 3B optimized settings"""
        if not MATRIX_AVAILABLE:
            logger.error("RGB Matrix library not available")
            return
            
        try:
            options = RGBMatrixOptions()
            
            # Hardware configuration for Adafruit Bonnet with pins 4 and 18 connected
            # Use adafruit-hat-pwm for better flicker reduction when pins 4/18 are connected
            options.rows = 32
            options.cols = 64
            options.chain_length = 1
            options.parallel = 1
            options.hardware_mapping = 'adafruit-hat-pwm'  # For pins 4/18 connection
            
            # Pi 3B optimized settings for reduced flickering
            options.brightness = self.brightness
            options.pwm_bits = 11  # Increased for smoother color transitions
            options.pwm_lsb_nanoseconds = 130  # Adjusted for better PWM resolution
            options.led_rgb_sequence = 'RGB'
            options.gpio_slowdown = 2  # Important for Pi 3B stability
            options.show_refresh_rate = False
            options.limit_refresh_rate_hz = 120  # Higher refresh rate reduces visible flicker
            
            # Force software pulsing to avoid startup failures
            # Even with capability set, the RGBMatrix library may not be able to use hardware pulsing
            # Software pulsing still works well with the optimized PWM settings below
            use_hardware_pulsing = False
            logger.info("Using software pulsing (hardware pulsing disabled to ensure reliable startup)")
            
            # Always use software pulsing to prevent library from exiting
            options.disable_hardware_pulsing = True
            
            logger.info(f"Initializing RGB Matrix: {options.rows}x{options.cols}, brightness={self.brightness}, hardware_pulsing={use_hardware_pulsing}, disable_hardware_pulsing={options.disable_hardware_pulsing}")
            
            # If we think we can use hardware pulsing but it fails, the library will exit
            # So we need to be very conservative - only use hardware if we're absolutely sure
            # For now, let's default to software pulsing to ensure the service starts
            # The user can enable hardware pulsing later if needed
            if use_hardware_pulsing:
                logger.warning("Hardware pulsing enabled - if service fails to start, capability may not be working correctly")
            
            self.matrix = RGBMatrix(options=options)
            self.offscreen_canvas = self.matrix.CreateFrameCanvas()
            self.image = Image.new('RGB', (self.matrix.width, self.matrix.height))
            self.draw = ImageDraw.Draw(self.image)
            logger.info(f"RGB Matrix initialized successfully (hardware_pulsing={use_hardware_pulsing})")
            
        except Exception as e:
            logger.error(f"Failed to initialize RGB Matrix: {e}", exc_info=True)
            # Fallback mode
            self.image = Image.new('RGB', (64, 32))
            self.draw = ImageDraw.Draw(self.image)
            
    def _display_sport_logo(self, sport_id: str, sport_name: str):
        """Display sport logo if available"""
        try:
            if self.asset_loader:
                logo = self.asset_loader.get_sport_logo(sport_id)
                if logo:
                    # Resize to fit display (32x32 max)
                    logo = logo.resize((32, 32), Image.Resampling.LANCZOS)
                    # Paste logo on left side
                    self.matrix.image.paste(logo, (0, 0))
        except Exception as e:
            logger.debug(f"Could not display sport logo: {e}")
    
    def _load_fonts(self):
        """Load fonts for display"""
        try:
            # Try to load Press Start 2P font
            font_path = "assets/fonts/PressStart2P-Regular.ttf"
            if os.path.exists(font_path):
                self.font = ImageFont.truetype(font_path, 8)
                self.small_font = ImageFont.truetype(font_path, 6)
            else:
                self.font = ImageFont.load_default()
                self.small_font = ImageFont.load_default()
        except Exception as e:
            logger.warning(f"Could not load custom font: {e}")
            self.font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()
        
        # Show test pattern after fonts are loaded
        if self.matrix and self.draw:
            try:
                self.draw.rectangle([0, 0, self.matrix.width-1, self.matrix.height-1], fill=(0, 0, 0))
                self.draw.text((10, 10), "READY", font=self.font, fill=(0, 255, 0))
                self.update()
                logger.info("Test pattern displayed successfully")
                time.sleep(1)  # Show "READY" for 1 second
            except Exception as e:
                logger.warning(f"Could not show test pattern: {e}")
            
    def set_brightness(self, brightness: int):
        """Set display brightness (0-100)"""
        self.brightness = max(0, min(100, brightness))
        if self.matrix:
            try:
                # RGB matrix expects brightness 0-100, not 0-255
                self.matrix.brightness = self.brightness
                logger.info(f"Brightness set to {self.brightness}%")
            except Exception as e:
                logger.error(f"Error setting brightness: {e}")
        else:
            logger.warning("Matrix not initialized, cannot set brightness")
        
    def clear(self):
        """Clear the display"""
        if self.image:
            self.image = Image.new('RGB', (self.image.width, self.image.height))
            self.draw = ImageDraw.Draw(self.image)
            
    def update(self):
        """Update the display"""
        if self.matrix and self.offscreen_canvas:
            try:
                self.offscreen_canvas.SetImage(self.image)
                self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)
            except Exception as e:
                logger.error(f"Error updating display: {e}", exc_info=True)
                
    def draw_text(self, text: str, x: int = None, y: int = None, 
                  color: tuple = (255, 255, 255), small: bool = False, center: bool = True):
        """Draw text on the display"""
        if not self.draw:
            return
        font = self.small_font if small else self.font
        if x is None or center:
            bbox = self.draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            if x is None:
                # Center in full width
                x = (self.image.width - text_width) // 2
            else:
                # Center within remaining space from x to end
                remaining_width = self.image.width - x
                x = x + (remaining_width - text_width) // 2
        if y is None:
            y = 0
        self.draw.text((x, y), text, font=font, fill=color)
        
    @property
    def width(self):
        return self.image.width if self.image else 64
        
    @property
    def height(self):
        return self.image.height if self.image else 32


class DisplayController:
    """Main display controller managing all modes"""
    
    def __init__(self, config_path: str = "config.json"):
        # Make config path absolute if relative (relative to script directory)
        if not os.path.isabs(config_path):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, config_path)
        # Store the absolute config path for reloading
        self.config_path = config_path
        logger.info(f"Loading config from: {config_path}")
        self.config = self._load_config(config_path)
        logger.info(f"Loaded config: sports={len(self.config.get('sports', []))}, stocks={len(self.config.get('stocks', []))}, crypto={len(self.config.get('crypto', []))}, weather={len(self.config.get('weather_locations', []))}")
        # Log actual config contents for debugging
        logger.debug(f"Config sports list: {self.config.get('sports', [])}")
        logger.debug(f"Config stocks list: {self.config.get('stocks', [])}")
        logger.debug(f"Config crypto list: {self.config.get('crypto', [])}")
        logger.debug(f"Config weather list: {self.config.get('weather_locations', [])}")
        self.matrix = MatrixDisplay(self.config)
        
        # Initialize asset loader
        try:
            from display_assets import AssetLoader
            self.asset_loader = AssetLoader()
        except Exception as e:
            logger.warning(f"Could not initialize asset loader: {e}")
            self.asset_loader = None
        
        # Mode state
        self.current_mode = "clock"
        self.mode_index = 0
        self.modes = ["clock", "sports", "stocks", "weather", "music", "brightness"]
        
        # Clock state - handle timezone errors gracefully
        try:
            timezone_str = self.config.get('timezone', 'UTC')
            self.clock_timezone = pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Unknown timezone '{timezone_str}', falling back to UTC")
            self.clock_timezone = pytz.UTC
        except Exception as e:
            logger.warning(f"Error setting timezone: {e}, falling back to UTC")
            self.clock_timezone = pytz.UTC
            
        self.clock_locations = self.config.get('clock_locations', [])
        self.current_clock_location = 0
        
        # Sports state
        self.sports_list = self.config.get('sports', [])
        self.current_sport = 0
        self.current_game = 0
        self.sports_data_cache = {}  # Cache for sports scores
        self.last_sports_update = 0
        
        # Stocks state - combine stocks and crypto into one list
        self.stocks_list = self.config.get('stocks', [])
        self.crypto_list = self.config.get('crypto', [])
        self.all_tickers = self.stocks_list + self.crypto_list
        self.current_ticker = 0
        self.stock_data_cache = {}  # Cache for stock prices
        self.last_stock_update = 0
        
        # Weather state
        self.weather_locations = self.config.get('weather_locations', [])
        self.current_weather_location = 0
        self.weather_data_cache = {}  # Cache for weather data
        self.last_weather_update = 0
        
        # Initialize managers if available
        self.config_manager = None
        self.cache_manager = None
        self.music_manager = None
        
        # Try to initialize music manager (works independently of other managers)
        try:
            from src.music_manager import MusicManager, SkipModuleException
            # Create a display manager wrapper for compatibility
            class DisplayManagerWrapper:
                def __init__(self, matrix):
                    self.matrix = matrix
                def clear(self):
                    self.matrix.clear()
                def draw_text(self, text, x=None, y=None, color=(255, 255, 255), font=None, **kwargs):
                    # Convert font parameter to small flag for MatrixDisplay
                    if font is None:
                        small = False
                    else:
                        # Check if font matches small or extra_small fonts
                        small = (font == self.small_font or font == self.extra_small_font or 
                                (hasattr(self.matrix, 'small_font') and font == self.matrix.small_font))
                    # Extract center from kwargs if present, default True
                    center = kwargs.get('center', True)
                    self.matrix.draw_text(text, x=x, y=y, color=color, small=small, center=center)
                def update_display(self):
                    self.matrix.update()
                def get_text_width(self, text, font):
                    """Calculate text width using the font"""
                    if not self.matrix.draw:
                        return len(text) * 6  # Rough estimate
                    # Use the appropriate font
                    if font == self.regular_font:
                        use_font = self.matrix.font
                    elif font == self.small_font:
                        use_font = self.matrix.small_font
                    elif font == self.extra_small_font:
                        use_font = self.matrix.small_font  # Use small_font as fallback
                    else:
                        use_font = font if font else self.matrix.font
                    bbox = self.matrix.draw.textbbox((0, 0), text, font=use_font)
                    return bbox[2] - bbox[0]
                @property
                def width(self):
                    return self.matrix.width
                @property
                def height(self):
                    return self.matrix.height
                @property
                def regular_font(self):
                    return self.matrix.font
                @property
                def small_font(self):
                    return self.matrix.small_font
                @property
                def extra_small_font(self):
                    return self.matrix.small_font  # Use small_font as extra_small
                @property
                def bdf_5x7_font(self):
                    # Map BDF font to small_font (PIL font) for compatibility
                    return self.matrix.small_font
                @property
                def image(self):
                    return self.matrix.image
                @property
                def draw(self):
                    return self.matrix.draw
            
            display_wrapper = DisplayManagerWrapper(self.matrix)
            # Check if music is enabled in config
            music_config = self.config.get('music', {})
            if music_config.get('enabled', False):
                self.music_manager = MusicManager(display_wrapper, self.config)
                # Start polling for track updates
                self.music_manager.start_polling()
                logger.info("Music manager initialized and polling started")
            else:
                logger.info("Music manager disabled in config")
        except (ImportError, SyntaxError, IndentationError) as e:
            logger.info(f"Music manager not available: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize music manager: {e}", exc_info=True)
        
        if MANAGERS_AVAILABLE:
            try:
                self.config_manager = ConfigManager()
                self.cache_manager = CacheManager()
                full_config = self.config_manager.load_config()
                
                # Create a display manager wrapper for compatibility
                class DisplayManagerWrapper:
                    def __init__(self, matrix):
                        self.matrix = matrix
                    def clear(self):
                        self.matrix.clear()
                    def draw_text(self, text, x=None, y=None, color=(255, 255, 255), font=None, **kwargs):
                        # Convert font parameter to small flag for MatrixDisplay
                        if font is None:
                            small = False
                        else:
                            # Check if font matches small or extra_small fonts
                            small = (font == self.small_font or font == self.extra_small_font or 
                                    (hasattr(self.matrix, 'small_font') and font == self.matrix.small_font))
                        # Extract center from kwargs if present, default True
                        center = kwargs.get('center', True)
                        self.matrix.draw_text(text, x=x, y=y, color=color, small=small, center=center)
                    def update_display(self):
                        self.matrix.update()
                    def get_text_width(self, text, font):
                        """Calculate text width using the font"""
                        if not self.matrix.draw:
                            return len(text) * 6  # Rough estimate
                        # Use the appropriate font
                        if font == self.regular_font:
                            use_font = self.matrix.font
                        elif font == self.small_font:
                            use_font = self.matrix.small_font
                        elif font == self.extra_small_font:
                            use_font = self.matrix.small_font  # Use small_font as fallback
                        else:
                            use_font = font if font else self.matrix.font
                        bbox = self.matrix.draw.textbbox((0, 0), text, font=use_font)
                        return bbox[2] - bbox[0]
                    @property
                    def width(self):
                        return self.matrix.width
                    @property
                    def height(self):
                        return self.matrix.height
                    @property
                    def regular_font(self):
                        return self.matrix.font
                    @property
                    def small_font(self):
                        return self.matrix.small_font
                    @property
                    def extra_small_font(self):
                        return self.matrix.small_font  # Use small_font as extra_small
                    @property
                    def bdf_5x7_font(self):
                        # Map BDF font to small_font (PIL font) for compatibility
                        return self.matrix.small_font
                    @property
                    def image(self):
                        return self.matrix.image
                    @property
                    def draw(self):
                        return self.matrix.draw
                
                display_wrapper = DisplayManagerWrapper(self.matrix)
                
                # Initialize managers
                self.clock_manager = Clock(display_wrapper, full_config) if Clock else None
                self.weather_manager = WeatherManager(full_config, display_wrapper) if WeatherManager else None
                self.stock_manager = StockManager(full_config, display_wrapper) if StockManager else None
            except Exception as e:
                logger.error(f"Failed to initialize managers: {e}", exc_info=True)
                self.clock_manager = None
                self.weather_manager = None
                self.stock_manager = None
        else:
            self.clock_manager = None
            self.weather_manager = None
            self.stock_manager = None
            
        self.last_update = time.time()
        self.update_interval = 1.0  # Update every second
        self.reload_file = "/tmp/matrix_display_reload"
        self.last_config_check = time.time()
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        default_config = {
            "brightness": 50,
            "timezone": "America/New_York",
            "clock_locations": [],
            "sports": [],
            "stocks": [],
            "crypto": [],
            "weather_locations": [],
            "music": {
                "enabled": False,
                "preferred_source": "spotify",
                "POLLING_INTERVAL_SECONDS": 2
            }
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                return default_config
        else:
            # Create default config file
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
            
    def save_config(self):
        """Save current configuration"""
        try:
            with open("config.json", 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            
    def reload_config(self):
        """Reload configuration from file"""
        try:
            # Use the stored config path
            config_path = getattr(self, 'config_path', "config.json")
            if not os.path.isabs(config_path):
                script_dir = os.path.dirname(os.path.abspath(__file__))
                config_path = os.path.join(script_dir, config_path)
            logger.info(f"Reloading config from: {config_path}")
            self.config = self._load_config(config_path)
            # Update state from new config
            self.clock_locations = self.config.get('clock_locations', [])
            self.sports_list = self.config.get('sports', [])
            self.stocks_list = self.config.get('stocks', [])
            self.crypto_list = self.config.get('crypto', [])
            self.all_tickers = self.stocks_list + self.crypto_list
            self.weather_locations = self.config.get('weather_locations', [])
            # Update brightness
            new_brightness = self.config.get('brightness', 50)
            if new_brightness != self.matrix.brightness:
                self.matrix.set_brightness(new_brightness)
            
            # Reload music manager if config changed
            music_config = self.config.get('music', {})
            music_enabled = music_config.get('enabled', False)
            
            if music_enabled and not self.music_manager:
                # Music was just enabled, try to initialize it
                try:
                    from src.music_manager import MusicManager, SkipModuleException
                    class DisplayManagerWrapper:
                        def __init__(self, matrix):
                            self.matrix = matrix
                        def clear(self):
                            self.matrix.clear()
                        def draw_text(self, text, x=None, y=None, color=(255, 255, 255), font=None, **kwargs):
                            # Convert font parameter to small flag for MatrixDisplay
                            if font is None:
                                small = False
                            else:
                                # Check if font matches small or extra_small fonts
                                small = (font == self.small_font or font == self.extra_small_font or 
                                        (hasattr(self.matrix, 'small_font') and font == self.matrix.small_font))
                            # Extract center from kwargs if present, default True
                            center = kwargs.get('center', True)
                            self.matrix.draw_text(text, x=x, y=y, color=color, small=small, center=center)
                        def update_display(self):
                            self.matrix.update()
                        def get_text_width(self, text, font):
                            """Calculate text width using the font"""
                            if not self.matrix.draw:
                                return len(text) * 6  # Rough estimate
                            # Use the appropriate font
                            if font == self.regular_font:
                                use_font = self.matrix.font
                            elif font == self.small_font:
                                use_font = self.matrix.small_font
                            elif font == self.extra_small_font:
                                use_font = self.matrix.small_font  # Use small_font as fallback
                            else:
                                use_font = font if font else self.matrix.font
                            bbox = self.matrix.draw.textbbox((0, 0), text, font=use_font)
                            return bbox[2] - bbox[0]
                        @property
                        def width(self):
                            return self.matrix.width
                        @property
                        def height(self):
                            return self.matrix.height
                        @property
                        def regular_font(self):
                            return self.matrix.font
                        @property
                        def small_font(self):
                            return self.matrix.small_font
                        @property
                        def extra_small_font(self):
                            return self.matrix.small_font  # Use small_font as extra_small
                        @property
                        def bdf_5x7_font(self):
                            # Map BDF font to small_font (PIL font) for compatibility
                            return self.matrix.small_font
                        @property
                        def image(self):
                            return self.matrix.image
                        @property
                        def draw(self):
                            return self.matrix.draw
                    
                    display_wrapper = DisplayManagerWrapper(self.matrix)
                    self.music_manager = MusicManager(display_wrapper, self.config)
                    # Start polling for track updates
                    self.music_manager.start_polling()
                    logger.info("Music manager initialized after config reload and polling started")
                except Exception as e:
                    logger.error(f"Failed to initialize music manager after reload: {e}")
            elif not music_enabled and self.music_manager:
                # Music was disabled, stop polling
                try:
                    self.music_manager.stop_polling()
                except:
                    pass
                self.music_manager = None
                logger.info("Music manager stopped after config reload")
            elif self.music_manager:
                # Music manager exists, update its config
                try:
                    self.music_manager.config = self.config
                    self.music_manager._load_config()
                except Exception as e:
                    logger.error(f"Error updating music manager config: {e}")
            
            logger.info(f"Configuration reloaded: sports={len(self.sports_list)}, stocks={len(self.stocks_list)}, crypto={len(self.crypto_list)}, weather={len(self.weather_locations)}, music_enabled={music_enabled}")
        except Exception as e:
            logger.error(f"Error reloading config: {e}")
            
    def set_mode(self, mode: str):
        """Set the current display mode"""
        if mode in self.modes:
            self.current_mode = mode
            self.mode_index = self.modes.index(mode)
            logger.info(f"Mode changed to: {mode}")
            
    def cycle_mode(self, direction: int = 1):
        """Cycle to next/previous mode"""
        self.mode_index = (self.mode_index + direction) % len(self.modes)
        self.current_mode = self.modes[self.mode_index]
        logger.info(f"Mode cycled to: {self.current_mode}")
        
    # Clock mode controls
    def next_clock_location(self):
        """Next time zone location"""
        if self.clock_locations:
            self.current_clock_location = (self.current_clock_location + 1) % len(self.clock_locations)
            logger.info(f"Clock location: {self.current_clock_location}")
            
    def prev_clock_location(self):
        """Previous time zone location"""
        if self.clock_locations:
            self.current_clock_location = (self.current_clock_location - 1) % len(self.clock_locations)
            logger.info(f"Clock location: {self.current_clock_location}")
            
    # Sports mode controls
    def next_sport(self):
        """Next sport"""
        if self.sports_list:
            self.current_sport = (self.current_sport + 1) % len(self.sports_list)
            self.current_game = 0
            logger.info(f"Sport: {self.current_sport}")
            
    def prev_sport(self):
        """Previous sport"""
        if self.sports_list:
            self.current_sport = (self.current_sport - 1) % len(self.sports_list)
            self.current_game = 0
            logger.info(f"Sport: {self.current_sport}")
            
    def next_game(self):
        """Next game in current sport - loops back to first game"""
        # Get current sport's games to determine loop
        sport = self.sports_list[self.current_sport] if self.sports_list and self.current_sport < len(self.sports_list) else None
        if sport:
            # Use the same logic as display_sports() to extract sport_id
            if isinstance(sport, str):
                sport_id = sport.lower()
            elif isinstance(sport, dict):
                sport_id = sport.get('id') or sport.get('name')
                if sport_id:
                    sport_id = str(sport_id).lower()
                else:
                    sport_id = 'sports'
            else:
                sport_id = 'sports'
            
            # Ensure sport_id is not None
            if not sport_id:
                sport_id = 'sports'
            
            logger.debug(f"next_game: sport_id={sport_id}, cache keys={list(self.sports_data_cache.keys())}")
            games = self.sports_data_cache.get(sport_id, [])
            
            # If no games in cache, try to fetch them
            if not games or len(games) == 0:
                logger.info(f"No games in cache for {sport_id}, attempting to fetch...")
                try:
                    from sports_fetcher import fetch_espn_scores
                    games = fetch_espn_scores(sport_id)
                    if games:
                        self.sports_data_cache[sport_id] = games
                        self.last_sports_update = time.time()
                        logger.info(f"Fetched {len(games)} games for sport {sport_id}")
                except Exception as e:
                    logger.error(f"Error fetching games in next_game: {e}")
            
            if games and len(games) > 0:
                old_game = self.current_game
                self.current_game = (self.current_game + 1) % len(games)  # Loop back to 0
                logger.info(f"Game: {old_game} -> {self.current_game} (total games: {len(games)})")
                # Force immediate display update by calling display_sports directly
                # Clear first to prevent overlap
                self.matrix.clear()
                try:
                    self.display_sports()
                except Exception as e:
                    logger.error(f"Error updating display after next_game: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                logger.warning(f"No games found for sport {sport_id} (cache keys: {list(self.sports_data_cache.keys())})")
                self.current_game = 0  # Reset if no games
        else:
            logger.warning("No sport selected")
            self.current_game = 0
        
    def prev_game(self):
        """Previous game in current sport - loops back to last game"""
        # Get current sport's games to determine loop
        sport = self.sports_list[self.current_sport] if self.sports_list and self.current_sport < len(self.sports_list) else None
        if sport:
            # Use the same logic as display_sports() to extract sport_id
            if isinstance(sport, str):
                sport_id = sport.lower()
            elif isinstance(sport, dict):
                sport_id = sport.get('id') or sport.get('name')
                if sport_id:
                    sport_id = str(sport_id).lower()
                else:
                    sport_id = 'sports'
            else:
                sport_id = 'sports'
            
            # Ensure sport_id is not None
            if not sport_id:
                sport_id = 'sports'
            
            logger.debug(f"prev_game: sport_id={sport_id}, cache keys={list(self.sports_data_cache.keys())}")
            games = self.sports_data_cache.get(sport_id, [])
            
            # If no games in cache, try to fetch them
            if not games or len(games) == 0:
                logger.info(f"No games in cache for {sport_id}, attempting to fetch...")
                try:
                    from sports_fetcher import fetch_espn_scores
                    games = fetch_espn_scores(sport_id)
                    if games:
                        self.sports_data_cache[sport_id] = games
                        self.last_sports_update = time.time()
                        logger.info(f"Fetched {len(games)} games for sport {sport_id}")
                except Exception as e:
                    logger.error(f"Error fetching games in prev_game: {e}")
            
            if games and len(games) > 0:
                old_game = self.current_game
                self.current_game = (self.current_game - 1) % len(games)  # Loop back to last game
                logger.info(f"Game: {old_game} -> {self.current_game} (total games: {len(games)})")
                # Force immediate display update by calling display_sports directly
                # Clear first to prevent overlap
                self.matrix.clear()
                try:
                    self.display_sports()
                except Exception as e:
                    logger.error(f"Error updating display after prev_game: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                logger.warning(f"No games found for sport {sport_id} (cache keys: {list(self.sports_data_cache.keys())})")
                self.current_game = 0
        else:
            logger.warning("No sport selected")
            self.current_game = 0
        
    # Stocks mode controls
    def next_ticker(self):
        """Next stock/crypto ticker"""
        if self.all_tickers:
            self.current_ticker = (self.current_ticker + 1) % len(self.all_tickers)
            logger.info(f"Ticker: {self.current_ticker}")
            
    def prev_ticker(self):
        """Previous stock/crypto ticker"""
        if self.all_tickers:
            self.current_ticker = (self.current_ticker - 1) % len(self.all_tickers)
            logger.info(f"Ticker: {self.current_ticker}")
            
    # Weather mode controls
    def next_weather_location(self):
        """Next weather location"""
        if self.weather_locations:
            self.current_weather_location = (self.current_weather_location + 1) % len(self.weather_locations)
            logger.info(f"Weather location: {self.current_weather_location}")
            
    def prev_weather_location(self):
        """Previous weather location"""
        if self.weather_locations:
            self.current_weather_location = (self.current_weather_location - 1) % len(self.weather_locations)
            logger.info(f"Weather location: {self.current_weather_location}")
            
    # Brightness controls
    def brightness_up(self):
        """Increase brightness"""
        new_brightness = min(100, self.config['brightness'] + 5)
        self.config['brightness'] = new_brightness
        self.matrix.set_brightness(new_brightness)
        self.save_config()
        
    def brightness_down(self):
        """Decrease brightness"""
        new_brightness = max(0, self.config['brightness'] - 5)
        self.config['brightness'] = new_brightness
        self.matrix.set_brightness(new_brightness)
        self.save_config()
        
    def display_clock(self):
        """Display clock mode"""
        if self.clock_manager:
            try:
                self.clock_manager.display_time()
            except Exception as e:
                logger.error(f"Error displaying clock: {e}")
                # Fall through to fallback
                self._display_clock_fallback()
        else:
            self._display_clock_fallback()
            
    def _display_clock_fallback(self):
        """Fallback clock display"""
        try:
            self.matrix.clear()
            
            # Get timezone from current clock location, not default
            tz = self.clock_timezone  # Default fallback
            location_name = ""
            if self.clock_locations and self.current_clock_location < len(self.clock_locations):
                location = self.clock_locations[self.current_clock_location]
                if isinstance(location, dict):
                    tz_str = location.get('timezone', location.get('tz', ''))
                    location_name = location.get('name', location.get('label', ''))
                elif isinstance(location, str):
                    tz_str = location
                    location_name = location
                else:
                    tz_str = str(location)
                    location_name = tz_str
                
                if tz_str:
                    try:
                        tz = pytz.timezone(tz_str)
                    except Exception as e:
                        logger.warning(f"Invalid timezone '{tz_str}', using default: {e}")
                        tz = self.clock_timezone
            
            now = datetime.now(tz)
            time_str = now.strftime('%I:%M %p').lstrip('0')  # Remove leading zero
            if time_str.startswith(' '):
                time_str = time_str[1:]
            self.matrix.draw_text(time_str, y=6, color=(255, 255, 255), center=True)
            date_str = now.strftime('%b %d')
            self.matrix.draw_text(date_str, y=16, color=(200, 200, 200), small=True, center=True)
            # Display timezone abbreviation under date (instead of location name)
            try:
                # Get timezone abbreviation from the datetime object
                tz_abbr = now.strftime('%Z')  # Gets timezone abbreviation (e.g., "CST", "EST")
                if not tz_abbr or tz_abbr == now.strftime('%z'):  # If abbreviation not available, try alternative
                    # Fall back to timezone name
                    tz_name = str(tz).split('/')[-1] if '/' in str(tz) else str(tz)
                    tz_name = tz_name.replace('_', ' ')
                    tz_abbr = tz_name[:4].upper()  # Use first 4 chars of timezone name
            except Exception:
                # Final fallback
                tz_name = str(tz).split('/')[-1] if '/' in str(tz) else str(tz)
                tz_abbr = tz_name.replace('_', ' ')[:4].upper()
            
            # Display timezone abbreviation (should be short like "CST", "EST", "PST")
            self.matrix.draw_text(tz_abbr[:6], y=24, color=(150, 150, 150), small=True, center=True)
            self.matrix.update()
        except Exception as e:
            logger.error(f"Error in clock fallback: {e}")
            # Show error on display
            self.matrix.clear()
            self.matrix.draw_text("CLOCK ERR", y=10, color=(255, 0, 0))
            self.matrix.update()
            
    def display_sports(self):
        """Display sports mode with actual scores"""
        # Clear the image buffer completely before drawing
        self.matrix.clear()
        # Ensure the clear is applied immediately by recreating the image
        if self.matrix.image:
            self.matrix.image = Image.new('RGB', (self.matrix.image.width, self.matrix.image.height))
            self.matrix.draw = ImageDraw.Draw(self.matrix.image)
        
        logger.debug(f"display_sports: sports_list={self.sports_list}, current_sport={self.current_sport}, len={len(self.sports_list) if self.sports_list else 0}")
        if not self.sports_list or self.current_sport >= len(self.sports_list):
            logger.warning(f"No sports configured or invalid index: sports_list={self.sports_list}, current_sport={self.current_sport}")
            self.matrix.draw_text("NO SPORTS", y=10, color=(255, 0, 0))
            self.matrix.update()
            return
            
        sport = self.sports_list[self.current_sport]
        
        # Handle different sport data formats
        if isinstance(sport, str):
            # If sport is just a string (e.g., "NFL"), use it directly
            sport_name = sport.upper()
            sport_id = sport.lower()
        elif isinstance(sport, dict):
            # If sport is a dict with 'name' and 'id' keys
            sport_name = sport.get('name', 'SPORTS')
            if isinstance(sport_name, str):
                sport_name = sport_name.upper()
            else:
                sport_name = 'SPORTS'
            sport_id = sport.get('id') or sport.get('name')
            if sport_id:
                sport_id = str(sport_id).lower()
            else:
                sport_id = sport_name.lower() if sport_name else 'sports'
        else:
            # Fallback
            sport_name = 'SPORTS'
            sport_id = 'sports'
        
        # Ensure sport_id is not None
        if not sport_id:
            sport_id = sport_name.lower() if sport_name else 'sports'
        
        # Normalize sport_id for logo lookup (ESPN uses different IDs than we need)
        # Map ESPN sport paths to our logo directory names
        sport_id_for_logos = sport_id.lower()
        if 'college-football' in sport_id_for_logos or 'ncaaf' in sport_id_for_logos:
            sport_id_for_logos = 'ncaaf'
        elif 'college-basketball' in sport_id_for_logos or 'mens-college-basketball' in sport_id_for_logos or 'ncaab' in sport_id_for_logos:
            sport_id_for_logos = 'ncaab'
        elif 'ncaa' in sport_id_for_logos:
            sport_id_for_logos = 'ncaa'
        
        logger.debug(f"Sport ID for scores: {sport_id}, for logos: {sport_id_for_logos}")
        
        # Fetch scores if cache is old (update every 60 seconds)
        current_time = time.time()
        
        # Check if we need to fetch/refresh games for this sport
        if (sport_id not in self.sports_data_cache or 
            current_time - self.last_sports_update > 60):
            try:
                from sports_fetcher import fetch_espn_scores
                games = fetch_espn_scores(sport_id)
                if games:
                    self.sports_data_cache[sport_id] = games
                    self.last_sports_update = current_time
                    logger.info(f"Fetched {len(games)} games for sport {sport_id}")
                else:
                    logger.warning(f"No games returned from API for sport {sport_id}")
            except Exception as e:
                logger.error(f"Error fetching sports scores for {sport_id}: {e}")
                import traceback
                traceback.print_exc()
        
        games = self.sports_data_cache.get(sport_id, [])
        logger.debug(f"display_sports: sport_id={sport_id}, games in cache={len(games)}, cache keys={list(self.sports_data_cache.keys())}")
        
        if games and len(games) > 0 and self.current_game < len(games):
            game = games[self.current_game]
            # Display: AWAY @ HOME or AWAY vs HOME
            away = game.get('away_team', 'AWAY')[:4]  # Limit to 4 chars
            home = game.get('home_team', 'HOME')[:4]
            away_score = str(game.get('away_score', 0))
            home_score = str(game.get('home_score', 0))
            
            # Try to load team logos
            away_logo = None
            home_logo = None
            if self.asset_loader:
                logger.info(f"Loading logos for sport_id={sport_id_for_logos}, away={away}, home={home}")
                try:
                    away_logo = self.asset_loader.get_sport_logo(sport_id_for_logos, away)
                    logger.info(f"Loading away logo for {away} (sport_id={sport_id_for_logos}): {away_logo is not None}")
                except Exception as e:
                    logger.error(f"Error loading away logo: {e}")
                try:
                    home_logo = self.asset_loader.get_sport_logo(sport_id_for_logos, home)
                    logger.info(f"Loading home logo for {home} (sport_id={sport_id_for_logos}): {home_logo is not None}")
                except Exception as e:
                    logger.error(f"Error loading home logo: {e}")
            
            # Layout: Small logos on sides, team names and scores in center
            # Top: Status (period/time/FINAL/Scheduled)
            # Middle: Small logos on sides, team names and scores in center
            # Bottom: Down & Distance (if live game)
            
            center_y = self.matrix.image.height // 2  # 16 for 32px height
            
            # Display small logos on the sides (16x16 to avoid overlap)
            logo_size = 16  # Smaller logos that won't overlap with text
            if away_logo:
                try:
                    away_logo_resized = away_logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                    away_y = center_y - (logo_size // 2)  # Center vertically
                    away_x = 2  # Small margin from left edge
                    if away_logo_resized.mode == 'RGBA':
                        self.matrix.image.paste(away_logo_resized, (away_x, away_y), away_logo_resized)
                    else:
                        self.matrix.image.paste(away_logo_resized, (away_x, away_y))
                    logger.debug(f"Displayed away logo: {away}")
                except Exception as e:
                    logger.error(f"Could not display away logo: {e}")
            if home_logo:
                try:
                    home_logo_resized = home_logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                    home_y = center_y - (logo_size // 2)  # Center vertically
                    home_x = self.matrix.image.width - logo_size - 2  # Small margin from right edge
                    if home_logo_resized.mode == 'RGBA':
                        self.matrix.image.paste(home_logo_resized, (home_x, home_y), home_logo_resized)
                    else:
                        self.matrix.image.paste(home_logo_resized, (home_x, home_y))
                    logger.debug(f"Displayed home logo: {home}")
                except Exception as e:
                    logger.error(f"Could not display home logo: {e}")
            
            # Display team names and scores in the center (with space for logos on sides)
            teams_text = f"{away} @ {home}"
            score_text = f"{away_score}-{home_score}"
            
            # Draw team names at top of center area (centered in available space)
            self.matrix.draw_text(teams_text, y=center_y - 8, color=(255, 255, 255), small=True, center=True)
            
            # Draw score below team names
            self.matrix.draw_text(score_text, y=center_y + 2, color=(255, 255, 0), center=True)
            
            # Top middle: Period/time/FINAL/Scheduled
            status_text = ""
            status_id = game.get('status_id', '').upper()
            
            # Check status_id first, then fall back to boolean flags
            if 'FINAL' in status_id or game.get('is_final', False):
                status_text = "FINAL"
            elif 'IN_PROGRESS' in status_id or 'HALFTIME' in status_id or 'DELAYED' in status_id or game.get('is_live', False):
                # Show clock and period for live games
                clock = game.get('clock', '')
                period_name = game.get('period_name', '')
                if clock and period_name:
                    status_text = f"{clock} {period_name}"
                elif period_name:
                    status_text = period_name
                elif clock:
                    status_text = clock
                else:
                    status_text = "LIVE"
            elif 'SCHEDULED' in status_id or 'PRE' in status_id or game.get('is_scheduled', False):
                # Show date and time for scheduled games
                date_str = game.get('date', '')
                if date_str:
                    try:
                        from datetime import datetime
                        import pytz
                        # Parse ISO format date (handle both with and without timezone)
                        if 'Z' in date_str:
                            game_date_utc = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            # Convert to local timezone
                            if game_date_utc.tzinfo:
                                local_tz_str = self.config.get('local_timezone', 'America/New_York')
                                try:
                                    local_tz = pytz.timezone(local_tz_str)
                                except pytz.exceptions.UnknownTimeZoneError:
                                    logger.warning(f"Unknown local timezone '{local_tz_str}', defaulting to America/New_York")
                                    local_tz = pytz.timezone('America/New_York')
                                game_date = game_date_utc.astimezone(local_tz)
                            else:
                                game_date = game_date_utc
                        elif '+' in date_str or date_str.count('-') >= 3:
                            game_date = datetime.fromisoformat(date_str)
                            if game_date.tzinfo:
                                local_tz_str = self.config.get('local_timezone', 'America/New_York')
                                try:
                                    local_tz = pytz.timezone(local_tz_str)
                                except pytz.exceptions.UnknownTimeZoneError:
                                    local_tz = pytz.timezone('America/New_York')
                                game_date = game_date.astimezone(local_tz)
                        else:
                            game_date = datetime.fromisoformat(date_str.split('.')[0])
                        
                        # Format as "MM/DD H:MMAM/PM"
                        date_display = game_date.strftime("%m/%d")
                        hour = game_date.hour
                        minute = game_date.minute
                        am_pm = "AM" if hour < 12 else "PM"
                        hour_12 = hour % 12
                        if hour_12 == 0:
                            hour_12 = 12
                        time_display = f"{hour_12}:{minute:02d}{am_pm}"
                        status_text = f"{date_display} {time_display}"
                        logger.debug(f"Formatted scheduled game time: {status_text}")
                    except Exception as e:
                        logger.error(f"Error parsing date '{date_str}': {e}")
                        status_text = "SCHEDULED"
            else:
                status_desc = game.get('status', '')
                if status_desc and status_desc not in ['Scheduled', 'In Progress', 'Final']:
                    status_text = status_desc
            
            # Display status at top middle (y=1)
            if status_text:
                max_chars = 12 if ('/' in status_text and ('AM' in status_text or 'PM' in status_text)) else 8
                if len(status_text) > max_chars:
                    status_text = status_text[:max_chars-1] + '…' if max_chars > 8 else status_text[:max_chars]
                try:
                    tiny_font_path = "assets/fonts/PressStart2P-Regular.ttf"
                    if os.path.exists(tiny_font_path):
                        tiny_font = ImageFont.truetype(tiny_font_path, 5)
                        bbox = self.matrix.draw.textbbox((0, 0), status_text, font=tiny_font)
                        text_width = bbox[2] - bbox[0]
                        x = (self.matrix.image.width - text_width) // 2
                        self.matrix.draw.text((x, 1), status_text, font=tiny_font, fill=(200, 200, 200))
                    else:
                        self.matrix.draw_text(status_text[:8], y=1, color=(200, 200, 200), small=True, center=True)
                except Exception as e:
                    logger.debug(f"Error using tiny font: {e}")
                    self.matrix.draw_text(status_text[:8], y=1, color=(200, 200, 200), small=True, center=True)
            
            # Bottom: Down & Distance (for live games)
            down_distance = game.get('down_distance_text', '')
            if down_distance and (game.get('is_live', False) or 'IN_PROGRESS' in status_id):
                try:
                    tiny_font_path = "assets/fonts/PressStart2P-Regular.ttf"
                    if os.path.exists(tiny_font_path):
                        tiny_font = ImageFont.truetype(tiny_font_path, 5)
                        bbox = self.matrix.draw.textbbox((0, 0), down_distance, font=tiny_font)
                        text_width = bbox[2] - bbox[0]
                        x = (self.matrix.image.width - text_width) // 2
                        self.matrix.draw.text((x, 26), down_distance, font=tiny_font, fill=(150, 255, 150))
                    else:
                        self.matrix.draw_text(down_distance[:8], y=26, color=(150, 255, 150), small=True, center=True)
                except Exception as e:
                    logger.debug(f"Error displaying down & distance: {e}")
                    self.matrix.draw_text(down_distance[:8], y=26, color=(150, 255, 150), small=True, center=True)
        else:
            # No games available or current_game out of bounds - loop back to first game
            if games and len(games) > 0:
                # Loop back to first game instead of showing template
                self.current_game = 0
                # Recursively call to display the first game
                self.display_sports()
                return
            else:
                # No games available - show sport name and try to load logo
                self.matrix.draw_text(sport_name[:8], y=5, color=(255, 255, 0))
                # Try to load and display team logo if available
                try:
                    self._display_sport_logo(sport_id, sport_name)
                except:
                    pass
                # Show "NO GAMES" if no games found
                self.matrix.draw_text("NO GAMES", y=20, color=(200, 200, 200), small=True)
            
        self.matrix.update()
        
    def display_stocks(self):
        """Display stocks/crypto mode with actual prices"""
        self.matrix.clear()
        
        logger.debug(f"display_stocks: all_tickers={self.all_tickers}, current_ticker={self.current_ticker}, len={len(self.all_tickers) if self.all_tickers else 0}")
        if not self.all_tickers or self.current_ticker >= len(self.all_tickers):
            logger.warning(f"No tickers configured or invalid index: all_tickers={self.all_tickers}, current_ticker={self.current_ticker}")
            self.matrix.draw_text("NO TICKERS", y=10, color=(255, 0, 0))
            self.matrix.update()
            return
            
        ticker = self.all_tickers[self.current_ticker]
        
        # Fetch price if cache is old (update every 30 seconds)
        current_time = time.time()
        cache_key = ticker
        
        if (cache_key not in self.stock_data_cache or 
            current_time - self.last_stock_update > 30):
            try:
                from stock_fetcher import fetch_stock_price, fetch_crypto_price
                
                # Determine if it's crypto or stock
                is_crypto = ticker in self.crypto_list
                
                if is_crypto:
                    data = fetch_crypto_price(ticker)
                else:
                    data = fetch_stock_price(ticker)
                    
                if data:
                    self.stock_data_cache[cache_key] = data
                    self.last_stock_update = current_time
            except Exception as e:
                logger.error(f"Error fetching stock price: {e}")
        
        data = self.stock_data_cache.get(cache_key)
        
        if data:
            # Try to load stock/crypto icon
            icon = None
            if self.asset_loader:
                icon = self.asset_loader.get_stock_icon(ticker)
            
            # Display ticker and price
            price = data.get('price', 0)
            change = data.get('change', 0)
            change_pct = data.get('change_percent', 0)
            
            # If icon available, show it on left side
            if icon:
                try:
                    icon = icon.resize((16, 16), Image.Resampling.LANCZOS)
                    self.matrix.image.paste(icon, (0, 8))
                except:
                    pass
            
            # Line 1: Ticker - center aligned
            self.matrix.draw_text(ticker[:6], y=2, color=(0, 255, 0), small=True, center=True)
            # Line 2: Price - offset to right to avoid icon overlap
            price_str = f"${price:.2f}" if price < 1000 else f"${price:.0f}"
            # Offset x position if icon is present (icon is 16px wide + 2px spacing)
            x_offset = 20 if icon else None
            self.matrix.draw_text(price_str, x=x_offset, y=14, color=(255, 255, 255), small=True, center=(icon is None))
            # Line 3: Change percentage - center aligned
            if change >= 0:
                change_color = (0, 255, 0)  # Green
                change_str = f"+{change_pct:.1f}%"
            else:
                change_color = (255, 0, 0)  # Red
                change_str = f"{change_pct:.1f}%"
            self.matrix.draw_text(change_str, y=22, color=change_color, small=True, center=True)
        else:
            # No data available, just show ticker
            self.matrix.draw_text(ticker[:8], y=10, color=(0, 255, 0))
            
        self.matrix.update()
            
    def display_weather(self):
        """Display weather mode with actual weather data"""
        self.matrix.clear()
        
        logger.debug(f"display_weather: weather_locations={self.weather_locations}, current_weather_location={self.current_weather_location}, len={len(self.weather_locations) if self.weather_locations else 0}")
        if not self.weather_locations or self.current_weather_location >= len(self.weather_locations):
            logger.warning(f"No weather locations configured or invalid index: weather_locations={self.weather_locations}, current_weather_location={self.current_weather_location}")
            self.matrix.draw_text("NO WEATHER", y=10, color=(255, 0, 0))
            self.matrix.update()
            return
            
        location = self.weather_locations[self.current_weather_location]
        location_name = location.get('name', 'WEATHER')
        city = location.get('city', '')
        state = location.get('state', '')
        api_key = location.get('api_key', '')
        
        # Fetch weather if cache is old (update every 300 seconds = 5 minutes)
        current_time = time.time()
        cache_key = location_name
        
        if (cache_key not in self.weather_data_cache or 
            current_time - self.last_weather_update > 300):
            try:
                from weather_fetcher import fetch_weather
                data = fetch_weather(city, state, api_key)
                if data:
                    self.weather_data_cache[cache_key] = data
                    self.last_weather_update = current_time
            except Exception as e:
                logger.error(f"Error fetching weather: {e}")
        
        data = self.weather_data_cache.get(cache_key)
        
        if data:
            # Try to load weather icon with day/night awareness
            condition = data.get('condition', 'Unknown')
            icon = None
            if self.asset_loader:
                # Determine if it's day or night at the location
                is_day = data.get('is_day', True)  # Default to day if not available
                icon = self.asset_loader.get_weather_icon(condition, is_day=is_day)
            
            # Display location and temperature
            temp = data.get('temp', 0)
            
            # If icon available, show it on left side
            if icon:
                try:
                    icon = icon.resize((16, 16), Image.Resampling.LANCZOS)
                    self.matrix.image.paste(icon, (0, 8))
                except:
                    pass
            
            # Line 1: Location name - handle long names better
            # For very long names, split into two lines or truncate intelligently
            max_chars_single = 10  # Max chars that fit on one line
            if len(location_name) > max_chars_single:
                # Try to split on space if possible
                words = location_name.split()
                if len(words) > 1 and len(words[0]) <= max_chars_single:
                    # Split into two lines
                    line1 = words[0]
                    line2 = ' '.join(words[1:])[:max_chars_single]
                    self.matrix.draw_text(line1, y=0, color=(0, 200, 255), small=True, center=True)
                    self.matrix.draw_text(line2, y=8, color=(0, 200, 255), small=True, center=True)
                else:
                    # Just truncate and center
                    location_display = location_name[:max_chars_single]
                    self.matrix.draw_text(location_display, y=2, color=(0, 200, 255), small=True, center=True)
            else:
                # Center align for short names
                self.matrix.draw_text(location_name, y=2, color=(0, 200, 255), small=True, center=True)
            
            # Line 2: Temperature - center aligned (adjust y based on whether location is split)
            temp_y = 18 if len(location_name) <= max_chars_single else 16
            temp_str = f"{temp}°F"
            self.matrix.draw_text(temp_str, y=temp_y, color=(255, 255, 255), center=True)
            
            # Line 3: Condition - truncate intelligently
            max_cond_chars = 8
            cond_y = 26 if len(location_name) <= max_chars_single else 24
            if len(condition) > max_cond_chars:
                # Truncate condition
                cond_str = condition[:max_cond_chars]
                self.matrix.draw_text(cond_str, y=cond_y, color=(200, 200, 255), small=True, center=True)
            else:
                # Center align for short conditions
                self.matrix.draw_text(condition, y=cond_y, color=(200, 200, 255), small=True, center=True)
        else:
            # No data available, just show location name
            self.matrix.draw_text(location_name[:8], y=10, color=(0, 200, 255))
            
        self.matrix.update()
            
    def display_music(self):
        """Display music mode with Spotify/YouTube Music"""
        if self.music_manager:
            try:
                # Activate music display if not already active
                if not self.music_manager.is_music_display_active:
                    self.music_manager.activate_music_display()
                # Use the music manager's display method
                self.music_manager.display()
            except Exception as skip_exc:
                # Check if this is a SkipModuleException (nothing playing)
                if SkipModuleException and isinstance(skip_exc, SkipModuleException):
                    # Nothing is playing - show message (don't auto-cycle, let user manually cycle if desired)
                    self.matrix.clear()
                    self.matrix.draw_text("MUSIC", y=5, color=(255, 255, 0), small=True, center=True)
                    self.matrix.draw_text("NOTHING", y=20, color=(200, 200, 200), small=True, center=True)
                    self.matrix.update()
                else:
                    # Other error - log and show error message
                    logger.error(f"Error displaying music: {skip_exc}", exc_info=True)
                    # Fallback display
                    self.matrix.clear()
                    self.matrix.draw_text("MUSIC", y=5, color=(255, 255, 0), small=True, center=True)
                    self.matrix.draw_text("ERROR", y=20, color=(255, 0, 0), small=True, center=True)
                    self.matrix.update()
        else:
            # No music manager available
            self.matrix.clear()
            self.matrix.draw_text("MUSIC", y=5, color=(255, 255, 0), small=True, center=True)
            self.matrix.draw_text("NOT CONFIG", y=20, color=(200, 200, 200), small=True, center=True)
            self.matrix.update()
        
    def display_brightness(self):
        """Display brightness setting"""
        self.matrix.clear()
        brightness = self.config.get('brightness', 50)
        # Use shorter text to fit on screen, larger font for brightness value
        self.matrix.draw_text("BRIGHT", y=5, color=(255, 255, 0), small=True, center=True)
        self.matrix.draw_text(f"{brightness}%", y=20, color=(255, 255, 255), center=True)  # Regular font (not small)
        self.matrix.update()
        
    def update(self):
        """Update display based on current mode"""
        current_time = time.time()
        
        # Check for config reload request (every 2 seconds)
        if current_time - self.last_config_check > 2.0:
            self.last_config_check = current_time
            if os.path.exists(self.reload_file):
                try:
                    self.reload_config()
                    os.remove(self.reload_file)  # Remove reload trigger
                    logger.info("Configuration reloaded from web interface")
                except Exception as e:
                    logger.error(f"Error reloading config: {e}")
        
        if current_time - self.last_update < self.update_interval:
            return
        self.last_update = current_time
        
        try:
            if self.current_mode == "clock":
                self.display_clock()
            elif self.current_mode == "sports":
                self.display_sports()
            elif self.current_mode == "stocks":
                self.display_stocks()
            elif self.current_mode == "weather":
                self.display_weather()
            elif self.current_mode == "music":
                self.display_music()
            elif self.current_mode == "brightness":
                self.display_brightness()
        except Exception as e:
            logger.error(f"Error updating display: {e}", exc_info=True)
            # Show error on display
            try:
                self.matrix.clear()
                self.matrix.draw_text("ERROR", y=10, color=(255, 0, 0))
                self.matrix.update()
            except:
                pass
            
    def run(self):
        """Main run loop"""
        logger.info("Display controller started")
        # Initial display update
        try:
            self.update()
        except Exception as e:
            logger.error(f"Error in initial update: {e}", exc_info=True)
            
        try:
            while True:
                self.update()
                time.sleep(0.1)  # Small sleep to prevent CPU spinning
        except KeyboardInterrupt:
            logger.info("Display controller stopped")
        except Exception as e:
            logger.error(f"Error in run loop: {e}", exc_info=True)


if __name__ == "__main__":
    controller = DisplayController()
    controller.run()
