import os
import json
import logging
from datetime import date
from PIL import ImageDraw, ImageFont
from src.config_manager import ConfigManager
import time
try:
    import freetype
except ImportError:
    freetype = None

# Configure logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class OfTheDayManager:
    def __init__(self, display_manager, config):
        logger.info("Initializing OfTheDayManager")
        self.display_manager = display_manager
        self.config = config
        self.of_the_day_config = config.get('of_the_day', {})
        self.enabled = self.of_the_day_config.get('enabled', False)
        self.update_interval = self.of_the_day_config.get('update_interval', 3600)  # 1 hour default
        self.subtitle_rotate_interval = self.of_the_day_config.get('subtitle_rotate_interval', 10)  # 10 seconds default
        self.display_rotate_interval = self.of_the_day_config.get('display_rotate_interval', 30)  # 30 seconds default
        self.last_update = 0
        self.last_display_log = 0
        self.current_day = None
        self.current_items = {}
        self.current_item_index = 0
        self.current_category_index = 0
        self.last_drawn_category_index = -1
        self.last_drawn_day = None
        self.force_clear = False
        self.rotation_state = 0  # 0 = subtitle, 1 = description
        self.last_rotation_time = time.time()
        self.last_category_rotation_time = time.time()

        # Load fonts with robust path resolution and fallbacks
        try:
            # Try multiple font directory locations
            script_dir = os.path.dirname(os.path.abspath(__file__))
            possible_font_dirs = [
                os.path.abspath(os.path.join(script_dir, '..', 'assets', 'fonts')),  # Relative to src/
                os.path.abspath(os.path.join(os.getcwd(), 'assets', 'fonts')),      # Relative to project root
                os.path.abspath('assets/fonts'),  # Simple relative path made absolute
                'assets/fonts'  # Simple relative path
            ]
            
            font_dir = None
            for potential_dir in possible_font_dirs:
                if os.path.exists(potential_dir):
                    font_dir = potential_dir
                    logger.debug(f"Found font directory at: {font_dir}")
                    break
            
            if font_dir is None:
                logger.warning("No font directory found, using fallback fonts")
                raise FileNotFoundError("Font directory not found")

            def _safe_load_bdf_font(filename):
                try:
                    # Try multiple font paths
                    font_paths = [
                        os.path.abspath(os.path.join(font_dir, filename)),
                        os.path.join(font_dir, filename),
                        os.path.join(script_dir, '..', 'assets', 'fonts', filename),
                        os.path.join(script_dir, '..', 'assets', 'fonts', filename)
                    ]
                    
                    for font_path in font_paths:
                        abs_font_path = os.path.abspath(font_path)
                        if os.path.exists(abs_font_path):
                            logger.debug(f"Loading BDF font: {abs_font_path}")
                            if freetype is not None:
                                return freetype.Face(abs_font_path)
                            else:
                                logger.warning("freetype module not available, cannot load BDF fonts")
                                return None
                    
                    logger.debug(f"Font file not found: {filename}")
                    # List available fonts for debugging
                    try:
                        available_fonts = [f for f in os.listdir(font_dir) if f.endswith('.bdf')]
                        logger.debug(f"Available BDF fonts in {font_dir}: {available_fonts}")
                    except:
                        pass
                    return None
                except Exception as e:
                    logger.debug(f"Failed to load BDF font '{filename}': {e}")
                    return None

            self.title_font = _safe_load_bdf_font('ic8x8u.bdf')
            self.body_font = _safe_load_bdf_font('MatrixLight6.bdf')

            # Fallbacks if BDF fonts aren't available
            if self.title_font is None:
                self.title_font = getattr(self.display_manager, 'bdf_5x7_font', None) or getattr(self.display_manager, 'small_font', ImageFont.load_default())
                logger.info("Using fallback font for title in OfTheDayManager")
            if self.body_font is None:
                self.body_font = getattr(self.display_manager, 'bdf_5x7_font', None) or getattr(self.display_manager, 'small_font', ImageFont.load_default())
                logger.info("Using fallback font for body in OfTheDayManager")

            # Log font types for debugging
            logger.debug(f"Title font type: {type(self.title_font).__name__}")
            logger.debug(f"Body font type: {type(self.body_font).__name__}")
        except Exception as e:
            logger.warning(f"Error during font initialization, using fallbacks: {e}")
            # Last-resort fallback
            self.title_font = getattr(self.display_manager, 'small_font', ImageFont.load_default())
            self.body_font = getattr(self.display_manager, 'small_font', ImageFont.load_default())

        # Load categories and their data
        self.categories = self.of_the_day_config.get('categories', {})
        self.category_order = self.of_the_day_config.get('category_order', [])
        
        # Display properties
        self.title_color = (255, 255, 255)  # White
        self.subtitle_color = (200, 200, 200)  # Light gray
        self.background_color = (0, 0, 0)  # Black
        
        # State management
        self.force_clear = False
        self.last_drawn_category_index = -1
        self.last_drawn_day = None
        
        # Load data files
        self.data_files = {}
        logger.info("Loading data files for OfTheDayManager...")
        self._load_data_files()
        logger.info(f"Loaded {len(self.data_files)} data files: {list(self.data_files.keys())}")
        
        logger.info(f"OfTheDayManager configuration: enabled={self.enabled}, categories={list(self.categories.keys())}")
        
        if self.enabled:
            logger.info("OfTheDayManager is enabled, loading today's items...")
            self._load_todays_items()
            logger.info(f"After loading, current_items has {len(self.current_items)} items: {list(self.current_items.keys())}")
        else:
            logger.warning("OfTheDayManager is disabled in configuration")
    
    def _load_data_files(self):
        """Load all data files for enabled categories."""
        if not self.enabled:
            logger.debug("OfTheDayManager is disabled, skipping data file loading")
            return
            
        logger.info(f"Loading data files for {len(self.categories)} categories")
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Script directory: {os.path.dirname(__file__)}")
        
        # Additional debugging for Pi environment
        logger.debug(f"Absolute script directory: {os.path.abspath(os.path.dirname(__file__))}")
        logger.debug(f"Absolute working directory: {os.path.abspath(os.getcwd())}")
        
        # Check if we're running on Pi
        if os.path.exists('/home/ledpi'):
            logger.debug("Detected Pi environment (/home/ledpi exists)")
        else:
            logger.debug("Not running on Pi environment")
            
        for category_name, category_config in self.categories.items():
            logger.debug(f"Processing category: {category_name}")
            if not category_config.get('enabled', True):
                logger.debug(f"Skipping disabled category: {category_name}")
                continue
                
            data_file = category_config.get('data_file')
            if not data_file:
                logger.warning(f"No data file specified for category: {category_name}")
                continue
                
            try:
                # Try multiple possible paths for data files
                script_dir = os.path.dirname(os.path.abspath(__file__))
                current_dir = os.getcwd()
                project_root = os.path.dirname(script_dir)  # Go up one level from src/ to project root
                possible_paths = []
                
                logger.debug(f"Script directory: {script_dir}")
                logger.debug(f"Current working directory: {current_dir}")
                logger.debug(f"Project root directory: {project_root}")
                logger.debug(f"Data file from config: {data_file}")
                
                if os.path.isabs(data_file):
                    possible_paths.append(data_file)
                else:
                    # Always try multiple paths regardless of how data_file is specified
                    possible_paths.extend([
                        os.path.join(current_dir, data_file),  # Current working directory first
                        os.path.join(project_root, data_file),  # Project root directory
                        os.path.join(script_dir, '..', data_file),  # Relative to script directory
                        data_file  # Direct path
                    ])
                    
                    # If data_file doesn't already contain 'of_the_day/', also try with it
                    if not data_file.startswith('of_the_day/'):
                        possible_paths.extend([
                            os.path.join(current_dir, 'of_the_day', os.path.basename(data_file)),
                            os.path.join(project_root, 'of_the_day', os.path.basename(data_file)),
                            os.path.join(script_dir, '..', 'of_the_day', os.path.basename(data_file)),
                            os.path.join('of_the_day', os.path.basename(data_file))
                        ])
                    else:
                        # If data_file already contains 'of_the_day/', try extracting just the filename
                        filename = os.path.basename(data_file)
                        possible_paths.extend([
                            os.path.join(current_dir, 'of_the_day', filename),
                            os.path.join(project_root, 'of_the_day', filename),
                            os.path.join(script_dir, '..', 'of_the_day', filename),
                            os.path.join('of_the_day', filename)
                        ])
                
                # Debug: Show all paths before deduplication
                logger.debug(f"All possible paths before deduplication: {possible_paths}")
                
                # Remove duplicates while preserving order
                seen = set()
                unique_paths = []
                for path in possible_paths:
                    abs_path = os.path.abspath(path)
                    if abs_path not in seen:
                        seen.add(abs_path)
                        unique_paths.append(abs_path)
                possible_paths = unique_paths
                
                # Debug: Show paths after deduplication
                logger.debug(f"Unique paths after deduplication: {possible_paths}")
                
                file_path = None
                for potential_path in possible_paths:
                    abs_path = os.path.abspath(potential_path)
                    if os.path.exists(abs_path):
                        file_path = abs_path
                        logger.debug(f"Found data file for {category_name} at: {file_path}")
                        break
                
                # Final fallback - try the direct path relative to current working directory
                if file_path is None:
                    direct_path = os.path.join(current_dir, 'of_the_day', os.path.basename(data_file))
                    if os.path.exists(direct_path):
                        file_path = direct_path
                        logger.debug(f"Found data file for {category_name} using direct fallback: {file_path}")
                
                if file_path is None:
                    # Use the first attempted path for error reporting
                    file_path = os.path.abspath(possible_paths[0])
                    logger.debug(f"No data file found for {category_name}, tried: {[os.path.abspath(p) for p in possible_paths]}")
                    
                    # Additional debugging - check if parent directory exists
                    parent_dir = os.path.dirname(file_path)
                    logger.debug(f"Parent directory: {parent_dir}")
                    logger.debug(f"Parent directory exists: {os.path.exists(parent_dir)}")
                    if os.path.exists(parent_dir):
                        try:
                            parent_contents = os.listdir(parent_dir)
                            logger.debug(f"Parent directory contents: {parent_contents}")
                        except PermissionError:
                            logger.debug(f"Permission denied accessing parent directory: {parent_dir}")
                        except Exception as e:
                            logger.debug(f"Error listing parent directory: {e}")
                
                logger.debug(f"Attempting to load {category_name} from: {file_path}")
                
                if os.path.exists(file_path):
                    logger.debug(f"File exists, checking permissions...")
                    if not os.access(file_path, os.R_OK):
                        logger.error(f"File exists but is not readable: {file_path}")
                        self.data_files[category_name] = {}
                        continue
                    
                    # Get file size for debugging
                    file_size = os.path.getsize(file_path)
                    logger.debug(f"File size: {file_size} bytes")
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.data_files[category_name] = json.load(f)
                    
                    logger.info(f"Loaded data file for {category_name}: {len(self.data_files[category_name])} items")
                    logger.debug(f"Sample keys from {category_name}: {list(self.data_files[category_name].keys())[:5]}")
                    
                    # Validate that we have data
                    if not self.data_files[category_name]:
                        logger.warning(f"Loaded data file for {category_name} but it's empty!")
                    
                else:
                    logger.error(f"Data file not found for {category_name}: {file_path}")
                    parent_dir = os.path.dirname(file_path)
                    if os.path.exists(parent_dir):
                        try:
                            dir_contents = os.listdir(parent_dir)
                            logger.error(f"Directory contents of {parent_dir}: {dir_contents}")
                        except PermissionError:
                            logger.error(f"Permission denied accessing directory: {parent_dir}")
                        except Exception as e:
                            logger.error(f"Error listing directory {parent_dir}: {e}")
                    else:
                        logger.error(f"Parent directory does not exist: {parent_dir}")
                    logger.error(f"Tried paths: {[os.path.abspath(p) for p in possible_paths]}")
                    self.data_files[category_name] = {}
                    
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error loading data file for {category_name}: {e}")
                logger.error(f"File path: {file_path}")
                self.data_files[category_name] = {}
            except UnicodeDecodeError as e:
                logger.error(f"Unicode decode error loading data file for {category_name}: {e}")
                logger.error(f"File path: {file_path}")
                self.data_files[category_name] = {}
            except Exception as e:
                logger.error(f"Unexpected error loading data file for {category_name}: {e}")
                logger.error(f"File path: {file_path}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                self.data_files[category_name] = {}
    
    def _load_todays_items(self):
        """Load items for today based on the current date."""
        if not self.enabled:
            return
            
        today = date.today()
        day_of_year = today.timetuple().tm_yday
        logger.info(f"Loading items for day {day_of_year} of the year")
        logger.debug(f"Available data files: {list(self.data_files.keys())}")
        
        self.current_items = {}
        
        for category_name, category_config in self.categories.items():
            if not category_config.get('enabled', True):
                logger.debug(f"Skipping disabled category: {category_name}")
                continue
                
            data = self.data_files.get(category_name, {})
            if not data:
                logger.warning(f"No data loaded for category: {category_name}")
                logger.debug(f"Data files available: {list(self.data_files.keys())}")
                logger.debug(f"Category config: {category_config}")
                continue
                
            logger.debug(f"Checking category {category_name} for day {day_of_year}")
            logger.debug(f"Data file contains {len(data)} items")
            
            # Get item for today (day of year)
            item = data.get(str(day_of_year))
            if item:
                self.current_items[category_name] = item
                logger.info(f"Loaded {category_name} item for day {day_of_year}: {item.get('title', 'No title')}")
            else:
                logger.warning(f"No item found for {category_name} on day {day_of_year}")
                # Show more detailed information about available days
                available_days = [k for k in data.keys() if k.isdigit()]
                nearby_days = [k for k in available_days if abs(int(k) - day_of_year) <= 5]
                logger.debug(f"Available days in {category_name}: {sorted(available_days)[:10]}...")
                logger.debug(f"Days near {day_of_year}: {sorted(nearby_days)}")
        
        self.current_day = today
        self.current_category_index = 0
        self.current_item_index = 0
    
    def update(self, current_time):
        """Update items if needed (daily or on interval)."""
        if not self.enabled:
            logger.debug("OfTheDayManager is disabled, skipping update")
            return
        
        today = date.today()
        
        # Check if we need to load new items (new day or first time)
        if self.current_day != today:
            logger.info("New day detected, loading new items")
            self._load_todays_items()
        
        # Check if we need to update based on interval
        if current_time - self.last_update > self.update_interval:
            logger.debug("OfTheDayManager update interval reached")
            self.last_update = current_time
    
    def _draw_bdf_text(self, draw, face, text, x, y, color=(255,255,255)):
        """Draw text for both BDF (FreeType Face) and PIL TTF fonts."""
        try:
            # If we have a PIL font, use native text rendering
            if freetype is None or not isinstance(face, freetype.Face):
                draw.text((x, y), text, fill=color, font=face)
                return

            # Compute baseline from font ascender so caller can pass top-left y
            try:
                ascender_px = face.size.ascender >> 6
            except Exception:
                ascender_px = 0
            baseline_y = y + ascender_px

            # Otherwise, render BDF glyphs manually
            for char in text:
                face.load_char(char)
                bitmap = face.glyph.bitmap
                
                # Get glyph metrics
                glyph_left = face.glyph.bitmap_left
                glyph_top = face.glyph.bitmap_top
                
                for i in range(bitmap.rows):
                    for j in range(bitmap.width):
                        try:
                            byte_index = i * bitmap.pitch + (j // 8)
                            if byte_index < len(bitmap.buffer):
                                byte = bitmap.buffer[byte_index]
                                if byte & (1 << (7 - (j % 8))):
                                    # Calculate actual pixel position
                                    pixel_x = x + glyph_left + j
                                    pixel_y = baseline_y - glyph_top + i
                                    # Only draw if within bounds
                                    if (0 <= pixel_x < self.display_manager.width and 0 <= pixel_y < self.display_manager.height):
                                        draw.point((pixel_x, pixel_y), fill=color)
                        except IndexError:
                            logger.warning(f"Index out of range for char '{char}' at position ({i}, {j})")
                            continue
                x += face.glyph.advance.x >> 6
        except Exception as e:
            logger.error(f"Error in _draw_bdf_text: {e}", exc_info=True)

    def draw_item(self, category_name, item):
        try:
            title = item.get('title', 'No Title')
            subtitle = item.get('subtitle', '')
            description = item.get('description', '')
            draw = ImageDraw.Draw(self.display_manager.image)
            matrix_width = self.display_manager.matrix.width
            matrix_height = self.display_manager.matrix.height
            title_font = self.title_font
            body_font = self.body_font
            
            # Get font heights using DisplayManager helpers (handles BDF and PIL fonts)
            try:
                title_height = self.display_manager.get_font_height(title_font)
            except Exception:
                title_height = 8
            try:
                body_height = self.display_manager.get_font_height(body_font)
            except Exception:
                body_height = 8
            
            # --- Dynamic Spacing Calculation ---
            # Calculate how much space we need and distribute it evenly
            margin_top = 8  # Shift everything down by 6 pixels
            margin_bottom = 1
            underline_space = 1  # Space for underline
            
            # Determine current content
            current_text = subtitle if (self.rotation_state == 0 and subtitle) else description
            if not current_text:
                current_text = ""
            
            # Pre-wrap the body text to determine how many lines we'll need
            available_width = matrix_width - 4  # Leave some margin
            wrapped_lines = self._wrap_text(current_text, available_width, body_font, max_lines=10, 
                                          line_height=body_height, max_height=matrix_height)
            # Filter out empty lines for spacing calculation
            actual_body_lines = [line for line in wrapped_lines if line.strip()]
            num_body_lines = len(actual_body_lines)
            
            # Calculate total content height needed
            title_content_height = title_height
            underline_content_height = underline_space
            body_content_height = num_body_lines * body_height if num_body_lines > 0 else 0
            
            total_content_height = title_content_height + underline_content_height + body_content_height
            available_space = matrix_height - margin_top - margin_bottom
            
            # Calculate dynamic spacing
            if total_content_height < available_space:
                # We have extra space - distribute it
                extra_space = available_space - total_content_height
                if num_body_lines > 0:
                    # Distribute space: 30% after title, 70% between body lines
                    space_after_title = max(2, int(extra_space * 0.3))
                    space_between_lines = max(1, int(extra_space * 0.7 / max(1, num_body_lines - 1))) if num_body_lines > 1 else 0
                else:
                    # No body text - just center the title
                    space_after_title = extra_space // 2
                    space_between_lines = 0
            else:
                # Tight spacing
                space_after_title = 4
                space_between_lines = 1
            
            # --- Draw Title ---
            title_y = margin_top
            
            # Calculate title width for centering
            try:
                title_width = self.display_manager.get_text_width(title, title_font)
            except Exception:
                title_width = len(title) * 6
            
            # Center the title
            title_x = (matrix_width - title_width) // 2
            self._draw_bdf_text(draw, title_font, title, title_x, title_y, color=self.title_color)
            
            # --- Draw Underline ---
            underline_y = title_y + title_height + 1  # Reduced space after title
            underline_x_start = title_x
            underline_x_end = title_x + title_width
            draw.line([(underline_x_start, underline_y), (underline_x_end, underline_y)], fill=self.title_color, width=1)

            # --- Draw Body Text with Dynamic Spacing ---
            if num_body_lines > 0:
                body_start_y = underline_y + space_after_title + 1  # Shift description down 1 pixel
                current_y = body_start_y
                
                for i, line in enumerate(actual_body_lines):
                    if line.strip():  # Only draw non-empty lines
                        # Center each line of body text
                        try:
                            line_width = self.display_manager.get_text_width(line, body_font)
                        except Exception:
                            line_width = len(line) * 6
                        line_x = (matrix_width - line_width) // 2
                        
                        # Draw the line
                        self._draw_bdf_text(draw, body_font, line, line_x, current_y, color=self.subtitle_color)
                        
                        # Move to next line position
                        if i < len(actual_body_lines) - 1:  # Not the last line
                            current_y += body_height + space_between_lines
            
            return True
        except Exception as e:
            logger.error(f"Error drawing 'of the day' item: {e}", exc_info=True)
            return False

    def _wrap_text(self, text, max_width, face, max_lines=3, line_height=8, max_height=24):
        if not text:
            return [""]
        lines = []
        current_line = []
        words = text.split()
        for word in words:
            test_line = ' '.join(current_line + [word]) if current_line else word
            try:
                text_width = self.display_manager.get_text_width(test_line, face)
            except Exception:
                text_width = len(test_line) * 6
            if text_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    truncated = word
                    while len(truncated) > 0:
                        try:
                            test_width = self.display_manager.get_text_width(truncated + "...", face)
                        except Exception:
                            test_width = len(truncated) * 6
                        if test_width <= max_width:
                            lines.append(truncated + "...")
                            break
                        truncated = truncated[:-1]
                    if not truncated:
                        lines.append(word[:10] + "...")
            # Check if we've filled all lines (accounting for line spacing)
            if len(lines) * line_height >= max_height or len(lines) >= max_lines:
                break
        if current_line and (len(lines) * line_height < max_height and len(lines) < max_lines):
            lines.append(' '.join(current_line))
        while len(lines) < max_lines:
            lines.append("")
        return lines[:max_lines]
    
    def display(self, force_clear=False):
        if not self.enabled:
            return
        if not self.current_items:
            current_time = time.time()
            if not hasattr(self, 'last_warning_time') or current_time - self.last_warning_time > 10:
                logger.warning(f"OfTheDayManager has no current items.")
                self.last_warning_time = current_time
            return
        now = time.time()
        # Handle subtitle/description rotation
        if now - self.last_rotation_time > self.subtitle_rotate_interval:
            self.rotation_state = (self.rotation_state + 1) % 2
            self.last_rotation_time = now
            # Force redraw
            self.last_drawn_category_index = -1
            self.last_drawn_day = None
        # Handle OTD category rotation
        if now - self.last_category_rotation_time > self.display_rotate_interval:
            # Find the next category with valid data
            original_index = self.current_category_index
            self.current_category_index = (self.current_category_index + 1) % len(self.current_items)
            
            # If we've cycled through all categories and none have data, reset to first
            if self.current_category_index == original_index:
                logger.warning("No categories have valid data, staying on current category")
            else:
                logger.info(f"Internal rotation: from category index {original_index} to {self.current_category_index}")
                logger.info(f"Available categories with data: {list(self.current_items.keys())}")
            
            self.last_category_rotation_time = now
            # Reset subtitle/description rotation when switching category
            self.rotation_state = 0
            self.last_rotation_time = now
            # Force redraw
            self.last_drawn_category_index = -1
            self.last_drawn_day = None
        content_has_changed = self.current_category_index != self.last_drawn_category_index or self.current_day != self.last_drawn_day
        if not content_has_changed and not force_clear:
            return
        try:
            category_names = list(self.current_items.keys())
            if not category_names or self.current_category_index >= len(category_names):
                self.current_category_index = 0
                if not category_names: return
            current_category = category_names[self.current_category_index]
            current_item = self.current_items[current_category]
            current_time = time.time()
            if current_time - self.last_display_log > 5:
                logger.info(f"Displaying {current_category}: {current_item.get('title', 'No Title')}")
                self.last_display_log = current_time
            self.display_manager.clear()
            self.draw_item(current_category, current_item)
            self.display_manager.update_display()
            self.last_drawn_category_index = self.current_category_index
            self.last_drawn_day = self.current_day
        except Exception as e:
            logger.error(f"Error displaying 'of the day' item: {e}", exc_info=True)
    
    def advance_item(self):
        """Advance to the next item. Called by DisplayController when display time is up."""
        if not self.enabled:
            logger.debug("OfTheDayManager is disabled, skipping item advance")
            return
            
        # Check if internal rotation should happen first
        now = time.time()
        if now - self.last_category_rotation_time > self.display_rotate_interval:
            # Let the internal rotation handle it
            logger.debug("Internal rotation timer triggered, skipping external advance")
            return
            
        # Only advance if internal rotation hasn't happened recently
        # Add a buffer to prevent conflicts
        if now - self.last_category_rotation_time < self.display_rotate_interval - 5:
            logger.debug("Too close to internal rotation time, skipping external advance")
            return
            
        category_names = list(self.current_items.keys())
        if not category_names:
            return
            
        # Advance to next category
        original_index = self.current_category_index
        self.current_category_index = (self.current_category_index + 1) % len(category_names)
        
        # Update rotation time to prevent immediate internal rotation
        self.last_category_rotation_time = now
        
        # Reset subtitle/description rotation when switching category
        self.rotation_state = 0
        self.last_rotation_time = now
        
        # Force redraw
        self.last_drawn_category_index = -1
        self.last_drawn_day = None
        
        logger.debug(f"OfTheDayManager externally advanced from category index {original_index} to {self.current_category_index}") 