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
import io
import threading
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
        # Live web preview: the exact frame last pushed toward the real
        # panel, copied out in update() below so the dashboard can serve
        # it as a PNG without touching the offscreen canvas the hardware
        # library owns. Lock guards the copy against a torn read while a
        # new frame is being written - cheap since frames are tiny (64x32).
        self.last_frame = None
        self.last_frame_lock = threading.Lock()
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
            # Try different hardware mappings - the test program might use a different one
            # Common options: 'regular', 'adafruit-hat', 'adafruit-hat-pwm', 'adafruit-rgb-matrix-pi'
            options.hardware_mapping = 'adafruit-hat-pwm'  # Use adafruit-hat-pwm for better flicker reduction
            
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
            
            # Verify matrix is actually initialized and can be queried
            logger.info(f"RGB Matrix initialized successfully (hardware_pulsing={use_hardware_pulsing})")
            logger.info(f"Matrix dimensions: {self.matrix.width}x{self.matrix.height}")
            logger.info(f"Matrix object type: {type(self.matrix)}")
            logger.info(f"Offscreen canvas type: {type(self.offscreen_canvas)}")
            
            
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
        """Load fonts for display. small/tiny are native-size bitmap fonts
        (see pixel_fonts.py) - PressStart2P shrunk below its 8px grid
        misrendered letters and digits."""
        from pixel_fonts import fonts as pixel_fonts
        self.fonts = pixel_fonts()
        self.font = self.fonts["large"]
        self.small_font = self.fonts["small"]
        self.tiny_font = self.fonts["tiny"]
        
        # Display is ready - no test pattern needed
            
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
        if self.image and self.draw:
            logger.debug(f"Clearing display, current image size: {self.image.size if self.image else 'None'}")
            # Fill existing image with black instead of creating a new one
            # This preserves the image reference which might be important for the offscreen canvas
            self.draw.rectangle([0, 0, self.image.width-1, self.image.height-1], fill=(0, 0, 0))
            logger.debug("Display cleared by filling with black")
        elif self.image:
            # If draw doesn't exist, recreate both
            self.image = Image.new('RGB', (self.image.width, self.image.height))
            self.draw = ImageDraw.Draw(self.image)
            logger.debug("Display cleared, new image created (draw was None)")
            
    def update(self):
        """Update the display"""
        # Captured first and unconditionally: this is the fully-drawn
        # frame for this cycle regardless of whether the real hardware
        # push below succeeds, so the web preview keeps working even if
        # MATRIX_AVAILABLE is false or a real panel isn't attached.
        if self.image:
            with self.last_frame_lock:
                self.last_frame = self.image.copy()

        if not self.matrix:
            logger.warning("Matrix not initialized, cannot update display")
            return
        if not self.offscreen_canvas:
            logger.warning("Offscreen canvas not initialized, cannot update display")
            return
        if not self.image:
            logger.warning("Image buffer not initialized, cannot update display")
            return
        try:
            # Update display
            logger.debug(f"Calling SetImage and SwapOnVSync, image size: {self.image.size if self.image else 'None'}")
            # Make sure we're using the current image reference
            current_image = self.image
            if current_image:
                self.offscreen_canvas.SetImage(current_image)
                self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)
                logger.debug("Matrix hardware update completed successfully")
            else:
                logger.error("update(): Image is None, cannot update display")
        except Exception as e:
            logger.error(f"Error updating display: {e}", exc_info=True)
            import traceback
            traceback.print_exc()

    def get_preview_png(self, scale: int = 8) -> Optional[bytes]:
        """PNG bytes of the last rendered frame, scaled up with nearest-
        neighbor so individual LEDs stay crisp blocky squares instead of
        blurring into a smooth (and misleading) image. Returns None if no
        frame has been rendered yet."""
        with self.last_frame_lock:
            frame = self.last_frame.copy() if self.last_frame else None
        if frame is None:
            return None
        scaled = frame.resize((frame.width * scale, frame.height * scale), Image.NEAREST)
        buf = io.BytesIO()
        scaled.save(buf, format='PNG')
        return buf.getvalue()
                
    def draw_text(self, text: str, x: int = None, y: int = None, 
                  color: tuple = (255, 255, 255), small: bool = False, center: bool = True, font=None, letter_spacing: int = 0):
        """Draw text on the display with optional letter spacing reduction"""
        if not self.draw:
            return
        if font is None:
            font = self.small_font if small else self.font
        
        # If letter spacing is specified (negative to reduce spacing), draw character by character
        if letter_spacing < 0:
            if x is None or center:
                # Calculate total width with reduced spacing
                total_width = 0
                for char in text:
                    bbox = self.draw.textbbox((0, 0), char, font=font)
                    char_width = bbox[2] - bbox[0]
                    total_width += char_width + letter_spacing
                total_width -= letter_spacing  # Don't add spacing after last char
                
                if x is None:
                    x = (self.image.width - total_width) // 2
                else:
                    remaining_width = self.image.width - x
                    x = x + (remaining_width - total_width) // 2
            
            if y is None:
                y = 0
            
            # Draw each character with reduced spacing
            current_x = x
            for char in text:
                self.draw.text((current_x, y), char, font=font, fill=color)
                bbox = self.draw.textbbox((0, 0), char, font=font)
                char_width = bbox[2] - bbox[0]
                current_x += char_width + letter_spacing
        else:
            # Normal drawing
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
    
    def __init__(self, config_path: str = "config/config.json"):
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
        
        # Mode state - build modes list based on enabled flags
        self.current_mode = "clock"
        self.mode_index = 0
        self._build_modes_list()

        # Auto-rotation between modes (clock/sports/stocks/weather/...).
        # display.display_durations already existed in config as a
        # per-mode seconds value (clock: 15, weather: 30, stocks: 30, ...)
        # but nothing ever read it - modes only ever changed via a manual
        # remote/API call. Mirrors the clock_locations auto-rotation
        # pattern below.
        import time as _time_mod
        self.last_mode_rotation_time = _time_mod.time()
        self.mode_display_durations = self.config.get('display', {}).get('display_durations', {})
        self.default_mode_duration = 20

        # Sub-item auto-rotation *within* a mode (weather locations,
        # stock/crypto tickers, favorite games, photos/gifs) - previously
        # only next/prev via remote control ever changed these; a mode
        # just sat on index 0 forever otherwise. Each mode's own on-screen
        # duration above is made dynamic (see _current_mode_duration) so a
        # full lap through every configured item fits before the display
        # moves to the next top-level mode, instead of truncating it.
        self.item_rotation_seconds = self.config.get('display', {}).get('item_rotation_seconds', {})
        self.last_weather_item_time = _time_mod.time()
        self.last_stock_item_time = _time_mod.time()
        self.last_sports_item_time = _time_mod.time()
        self.last_image_item_time = _time_mod.time()
        
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
        # Automatic rotation between clock_locations - manual next/prev via
        # CONTROL_ACTIONS already worked on this index, but nothing ever
        # synced it into clock_manager (a separate Clock instance that only
        # reads config["timezone"] once at init), so the display never
        # actually changed. Fixed in display_clock() below, which also
        # drives this auto-advance.
        import time as _time_mod
        self.last_clock_rotation_time = _time_mod.time()
        self.clock_rotation_interval = self.config.get('clock', {}).get('location_rotation_seconds', 8)
        
        # Sports state
        self.sports_list = self.config.get('sports', [])
        self.favorite_teams = self.config.get('favorite_teams', [])
        self.current_sport = 0
        self.current_game = 0
        self.sports_data_cache = {}  # Cache for sports scores
        self.favorites_cache = []  # Cache for favorite team games (list, not dict)
        self.last_sports_update = {}  # Track last update time per sport_id (dict)
        self.date_range_cache = {}  # Cache for date range game fetches (sport_id -> (games, timestamp))
        self.last_favorites_date_range_update = 0  # Track when we last fetched date ranges for favorites
        
        # Stocks state - separate stocks and crypto lists with sub-mode switching
        self.stocks_list = self.config.get('stocks', {}).get('symbols', [])
        self.crypto_list = self.config.get('crypto', {}).get('symbols', [])
        self.stocks_submode = "stocks"  # "stocks" or "crypto"
        self.current_stock_index = 0
        self.current_crypto_index = 0
        self.stock_data_cache = {}  # Cache for stock prices
        self.stock_update_times = {}  # ticker -> last fetch attempt
        
        # Fantasy mode state
        self.fantasy_players = self.config.get('fantasy_players', [])
        self.current_fantasy_player = 0
        self.fantasy_player_cache = {}  # Cache for player stats
        self.last_fantasy_update = 0
        # Group players by sport for cycling
        self.fantasy_sports = ['nfl', 'nba', 'nhl']  # Supported sports
        self.current_fantasy_sport_index = 0  # Current sport being displayed
        # Initialize to first available sport
        if self.fantasy_players:
            first_player_sport = self.fantasy_players[0].get('sport', 'nfl').lower()
            if first_player_sport in self.fantasy_sports:
                self.current_fantasy_sport_index = self.fantasy_sports.index(first_player_sport)
        
        # Weather state
        self.weather_locations = self.config.get('weather_locations', [])
        self.current_weather_location = 0
        self.weather_data_cache = {}  # Cache for weather data
        self.last_weather_update = 0
        
        # Images state
        self.current_image_list = "photos"  # "photos" or "gifs"
        self.current_image_index = 0
        self.photo_list = []
        self.gif_list = []
        self.current_gif_frame = 0
        self.last_gif_update = 0
        self.current_gif_image = None
        self._load_image_lists()
        
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
                def draw_text(self, text, x=None, y=None, color=(255, 255, 255), font=None, letter_spacing=0, **kwargs):
                    # Convert font parameter to small flag for MatrixDisplay
                    if font is None:
                        small = False
                    else:
                        # Check if font matches small or extra_small fonts
                        small = (font == self.small_font or font == self.extra_small_font or 
                                (hasattr(self.matrix, 'small_font') and font == self.matrix.small_font))
                    # Extract center from kwargs if present, default True
                    center = kwargs.get('center', True)
                    self.matrix.draw_text(text, x=x, y=y, color=color, small=small, center=center, font=font, letter_spacing=letter_spacing)
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
                        # Two calling conventions land here. WeatherManager
                        # passes an explicit font object and relies on this
                        # wrapper's own centering; Clock passes a plain
                        # small_font=True/False boolean and always
                        # pre-computes its own absolute x for every call
                        # (including its centered weekday line, which it
                        # centers itself via its own width math before
                        # calling here) - it never wants this wrapper's
                        # additional center-within-remaining-space-from-x
                        # recalculation layered on top. Both defaults below
                        # used to silently do the wrong thing for every
                        # Clock call: small_font landed unused in **kwargs
                        # (always rendering the oversized regular font), and
                        # center defaulted to True and re-centered text
                        # Clock had already positioned exactly, overlapping
                        # elements meant to sit side by side (time + AM/PM).
                        is_clock_call = 'small_font' in kwargs
                        if is_clock_call:
                            small = bool(kwargs['small_font'])
                        elif font is None:
                            small = False
                        else:
                            small = (font == self.small_font or font == self.extra_small_font or
                                    (hasattr(self.matrix, 'small_font') and font == self.matrix.small_font))
                        center = kwargs.get('center', False if is_clock_call else True)
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
                    def is_currently_scrolling(self):
                        # This simpler MatrixDisplay wrapper has no scroll
                        # animation or deferred-update queue - StockManager's
                        # update_stock_data() only needs a real answer here to
                        # decide whether to defer; "never scrolling" means it
                        # always proceeds straight to the update, which is
                        # correct for this wrapper.
                        return False
                    def defer_update(self, callback, priority=0):
                        # No deferred-update queue exists on this wrapper -
                        # only reachable if is_currently_scrolling() above
                        # ever returned True, which it doesn't.
                        callback()
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
            
        self.last_update = 0  # Initialize to 0 so first update happens immediately
        self.update_interval = 0.1  # Update every 0.1 seconds for smoother display and responsiveness
        
        # Preload favorites cache in background if favorite teams are configured
        if self.favorite_teams:
            def preload_favorites():
                try:
                    logger.info("Preloading favorites cache on startup...")
                    favorite_games = self._get_favorite_games()
                    self.favorites_cache = favorite_games
                    self.last_favorites_date_range_update = time.time()
                    logger.info(f"Preloaded {len(favorite_games)} favorite games on startup")
                except Exception as e:
                    logger.error(f"Error preloading favorites cache: {e}")
                    import traceback
                    traceback.print_exc()
            
            import threading
            preload_thread = threading.Thread(target=preload_favorites, daemon=True)
            preload_thread.start()
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        default_config = {
            "brightness": 50,
            "timezone": "America/New_York",
            "clock_locations": [],
            "sports": [],
            "stocks": [],
            "crypto": [],
            "fantasy_players": [],
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
            config_path = getattr(self, "config_path", "config/config.json")
            if not os.path.isabs(config_path):
                script_dir = os.path.dirname(os.path.abspath(__file__))
                config_path = os.path.join(script_dir, config_path)
            logger.info(f"Reloading config from: {config_path}")
            self.config = self._load_config(config_path)
            # Update state from new config
            self.clock_locations = self.config.get('clock_locations', [])
            self.sports_list = self.config.get('sports', [])
            self.favorite_teams = self.config.get('favorite_teams', [])
            # Clamp current_sport to valid range after config reload
            effective_list = self._get_effective_sports_list()
            if effective_list and self.current_sport >= len(effective_list):
                self.current_sport = 0
                self.current_game = 0
            self.stocks_list = self.config.get('stocks', {}).get('symbols', [])
            self.crypto_list = self.config.get('crypto', {}).get('symbols', [])
            # Reset indices if lists changed
            if self.current_stock_index >= len(self.stocks_list):
                self.current_stock_index = 0
            if self.current_crypto_index >= len(self.crypto_list):
                self.current_crypto_index = 0
            self.fantasy_players = self.config.get('fantasy_players', [])
            if self.current_fantasy_player >= len(self.fantasy_players):
                self.current_fantasy_player = 0
            # Reset to first available sport if needed
            if self.fantasy_players:
                first_player_sport = self.fantasy_players[0].get('sport', 'nfl').lower()
                if first_player_sport in self.fantasy_sports:
                    self.current_fantasy_sport_index = self.fantasy_sports.index(first_player_sport)
            self.weather_locations = self.config.get('weather_locations', [])
            # Reload image lists
            self._load_image_lists()
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
            
            # Rebuild modes list based on enabled flags
            old_modes = self.modes.copy()
            self._build_modes_list()
            self.mode_display_durations = self.config.get('display', {}).get('display_durations', {})
            
            # If modes changed, adjust current mode if needed
            if old_modes != self.modes:
                if self.current_mode not in self.modes:
                    # Current mode was disabled, switch to clock
                    self.current_mode = "clock"
                    self.mode_index = 0
                    logger.info(f"Mode '{self.current_mode}' was disabled, switching to clock")
                else:
                    # Update mode_index to match new modes list
                    self.mode_index = self.modes.index(self.current_mode)
            
            fantasy_enabled = self.config.get('fantasy_mode', {}).get('enabled', True)
            stocks_enabled = self.config.get('stocks_mode', {}).get('enabled', True)
            weather_enabled = self.config.get('weather_mode', {}).get('enabled', True)
            
            logger.info(f"Configuration reloaded: sports={len(self.sports_list)}, stocks={len(self.stocks_list)}, crypto={len(self.crypto_list)}, weather={len(self.weather_locations)}, fantasy_enabled={fantasy_enabled}, stocks_enabled={stocks_enabled}, weather_enabled={weather_enabled}, music_enabled={music_enabled}")
        except Exception as e:
            logger.error(f"Error reloading config: {e}")
            
    def _item_interval(self, key: str, default: float) -> float:
        """Seconds to show one item of a sub-rotated list (weather
        location, ticker, game, photo/gif) before advancing to the next.
        Config override lives at display.item_rotation_seconds.<key>."""
        return self.item_rotation_seconds.get(key, default)

    def _build_modes_list(self):
        """Build the modes list based on enabled flags in config"""
        modes = ["clock", "sports"]  # Always enabled
        
        # Check fantasy mode
        fantasy_config = self.config.get('fantasy_mode', {})
        if fantasy_config.get('enabled', True):  # Default to enabled
            modes.append("fantasy")
        
        # Check stocks mode
        stocks_config = self.config.get('stocks_mode', {})
        if stocks_config.get('enabled', True):  # Default to enabled
            modes.append("stocks")
        
        # Check weather mode
        weather_config = self.config.get('weather_mode', {})
        if weather_config.get('enabled', True):  # Default to enabled
            modes.append("weather")
        
        # Check music mode
        music_config = self.config.get('music', {})
        if music_config.get('enabled', False):
            modes.append("music")
        
        # Always include images and brightness
        modes.extend(["images", "brightness"])
        
        self.modes = modes
        logger.info(f"Built modes list: {self.modes}")
        
        # Adjust mode_index if current mode is no longer in list
        if self.current_mode not in self.modes:
            self.current_mode = "clock"
            self.mode_index = 0
    
    def _reset_item_rotation(self, mode: str):
        """Start a fresh, complete lap through a mode's own sub-items
        (weather locations / tickers / games / photos-gifs) every time
        that mode becomes active, so the dynamic duration computed in
        _current_mode_duration() always covers item 0 through the end -
        continuing from a stale mid-list index would risk showing some
        items twice and others not at all within a single visit."""
        now = time.time()
        if mode == 'weather':
            self.current_weather_location = 0
            self.last_weather_item_time = now
        elif mode == 'stocks':
            self.current_stock_index = 0
            self.current_crypto_index = 0
            self.stocks_submode = "stocks"
            self.last_stock_item_time = now
        elif mode == 'sports':
            self.current_sport = 0
            self.current_game = 0
            self.last_sports_item_time = now
        elif mode == 'images':
            self.current_image_list = "photos"
            self.current_image_index = 0
            self.last_image_item_time = now

    def set_mode(self, mode: str):
        """Set the current display mode"""
        if mode in self.modes:
            self.current_mode = mode
            self.mode_index = self.modes.index(mode)
            self.last_mode_rotation_time = time.time()
            self._reset_item_rotation(mode)
            logger.info(f"Mode changed to: {mode}")
            
    def cycle_mode(self, direction: int = 1):
        """Cycle to next/previous mode"""
        self.mode_index = (self.mode_index + direction) % len(self.modes)
        self.current_mode = self.modes[self.mode_index]
        self.last_mode_rotation_time = time.time()
        self._reset_item_rotation(self.current_mode)
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
    def _get_effective_sports_list(self):
        """Get sports list with favorites prepended if they exist"""
        effective_list = []
        # Add favorites as first item if any favorites exist
        if self.favorite_teams and len(self.favorite_teams) > 0:
            effective_list.append({'name': 'FAVORITES', 'id': 'favorites', 'is_favorites': True})
        # Add regular sports
        effective_list.extend(self.sports_list)
        return effective_list
    
    @staticmethod
    def _canonical_sport(sport):
        sport = (sport or '').lower().strip()
        if sport in ['ncaam', 'ncaab', 'mens-college-basketball', 'college-basketball']:
            return 'ncaam'
        if sport in ['ncaaf', 'college-football']:
            return 'ncaaf'
        return sport

    @staticmethod
    def _has_active_game(games):
        """True if any game is live, or scheduled to have started within the
        last 5 hours but not yet marked final - those need fast refreshes."""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        for g in games or []:
            if g.get('is_live'):
                return True
            if g.get('is_final'):
                continue
            try:
                start = datetime.fromisoformat((g.get('date') or '').replace('Z', '+00:00'))
                if start.tzinfo and now - timedelta(hours=5) <= start <= now:
                    return True
            except ValueError:
                continue
        return False

    def _favorites_cache_ttl(self):
        return 60 if self._has_active_game(self.favorites_cache) else 300

    def _get_favorite_games(self):
        """Get all games involving favorite teams, including closest previous/next games"""
        favorite_games = []
        if not self.favorite_teams or len(self.favorite_teams) == 0:
            logger.debug("No favorite teams configured")
            return favorite_games
        
        # Get favorite teams with their sports
        favorite_teams_by_sport = {}
        for fav in self.favorite_teams:
            sport = fav.get('sport', '').lower().strip()
            team_abbr = fav.get('team', '').upper().strip()
            if sport and team_abbr:
                # Normalize sport names for consistency
                sport = self._canonical_sport(sport)
                if sport not in favorite_teams_by_sport:
                    favorite_teams_by_sport[sport] = set()
                favorite_teams_by_sport[sport].add(team_abbr)
        
        if not favorite_teams_by_sport:
            logger.debug("No valid favorite teams found")
            return favorite_games
        
        logger.debug(f"Looking for favorite teams by sport: {favorite_teams_by_sport}")
        
        # Get current time for comparison
        from datetime import datetime
        now = datetime.now()
        current_time = time.time()
        
        # Cache date range fetches for 10 minutes to avoid blocking
        DATE_RANGE_CACHE_TTL = 600  # 10 minutes
        
        # For each sport with favorite teams, fetch games from a date range (with caching)
        for sport_id, team_set in favorite_teams_by_sport.items():
            try:
                # Check cache first
                cached_data = self.date_range_cache.get(sport_id)
                all_games = None
                
                cache_ttl = 60 if cached_data and self._has_active_game(cached_data[0]) else DATE_RANGE_CACHE_TTL
                if cached_data and (current_time - cached_data[1]) < cache_ttl:
                    # Use cached data
                    all_games = cached_data[0]
                    logger.debug(f"Using cached date range games for {sport_id} ({len(all_games)} games)")
                else:
                    # Fetch games using sport-specific date ranges
                    from sports_fetcher import fetch_espn_scores_for_date_range, fetch_espn_scores_for_week, fetch_ncaaf_games_with_week_iteration
                    
                    if sport_id == 'nfl':
                        # NFL: last week + this week. This used to reuse
                        # sports_data_cache['nfl'], which nothing refreshes
                        # when only favorites are shown - Sunday's games sat
                        # at 0-0 "scheduled" for days after they ended.
                        from sports_fetcher import fetch_nfl_recent_weeks
                        all_games = fetch_nfl_recent_weeks()
                        logger.info(f"Fetched NFL games for last week + this week ({len(all_games)} games)")
                    elif sport_id == 'ncaaf':
                        # NCAAF: For each favorite team, iterate through weeks until games found
                        all_games = []
                        for team_abbr in team_set:
                            team_games = fetch_ncaaf_games_with_week_iteration(team_abbr, max_weeks_back=4)
                            all_games.extend(team_games)
                        # Remove duplicates
                        seen_games = set()
                        unique_games = []
                        for game in all_games:
                            game_key = (
                                game.get('date', ''),
                                game.get('home_team', ''),
                                game.get('away_team', '')
                            )
                            if game_key not in seen_games:
                                seen_games.add(game_key)
                                unique_games.append(game)
                        all_games = unique_games
                        logger.info(f"Fetched NCAAF games for favorite teams ({len(all_games)} unique games)")
                    elif sport_id in ['nba', 'nhl']:
                        # NBA/NHL: Previous day, today, next day (3 days)
                        all_games = fetch_espn_scores_for_date_range(sport_id, days_back=1, days_forward=1)
                        logger.info(f"Fetched {sport_id} games for previous day, today, next day ({len(all_games)} games)")
                    elif sport_id in ['ncaam', 'ncaab']:
                        # NCAAM: Previous 2 days, next 5 days (7 days)
                        # Use 'ncaam' as the canonical sport_id for fetching
                        all_games = fetch_espn_scores_for_date_range('ncaam', days_back=2, days_forward=5)
                        logger.info(f"Fetched ncaam games for previous 2 days, next 5 days ({len(all_games)} games)")
                    else:
                        # Default: 3 days back, 7 days forward
                        all_games = fetch_espn_scores_for_date_range(sport_id, days_back=3, days_forward=7)
                        logger.info(f"Fetched {sport_id} games with default date range ({len(all_games)} games)")
                    
                    # Cache the results
                    self.date_range_cache[sport_id] = (all_games, current_time)
                    logger.info(f"Cached {len(all_games)} games for {sport_id}")
                
                # For each favorite team in this sport, find closest previous and next games
                for team_abbr in team_set:
                    team_games = []
                    for game in all_games:
                        away_team = game.get('away_team', '').upper().strip()
                        home_team = game.get('home_team', '').upper().strip()
                        if away_team == team_abbr or home_team == team_abbr:
                            # Parse game date
                            game_date = None
                            date_str = game.get('date', '')
                            if date_str:
                                try:
                                    # Parse ISO format date
                                    if 'Z' in date_str:
                                        game_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                    elif '+' in date_str or date_str.count('-') >= 3:
                                        game_date = datetime.fromisoformat(date_str)
                                    else:
                                        # Try parsing as YYYY-MM-DDTHH:MM:SS
                                        game_date = datetime.fromisoformat(date_str.split('.')[0])
                                    
                                    # Make timezone-naive for comparison
                                    if game_date.tzinfo:
                                        game_date = game_date.replace(tzinfo=None)
                                except Exception as e:
                                    logger.debug(f"Error parsing date '{date_str}': {e}")
                                    continue
                            
                            if game_date:
                                game['_parsed_date'] = game_date
                                game['_time_diff'] = (game_date - now).total_seconds()
                                team_games.append(game)
                    
                    # Find closest previous and next games
                    previous_games = [g for g in team_games if g.get('_time_diff', 0) < 0]  # Past games
                    next_games = [g for g in team_games if g.get('_time_diff', 0) >= 0]  # Future/current games
                    
                    # Sort previous games by date (most recent first)
                    previous_games.sort(key=lambda g: g.get('_time_diff', 0), reverse=True)
                    # Sort next games by date (soonest first)
                    next_games.sort(key=lambda g: g.get('_time_diff', 0))
                    
                    # Add closest previous game (if any)
                    if previous_games:
                        closest_previous = previous_games[0].copy()
                        closest_previous['sport_id'] = sport_id
                        closest_previous['_is_closest_previous'] = True
                        favorite_games.append(closest_previous)
                        logger.debug(f"Found closest previous game for {team_abbr}: {closest_previous.get('away_team')} @ {closest_previous.get('home_team')} on {closest_previous.get('date', '')[:10]}")
                    
                    # Add closest next game (if any)
                    if next_games:
                        closest_next = next_games[0].copy()
                        closest_next['sport_id'] = sport_id
                        closest_next['_is_closest_next'] = True
                        favorite_games.append(closest_next)
                        logger.debug(f"Found closest next game for {team_abbr}: {closest_next.get('away_team')} @ {closest_next.get('home_team')} on {closest_next.get('date', '')[:10]}")
                    
                    # Also add any live games for this team (they might not be closest)
                    for game in team_games:
                        if game.get('is_live', False):
                            game_copy = game.copy()
                            game_copy['sport_id'] = sport_id
                            # Check if we already added this game
                            if not any(
                                g.get('away_team') == game_copy.get('away_team') and
                                g.get('home_team') == game_copy.get('home_team') and
                                g.get('date') == game_copy.get('date')
                                for g in favorite_games
                            ):
                                favorite_games.append(game_copy)
                                logger.debug(f"Found live game for {team_abbr}: {game_copy.get('away_team')} @ {game_copy.get('home_team')}")
                
            except Exception as e:
                logger.error(f"Error fetching games for favorite sport {sport_id}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Also check games already in cache (for today's games that might already be loaded).
        # Matched per sport: abbreviations repeat across leagues (DAL, TB,
        # CHI, TEX...), and matching them league-blind pulled Bears, Stars,
        # Wings and Longhorns games into the favorites rotation.
        for sport_id in self.sports_data_cache.keys():
            favorite_team_set = favorite_teams_by_sport.get(self._canonical_sport(sport_id), set())
            games = self.sports_data_cache.get(sport_id, [])
            for game in games:
                away_team = game.get('away_team', '').upper().strip()
                home_team = game.get('home_team', '').upper().strip()
                if away_team in favorite_team_set or home_team in favorite_team_set:
                    # Check if we already added this game
                    if not any(
                        g.get('away_team') == game.get('away_team') and
                        g.get('home_team') == game.get('home_team') and
                        g.get('date') == game.get('date')
                        for g in favorite_games
                    ):
                        game_copy = game.copy()
                        game_copy['sport_id'] = sport_id
                        favorite_games.append(game_copy)
                        logger.debug(f"Found cached favorite game: {away_team} @ {home_team} ({sport_id})")
        
        # Sort: live games first, then scheduled (by date), then finished (by date, most recent first)
        favorite_games.sort(key=lambda g: (
            0 if g.get('is_live', False) else (1 if g.get('is_scheduled', False) else 2),
            g.get('_time_diff', 0) if g.get('_time_diff') is not None else (999999999 if g.get('is_scheduled') else -999999999)
        ))
        
        logger.info(f"Found {len(favorite_games)} total favorite games (including closest previous/next)")
        return favorite_games
    
    def next_sport(self):
        """Next sport"""
        effective_list = self._get_effective_sports_list()
        if effective_list:
            self.current_sport = (self.current_sport + 1) % len(effective_list)
            # Only reset game index if switching away from favorites
            current_sport_item = effective_list[(self.current_sport - 1) % len(effective_list)] if effective_list else None
            if not (isinstance(current_sport_item, dict) and current_sport_item.get('is_favorites', False)):
                self.current_game = 0
            logger.info(f"Sport: {self.current_sport}")
            
    def prev_sport(self):
        """Previous sport"""
        effective_list = self._get_effective_sports_list()
        if effective_list:
            self.current_sport = (self.current_sport - 1) % len(effective_list)
            # Only reset game index if switching away from favorites
            current_sport_item = effective_list[(self.current_sport + 1) % len(effective_list)] if effective_list else None
            if not (isinstance(current_sport_item, dict) and current_sport_item.get('is_favorites', False)):
                self.current_game = 0
            logger.info(f"Sport: {self.current_sport}")
            
    def next_game(self):
        """Next game in current sport - loops back to first game"""
        effective_list = self._get_effective_sports_list()
        
        # Clamp current_sport to valid range
        if effective_list and self.current_sport >= len(effective_list):
            self.current_sport = 0
        
        sport = effective_list[self.current_sport] if effective_list and self.current_sport < len(effective_list) else None
        
        # Check if this is favorites
        if isinstance(sport, dict) and sport.get('is_favorites', False):
            # Use cached favorite games if available and fresh (cache for 5 minutes)
            current_time = time.time()
            FAVORITES_CACHE_TTL = self._favorites_cache_ttl()  # 60s while a favorite is live, else 5 min
            
            if (isinstance(self.favorites_cache, list) and 
                len(self.favorites_cache) > 0 and
                (current_time - self.last_favorites_date_range_update) < FAVORITES_CACHE_TTL):
                # Use cached favorite games
                favorite_games = self.favorites_cache
                logger.debug(f"Using cached favorite games ({len(favorite_games)} games)")
            else:
                # Only fetch today's games for favorite sports (quick fetch)
                favorite_sports = set()
                for fav in self.favorite_teams:
                    favorite_sports.add(fav.get('sport', '').lower())
                
                for sport_id in favorite_sports:
                    if sport_id and (sport_id not in self.sports_data_cache or 
                                     current_time - self.last_sports_update.get(sport_id, 0) > 60):
                        try:
                            from sports_fetcher import fetch_espn_scores
                            games = fetch_espn_scores(sport_id)
                            if games:
                                self.sports_data_cache[sport_id] = games
                                self.last_sports_update[sport_id] = time.time()
                                logger.info(f"Fetched {len(games)} games for favorite sport {sport_id}")
                        except Exception as e:
                            logger.error(f"Error fetching games for favorite sport {sport_id}: {e}")
                
                # Get fresh favorite games list (this will use date range cache if available)
                favorite_games = self._get_favorite_games()
                self.favorites_cache = favorite_games
                self.last_favorites_date_range_update = current_time
            
            if favorite_games and len(favorite_games) > 0:
                old_game = self.current_game
                self.current_game = (self.current_game + 1) % len(favorite_games)
                logger.info(f"Favorite game: {old_game} -> {self.current_game} (total: {len(favorite_games)})")
                # Force immediate display update
                self.matrix.clear()
                try:
                    self.display_sports()
                except Exception as e:
                    logger.error(f"Error updating display after next_game (favorites): {e}")
            else:
                logger.warning(f"No favorite games available (count: {len(favorite_games) if favorite_games else 0})")
            return
        
        # Get current sport's games to determine loop
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
                        self.last_sports_update[sport_id] = time.time()
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
        effective_list = self._get_effective_sports_list()
        
        # Clamp current_sport to valid range
        if effective_list and self.current_sport >= len(effective_list):
            self.current_sport = 0
        
        sport = effective_list[self.current_sport] if effective_list and self.current_sport < len(effective_list) else None
        
        # Check if this is favorites
        if isinstance(sport, dict) and sport.get('is_favorites', False):
            # Use cached favorite games if available and fresh (cache for 5 minutes)
            current_time = time.time()
            FAVORITES_CACHE_TTL = self._favorites_cache_ttl()  # 60s while a favorite is live, else 5 min
            
            if (isinstance(self.favorites_cache, list) and 
                len(self.favorites_cache) > 0 and
                (current_time - self.last_favorites_date_range_update) < FAVORITES_CACHE_TTL):
                # Use cached favorite games
                favorite_games = self.favorites_cache
                logger.debug(f"Using cached favorite games ({len(favorite_games)} games)")
            else:
                # Only fetch today's games for favorite sports (quick fetch)
                favorite_sports = set()
                for fav in self.favorite_teams:
                    favorite_sports.add(fav.get('sport', '').lower())
                
                for sport_id in favorite_sports:
                    if sport_id and (sport_id not in self.sports_data_cache or 
                                     current_time - self.last_sports_update.get(sport_id, 0) > 60):
                        try:
                            from sports_fetcher import fetch_espn_scores
                            games = fetch_espn_scores(sport_id)
                            if games:
                                self.sports_data_cache[sport_id] = games
                                self.last_sports_update[sport_id] = time.time()
                                logger.info(f"Fetched {len(games)} games for favorite sport {sport_id}")
                        except Exception as e:
                            logger.error(f"Error fetching games for favorite sport {sport_id}: {e}")
                
                # Get fresh favorite games list (this will use date range cache if available)
                favorite_games = self._get_favorite_games()
                self.favorites_cache = favorite_games
                self.last_favorites_date_range_update = current_time
            
            if favorite_games and len(favorite_games) > 0:
                old_game = self.current_game
                self.current_game = (self.current_game - 1) % len(favorite_games)
                logger.info(f"Favorite game: {old_game} -> {self.current_game} (total: {len(favorite_games)})")
                # Force immediate display update
                self.matrix.clear()
                try:
                    self.display_sports()
                except Exception as e:
                    logger.error(f"Error updating display after prev_game (favorites): {e}")
            else:
                logger.warning(f"No favorite games available (count: {len(favorite_games) if favorite_games else 0})")
            return
        
        # Get current sport's games to determine loop
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
                        self.last_sports_update[sport_id] = time.time()
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
    def switch_stocks_submode(self):
        """Switch between stocks and crypto sub-modes"""
        if self.stocks_submode == "stocks":
            if self.crypto_list and len(self.crypto_list) > 0:
                self.stocks_submode = "crypto"
                logger.info("Switched to crypto sub-mode")
            else:
                logger.info("No crypto configured, staying in stocks")
        else:
            if self.stocks_list and len(self.stocks_list) > 0:
                self.stocks_submode = "stocks"
                logger.info("Switched to stocks sub-mode")
            else:
                logger.info("No stocks configured, staying in crypto")
    
    def next_ticker(self):
        """Next stock/crypto ticker in current sub-mode"""
        if self.stocks_submode == "stocks":
            if self.stocks_list:
                self.current_stock_index = (self.current_stock_index + 1) % len(self.stocks_list)
                logger.info(f"Stock: {self.current_stock_index}")
        else:  # crypto
            if self.crypto_list:
                self.current_crypto_index = (self.current_crypto_index + 1) % len(self.crypto_list)
                logger.info(f"Crypto: {self.current_crypto_index}")
            
    def prev_ticker(self):
        """Previous stock/crypto ticker in current sub-mode"""
        if self.stocks_submode == "stocks":
            if self.stocks_list:
                self.current_stock_index = (self.current_stock_index - 1) % len(self.stocks_list)
                logger.info(f"Stock: {self.current_stock_index}")
        else:  # crypto
            if self.crypto_list:
                self.current_crypto_index = (self.current_crypto_index - 1) % len(self.crypto_list)
                logger.info(f"Crypto: {self.current_crypto_index}")
            
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
    
    # Images mode controls
    def _load_image_lists(self):
        """Load list of photos and GIFs from assets directories"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        photo_dir = os.path.join(script_dir, "assets", "photo_list")
        gif_dir = os.path.join(script_dir, "assets", "gif_list")
        
        self.photo_list = []
        self.gif_list = []
        
        # Load photos
        if os.path.exists(photo_dir):
            for filename in sorted(os.listdir(photo_dir)):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    self.photo_list.append(os.path.join(photo_dir, filename))
        
        # Load GIFs
        if os.path.exists(gif_dir):
            for filename in sorted(os.listdir(gif_dir)):
                if filename.lower().endswith('.gif'):
                    self.gif_list.append(os.path.join(gif_dir, filename))
        
        logger.info(f"Loaded {len(self.photo_list)} photos and {len(self.gif_list)} GIFs")
    
    def switch_image_list(self):
        """Switch between photos and GIFs lists"""
        if self.current_image_list == "photos":
            self.current_image_list = "gifs"
            self.current_image_index = 0
            self.current_gif_frame = 0
            self.current_gif_image = None
        else:
            self.current_image_list = "photos"
            self.current_image_index = 0
        logger.info(f"Switched to {self.current_image_list} list")
    
    def next_image(self):
        """Next image in current list"""
        if self.current_image_list == "photos":
            if self.photo_list:
                self.current_image_index = (self.current_image_index + 1) % len(self.photo_list)
                logger.info(f"Photo: {self.current_image_index}")
        else:
            if self.gif_list:
                self.current_image_index = (self.current_image_index + 1) % len(self.gif_list)
                self.current_gif_frame = 0
                self.current_gif_image = None
                logger.info(f"GIF: {self.current_image_index}")
    
    def prev_image(self):
        """Previous image in current list"""
        if self.current_image_list == "photos":
            if self.photo_list:
                self.current_image_index = (self.current_image_index - 1) % len(self.photo_list)
                logger.info(f"Photo: {self.current_image_index}")
        else:
            if self.gif_list:
                self.current_image_index = (self.current_image_index - 1) % len(self.gif_list)
                self.current_gif_frame = 0
                self.current_gif_image = None
                logger.info(f"GIF: {self.current_image_index}")
            
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
        
    def _resolve_current_clock_timezone(self):
        """The timezone for whichever clock_locations entry is selected,
        falling back to the single top-level config timezone when no
        locations are configured."""
        if self.clock_locations and self.current_clock_location < len(self.clock_locations):
            location = self.clock_locations[self.current_clock_location]
            if isinstance(location, dict):
                tz_str = location.get("timezone", location.get("tz", ""))
            elif isinstance(location, str):
                tz_str = location
            else:
                tz_str = str(location)
            if tz_str:
                try:
                    return pytz.timezone(tz_str)
                except Exception as e:
                    logger.warning(f"Invalid timezone '{tz_str}' for clock_locations[{self.current_clock_location}], using default: {e}")
        return self.clock_timezone

    def display_clock(self):
        """Display clock mode"""
        import time as _time_mod
        just_rotated = False
        if len(self.clock_locations) > 1:
            elapsed = _time_mod.time() - self.last_clock_rotation_time
            if elapsed >= self.clock_rotation_interval:
                self.next_clock_location()
                self.last_clock_rotation_time = _time_mod.time()
                just_rotated = True

        if self.clock_manager:
            try:
                # Keep the shared Clock instance's timezone in sync with
                # whichever clock_locations entry is currently selected -
                # it has no other way to know this index exists.
                self.clock_manager.timezone = self._resolve_current_clock_timezone()
                # force_clear so the redraw isn't skipped by display_time()'s
                # own change-detection on the rare chance the new zone's
                # time/date string happens to match what was last drawn.
                self.clock_manager.display_time(force_clear=just_rotated)
            except Exception as e:
                logger.error(f"Error displaying clock: {e}")
                # Fall through to fallback
                self._display_clock_fallback()
        else:
            self._display_clock_fallback()
            
    def _display_clock_fallback(self):
        """Fallback clock display"""
        try:
            if not self.matrix:
                logger.error("Matrix not initialized in _display_clock_fallback")
                return
            logger.debug("_display_clock_fallback: Starting clock display")
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
            logger.debug(f"Clock display: time={time_str}, date={date_str}, tz={tz_abbr}")
            self.matrix.update()
        except Exception as e:
            logger.error(f"Error in clock fallback: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            # Show error on display
            try:
                if self.matrix:
                    self.matrix.clear()
                    self.matrix.draw_text("CLOCK ERR", y=10, color=(255, 0, 0))
                    self.matrix.update()
            except Exception as display_err:
                logger.error(f"Error showing clock error on display: {display_err}")
            
    # ------------------------------------------------------------------
    # Shared drawing helpers (sports + stocks). Both sports paths
    # (favorites and per-league) used to carry their own ~200-line copy of
    # the game layout; they now both call _draw_game.
    # ------------------------------------------------------------------

    def _fit_font(self, text, max_width, ladder=("large", "medium", "small", "tiny")):
        """Largest font from the ladder whose rendering of text fits max_width."""
        fonts = self.matrix.fonts
        for name in ladder:
            font = fonts[name]
            if self._text_width(text, font) <= max_width:
                return font
        return fonts[ladder[-1]]

    def _text_width(self, text, font):
        bbox = self.matrix.draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

    def _text_height(self, font):
        bbox = self.matrix.draw.textbbox((0, 0), "0A", font=font)
        return bbox[3]

    def _draw_label(self, text, font, color, x=None, y=0, center_x=None, outline=True, clamp=(0, 64)):
        """Draw text at x, or centered on center_x (default: panel center),
        kept inside the clamp range, with an optional 1px black outline so it
        stays readable over a logo."""
        draw = self.matrix.draw
        width = self._text_width(text, font)
        if x is None:
            cx = self.matrix.image.width / 2 if center_x is None else center_x
            x = int(round(cx - width / 2))
        x = max(clamp[0], min(x, clamp[1] - width))
        if outline:
            for dx, dy in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)):
                draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0))
        draw.text((x, y), text, font=font, fill=color)

    @staticmethod
    def _fit_logo(img, size, max_aspect=None):
        """Crop a logo to its visible pixels and scale it to fit size x size,
        keeping its aspect ratio - most source logos carry transparent padding
        that made them render far smaller than their slot. Returns None when
        max_aspect is set and the visible logo is wider than that (wordmarks
        like 'intel' or 'charles SCHWAB' are unreadable at ~20px)."""
        if img is None:
            return None
        img = img.convert('RGBA')
        alpha_box = img.getchannel('A').getbbox()
        if alpha_box:
            img = img.crop(alpha_box)
        if img.width and img.height and max_aspect and img.width / img.height > max_aspect:
            return None
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        return img

    def _paste_logo(self, img, box_x, box_y, size):
        """Paste an already-fitted logo centered inside a size x size box."""
        if img is None:
            return
        x = box_x + (size - img.width) // 2
        y = box_y + (size - img.height) // 2
        self.matrix.image.paste(img, (x, y), img)

    @staticmethod
    def _team_label(name):
        """ESPN puts placeholder names ("Yankees/Red Sox", "TBD") in the
        abbreviation slot for undecided playoff matchups."""
        name = (name or '').strip()
        if not name or '/' in name or len(name) > 5:
            return 'TBD'
        return name.upper()

    def _local_game_time(self, date_str):
        from datetime import datetime
        import pytz
        game_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        if game_date.tzinfo:
            try:
                local_tz = pytz.timezone(self.config.get('local_timezone', 'America/New_York'))
            except pytz.exceptions.UnknownTimeZoneError:
                local_tz = pytz.timezone('America/New_York')
            game_date = game_date.astimezone(local_tz)
        return game_date

    def _game_status(self, game):
        """(text, color) for the status row: FINAL / live clock / start time."""
        status_id = (game.get('status_id') or '').upper()
        short = (game.get('status_short_detail') or '').strip()
        if 'POSTPONED' in status_id:
            return 'PPD', (255, 160, 0)
        if 'CANCEL' in status_id:
            return 'CANCELED', (255, 160, 0)
        if 'FINAL' in status_id or game.get('is_final'):
            # "Final/OT", "Final/10" keep their extra-time marker
            text = short.upper() if short.upper().startswith('FINAL') else 'FINAL'
            return text, (200, 200, 200)
        if game.get('is_live') or any(s in status_id for s in ('IN_PROGRESS', 'HALFTIME', 'DELAYED', 'END_PERIOD')):
            down_distance = game.get('down_distance_text', '')
            text = down_distance or short or game.get('status_detail', '') or 'LIVE'
            text = (text.replace(' - ', ' ').replace('Quarter', 'Q').replace('Halftime', 'HALF')
                        .replace('1st', '1ST').replace('2nd', '2ND').replace('3rd', '3RD').replace('4th', '4TH'))
            return text.upper(), (255, 80, 80)
        date_str = game.get('date', '')
        if date_str:
            try:
                from datetime import datetime
                game_date = self._local_game_time(date_str)
                hour = game_date.hour % 12 or 12
                ampm = 'A' if game_date.hour < 12 else 'P'
                clock = f"{hour}{ampm}M" if game_date.minute == 0 else f"{hour}:{game_date.minute:02d}{ampm}"
                if game_date.date() == datetime.now(game_date.tzinfo).date():
                    return f"TODAY {clock}", (255, 255, 255)
                return f"{game_date.month}/{game_date.day} {clock}", (255, 255, 255)
            except Exception as e:
                logger.debug(f"Error parsing game date '{date_str}': {e}")
        return (short or 'SCHEDULED').upper(), (255, 255, 255)

    def _draw_game(self, game, sport_id_for_logos):
        """One game on the 64x32 panel:
            y=0-6    status (FINAL / live clock / start time), full width
            y=7-24   18px logos at both edges, score large in the 28px gap
            y=25-31  team abbreviations under their logos
        """
        if not self.matrix.draw:
            return
        W = self.matrix.image.width
        LOGO, LOGO_Y = 18, 7
        fonts = self.matrix.fonts

        away = self._team_label(game.get('away_team'))
        home = self._team_label(game.get('home_team'))

        if self.asset_loader:
            for side, abbr, box_x in (('away', away, 0), ('home', home, W - LOGO)):
                if abbr == 'TBD':
                    continue
                try:
                    logo = self.asset_loader.get_sport_logo(
                        sport_id_for_logos, abbr, logo_url=game.get(f'{side}_logo_url', ''))
                    self._paste_logo(self._fit_logo(logo, LOGO), box_x, LOGO_Y, LOGO)
                except Exception as e:
                    logger.error(f"Could not display {side} logo for {abbr}: {e}")

        status_text, status_color = self._game_status(game)
        status_font = self._fit_font(status_text, W, ("small", "tiny"))
        if self._text_width(status_text, status_font) > W:
            status_text = status_text[:W // 4]
        self._draw_label(status_text, status_font, status_color, y=0, outline=False)

        if not game.get('is_scheduled') or game.get('is_live') or game.get('is_final'):
            score_text = f"{game.get('away_score', 0) or 0}-{game.get('home_score', 0) or 0}"
            gap = W - 2 * LOGO
            score_font = self._fit_font(score_text, gap + 2)
            score_y = LOGO_Y + (LOGO - self._text_height(score_font)) // 2
            self._draw_label(score_text, score_font, (255, 255, 0), y=score_y)
        else:
            self._draw_label('@', fonts['small'], (150, 150, 150), y=LOGO_Y + 5)

        abbr_y = LOGO_Y + LOGO
        for abbr, center_x, clamp in ((away, LOGO / 2, (0, W // 2)), (home, W - LOGO / 2, (W // 2, W))):
            font = self._fit_font(abbr, W // 2, ("small", "tiny"))
            self._draw_label(abbr, font, (0, 255, 255), y=abbr_y, center_x=center_x, clamp=clamp, outline=False)

    def display_sports(self):
        """Display sports mode with actual scores"""
        # Clear the image buffer completely before drawing
        self.matrix.clear()
        # Ensure the clear is applied immediately by recreating the image
        if self.matrix.image:
            self.matrix.image = Image.new('RGB', (self.matrix.image.width, self.matrix.image.height))
            self.matrix.draw = ImageDraw.Draw(self.matrix.image)

        now = time.time()
        if now - self.last_sports_item_time >= self._item_interval('sports', 8):
            # Set BEFORE calling next_game(): next_game() recursively
            # calls display_sports() itself (for instant remote-control
            # feedback), and that re-entrant call runs this same check
            # again. Setting the timestamp first makes the re-entrant call
            # see an unexpired timer and skip - without this, one real 8s
            # tick spiraled into hundreds of advances within milliseconds.
            self.last_sports_item_time = now
            prev_game = self.current_game
            self.next_game()
            # Wrapped back to game 0 (or there was only ever one game) -
            # also step to the next configured sport/favorites entry so a
            # continuous cycle eventually shows every game AND every
            # sport, not just the first sport's games forever.
            if self.current_game <= prev_game:
                effective_list_for_wrap = self._get_effective_sports_list()
                if len(effective_list_for_wrap) > 1:
                    self.next_sport()

        effective_list = self._get_effective_sports_list()
        logger.debug(f"display_sports: effective_list length={len(effective_list)}, current_sport={self.current_sport}")
        
        # Clamp current_sport to valid range
        if effective_list and self.current_sport >= len(effective_list):
            logger.warning(f"current_sport {self.current_sport} out of bounds, clamping to 0 (effective_list length={len(effective_list)})")
            self.current_sport = 0
            self.current_game = 0
        
        if not effective_list or len(effective_list) == 0:
            logger.warning(f"No sports configured: effective_list length={len(effective_list)}")
            self.matrix.draw_text("NO SPORTS", y=10, color=(255, 0, 0), small=True, center=True)
            self.matrix.update()
            return
            
        sport = effective_list[self.current_sport]
        
        # Check if this is the favorites page
        if isinstance(sport, dict) and sport.get('is_favorites', False):
            # Display favorites - use cached data immediately for fast display
            current_time = time.time()
            FAVORITES_CACHE_TTL = self._favorites_cache_ttl()  # 60s while a favorite is live, else 5 min
            
            # Always use cached data first for immediate display
            if (isinstance(self.favorites_cache, list) and 
                len(self.favorites_cache) > 0 and
                (current_time - self.last_favorites_date_range_update) < FAVORITES_CACHE_TTL):
                # Use cached favorite games immediately
                favorite_games = self.favorites_cache
                logger.debug(f"Using cached favorite games in display_sports ({len(favorite_games)} games)")
            else:
                # Cache is stale or empty - use empty list for now, fetch in background
                favorite_games = self.favorites_cache if isinstance(self.favorites_cache, list) else []
                logger.debug(f"Favorites cache stale/empty, using existing cache ({len(favorite_games)} games) and fetching in background")
                
                # Trigger background fetch in a separate thread to avoid blocking.
                # Guarded: this runs every frame (~7/s) while the cache is
                # stale, and an MLB/NCAA date-range fetch takes several
                # seconds - without the flag it stacked up dozens of
                # identical fetch threads per refresh.
                def fetch_favorites_background():
                    try:
                        # Get fresh favorite games list (this will use date range cache if available)
                        fresh_games = self._get_favorite_games()
                        self.favorites_cache = fresh_games
                        self.last_favorites_date_range_update = time.time()
                        logger.info(f"Background fetch completed: {len(fresh_games)} favorite games")
                    except Exception as e:
                        logger.error(f"Error in background favorite games fetch: {e}")
                    finally:
                        self._favorites_fetch_running = False
                
                if not getattr(self, '_favorites_fetch_running', False):
                    self._favorites_fetch_running = True
                    import threading
                    threading.Thread(target=fetch_favorites_background, daemon=True).start()
            
            if not favorite_games or len(favorite_games) == 0:
                self.matrix.draw_text("NO FAVS", y=10, color=(255, 255, 0), small=True, center=True)
                self.matrix.update()
                return
            
            # Display favorite game - clamp index to valid range
            # IMPORTANT: Make sure we don't reset the index if it's valid
            if len(favorite_games) > 0:
                if self.current_game >= len(favorite_games):
                    self.current_game = 0
                elif self.current_game < 0:
                    self.current_game = len(favorite_games) - 1
            else:
                self.current_game = 0
            
            logger.debug(f"Displaying favorite game {self.current_game} of {len(favorite_games)} total favorite games (cache type: {type(self.favorites_cache)})")
            if len(favorite_games) == 0:
                self.matrix.draw_text("NO FAVS", y=10, color=(255, 255, 0), small=True, center=True)
                self.matrix.update()
                return
            
            game = favorite_games[self.current_game]
            sport_id = game.get('sport_id', 'sports')
            
            # Determine sport_id_for_logos
            sport_id_for_logos = sport_id.lower()
            if 'college-football' in sport_id_for_logos or 'ncaaf' in sport_id_for_logos:
                sport_id_for_logos = 'ncaaf'
            elif 'college-basketball' in sport_id_for_logos or 'mens-college-basketball' in sport_id_for_logos or 'ncaab' in sport_id_for_logos:
                sport_id_for_logos = 'ncaab'
            elif 'ncaa' in sport_id_for_logos:
                sport_id_for_logos = 'ncaa'
            
            self._draw_game(game, sport_id_for_logos)
            self.matrix.update()
            return
        
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
        
        # Fetch scores - update more frequently for live games
        current_time = time.time()
        
        # Check if we have any live games to determine update frequency
        has_live_games = False
        if sport_id in self.sports_data_cache:
            for game in self.sports_data_cache.get(sport_id, []):
                if game.get('is_live', False):
                    has_live_games = True
                    break
        
        # Update every 10 seconds for live games, 60 seconds otherwise
        update_interval = 10 if has_live_games else 60
        
        # Check if we need to fetch/refresh games for this sport
        games = self.sports_data_cache.get(sport_id, [])
        needs_fetch = (sport_id not in self.sports_data_cache or 
                      current_time - self.last_sports_update.get(sport_id, 0) > update_interval)
        
        # If cache is stale, fetch in background but use cached data for immediate display
        if needs_fetch and games:
            # Use cached data immediately, fetch in background
            logger.debug(f"Cache stale for {sport_id}, using cached data ({len(games)} games) and fetching in background")
            
            def fetch_sports_background():
                try:
                    from sports_fetcher import fetch_espn_scores
                    fetched_games = fetch_espn_scores(sport_id)
                    if fetched_games:
                        self.sports_data_cache[sport_id] = fetched_games
                        self.last_sports_update[sport_id] = time.time()
                        logger.info(f"Background fetch completed: {len(fetched_games)} games for sport {sport_id}")
                    else:
                        logger.warning(f"No games returned from API for sport {sport_id}")
                except Exception as e:
                    logger.error(f"Error in background sports fetch for {sport_id}: {e}")
            
            import threading
            fetch_thread = threading.Thread(target=fetch_sports_background, daemon=True)
            fetch_thread.start()
        elif needs_fetch:
            # No cached data, fetch immediately (blocking, but only if no cache)
            try:
                from sports_fetcher import fetch_espn_scores
                games = fetch_espn_scores(sport_id)
                if games:
                    self.sports_data_cache[sport_id] = games
                    self.last_sports_update[sport_id] = current_time
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
            self._draw_game(game, sport_id_for_logos)
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

        if (len(self.stocks_list) + len(self.crypto_list)) > 1:
            now = time.time()
            if now - self.last_stock_item_time >= self._item_interval('stocks', 6):
                self.last_stock_item_time = now
                current_list = self.stocks_list if self.stocks_submode == "stocks" else self.crypto_list
                current_index = self.current_stock_index if self.stocks_submode == "stocks" else self.current_crypto_index
                self.next_ticker()
                # Wrapped back to the start of this list - move to the
                # other one so a continuous cycle sees every stock AND
                # every crypto, not just one list forever.
                if current_list and current_index >= len(current_list) - 1:
                    other_list = self.crypto_list if self.stocks_submode == "stocks" else self.stocks_list
                    if other_list:
                        self.switch_stocks_submode()

        # Get current ticker based on sub-mode
        if self.stocks_submode == "stocks":
            ticker_list = self.stocks_list
            current_index = self.current_stock_index
            if not ticker_list or current_index >= len(ticker_list):
                logger.warning(f"No stocks configured or invalid index")
                self.matrix.draw_text("NO STOCKS", y=10, color=(255, 0, 0), small=True, center=True)
                self.matrix.update()
                return
            ticker = ticker_list[current_index]
        else:  # crypto
            ticker_list = self.crypto_list
            current_index = self.current_crypto_index
            if not ticker_list or current_index >= len(ticker_list):
                logger.warning(f"No crypto configured or invalid index")
                self.matrix.draw_text("NO CRYPTO", y=10, color=(255, 0, 0), small=True, center=True)
                self.matrix.update()
                return
            ticker = ticker_list[current_index]
        
        logger.debug(f"display_stocks: submode={self.stocks_submode}, ticker={ticker}, index={current_index}")
        
        # Per-ticker refresh. This used to share one last_stock_update
        # timestamp across every ticker, so with items rotating every few
        # seconds only about one ticker in five ever refetched - the rest
        # showed prices days old (INTC sat at a previous session's close).
        current_time = time.time()
        cache_key = ticker
        is_crypto = ticker in self.crypto_list
        if current_time - self.stock_update_times.get(cache_key, 0) > 60:
            self.stock_update_times[cache_key] = current_time

            def fetch_price():
                try:
                    from stock_fetcher import fetch_stock_price, fetch_crypto_price
                    data = fetch_crypto_price(ticker) if is_crypto else fetch_stock_price(ticker)
                    if data:
                        self.stock_data_cache[cache_key] = data
                except Exception as e:
                    logger.error(f"Error fetching price for {ticker}: {e}")

            if cache_key in self.stock_data_cache:
                import threading
                threading.Thread(target=fetch_price, daemon=True).start()
            else:
                fetch_price()

        data = self.stock_data_cache.get(cache_key)
        # "BTC-USD" -> "BTC": the quote currency is implied
        symbol = ticker.upper()
        if is_crypto and symbol.endswith('-USD'):
            symbol = symbol[:-4]

        if data and self.matrix.draw:
            fonts = self.matrix.fonts
            W = self.matrix.image.width
            price = data.get('price', 0) or 0
            change_pct = data.get('change_percent', 0) or 0

            # Icon on the left, 20x20, cropped to its visible pixels. Wide
            # wordmark logos (intel, charles SCHWAB, SUPERMICRO) are
            # unreadable at this size, so those tickers go text-only.
            icon = None
            if self.asset_loader:
                icon = self._fit_logo(self.asset_loader.get_stock_icon(ticker, is_crypto=is_crypto), 20, max_aspect=1.6)
            if icon:
                self._paste_logo(icon, 0, 6, 20)
                col_x, col_w = 22, W - 22
            else:
                col_x, col_w = 0, W
            center = col_x + col_w / 2

            if price >= 1000:
                price_str = f"${price:,.0f}"
            elif price >= 1:
                price_str = f"${price:.2f}"
            else:
                price_str = f"${price:.4f}"
            up = change_pct >= 0
            change_str = f"{'+' if up else ''}{change_pct:.2f}%"
            change_color = (0, 255, 0) if up else (255, 40, 40)

            clamp = (col_x, W)
            self._draw_label(symbol, self._fit_font(symbol, col_w), (0, 200, 255),
                             y=0, center_x=center, clamp=clamp, outline=False)
            self._draw_label(price_str, self._fit_font(price_str, col_w, ("medium", "small", "tiny")),
                             (255, 255, 255), y=11, center_x=center, clamp=clamp, outline=False)
            self._draw_label(change_str, self._fit_font(change_str, col_w, ("small", "tiny")),
                             change_color, y=24, center_x=center, clamp=clamp, outline=False)
        else:
            self.matrix.draw_text(symbol[:8], y=12, color=(0, 200, 255))

        self.matrix.update()
    
    def next_fantasy_player(self):
        """Next fantasy player in current sport"""
        current_sport = self.fantasy_sports[self.current_fantasy_sport_index]
        players_in_sport = [i for i, p in enumerate(self.fantasy_players) 
                           if p.get('sport', 'nfl').lower() == current_sport]
        if players_in_sport:
            current_idx = players_in_sport.index(self.current_fantasy_player) if self.current_fantasy_player in players_in_sport else 0
            next_idx = (current_idx + 1) % len(players_in_sport)
            self.current_fantasy_player = players_in_sport[next_idx]
            logger.info(f"Fantasy player: {self.current_fantasy_player} (sport: {current_sport})")
            self.matrix.clear()
            self.display_fantasy()
    
    def prev_fantasy_player(self):
        """Previous fantasy player in current sport"""
        current_sport = self.fantasy_sports[self.current_fantasy_sport_index]
        players_in_sport = [i for i, p in enumerate(self.fantasy_players) 
                           if p.get('sport', 'nfl').lower() == current_sport]
        if players_in_sport:
            current_idx = players_in_sport.index(self.current_fantasy_player) if self.current_fantasy_player in players_in_sport else 0
            prev_idx = (current_idx - 1) % len(players_in_sport)
            self.current_fantasy_player = players_in_sport[prev_idx]
            logger.info(f"Fantasy player: {self.current_fantasy_player} (sport: {current_sport})")
            self.matrix.clear()
            self.display_fantasy()
    
    def next_fantasy_sport(self):
        """Cycle to next sport"""
        self.current_fantasy_sport_index = (self.current_fantasy_sport_index + 1) % len(self.fantasy_sports)
        current_sport = self.fantasy_sports[self.current_fantasy_sport_index]
        # Find first player in this sport
        players_in_sport = [i for i, p in enumerate(self.fantasy_players) 
                           if p.get('sport', 'nfl').lower() == current_sport]
        if players_in_sport:
            self.current_fantasy_player = players_in_sport[0]
        logger.info(f"Fantasy sport: {current_sport}")
        self.matrix.clear()
        self.display_fantasy()
    
    def prev_fantasy_sport(self):
        """Cycle to previous sport"""
        self.current_fantasy_sport_index = (self.current_fantasy_sport_index - 1) % len(self.fantasy_sports)
        current_sport = self.fantasy_sports[self.current_fantasy_sport_index]
        # Find first player in this sport
        players_in_sport = [i for i, p in enumerate(self.fantasy_players) 
                           if p.get('sport', 'nfl').lower() == current_sport]
        if players_in_sport:
            self.current_fantasy_player = players_in_sport[0]
        logger.info(f"Fantasy sport: {current_sport}")
        self.matrix.clear()
        self.display_fantasy()
    
    def _truncate_text_to_fit(self, text: str, font, max_width: int, letter_spacing: int = 0) -> str:
        """Truncate text to fit within max_width pixels, accounting for letter spacing"""
        if not self.matrix.draw:
            # Fallback: character-based truncation
            return text[:max_width] if len(text) > max_width else text
        
        # Calculate text width with letter spacing
        def get_text_width(txt):
            if letter_spacing < 0:
                width = 0
                for char in txt:
                    bbox = self.matrix.draw.textbbox((0, 0), char, font=font)
                    char_width = bbox[2] - bbox[0]
                    width += char_width + letter_spacing
                width -= letter_spacing  # Don't add spacing after last char
                return width
            else:
                bbox = self.matrix.draw.textbbox((0, 0), txt, font=font)
                return bbox[2] - bbox[0]
        
        if get_text_width(text) <= max_width:
            return text
        
        # Truncate from the end, keeping the team abbreviation
        # Try to preserve "(TEAM)" if present
        if '(' in text and ')' in text:
            # Extract team part
            paren_start = text.rfind('(')
            team_part = text[paren_start:]
            name_part = text[:paren_start]
            
            # Truncate name part character by character
            truncated_name = name_part
            while len(truncated_name) > 1:
                test_text = truncated_name + team_part
                test_width = get_text_width(test_text)
                
                if test_width <= max_width:
                    return test_text
                truncated_name = truncated_name[:-1]
            
            # If even single char doesn't fit, return team part only
            return team_part
        else:
            # No team part, just truncate
            truncated = text
            while len(truncated) > 1:
                if get_text_width(truncated) <= max_width:
                    return truncated
                truncated = truncated[:-1]
            return truncated
    
    def _truncate_text(self, text: str, max_width: int = None, small: bool = True) -> str:
        """Truncate text to fit within max_width pixels (defaults to display width)"""
        if not self.matrix.draw:
            # Fallback: character-based truncation
            if max_width is None:
                max_width = self.matrix.width
            return text[:max_width] if len(text) > max_width else text
        
        font = self.matrix.small_font if small else self.matrix.font
        
        # Use display width - since text is centered, we can use the full width
        # The draw_text function centers the text, so slight overflow is acceptable
        if max_width is None:
            max_width = self.matrix.width  # Use full width (64px for standard display)
        
        # Check if text fits (with small tolerance for centering)
        bbox = self.matrix.draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        
        # Only truncate if text is significantly wider than display (allow 5px overflow for centering)
        if text_width <= max_width + 5:
            return text
        
        # Simple linear search from end to find longest fit
        # This is more reliable than binary search for variable-width fonts
        for i in range(len(text), 0, -1):
            test_text = text[:i] + "..."
            bbox = self.matrix.draw.textbbox((0, 0), test_text, font=font)
            test_width = bbox[2] - bbox[0]
            
            if test_width <= max_width:
                return test_text
        
        # If even "..." doesn't fit, return it anyway
        return "..."
    
    def _calculate_fantasy_score(self, data: Dict[str, Any], sport: str) -> float:
        """Calculate fantasy score based on sport-specific rules"""
        score = 0.0
        sport = sport.lower()
        
        if sport == 'nfl':
            # Passing stats
            pass_yds = float(data.get('passing_yards', 0) or 0)
            pass_tds = int(data.get('passing_tds', 0) or 0)
            interceptions = int(data.get('passing_ints', 0) or 0)
            score += pass_yds * 0.04
            score += pass_tds * 4
            score += interceptions * -1
            
            # Rushing stats
            rush_yds = float(data.get('rushing_yards', 0) or 0)
            rush_tds = int(data.get('rushing_tds', 0) or 0)
            score += rush_yds * 0.1
            score += rush_tds * 6
            
            # Receiving stats
            receptions = int(data.get('receptions', 0) or 0)
            rec_yds = float(data.get('receiving_yards', 0) or 0)
            rec_tds = int(data.get('receiving_tds', 0) or 0)
            score += receptions * 1
            score += rec_yds * 0.1
            score += rec_tds * 6
            
            # Other stats (if available)
            fumbles_lost = int(data.get('fumbles_lost', 0) or 0)
            score += fumbles_lost * -1
            
        elif sport == 'nba':
            points = float(data.get('points', 0) or 0)
            rebounds = float(data.get('rebounds', 0) or 0)
            assists = float(data.get('assists', 0) or 0)
            blocks = float(data.get('blocks', 0) or 0)
            steals = float(data.get('steals', 0) or 0)
            turnovers = float(data.get('turnovers', 0) or 0)
            
            score += points * 1
            score += rebounds * 1.2
            score += assists * 1.5
            score += blocks * 3
            score += steals * 3
            score += turnovers * -1
            
        elif sport == 'nhl':
            # Skater stats
            goals = int(data.get('goals', 0) or 0)
            assists = int(data.get('assists', 0) or 0)
            shots = int(data.get('shots', 0) or 0)
            plus_minus = int(data.get('plus_minus', 0) or 0)
            blocks = int(data.get('blocks', 0) or 0)
            
            score += goals * 3
            score += assists * 2
            score += shots * 0.5
            score += plus_minus * 1
            score += blocks * 0.5
            
            # Goalie stats (if available)
            wins = int(data.get('wins', 0) or 0)
            goals_against = int(data.get('goals_against', 0) or 0)
            saves = int(data.get('saves', 0) or 0)
            shutouts = int(data.get('shutouts', 0) or 0)
            
            if wins > 0 or saves > 0:  # Likely a goalie
                score = wins * 3
                score += goals_against * -1
                score += saves * 0.2
                score += shutouts * 2
        
        return round(score, 2)
    
    def display_fantasy(self):
        """Display fantasy mode with player stats"""
        self.matrix.clear()
        
        # Get current sport
        current_sport = self.fantasy_sports[self.current_fantasy_sport_index]
        
        # Filter players for current sport
        players_in_sport = [p for p in self.fantasy_players 
                           if p.get('sport', 'nfl').lower() == current_sport]
        
        if not players_in_sport:
            # No players for this sport, show sport name
            self.matrix.draw_text(f"NO {current_sport.upper()}", y=10, color=(255, 0, 0), small=True, center=True)
            self.matrix.draw_text("PLAYERS", y=18, color=(255, 0, 0), small=True, center=True)
            self.matrix.update()
            return
        
        # Find current player index in filtered list
        if self.current_fantasy_player >= len(self.fantasy_players):
            self.current_fantasy_player = 0
        
        player_config = self.fantasy_players[self.current_fantasy_player]
        player_sport = player_config.get('sport', 'nfl').lower()
        
        # If current player is not in current sport, switch to first player in sport
        if player_sport != current_sport:
            self.current_fantasy_player = next((i for i, p in enumerate(self.fantasy_players) 
                                              if p.get('sport', 'nfl').lower() == current_sport), 0)
            player_config = self.fantasy_players[self.current_fantasy_player]
        
        player_name = player_config.get('name', '')
        team_abbr = player_config.get('team', '')
        sport = player_config.get('sport', 'nfl').lower()
        
        if not player_name:
            self.matrix.draw_text("NO NAME", y=10, color=(255, 0, 0))
            self.matrix.update()
            return
        
        # Fetch player stats if cache is old (update every 60 seconds)
        current_time = time.time()
        cache_key = f"{sport}_{player_name}_{team_abbr}"
        
        if (cache_key not in self.fantasy_player_cache or 
            current_time - self.last_fantasy_update > 60):
            try:
                from player_stats_fetcher import fetch_player_stats
                logger.info(f"Fetching {sport.upper()} stats for {player_name} ({team_abbr})")
                data = fetch_player_stats(player_name, team_abbr, sport)
                if data:
                    self.fantasy_player_cache[cache_key] = data
                    self.last_fantasy_update = current_time
                    logger.info(f"Successfully fetched stats for {player_name}: {data}")
                else:
                    logger.warning(f"No stats found for {player_name} ({team_abbr})")
            except Exception as e:
                logger.error(f"Error fetching player stats: {e}", exc_info=True)
                data = None
        else:
            data = self.fantasy_player_cache.get(cache_key)
            logger.debug(f"Using cached stats for {player_name}")
        
        if data:
            # Abbreviate player name more aggressively for long names
            name_parts = player_name.split()
            if len(name_parts) >= 2:
                # Use first initial and last name, no space: "J.Robertson"
                abbreviated_name = f"{name_parts[0][0]}.{name_parts[-1]}"
            else:
                abbreviated_name = player_name
            
            # Get team abbreviation for display
            team_display = data.get('team', team_abbr) or team_abbr
            
            # Check if player is a kicker (has FG stats but no passing/rushing/receiving)
            is_kicker = (data.get('fg_made') is not None or data.get('fg_attempted') is not None) and \
                       data.get('passing_yards') is None and \
                       data.get('rushing_yards') is None and \
                       data.get('receiving_yards') is None
            
            # Line 1: Name (TEAM) - exactly 6 lines total
            # Make name compact: "J.Robertson(DAL)" format
            name_display = f"{abbreviated_name}({team_display})"
            
            # Truncate name if it's too long to fit on display
            tiny_font = getattr(self.matrix, 'tiny_font', None) or getattr(self, 'tiny_font', None)
            name_font = tiny_font if tiny_font else (getattr(self.matrix, 'small_font', None) or self.matrix.font)
            
            # Check if name fits, truncate last name if needed
            max_display_width = self.matrix.width - 4  # Leave 2px margin on each side for safety
            name_display = self._truncate_text_to_fit(name_display, name_font, max_display_width, letter_spacing=-1)
            
            # Build stats lines according to compact 6-line format
            stats_lines = []
            
            if sport == 'nfl':
                if is_kicker:
                    # NFL Kicker - 6 lines: Name, FGM/A, LNG, PAT, MISS, FPTS
                    fg_made = int(data.get('fg_made', 0) or 0)
                    fg_att = int(data.get('fg_attempted', 0) or 0)
                    fg_long = int(data.get('fg_long', 0) or 0)
                    xp_made = int(data.get('xp_made', 0) or 0)
                    xp_att = int(data.get('xp_attempted', 0) or 0)
                    # MISS = total misses (FG misses + XP misses)
                    fg_misses = fg_att - fg_made
                    xp_misses = xp_att - xp_made
                    total_misses = fg_misses + xp_misses
                    
                    stats_lines.append(f"FGM/A:{fg_made}/{fg_att}")
                    stats_lines.append(f"LNG:{fg_long}")
                    stats_lines.append(f"PAT:{xp_made}/{xp_att}")
                    stats_lines.append(f"MISS:{total_misses}")
                else:
                    # NFL QB/RB/WR/TE - 6 lines: Name, C/A PY, RA RY, RT RY, TTD FUM, FPTS
                    comp = int(data.get('passing_completions', 0) or 0)
                    att = int(data.get('passing_attempts', 0) or 0)
                    pass_yds = int(data.get('passing_yards', 0) or 0)
                    rush_att = int(data.get('rushing_attempts', 0) or 0)
                    rush_yds = int(data.get('rushing_yards', 0) or 0)
                    rec = int(data.get('receptions', 0) or 0)
                    targets = int(data.get('targets', 0) or 0)
                    rec_yds = int(data.get('receiving_yards', 0) or 0)
                    # Total touchdowns
                    pass_tds = int(data.get('passing_tds', 0) or 0)
                    rush_tds = int(data.get('rushing_tds', 0) or 0)
                    rec_tds = int(data.get('receiving_tds', 0) or 0)
                    total_tds = pass_tds + rush_tds + rec_tds
                    fumbles = int(data.get('fumbles', 0) or 0)
                    pass_ints = int(data.get('passing_ints', 0) or 0)
                    # Use INT for QBs, FUM for others
                    turnovers = pass_ints if pass_ints > 0 else fumbles
                    
                    stats_lines.append(f"C/A:{comp}/{att} PY:{pass_yds}")
                    stats_lines.append(f"RA:{rush_att} RY:{rush_yds}")
                    stats_lines.append(f"RT:{rec}/{targets} RY:{rec_yds}")
                    stats_lines.append(f"TTD:{total_tds} FUM:{turnovers}")
                    
            elif sport == 'nba':
                # NBA - 6 lines: Name, FG PTS, REB AST, STL BLK, TO PF, FPTS
                fg_made = int(data.get('fg_made', 0) or 0)
                fg_att = int(data.get('fg_attempted', 0) or 0)
                pts = int(data.get('points', 0) or 0)
                reb = int(data.get('rebounds', 0) or 0)
                ast = int(data.get('assists', 0) or 0)
                stl = int(data.get('steals', 0) or 0)
                blk = int(data.get('blocks', 0) or 0)
                to = int(data.get('turnovers', 0) or 0)
                pf = int(data.get('personal_fouls', 0) or 0)
                
                stats_lines.append(f"FG:{fg_made}/{fg_att} P:{pts}")
                stats_lines.append(f"REB:{reb} AST:{ast}")
                stats_lines.append(f"STL:{stl} BLK:{blk}")
                stats_lines.append(f"TO:{to} PF:{pf}")
                
            elif sport == 'nhl':
                # NHL - 6 lines: Name, G/A SOG, HIT BLK, PIM +/-, TOI, FPTS
                goals = int(data.get('goals', 0) or 0)
                assists = int(data.get('assists', 0) or 0)
                shots = int(data.get('shots', 0) or 0)
                hits = int(data.get('hits', 0) or 0)
                blk = int(data.get('blocks', 0) or 0)
                pim = int(data.get('penalty_minutes', 0) or 0)
                pm = int(data.get('plus_minus', 0) or 0)
                toi = data.get('time_on_ice', '0:00') or '0:00'
                # Format TOI to MM:SS if needed
                if isinstance(toi, str) and ':' in toi:
                    toi_parts = toi.split(':')
                    if len(toi_parts) >= 2:
                        toi_display = f"{toi_parts[0]}:{toi_parts[1][:2]}"
                    else:
                        toi_display = toi
                else:
                    toi_display = str(toi)
                
                stats_lines.append(f"G/A:{goals}/{assists} SOG:{shots}")
                stats_lines.append(f"HIT:{hits} BLK:{blk}")
                stats_lines.append(f"PIM:{pim} +/-:{pm}")
                stats_lines.append(f"TOI:{toi_display}")
            
            # Calculate fantasy score
            fantasy_score = self._calculate_fantasy_score(data, sport)
            stats_lines.append(f"FPTS:{fantasy_score:.1f}")
            
            # Display exactly 6 lines: Name + 5 stat lines
            # Use tiny font with reduced letter spacing for compact display
            tiny_font = getattr(self.matrix, 'tiny_font', None) or getattr(self, 'tiny_font', None)
            fantasy_font = tiny_font if tiny_font else (getattr(self.matrix, 'small_font', None) or self.matrix.font)
            
            # Fixed 6-line layout with 5px line height
            line_height = 5
            y_offset = 0
            
            # Line 0: Name (TEAM) - already truncated above
            self.matrix.draw_text(name_display, y=y_offset, color=(255, 255, 0), 
                                 font=name_font, center=True, letter_spacing=-1)
            
            # Lines 1-5: Stats (exactly 5 stat lines)
            if stats_lines:
                for i, stat_line in enumerate(stats_lines[:5]):
                    self.matrix.draw_text(stat_line, y=y_offset + (i + 1) * line_height, 
                                         color=(0, 255, 0), font=fantasy_font, center=True, letter_spacing=-1)
            else:
                # Stats found but no stat values - show message
                self.matrix.draw_text("NO STATS", y=y_offset + line_height, 
                                     color=(255, 165, 0), font=fantasy_font, center=True, letter_spacing=-1)
        else:
            # No stats available - show player info with helpful message
            name_parts = player_name.split()
            if len(name_parts) >= 2:
                abbreviated_name = f"{name_parts[0][0]}. {name_parts[-1]}"
            else:
                abbreviated_name = player_name
            # Use larger font when no stats to fill screen
            small_font = getattr(self.matrix, 'small_font', None) or self.matrix.font
            self.matrix.draw_text(abbreviated_name, y=0, color=(255, 255, 0), font=small_font, center=True, letter_spacing=-1)
            self.matrix.draw_text("NO STATS", y=6, color=(255, 0, 0), font=small_font, center=True, letter_spacing=-1)
        
        self.matrix.update()
            
    def display_weather(self):
        """Display weather mode with actual weather data"""
        self.matrix.clear()

        if len(self.weather_locations) > 1:
            now = time.time()
            if now - self.last_weather_item_time >= self._item_interval('weather', 6):
                self.last_weather_item_time = now
                self.next_weather_location()

        logger.debug(f"display_weather: weather_locations={self.weather_locations}, current_weather_location={self.current_weather_location}, len={len(self.weather_locations) if self.weather_locations else 0}")
        if not self.weather_locations or self.current_weather_location >= len(self.weather_locations):
            logger.warning(f"No weather locations configured or invalid index: weather_locations={self.weather_locations}, current_weather_location={self.current_weather_location}")
            self.matrix.draw_text("NO WEATHER", y=10, color=(255, 0, 0), small=True, center=True)
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

            # Line 1: Location name - handle long names better
            # For very long names, split into two lines or truncate intelligently
            max_chars_single = 10  # Max chars that fit on one line
            location_is_split = len(location_name) > max_chars_single and len(location_name.split()) > 1 and len(location_name.split()[0]) <= max_chars_single
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
                self.matrix.draw_text(location_name, y=0, color=(0, 200, 255), small=True, center=True)

            # Icon + temp/condition share the remaining band below the
            # location line, split into a left icon column and a right text
            # column - not stacked full-width center-on-center, which is
            # what previously left the icon and the temp/condition text each
            # centered independently on the same 64px midpoint, wasting the
            # space on the icon's side and never actually using the right
            # edge (confirmed live via /api/preview.png: real gap past the
            # temperature, every row optically left-of-center).
            band_top = 15 if location_is_split else 8
            icon_size = 22 if band_top <= 8 else 15
            icon_x = 0

            if icon:
                try:
                    icon_resized = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                    icon_y = band_top + (self.matrix.image.height - band_top - icon_size) // 2
                    self.matrix.image.paste(icon_resized, (icon_x, icon_y))
                except:
                    pass

            # Text column starts right after the icon and is centered within
            # that remaining space (draw_text's x + center=True centers
            # "from x to the right edge", not across the whole canvas) - so
            # it fills the room the icon left behind instead of the strip
            # down the middle of the whole display.
            text_x = icon_size + 2
            text_band_height = self.matrix.image.height - band_top
            temp_str = f"{temp}°F"
            # Temperature, then the condition word-wrapped onto up to two
            # lines in the text column (it used to be cut at 8 chars:
            # "Partly C"). The block is vertically centered in the band.
            col_w = self.matrix.image.width - text_x
            center = text_x + col_w / 2
            lines = []
            for word in condition.split():
                if lines and self._text_width(f"{lines[-1]} {word}", self.matrix.fonts["small"]) <= col_w:
                    lines[-1] = f"{lines[-1]} {word}"
                else:
                    lines.append(word)
            lines = lines[:2]
            block_h = 8 + 1 + 8 * len(lines)
            temp_y = band_top + max(0, (text_band_height - block_h) // 2)
            self.matrix.draw_text(temp_str, x=text_x, y=temp_y, color=(255, 255, 255), center=True)
            for i, line in enumerate(lines):
                font = self._fit_font(line, col_w, ("small", "tiny"))
                self._draw_label(line, font, (200, 200, 255), y=temp_y + 9 + i * 8,
                                 center_x=center, clamp=(text_x, self.matrix.image.width), outline=False)
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
        
    def display_images(self):
        """Display images/GIFs mode"""
        self.matrix.clear()

        if (len(self.photo_list) + len(self.gif_list)) > 1:
            now = time.time()
            if now - self.last_image_item_time >= self._item_interval('images', 6):
                self.last_image_item_time = now
                current_list = self.photo_list if self.current_image_list == "photos" else self.gif_list
                current_index = self.current_image_index
                self.next_image()
                if current_list and current_index >= len(current_list) - 1:
                    other_list = self.gif_list if self.current_image_list == "photos" else self.photo_list
                    if other_list:
                        self.switch_image_list()

        if self.current_image_list == "photos":
            if not self.photo_list:
                self.matrix.draw_text("NO PHOTOS", y=10, color=(255, 255, 0), small=True, center=True)
                self.matrix.update()
                return
            
            # Clamp index
            if self.current_image_index >= len(self.photo_list):
                self.current_image_index = 0
            
            photo_path = self.photo_list[self.current_image_index]
            try:
                img = Image.open(photo_path)
                # Convert to RGB if needed
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                # Resize to fit display (64x32)
                img = img.resize((self.matrix.width, self.matrix.height), Image.Resampling.LANCZOS)
                self.matrix.image = img
                self.matrix.draw = ImageDraw.Draw(self.matrix.image)
                self.matrix.update()
            except Exception as e:
                logger.error(f"Error displaying photo {photo_path}: {e}")
                self.matrix.draw_text("ERROR", y=10, color=(255, 0, 0))
                self.matrix.update()
        else:  # GIFs
            if not self.gif_list:
                self.matrix.draw_text("NO GIFS", y=10, color=(255, 255, 0))
                self.matrix.update()
                return
            
            # Clamp index
            if self.current_image_index >= len(self.gif_list):
                self.current_image_index = 0
            
            gif_path = self.gif_list[self.current_image_index]
            try:
                # Load GIF if not already loaded or if we switched GIFs
                if self.current_gif_image is None or self.current_gif_image.filename != gif_path:
                    self.current_gif_image = Image.open(gif_path)
                    self.current_gif_frame = 0
                
                # Animate GIF (update every 100ms)
                current_time = time.time()
                if current_time - self.last_gif_update > 0.1:
                    self.last_gif_update = current_time
                    
                    # Seek to current frame
                    try:
                        self.current_gif_image.seek(self.current_gif_frame)
                    except EOFError:
                        # Loop back to start
                        self.current_gif_frame = 0
                        self.current_gif_image.seek(0)
                    
                    # Convert to RGB if needed
                    frame = self.current_gif_image.copy()
                    if frame.mode != 'RGB':
                        frame = frame.convert('RGB')
                    
                    # Resize to fit display
                    frame = frame.resize((self.matrix.width, self.matrix.height), Image.Resampling.LANCZOS)
                    self.matrix.image = frame
                    self.matrix.draw = ImageDraw.Draw(self.matrix.image)
                    
                    # Move to next frame
                    self.current_gif_frame += 1
                
                self.matrix.update()
            except Exception as e:
                logger.error(f"Error displaying GIF {gif_path}: {e}")
                self.matrix.draw_text("ERROR", y=10, color=(255, 0, 0))
                self.matrix.update()
    
    def display_brightness(self):
        """Display brightness setting"""
        self.matrix.clear()
        brightness = self.config.get('brightness', 50)
        # Use shorter text to fit on screen, larger font for brightness value
        self.matrix.draw_text("BRIGHT", y=5, color=(255, 255, 0), small=True, center=True)
        self.matrix.draw_text(f"{brightness}%", y=20, color=(255, 255, 255), center=True)  # Regular font (not small)
        self.matrix.update()
        
    def _current_mode_duration(self) -> float:
        """How long the current mode stays on screen before auto-advancing.
        For modes with their own sub-item rotation (weather locations,
        stock/crypto tickers, favorite games, photos/gifs), this is
        stretched to item_count * per-item interval so a full lap always
        completes in one visit - otherwise a static duration could cut a
        long list off partway through, defeating the point of rotating
        sub-items at all. Falls back to the configured/static duration for
        modes without sub-items (images/sports/etc. with 0-1 items too)."""
        mode = self.current_mode
        static = self.mode_display_durations.get(mode, self.default_mode_duration)
        if mode == 'weather' and len(self.weather_locations) > 1:
            return max(static, len(self.weather_locations) * self._item_interval('weather', 6))
        if mode == 'stocks':
            n = len(self.stocks_list) + len(self.crypto_list)
            if n > 1:
                return max(static, n * self._item_interval('stocks', 6))
        if mode == 'sports' and len(self.favorites_cache) > 1:
            return max(static, len(self.favorites_cache) * self._item_interval('sports', 8))
        if mode == 'images':
            n = len(self.photo_list) + len(self.gif_list)
            if n > 1:
                return max(static, n * self._item_interval('images', 6))
        return static

    def update(self):
        """Update display based on current mode"""
        # Config reload used to be signaled via a polled trigger file, back
        # when web_config.py and this controller were separate processes.
        # They share one process now - web_config.py's save/upload routes
        # call reload_config()/_load_image_lists() directly instead.
        current_time = time.time()

        # Auto-rotate between enabled modes using display.display_durations
        # (already a per-mode seconds value in config - clock: 15,
        # weather: 30, stocks: 30, etc. - but never previously read by
        # anything). Checked ahead of the render throttle below so
        # rotation timing doesn't depend on it. A manual mode switch via
        # the remote/API resets last_mode_rotation_time in set_mode()/
        # cycle_mode(), so it always gets its own full duration first.
        if len(self.modes) > 1:
            duration = self._current_mode_duration()
            if current_time - self.last_mode_rotation_time >= duration:
                self.cycle_mode(1)

        if current_time - self.last_update < self.update_interval:
            return
        self.last_update = current_time
        
        # Update display for current mode
        logger.debug(f"Updating display for mode: {self.current_mode}")
        
        try:
            if self.current_mode == "clock":
                self.display_clock()
            elif self.current_mode == "sports":
                self.display_sports()
            elif self.current_mode == "fantasy":
                self.display_fantasy()
            elif self.current_mode == "stocks":
                self.display_stocks()
            elif self.current_mode == "weather":
                self.display_weather()
            elif self.current_mode == "music":
                self.display_music()
            elif self.current_mode == "images":
                self.display_images()
            elif self.current_mode == "brightness":
                self.display_brightness()
            else:
                logger.warning(f"Unknown mode: {self.current_mode}")
        except Exception as e:
            logger.error(f"Error updating display: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            # Show error on display
            try:
                if self.matrix:
                    self.matrix.clear()
                    self.matrix.draw_text("ERROR", y=10, color=(255, 0, 0))
                    self.matrix.update()
            except Exception as display_err:
                logger.error(f"Error showing error message on display: {display_err}")
            
    def run(self):
        """Main run loop"""
        logger.info("Display controller started")
        # Initial display update
        try:
            logger.info("Performing initial display update...")
            self.update()
            logger.info("Initial display update completed")
        except Exception as e:
            logger.error(f"Error in initial update: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            
        try:
            update_count = 0
            while True:
                self.update()
                update_count += 1
                if update_count % 100 == 0:  # Log every 10 seconds (100 * 0.1s)
                    logger.debug(f"Update loop running, count: {update_count}, mode: {self.current_mode}")
                time.sleep(0.1)  # Small sleep to prevent CPU spinning
        except KeyboardInterrupt:
            logger.info("Display controller stopped")
        except Exception as e:
            logger.error(f"Error in run loop: {e}", exc_info=True)
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    controller = DisplayController()
    controller.run()
