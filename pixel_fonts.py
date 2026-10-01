"""Native-size bitmap fonts for the 64x32 panel.

PressStart2P is an 8px grid font - rendered at 6px or 5px (the old
small/tiny fonts) Pillow resamples its glyphs, and they stop being
readable: B renders as D, 6 as G, 8 as 6 (BAL showed as "DAL", BTC as
"DTC", $84,016 as "$64,016" - confirmed live via /api/preview.png). The
BDF fonts in assets/fonts are drawn pixel-for-pixel at one size, so they
stay crisp. Pillow can't open BDF directly; each one is converted once to
Pillow's .pil/.pbm pair under assets/fonts/.pil-cache/ (gitignored).
"""

import logging
import os

from PIL import BdfFontFile, ImageFont

logger = logging.getLogger(__name__)

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")
CACHE_DIR = os.path.join(FONT_DIR, ".pil-cache")

_loaded = {}


def bdf(name: str):
    """Load assets/fonts/<name>.bdf as a Pillow bitmap font (cached)."""
    if name in _loaded:
        return _loaded[name]
    font = None
    try:
        pil_path = os.path.join(CACHE_DIR, f"{name}.pil")
        if not os.path.exists(pil_path):
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(os.path.join(FONT_DIR, f"{name}.bdf"), "rb") as fp:
                BdfFontFile.BdfFontFile(fp).save(os.path.join(CACHE_DIR, name))
        font = ImageFont.load(pil_path)
    except Exception as e:
        logger.warning(f"Could not load bitmap font {name}: {e}")
    _loaded[name] = font
    return font


def press_start(size: int = 8):
    """PressStart2P at its native 8px (or a multiple) - bold and legible."""
    key = f"ps2p-{size}"
    if key not in _loaded:
        try:
            _loaded[key] = ImageFont.truetype(os.path.join(FONT_DIR, "PressStart2P-Regular.ttf"), size)
        except Exception as e:
            logger.warning(f"Could not load PressStart2P: {e}")
            _loaded[key] = None
    return _loaded[key]


def fonts():
    """Size ladder used by the layouts, largest first. Missing fonts fall
    back to Pillow's default so the display never crashes on a font."""
    default = ImageFont.load_default()
    return {
        "large": press_start(8) or default,   # 8px tall, 8px advance
        "medium": bdf("6x9") or default,      # 9px tall, 6px advance
        "small": bdf("5x7") or default,       # 7px tall, 6px advance
        "tiny": bdf("4x6") or default,        # 6px tall, 4px advance
    }
