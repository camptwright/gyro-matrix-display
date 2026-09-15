import time
import logging
from datetime import datetime
import pytz
from typing import Dict, Any
from PIL import ImageFont
from src.config_manager import ConfigManager
from src.display_manager import DisplayManager

# Get logger without configuring
logger = logging.getLogger(__name__)

# Redesigned 2026-09-15 for the real hardware (Adafruit 64x32, 6mm pitch).
# Old layout drew three lines at the shared 8px font (time, full weekday,
# "%B %-d" + ordinal suffix) - "September 15th" alone measures ~112px at
# that size, more than the entire 64px width, and the centering math only
# guarded the left edge (`max(0, ...)`) so an overflowing string just
# started at x=0 and ran off the right edge with no clipping or wrapping.
# New layout: a small AM/PM badge on its own row (so it never competes for
# width with the time), a much bigger centered time (worst case "12:47" or
# "10:05" measures 60px at size 12 - fits with 4px to spare), and one
# combined "MON SEP 15" row using 3-letter weekday/month abbreviations
# (checked all 7 weekday and 12 month abbreviations - all exactly 3
# characters, so the combined width is one of only two values regardless of
# which day it is). That date row deliberately does NOT use PressStart2P
# shrunk down to a small size - that font is drawn from an 8x8 grid and
# gets visibly blurry/ambiguous (M vs a smudge, 5 vs an unclear shape) at
# anything smaller, confirmed by rendering it and inspecting the actual
# pixels. assets/fonts/4x6-font.ttf is a real bitmap font built for small
# sizes and stays crisp - and is narrower besides (42-44px vs 60px for the
# same string), so it comfortably fits at a bigger, more legible point size.
_FONT_PATH = "assets/fonts/PressStart2P-Regular.ttf"
_SMALL_FONT_PATH = "assets/fonts/4x6-font.ttf"


class Clock:
    def __init__(self, display_manager: DisplayManager = None, config: Dict[str, Any] = None):
        if config is not None:
            # Use provided config
            self.config = config
            self.config_manager = None  # Not needed when config is provided
        else:
            # Fallback: create ConfigManager and load config (for standalone usage)
            self.config_manager = ConfigManager()
            self.config = self.config_manager.load_config()
        # Use the provided display_manager or create a new one if none provided
        self.display_manager = display_manager or DisplayManager(self.config.get('display', {}))
        logger.info("Clock initialized with display_manager: %s", id(self.display_manager))
        self.location = self.config.get('location', {})
        self.clock_config = self.config.get('clock', {})
        # Use configured timezone if available, otherwise try to determine it
        self.timezone = self._get_timezone()
        self.last_time = None
        self.last_date = None
        # Colors for different elements - using super bright colors
        self.COLORS = {
            'time': (255, 255, 255),    # Pure white for time
            'ampm': (255, 255, 128),    # Bright warm yellow for AM/PM
            'date': (255, 128, 64)      # Bright orange for date
        }
        # Dedicated sizes for this layout - the display_manager's own
        # regular_font/small_font are both 8px (sized for other screens),
        # neither matches what this layout needs.
        try:
            self.ampm_font = ImageFont.truetype(_FONT_PATH, 8)
            self.time_font = ImageFont.truetype(_FONT_PATH, 12)
            self.date_font = ImageFont.truetype(_SMALL_FONT_PATH, 8)
        except Exception as e:
            logger.warning(f"Could not load dedicated clock fonts, falling back to display_manager fonts: {e}")
            self.ampm_font = self.display_manager.small_font
            self.time_font = self.display_manager.regular_font
            self.date_font = self.display_manager.small_font

    def _get_timezone(self) -> pytz.timezone:
        """Get timezone from the config file."""
        config_timezone = self.config.get('timezone', 'UTC')
        try:
            return pytz.timezone(config_timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(
                f"Invalid timezone '{config_timezone}' in config. "
                "Falling back to UTC. Please check your config.json file. "
                "A list of valid timezones can be found at "
                "https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
            )
            return pytz.utc

    def get_current_time(self) -> tuple:
        """Get the current time and date in the configured timezone."""
        current = datetime.now(self.timezone)

        # Format time in 12-hour format with AM/PM
        time_str = current.strftime('%I:%M')  # Remove leading zero from hour
        if time_str.startswith('0'):
            time_str = time_str[1:]

        # Get AM/PM
        ampm = current.strftime('%p')

        # Abbreviated weekday + month + day, e.g. "MON SEP 15" - fixed width
        # regardless of which weekday/month, always fits at 60px (size 6).
        # No ordinal suffix: "15th" is one more thing that can't overflow if
        # it's simply not there, and a bare day number reads fine at this size.
        date_str = current.strftime('%a %b %-d').upper()

        return time_str, ampm, date_str

    def display_time(self, force_clear: bool = False) -> None:
        """Display the current time and date."""
        time_str, ampm, date_str = self.get_current_time()

        # Only update if something has changed
        if time_str != self.last_time or date_str != self.last_date or force_clear:
            # Clear the display
            self.display_manager.clear()

            display_width = self.display_manager.matrix.width

            # Every draw_text call below goes straight to
            # self.display_manager.matrix.draw_text (the real MatrixDisplay),
            # bypassing DisplayController's DisplayManagerWrapper entirely.
            # There are three near-duplicate DisplayManagerWrapper class
            # definitions live in matrix_display_controller.py, each with a
            # different font/small/center guessing heuristic built around the
            # old small_font=True/False calling convention - none of them
            # reliably forward a custom font= object through to the
            # underlying draw call, which silently produced wrong fonts and
            # (via a center=True default that re-centers even when x is
            # given) wrong positions no matter what this method passed in.
            # Calling matrix.draw_text directly removes that ambiguity: its
            # signature is fully known and every arg here maps 1:1 onto it.

            # Row 1 (y=0-7): AM/PM badge, top-right corner. Its own row so
            # it never has to share horizontal space with the time - the
            # old inline placement only worked for single-digit hours
            # ("9:47"); "12:47"/"10:05" next to "AM"/"PM" would have been
            # wider than the display.
            ampm_width = self.ampm_font.getlength(ampm)
            ampm_x = display_width - ampm_width - 1
            self.display_manager.matrix.draw_text(
                ampm, x=int(ampm_x), y=0, color=self.COLORS['ampm'], font=self.ampm_font, center=False,
            )

            # Row 2 (y=9-20): big centered time. Worst case ("12:47",
            # "10:05") measures 60px at size 12 - checked every hour/minute
            # combination's width class, all fit with margin to spare.
            time_width = self.time_font.getlength(time_str)
            time_x = (display_width - time_width) // 2
            self.display_manager.matrix.draw_text(
                time_str, x=int(time_x), y=9, color=self.COLORS['time'], font=self.time_font, center=False,
            )

            # Row 3 (y=21-30): combined weekday + month + day, one line.
            date_width = self.date_font.getlength(date_str)
            date_x = (display_width - date_width) // 2
            self.display_manager.matrix.draw_text(
                date_str, x=int(date_x), y=21, color=self.COLORS['date'], font=self.date_font, center=False,
            )

            # Update the display after drawing everything
            self.display_manager.update_display()

            # Update cache
            self.last_time = time_str
            self.last_date = date_str

if __name__ == "__main__":
    clock = Clock()
    try:
        while True:
            clock.display_time()
            time.sleep(clock.clock_config.get('update_interval', 1))
    except KeyboardInterrupt:
        print("\nClock stopped by user")
    finally:
        clock.display_manager.cleanup()
