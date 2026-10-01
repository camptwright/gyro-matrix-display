#!/usr/bin/env python3
"""
Web Configuration Interface for Matrix Display

Also owns the live DisplayController: this process is the single service
that both edits persistent config (favorites, areas, toggles) and drives
the display + exposes live remote-control actions (mode switching,
in-mode navigation) that used to come from a BLE gyroscope remote.
"""

from flask import Flask, render_template_string, request, jsonify, send_from_directory, Response
import json
import os
import sys
import threading
import time
from pathlib import Path
from werkzeug.utils import secure_filename

app = Flask(__name__)
# Absolute path, but the same "config/config.json" convention ConfigManager
# (src/config_manager.py) uses by default -- matrix_display_controller.py's
# DisplayController and this file must agree on one config file now that
# they share a process.
_script_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(_script_dir, "config", "config.json")

print(f"Web config service using config file: {CONFIG_FILE}")


def load_config():
    """Load configuration from JSON file"""
    default_config = {
        "brightness": 50,
        "timezone": "America/New_York",
        "clock_locations": [],
        "sports": [],
        "favorite_teams": [],
        "stocks": {"enabled": True, "symbols": []},
        "crypto": {"enabled": True, "symbols": []},
        "fantasy_players": [],
        "weather_locations": [],
        "fantasy_mode": {
            "enabled": True
        },
        "stocks_mode": {
            "enabled": True
        },
        "weather_mode": {
            "enabled": True
        },
        "music": {
            "enabled": False,
            "preferred_source": "spotify",
            "POLLING_INTERVAL_SECONDS": 2
        }
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Merge with defaults
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            print(f"Error loading config: {e}")
            return default_config
    else:
        # Create default config file
        config_dir = os.path.dirname(CONFIG_FILE)
        if config_dir:  # Only create dir if there's a directory component
            os.makedirs(config_dir, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=2)
        return default_config


def save_config(config):
    """Save configuration to JSON file"""
    try:
        config_dir = os.path.dirname(CONFIG_FILE)
        if config_dir:  # Only create dir if there's a directory component
            os.makedirs(config_dir, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Config saved to: {CONFIG_FILE}")
        print(f"Config contents: sports={len(config.get('sports', []))}, stocks={len(config.get('stocks', []))}, crypto={len(config.get('crypto', []))}, fantasy_players={len(config.get('fantasy_players', []))}, weather={len(config.get('weather_locations', []))}")
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        import traceback
        traceback.print_exc()
        return False


# ─── Live display control ──────────────────────────────────────────────────
# Replaces the BLE gyroscope remote: this process now owns the running
# DisplayController directly (formerly done by receiver.py, a separate
# process with no connection to this one) and exposes its actions over
# HTTP for the "Remote Control" panel in the web UI.

try:
    from matrix_display_controller import DisplayController
except ImportError:
    DisplayController = None
    print("Warning: Could not import DisplayController; live control disabled")

display_controller: "DisplayController | None" = None


def start_display_controller():
    """Create the DisplayController and run its update loop in a background
    thread. Mirrors receiver.py's old ensure_display_controller()."""
    global display_controller
    if DisplayController is None:
        return
    if display_controller is not None:
        return
    try:
        display_controller = DisplayController()

        def run_display():
            try:
                display_controller.run()
            except Exception as e:
                print(f"Error in display loop: {e}")
                import traceback
                traceback.print_exc()

        threading.Thread(target=run_display, daemon=True, name="display-update").start()
        print("Display controller initialized and update loop started")
    except Exception as e:
        print(f"Error initializing display controller: {e}")
        import traceback
        traceback.print_exc()


def _music_action(method_name):
    def action(controller):
        manager = getattr(controller, "music_manager", None)
        if not manager:
            raise RuntimeError("Music manager not available")
        getattr(manager, method_name)()
    return action


# Every action the old BLE gesture handlers could trigger, keyed by an
# explicit name instead of (mode, axis, direction) -- see receiver.py in
# git history for the gesture-routing version this replaces.
CONTROL_ACTIONS = {
    "clock_prev_location": lambda c: c.prev_clock_location(),
    "clock_next_location": lambda c: c.next_clock_location(),
    "sports_prev_sport": lambda c: c.prev_sport(),
    "sports_next_sport": lambda c: c.next_sport(),
    "sports_prev_game": lambda c: c.prev_game(),
    "sports_next_game": lambda c: c.next_game(),
    "fantasy_prev_player": lambda c: c.prev_fantasy_player(),
    "fantasy_next_player": lambda c: c.next_fantasy_player(),
    "fantasy_prev_sport": lambda c: c.prev_fantasy_sport(),
    "fantasy_next_sport": lambda c: c.next_fantasy_sport(),
    "stocks_switch_submode": lambda c: c.switch_stocks_submode(),
    "stocks_prev_ticker": lambda c: c.prev_ticker(),
    "stocks_next_ticker": lambda c: c.next_ticker(),
    "weather_prev_location": lambda c: c.prev_weather_location(),
    "weather_next_location": lambda c: c.next_weather_location(),
    "images_switch_list": lambda c: c.switch_image_list(),
    "images_prev_image": lambda c: c.prev_image(),
    "images_next_image": lambda c: c.next_image(),
    "brightness_up": lambda c: c.brightness_up(),
    "brightness_down": lambda c: c.brightness_down(),
    "music_play_pause": _music_action("play_pause"),
    "music_prev_track": _music_action("skip_previous"),
    "music_next_track": _music_action("skip_next"),
}


def _require_controller():
    if display_controller is None:
        raise RuntimeError("Display controller is not running")
    return display_controller


@app.route('/api/control/state', methods=['GET'])
def control_state():
    try:
        controller = _require_controller()
        return jsonify({
            "current_mode": controller.current_mode,
            "modes": controller.modes,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@app.route('/api/control/mode', methods=['POST'])
def control_mode():
    try:
        controller = _require_controller()
        body = request.get_json(force=True, silent=True) or {}
        if "mode" in body:
            mode = body["mode"]
            if mode not in controller.modes:
                return jsonify({"error": f"Unknown or disabled mode: {mode}"}), 400
            controller.set_mode(mode)
        elif "direction" in body:
            raw = body["direction"]
            if isinstance(raw, str):
                direction = -1 if raw.lower() in ("prev", "previous", "-1") else 1
            else:
                direction = 1 if int(raw) >= 0 else -1
            controller.cycle_mode(direction)
        else:
            return jsonify({"error": "Request must include 'mode' or 'direction'"}), 400

        return jsonify({
            "current_mode": controller.current_mode,
            "modes": controller.modes,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/control/action', methods=['POST'])
def control_action():
    try:
        controller = _require_controller()
        body = request.get_json(force=True, silent=True) or {}
        action = body.get("action")
        handler = CONTROL_ACTIONS.get(action)
        if handler is None:
            return jsonify({"error": f"Unknown action: {action}"}), 400
        handler(controller)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/control/brightness', methods=['POST'])
def control_brightness():
    """Sets an absolute brightness value (0-100) -- distinct from the
    brightness_up/brightness_down step actions in CONTROL_ACTIONS, for a
    slider UI that needs to land exactly where the user dragged it."""
    try:
        controller = _require_controller()
        body = request.get_json(force=True, silent=True) or {}
        value = max(0, min(100, int(body.get("brightness"))))
        controller.config['brightness'] = value
        controller.matrix.set_brightness(value)
        controller.save_config()
        return jsonify({"success": True, "brightness": value})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Matrix Display Configuration</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="/static/htmx.min.js"></script>
    <style>
        :root {
            --bg-1: #667eea; --bg-2: #764ba2;
            --container-bg: #ffffff; --heading: #333;
            --section-bg: #f8f9fa; --section-heading: #667eea;
            --label: #555; --input-border: #ddd;
            --input-bg: #ffffff; --input-text: #1a1a1a;
            --accent: #667eea; --accent-hover: #5568d3;
            --item-bg: #ffffff; --item-border: #ddd;
            --muted: #666;
        }
        body.dark-mode {
            --bg-1: #0f172a; --bg-2: #1e1b4b;
            --container-bg: #1e293b; --heading: #e2e8f0;
            --section-bg: #0f172a; --section-heading: #a5b4fc;
            --label: #94a3b8; --input-border: #334155;
            --input-bg: #0f172a; --input-text: #e2e8f0;
            --accent: #818cf8; --accent-hover: #6366f1;
            --item-bg: #0f172a; --item-border: #334155;
            --muted: #94a3b8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, var(--bg-1) 0%, var(--bg-2) 100%);
            padding: 20px;
            min-height: 100vh;
            transition: background 0.2s ease;
        }
        .header-row {
            max-width: 1200px;
            margin: 0 auto 0;
            display: flex;
            justify-content: flex-end;
        }
        .theme-toggle {
            background: rgba(255,255,255,0.25);
            color: white;
            border: 1px solid rgba(255,255,255,0.4);
            padding: 8px 14px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 13px;
            margin-bottom: 10px;
        }
        .theme-toggle:hover { background: rgba(255,255,255,0.35); }
        .remote-link {
            display: inline-block;
            background: rgba(255,255,255,0.25);
            color: white;
            border: 1px solid rgba(255,255,255,0.4);
            padding: 8px 14px;
            border-radius: 20px;
            font-size: 13px;
            margin: 0 10px 10px 0;
            text-decoration: none;
        }
        .remote-link:hover { background: rgba(255,255,255,0.35); }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: var(--container-bg);
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 30px;
            transition: background 0.2s ease;
        }
        h1 {
            color: var(--heading);
            margin-bottom: 30px;
            text-align: center;
        }
        .section {
            margin-bottom: 40px;
            padding: 20px;
            background: var(--section-bg);
            border-radius: 8px;
            transition: background 0.2s ease;
        }
        .section h2 {
            color: var(--section-heading);
            margin-bottom: 15px;
            font-size: 1.5em;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: var(--label);
            font-weight: 500;
        }
        input, select {
            width: 100%;
            padding: 10px;
            border: 2px solid var(--input-border);
            border-radius: 5px;
            font-size: 14px;
            background: var(--input-bg);
            color: var(--input-text);
        }
        input:focus, select:focus {
            outline: none;
            border-color: var(--accent);
        }
        button {
            background: var(--accent);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            margin-right: 10px;
            margin-top: 10px;
        }
        button:hover {
            background: var(--accent-hover);
        }
        button.danger {
            background: #e74c3c;
        }
        button.danger:hover {
            background: #c0392b;
        }
        .item-list {
            margin-top: 15px;
        }
        .item {
            background: var(--item-bg);
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 5px;
            border: 1px solid var(--item-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .item-info {
            flex: 1;
        }
        .item-actions {
            display: flex;
            gap: 10px;
        }
        .brightness-control {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .brightness-slider {
            flex: 1;
        }
        .brightness-value {
            font-size: 1.2em;
            font-weight: bold;
            color: var(--accent);
            min-width: 50px;
        }
        .success {
            background: #2ecc71;
            color: white;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
            display: none;
        }
        .error {
            background: #e74c3c;
            color: white;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
            display: none;
        }
        .mode-buttons, .action-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .mode-buttons button {
            margin: 0;
        }
        .mode-buttons button.active-mode {
            background: #2ecc71;
        }
        .action-buttons {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #ddd;
        }
        .action-buttons button {
            margin: 0;
        }
        .current-mode-label {
            color: var(--muted);
            margin-bottom: 10px;
        }
        .current-mode-label strong {
            color: var(--accent);
        }
        .preview-wrap {
            display: flex;
            justify-content: center;
            background: #000;
            border-radius: 8px;
            padding: 16px;
        }
        .live-preview-img {
            width: 100%;
            max-width: 512px;
            height: auto;
            image-rendering: pixelated;
            image-rendering: crisp-edges;
            border-radius: 4px;
        }
        .live-preview-img.preview-offline {
            opacity: 0.3;
        }
        .preview-hint {
            text-align: center;
            font-size: 0.85em;
            color: var(--text-secondary, #888);
            margin-top: 8px;
        }
    </style>
</head>
<body>
    <div class="header-row">
        <a class="remote-link" href="/remote" target="_blank">📱 Open Remote Control</a>
        <button class="theme-toggle" onclick="toggleTheme()">
            <span id="themeIcon">🌙</span> <span id="themeText">Dark Mode</span>
        </button>
    </div>
    <div class="container">
        <h1>🎮 Matrix Display Configuration</h1>

        <div id="message"></div>

        <!-- Live Preview: mirrors the exact frame currently pushed to the
             real 64x32 panel, served by /api/preview.png (MatrixDisplay's
             last_frame, scaled 8x with nearest-neighbor so it reads as
             LEDs rather than a blurry photo). Polled on a plain interval
             rather than push/websocket - simplest thing that works for a
             ~3fps display and one viewer at a time. -->
        <div class="section">
            <h2>Live Preview</h2>
            <div class="preview-wrap">
                <img id="livePreview" src="/api/preview.png" alt="Live matrix display preview"
                     class="live-preview-img" onerror="this.classList.add('preview-offline')">
            </div>
            <p class="preview-hint">Updates ~3x/second - this is the exact frame the physical panel is showing.</p>
        </div>

        <!-- Remote Control (replaces the old BLE gyroscope remote) -->
        <div class="section">
            <h2>Remote Control</h2>
            <p class="current-mode-label">Current mode: <strong id="currentModeLabel">—</strong></p>
            <div class="mode-buttons" id="modeButtons"></div>
            <div class="action-buttons" id="modeActions"></div>
        </div>

        <!-- Brightness Control -->
        <div class="section">
            <h2>Brightness</h2>
            <div class="brightness-control">
                <label>Brightness Level:</label>
                <input type="range" id="brightness" min="0" max="100" value="{{ brightness }}" 
                       class="brightness-slider" oninput="updateBrightness(this.value)">
                <span class="brightness-value" id="brightnessValue">{{ brightness }}%</span>
            </div>
        </div>
        
        <!-- Clock Locations -->
        <div class="section">
            <h2>Clock Locations (Time Zones)</h2>
            <form hx-post="/htmx/clock/add" hx-target="#clockList" hx-swap="innerHTML"
                  hx-on::after-request="if(event.detail.successful) this.reset()">
                <div class="form-group">
                    <label>Location Name:</label>
                    <input type="text" name="name" placeholder="e.g., New York" required>
                </div>
                <div class="form-group">
                    <label>Time Zone:</label>
                    <select name="timezone">
                        <option value="America/New_York">America/New_York (EST/EDT)</option>
                        <option value="America/Chicago">America/Chicago (CST/CDT)</option>
                        <option value="America/Denver">America/Denver (MST/MDT)</option>
                        <option value="America/Los_Angeles">America/Los_Angeles (PST/PDT)</option>
                        <option value="Europe/London">Europe/London (GMT/BST)</option>
                        <option value="Europe/Paris">Europe/Paris (CET/CEST)</option>
                        <option value="Asia/Tokyo">Asia/Tokyo (JST)</option>
                        <option value="UTC">UTC</option>
                    </select>
                </div>
                <button type="submit">Add Location</button>
            </form>
            <div class="item-list" id="clockList">{{ clock_fragment|safe }}</div>
        </div>
        
        <!-- Sports -->
        <div class="section">
            <h2>Sports</h2>
            <form hx-post="/htmx/sports/add" hx-target="#sportsList" hx-swap="innerHTML"
                  hx-on::after-request="if(event.detail.successful) this.reset()">
                <div class="form-group">
                    <label>Sport Name:</label>
                    <input type="text" name="name" placeholder="e.g., NBA, NFL, MLB" required>
                </div>
                <div class="form-group">
                    <label>Team/League ID (optional):</label>
                    <input type="text" name="id" placeholder="e.g., team abbreviation">
                </div>
                <button type="submit">Add Sport</button>
            </form>
            <div class="item-list" id="sportsList">{{ sports_fragment|safe }}</div>
        </div>
        
        <!-- Favorite Teams -->
        <div class="section">
            <h2>Favorite Sports Teams</h2>
            <p style="font-size: 0.9em; color: #666; margin-bottom: 15px;">
                Add your favorite teams to see their games first in sports mode. Games involving your favorite teams will be shown in a separate "Favorites" section.
            </p>
            <form hx-post="/htmx/favorites/add" hx-target="#favoritesList" hx-swap="innerHTML"
                  hx-on::after-request="if(event.detail.successful) this.reset()">
                <div class="form-group">
                    <label>League/Sport:</label>
                    <select name="sport">
                        <option value="nfl">NFL</option>
                        <option value="nba">NBA</option>
                        <option value="mlb">MLB</option>
                        <option value="nhl">NHL</option>
                        <option value="ncaaf">NCAAF</option>
                        <option value="ncaam">NCAAM</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Team Name or Abbreviation:</label>
                    <input type="text" name="team" placeholder="e.g., LAL, Patriots, Yankees" style="text-transform: uppercase;" required>
                </div>
                <button type="submit">Add Favorite Team</button>
            </form>
            <div class="item-list" id="favoritesList">{{ favorites_fragment|safe }}</div>
        </div>
        
        <!-- Fantasy Players -->
        <div class="section">
            <h2>Fantasy Players</h2>
            <div class="form-group">
                <label>
                    <input type="checkbox" id="fantasyEnabled" onchange="updateFantasyEnabled()">
                    Enable Fantasy Mode
                </label>
            </div>
            <p style="font-size: 0.9em; color: #666; margin-bottom: 15px;">
                Add players to track their stats in fantasy mode. Supports NFL, NBA, and NHL. Use up/down flicks to cycle through sports, left/right to navigate players within each sport.
            </p>
            <form hx-post="/htmx/fantasy/add" hx-target="#fantasyPlayersList" hx-swap="innerHTML"
                  hx-on::after-request="if(event.detail.successful) this.reset()">
                <div class="form-group">
                    <label>Sport:</label>
                    <select name="sport">
                        <option value="nfl">NFL</option>
                        <option value="nba">NBA</option>
                        <option value="nhl">NHL</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Player Name:</label>
                    <input type="text" name="name" placeholder="e.g., Patrick Mahomes, Travis Kelce" required>
                </div>
                <div class="form-group">
                    <label>Team Abbreviation:</label>
                    <input type="text" name="team" placeholder="e.g., KC, BUF, SF" style="text-transform: uppercase;" required>
                </div>
                <button type="submit">Add Fantasy Player</button>
            </form>
            <div class="item-list" id="fantasyPlayersList">{{ fantasy_fragment|safe }}</div>
        </div>
        
        <!-- Stocks -->
        <div class="section">
            <h2>Stocks</h2>
            <div class="form-group">
                <label>
                    <input type="checkbox" id="stocksEnabled" onchange="updateStocksEnabled()">
                    Enable Stocks/Crypto Mode
                </label>
            </div>
            <form hx-post="/htmx/stocks/add" hx-target="#stocksList" hx-swap="innerHTML"
                  hx-on::after-request="if(event.detail.successful) this.reset()">
                <div class="form-group">
                    <label>Stock Ticker:</label>
                    <input type="text" name="ticker" placeholder="e.g., AAPL, MSFT, GOOGL" style="text-transform: uppercase;" required>
                </div>
                <button type="submit">Add Stock</button>
            </form>
            <div class="item-list" id="stocksList">{{ stocks_fragment|safe }}</div>
        </div>
        
        <!-- Crypto -->
        <div class="section">
            <h2>Cryptocurrency</h2>
            <form hx-post="/htmx/crypto/add" hx-target="#cryptoList" hx-swap="innerHTML"
                  hx-on::after-request="if(event.detail.successful) this.reset()">
                <div class="form-group">
                    <label>Crypto Ticker:</label>
                    <input type="text" name="ticker" placeholder="e.g., BTC, ETH, DOGE" style="text-transform: uppercase;" required>
                </div>
                <button type="submit">Add Crypto</button>
            </form>
            <div class="item-list" id="cryptoList">{{ crypto_fragment|safe }}</div>
        </div>
        
        <!-- Weather Locations -->
        <div class="section">
            <h2>Weather Locations</h2>
            <div class="form-group">
                <label>
                    <input type="checkbox" id="weatherEnabled" onchange="updateWeatherEnabled()">
                    Enable Weather Mode
                </label>
            </div>
            <form hx-post="/htmx/weather/add" hx-target="#weatherList" hx-swap="innerHTML"
                  hx-on::after-request="if(event.detail.successful) this.reset()">
                <div class="form-group">
                    <label>Location Name:</label>
                    <input type="text" name="name" placeholder="e.g., New York" required>
                </div>
                <div class="form-group">
                    <label>City:</label>
                    <input type="text" name="city" placeholder="e.g., New York" required>
                </div>
                <div class="form-group">
                    <label>State/Country:</label>
                    <input type="text" name="state" placeholder="e.g., NY, US" required>
                </div>
                <button type="submit">Add Location</button>
            </form>
            <div class="item-list" id="weatherList">{{ weather_fragment|safe }}</div>
        </div>
        
        <!-- Music Configuration -->
        <div class="section">
            <h2>Music (Spotify)</h2>
            <div class="form-group">
                <label>
                    <input type="checkbox" id="musicEnabled" onchange="updateMusicEnabled()">
                    Enable Music Mode
                </label>
            </div>
            <div class="form-group">
                <label>Preferred Source:</label>
                <select id="musicSource">
                    <option value="spotify">Spotify</option>
                </select>
            </div>
            <div class="form-group">
                <label>Polling Interval (seconds):</label>
                <input type="number" id="musicPollingInterval" min="1" max="10" value="2">
            </div>
            <p style="font-size: 0.9em; color: #666; margin-top: 10px;">
                Note: Spotify credentials must be configured in <code>config/config_secrets.json</code>
            </p>
        </div>
        
        <!-- Images/GIFs Upload -->
        <div class="section">
            <h2>Images & GIFs</h2>
            <p style="font-size: 0.9em; color: #666; margin-bottom: 15px;">
                Upload photos (PNG, JPG, JPEG) or GIFs to display on the matrix. Use up/down gestures to switch between photos and GIFs, and left/right to navigate through the list.
            </p>
            
            <div class="form-group">
                <label>Upload Type:</label>
                <select id="uploadType">
                    <option value="photo">Photo (PNG, JPG, JPEG)</option>
                    <option value="gif">GIF</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>Select File:</label>
                <input type="file" id="imageFile" accept=".png,.jpg,.jpeg,.gif">
            </div>
            
            <button onclick="uploadImage()">Upload Image/GIF</button>
            
            <div style="margin-top: 20px;">
                <h3>Uploaded Photos</h3>
                <div class="item-list" id="photosList"></div>
            </div>
            
            <div style="margin-top: 20px;">
                <h3>Uploaded GIFs</h3>
                <div class="item-list" id="gifsList"></div>
            </div>
        </div>
        
        <div style="text-align: center; margin-top: 30px;">
            <button onclick="saveConfig()" style="background: #2ecc71; font-size: 16px; padding: 15px 30px;">
                💾 Save Configuration
            </button>
        </div>
    </div>
    
    <script>
        let config = {{ config_json|safe }};

        // ─── Live Preview polling ──────────────────────────────────────
        // Plain interval + cache-busting query param, not a websocket -
        // the display only renders ~10x/second at most (see
        // DisplayController.update_interval), so anything push-based
        // would be a lot of machinery for a ~3fps still image.
        (function pollPreview() {
            const img = document.getElementById('livePreview');
            if (!img) return;
            setInterval(() => {
                img.src = '/api/preview.png?t=' + Date.now();
            }, 300);
        })();
        
        function showMessage(text, isError = false) {
            const msg = document.getElementById('message');
            msg.textContent = text;
            msg.className = isError ? 'error' : 'success';
            msg.style.display = 'block';
            setTimeout(() => {
                msg.style.display = 'none';
            }, 3000);
        }
        
        function updateBrightness(value) {
            document.getElementById('brightnessValue').textContent = value + '%';
            config.brightness = parseInt(value);
        }

        // ─── Remote control (replaces the old BLE gyroscope remote) ───────
        const MODE_LABELS = {
            clock: 'Clock', sports: 'Sports', fantasy: 'Fantasy',
            stocks: 'Stocks', weather: 'Weather', music: 'Music',
            images: 'Images', brightness: 'Brightness'
        };

        const MODE_ACTIONS = {
            clock: [['clock_prev_location', '◀ Prev Location'], ['clock_next_location', 'Next Location ▶']],
            sports: [
                ['sports_prev_sport', '◀ Prev Sport'], ['sports_next_sport', 'Next Sport ▶'],
                ['sports_prev_game', '◀ Prev Game'], ['sports_next_game', 'Next Game ▶']
            ],
            fantasy: [
                ['fantasy_prev_sport', '◀ Prev Sport'], ['fantasy_next_sport', 'Next Sport ▶'],
                ['fantasy_prev_player', '◀ Prev Player'], ['fantasy_next_player', 'Next Player ▶']
            ],
            stocks: [
                ['stocks_switch_submode', '⇄ Stocks / Crypto'],
                ['stocks_prev_ticker', '◀ Prev Ticker'], ['stocks_next_ticker', 'Next Ticker ▶']
            ],
            weather: [['weather_prev_location', '◀ Prev Location'], ['weather_next_location', 'Next Location ▶']],
            music: [
                ['music_prev_track', '◀ Prev Track'], ['music_play_pause', '⏯ Play / Pause'],
                ['music_next_track', 'Next Track ▶']
            ],
            images: [
                ['images_switch_list', '⇄ Photos / GIFs'],
                ['images_prev_image', '◀ Prev'], ['images_next_image', 'Next ▶']
            ],
            brightness: [['brightness_down', '− Dimmer'], ['brightness_up', '+ Brighter']],
        };

        function renderControlPanel(state) {
            document.getElementById('currentModeLabel').textContent = MODE_LABELS[state.current_mode] || state.current_mode;

            const modeButtons = document.getElementById('modeButtons');
            modeButtons.innerHTML = (state.modes || []).map(mode => {
                const active = mode === state.current_mode ? 'active-mode' : '';
                const label = MODE_LABELS[mode] || mode;
                return `<button class="${active}" onclick="setDisplayMode('${mode}')">${label}</button>`;
            }).join('');

            const actions = MODE_ACTIONS[state.current_mode] || [];
            document.getElementById('modeActions').innerHTML = actions.map(([action, label]) =>
                `<button onclick="sendControlAction('${action}')">${label}</button>`
            ).join('');
        }

        async function loadControlState() {
            try {
                const response = await fetch('/api/control/state');
                const state = await response.json();
                if (response.ok) {
                    renderControlPanel(state);
                }
            } catch (e) {
                console.error('Failed to load control state:', e);
            }
        }

        async function setDisplayMode(mode) {
            try {
                const response = await fetch('/api/control/mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode })
                });
                const state = await response.json();
                if (response.ok) {
                    renderControlPanel(state);
                } else {
                    showMessage(state.error || 'Failed to change mode', true);
                }
            } catch (e) {
                showMessage('Failed to change mode: ' + e, true);
            }
        }

        async function sendControlAction(action) {
            try {
                const response = await fetch('/api/control/action', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action })
                });
                const result = await response.json();
                if (!response.ok) {
                    showMessage(result.error || 'Action failed', true);
                }
            } catch (e) {
                showMessage('Action failed: ' + e, true);
            }
        }

        function updateMusicEnabled() {
            if (!config.music) {
                config.music = {};
            }
            try {
                const musicEnabledEl = document.getElementById('musicEnabled');
                if (musicEnabledEl) {
                    config.music.enabled = musicEnabledEl.checked;
                }
            } catch (e) {
                console.error('Error updating music enabled:', e);
            }
        }
        
        function updateFantasyEnabled() {
            if (!config.fantasy_mode) {
                config.fantasy_mode = {};
            }
            try {
                const fantasyEnabledEl = document.getElementById('fantasyEnabled');
                if (fantasyEnabledEl) {
                    config.fantasy_mode.enabled = fantasyEnabledEl.checked;
                }
            } catch (e) {
                console.error('Error updating fantasy enabled:', e);
            }
        }
        
        function updateStocksEnabled() {
            if (!config.stocks_mode) {
                config.stocks_mode = {};
            }
            try {
                const stocksEnabledEl = document.getElementById('stocksEnabled');
                if (stocksEnabledEl) {
                    config.stocks_mode.enabled = stocksEnabledEl.checked;
                }
            } catch (e) {
                console.error('Error updating stocks enabled:', e);
            }
        }
        
        function updateWeatherEnabled() {
            if (!config.weather_mode) {
                config.weather_mode = {};
            }
            try {
                const weatherEnabledEl = document.getElementById('weatherEnabled');
                if (weatherEnabledEl) {
                    config.weather_mode.enabled = weatherEnabledEl.checked;
                }
            } catch (e) {
                console.error('Error updating weather enabled:', e);
            }
        }
        
        async function loadImageLists() {
            try {
                const response = await fetch('/api/images/list');
                const data = await response.json();
                
                const photosList = document.getElementById('photosList');
                const gifsList = document.getElementById('gifsList');
                
                if (photosList && data.photos) {
                    photosList.innerHTML = data.photos.map((photo, idx) => `
                        <div class="item">
                            <div class="item-info">
                                <strong>${photo}</strong>
                            </div>
                            <div class="item-actions">
                                <button class="danger" onclick="deleteImage('photo', '${photo}')">Delete</button>
                            </div>
                        </div>
                    `).join('');
                }
                
                if (gifsList && data.gifs) {
                    gifsList.innerHTML = data.gifs.map((gif, idx) => `
                        <div class="item">
                            <div class="item-info">
                                <strong>${gif}</strong>
                            </div>
                            <div class="item-actions">
                                <button class="danger" onclick="deleteImage('gif', '${gif}')">Delete</button>
                            </div>
                        </div>
                    `).join('');
                }
            } catch (e) {
                console.error('Error loading image lists:', e);
            }
        }
        
        async function uploadImage() {
            const fileInput = document.getElementById('imageFile');
            const uploadType = document.getElementById('uploadType').value;
            const file = fileInput.files[0];
            
            if (!file) {
                showMessage('Please select a file', true);
                return;
            }
            
            // Validate file type
            const fileExt = file.name.split('.').pop().toLowerCase();
            if (uploadType === 'photo' && !['png', 'jpg', 'jpeg'].includes(fileExt)) {
                showMessage('Photo must be PNG, JPG, or JPEG', true);
                return;
            }
            if (uploadType === 'gif' && fileExt !== 'gif') {
                showMessage('File must be a GIF', true);
                return;
            }
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('type', uploadType);
            
            try {
                const response = await fetch('/api/images/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                if (result.success) {
                    showMessage(`File uploaded successfully: ${result.filename}`);
                    fileInput.value = '';
                    loadImageLists();
                } else {
                    showMessage(result.error || 'Upload failed', true);
                }
            } catch (e) {
                showMessage('Error uploading file: ' + e.message, true);
                console.error('Upload error:', e);
            }
        }
        
        async function deleteImage(type, filename) {
            if (!confirm(`Delete ${filename}?`)) {
                return;
            }
            
            try {
                const response = await fetch(`/api/images/delete/${type}/${encodeURIComponent(filename)}`, {
                    method: 'DELETE'
                });
                
                const result = await response.json();
                if (result.success) {
                    showMessage(`Deleted ${filename}`);
                    loadImageLists();
                } else {
                    showMessage(result.error || 'Delete failed', true);
                }
            } catch (e) {
                showMessage('Error deleting file: ' + e.message, true);
                console.error('Delete error:', e);
            }
        }
        
        function renderLists() {
            // Clock locations, sports, favorite teams, and fantasy
            // players are now server-rendered fragments too - see
            // their htmx forms. Same reasoning as stocks/crypto/weather
            // above: no client-side copy to fall out of sync.

            // Fantasy configuration
            if (!config.fantasy_mode) {
                config.fantasy_mode = { enabled: true };
            }
            try {
                const fantasyEnabledEl = document.getElementById('fantasyEnabled');
                if (fantasyEnabledEl) {
                    fantasyEnabledEl.checked = config.fantasy_mode.enabled !== false; // Default to true
                }
            } catch (e) {
                console.error('Error initializing fantasy config:', e);
            }
            
            // Stocks configuration
            if (!config.stocks_mode) {
                config.stocks_mode = { enabled: true };
            }
            try {
                const stocksEnabledEl = document.getElementById('stocksEnabled');
                if (stocksEnabledEl) {
                    stocksEnabledEl.checked = config.stocks_mode.enabled !== false; // Default to true
                }
            } catch (e) {
                console.error('Error initializing stocks config:', e);
            }
            
            // Weather configuration
            if (!config.weather_mode) {
                config.weather_mode = { enabled: true };
            }
            try {
                const weatherEnabledEl = document.getElementById('weatherEnabled');
                if (weatherEnabledEl) {
                    weatherEnabledEl.checked = config.weather_mode.enabled !== false; // Default to true
                }
            } catch (e) {
                console.error('Error initializing weather config:', e);
            }
            
            // Music configuration
            if (!config.music) {
                config.music = { enabled: false, preferred_source: "spotify", POLLING_INTERVAL_SECONDS: 2 };
            }
            try {
                const musicEnabledEl = document.getElementById('musicEnabled');
                const musicSourceEl = document.getElementById('musicSource');
                const musicPollingEl = document.getElementById('musicPollingInterval');
                if (musicEnabledEl) {
                    musicEnabledEl.checked = config.music.enabled || false;
                }
                if (musicSourceEl) {
                    musicSourceEl.value = config.music.preferred_source || "spotify";
                }
                if (musicPollingEl) {
                    musicPollingEl.value = config.music.POLLING_INTERVAL_SECONDS || 2;
                }
            } catch (e) {
                console.error('Error initializing music config:', e);
            }
        }
        
        // addClockLocation()/addSport()/addFavoriteTeam()/addFantasyPlayer()
        // removed - their forms now submit via htmx directly.

        // removeItem() removed - no remaining callers now that every
        // list section uses its own htmx delete route directly.

        async function saveConfig() {
            try {
                // Update fantasy config from form
                if (!config.fantasy_mode) {
                    config.fantasy_mode = {};
                }
                try {
                    const fantasyEnabledEl = document.getElementById('fantasyEnabled');
                    if (fantasyEnabledEl) {
                        config.fantasy_mode.enabled = fantasyEnabledEl.checked;
                    }
                } catch (e) {
                    console.error('Error reading fantasy config from form:', e);
                }
                
                // Update stocks config from form
                if (!config.stocks_mode) {
                    config.stocks_mode = {};
                }
                try {
                    const stocksEnabledEl = document.getElementById('stocksEnabled');
                    if (stocksEnabledEl) {
                        config.stocks_mode.enabled = stocksEnabledEl.checked;
                    }
                } catch (e) {
                    console.error('Error reading stocks config from form:', e);
                }
                
                // Update weather config from form
                if (!config.weather_mode) {
                    config.weather_mode = {};
                }
                try {
                    const weatherEnabledEl = document.getElementById('weatherEnabled');
                    if (weatherEnabledEl) {
                        config.weather_mode.enabled = weatherEnabledEl.checked;
                    }
                } catch (e) {
                    console.error('Error reading weather config from form:', e);
                }
                
                // Update music config from form
                if (!config.music) {
                    config.music = {};
                }
                try {
                    const musicEnabledEl = document.getElementById('musicEnabled');
                    const musicSourceEl = document.getElementById('musicSource');
                    const musicPollingEl = document.getElementById('musicPollingInterval');
                    if (musicEnabledEl) {
                        config.music.enabled = musicEnabledEl.checked;
                    }
                    if (musicSourceEl) {
                        config.music.preferred_source = musicSourceEl.value;
                    }
                    if (musicPollingEl) {
                        config.music.POLLING_INTERVAL_SECONDS = parseInt(musicPollingEl.value) || 2;
                    }
                } catch (e) {
                    console.error('Error reading music config from form:', e);
                }
                
                const response = await fetch('/api/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
                const result = await response.json();
                if (result.success) {
                    showMessage('Configuration saved successfully!');
                } else {
                    showMessage('Error saving configuration: ' + result.error, true);
                }
            } catch (error) {
                showMessage('Error saving configuration: ' + error, true);
            }
        }
        
        function toggleTheme() {
            const isDark = document.body.classList.toggle('dark-mode');
            document.getElementById('themeIcon').textContent = isDark ? '☀️' : '🌙';
            document.getElementById('themeText').textContent = isDark ? 'Light Mode' : 'Dark Mode';
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
        }

        function loadTheme() {
            const saved = localStorage.getItem('theme');
            const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
            const useDark = saved ? saved === 'dark' : prefersDark;
            if (useDark) {
                document.body.classList.add('dark-mode');
                document.getElementById('themeIcon').textContent = '☀️';
                document.getElementById('themeText').textContent = 'Light Mode';
            }
        }
        loadTheme();

        // Initialize
        renderLists();
        loadImageLists();
        loadControlState();
        setInterval(loadControlState, 5000);
    </script>
</body>
</html>
"""


# ─── htmx-managed lists ─────────────────────────────────────────────────
# Stocks, crypto, and weather locations moved off the page-load-then-mutate-
# a-JS-blob pattern that caused real bugs (a client-side type mismatch
# silently broke every section rendered after it). Each of these routes is
# the sole authority for its list: it reads config.json, mutates just its
# own key, saves, and returns the updated fragment - no shared client state
# to get out of sync with the backend's actual schema.

from markupsafe import escape as _esc


def _render_ticker_list(list_key, symbols):
    if not symbols:
        return ""
    items = []
    for idx, ticker in enumerate(symbols):
        items.append(f'''
            <div class="item">
                <div class="item-info"><strong>{_esc(ticker)}</strong></div>
                <div class="item-actions">
                    <button class="danger" hx-delete="/htmx/{list_key}/remove/{idx}"
                            hx-target="#{list_key}List" hx-swap="innerHTML"
                            hx-confirm="Remove {_esc(ticker)}?">Remove</button>
                </div>
            </div>''')
    return "".join(items)


def _render_weather_list(locations):
    if not locations:
        return ""
    items = []
    for idx, loc in enumerate(locations):
        name = _esc(loc.get("name", ""))
        city = _esc(loc.get("city", ""))
        state = _esc(loc.get("state", ""))
        items.append(f'''
            <div class="item">
                <div class="item-info"><strong>{name}</strong> - {city}, {state}</div>
                <div class="item-actions">
                    <button class="danger" hx-delete="/htmx/weather/remove/{idx}"
                            hx-target="#weatherList" hx-swap="innerHTML"
                            hx-confirm="Remove {name}?">Remove</button>
                </div>
            </div>''')
    return "".join(items)


@app.route('/htmx/stocks/add', methods=['POST'])
def htmx_add_stock():
    ticker = request.form.get('ticker', '').strip().upper()
    config = load_config()
    stocks = config.setdefault('stocks', {})
    symbols = stocks.setdefault('symbols', [])
    if ticker and ticker not in symbols:
        symbols.append(ticker)
        save_config(config)
        if display_controller is not None:
            try:
                display_controller.reload_config()
            except Exception as e:
                print(f"Could not reload config after stock add: {e}")
    return _render_ticker_list('stocks', symbols)


@app.route('/htmx/stocks/remove/<int:idx>', methods=['DELETE'])
def htmx_remove_stock(idx):
    config = load_config()
    symbols = config.setdefault('stocks', {}).setdefault('symbols', [])
    if 0 <= idx < len(symbols):
        symbols.pop(idx)
        save_config(config)
        if display_controller is not None:
            try:
                display_controller.reload_config()
            except Exception as e:
                print(f"Could not reload config after stock remove: {e}")
    return _render_ticker_list('stocks', symbols)


@app.route('/htmx/crypto/add', methods=['POST'])
def htmx_add_crypto():
    ticker = request.form.get('ticker', '').strip().upper()
    config = load_config()
    crypto = config.setdefault('crypto', {})
    symbols = crypto.setdefault('symbols', [])
    if ticker and ticker not in symbols:
        symbols.append(ticker)
        save_config(config)
        if display_controller is not None:
            try:
                display_controller.reload_config()
            except Exception as e:
                print(f"Could not reload config after crypto add: {e}")
    return _render_ticker_list('crypto', symbols)


@app.route('/htmx/crypto/remove/<int:idx>', methods=['DELETE'])
def htmx_remove_crypto(idx):
    config = load_config()
    symbols = config.setdefault('crypto', {}).setdefault('symbols', [])
    if 0 <= idx < len(symbols):
        symbols.pop(idx)
        save_config(config)
        if display_controller is not None:
            try:
                display_controller.reload_config()
            except Exception as e:
                print(f"Could not reload config after crypto remove: {e}")
    return _render_ticker_list('crypto', symbols)


@app.route('/htmx/weather/add', methods=['POST'])
def htmx_add_weather():
    name = request.form.get('name', '').strip()
    city = request.form.get('city', '').strip()
    state = request.form.get('state', '').strip()
    config = load_config()
    locations = config.setdefault('weather_locations', [])
    if name and city and state:
        locations.append({'name': name, 'city': city, 'state': state})
        save_config(config)
        if display_controller is not None:
            try:
                display_controller.reload_config()
            except Exception as e:
                print(f"Could not reload config after weather add: {e}")
    return _render_weather_list(locations)


@app.route('/htmx/weather/remove/<int:idx>', methods=['DELETE'])
def htmx_remove_weather(idx):
    config = load_config()
    locations = config.setdefault('weather_locations', [])
    if 0 <= idx < len(locations):
        locations.pop(idx)
        save_config(config)
        if display_controller is not None:
            try:
                display_controller.reload_config()
            except Exception as e:
                print(f"Could not reload config after weather remove: {e}")
    return _render_weather_list(locations)


# ─── htmx-managed lists, part 2 ────────────────────────────────────────
# Same pattern as stocks/crypto/weather above: each route is the sole
# authority for its own config key.

def _render_clock_list(locations):
    if not locations:
        return ""
    items = []
    for idx, loc in enumerate(locations):
        name = _esc(loc.get("name", ""))
        tz = _esc(loc.get("timezone", ""))
        items.append(f'''
            <div class="item">
                <div class="item-info"><strong>{name}</strong> - {tz}</div>
                <div class="item-actions">
                    <button class="danger" hx-delete="/htmx/clock/remove/{idx}"
                            hx-target="#clockList" hx-swap="innerHTML"
                            hx-confirm="Remove {name}?">Remove</button>
                </div>
            </div>''')
    return "".join(items)


def _render_sports_list(sports):
    if not sports:
        return ""
    items = []
    for idx, item in enumerate(sports):
        name = _esc(item.get("name", ""))
        sid = item.get("id")
        suffix = f" - {_esc(sid)}" if sid else ""
        items.append(f'''
            <div class="item">
                <div class="item-info"><strong>{name}</strong>{suffix}</div>
                <div class="item-actions">
                    <button class="danger" hx-delete="/htmx/sports/remove/{idx}"
                            hx-target="#sportsList" hx-swap="innerHTML"
                            hx-confirm="Remove {name}?">Remove</button>
                </div>
            </div>''')
    return "".join(items)


def _render_favorites_list(teams):
    if not teams:
        return ""
    items = []
    for idx, item in enumerate(teams):
        team = _esc(item.get("team", ""))
        sport = _esc(item.get("sport", "").upper())
        items.append(f'''
            <div class="item">
                <div class="item-info"><strong>{team}</strong> - {sport}</div>
                <div class="item-actions">
                    <button class="danger" hx-delete="/htmx/favorites/remove/{idx}"
                            hx-target="#favoritesList" hx-swap="innerHTML"
                            hx-confirm="Remove {team}?">Remove</button>
                </div>
            </div>''')
    return "".join(items)


def _render_fantasy_list(players):
    if not players:
        return ""
    items = []
    for idx, item in enumerate(players):
        name = _esc(item.get("name", ""))
        team = _esc(item.get("team") or "N/A")
        sport = _esc((item.get("sport") or "nfl").upper())
        items.append(f'''
            <div class="item">
                <div class="item-info"><strong>{name}</strong> - {team} ({sport})</div>
                <div class="item-actions">
                    <button class="danger" hx-delete="/htmx/fantasy/remove/{idx}"
                            hx-target="#fantasyPlayersList" hx-swap="innerHTML"
                            hx-confirm="Remove {name}?">Remove</button>
                </div>
            </div>''')
    return "".join(items)


def _reload_controller():
    if display_controller is not None:
        try:
            display_controller.reload_config()
        except Exception as e:
            print(f"Could not reload config: {e}")


@app.route('/htmx/clock/add', methods=['POST'])
def htmx_add_clock():
    name = request.form.get('name', '').strip()
    timezone = request.form.get('timezone', '').strip()
    config = load_config()
    locations = config.setdefault('clock_locations', [])
    if name and timezone:
        locations.append({'name': name, 'timezone': timezone})
        save_config(config)
        _reload_controller()
    return _render_clock_list(locations)


@app.route('/htmx/clock/remove/<int:idx>', methods=['DELETE'])
def htmx_remove_clock(idx):
    config = load_config()
    locations = config.setdefault('clock_locations', [])
    if 0 <= idx < len(locations):
        locations.pop(idx)
        save_config(config)
        _reload_controller()
    return _render_clock_list(locations)


@app.route('/htmx/sports/add', methods=['POST'])
def htmx_add_sport():
    name = request.form.get('name', '').strip()
    sport_id = request.form.get('id', '').strip()
    config = load_config()
    sports = config.setdefault('sports', [])
    if name:
        sports.append({'name': name, 'id': sport_id or None})
        save_config(config)
        _reload_controller()
    return _render_sports_list(sports)


@app.route('/htmx/sports/remove/<int:idx>', methods=['DELETE'])
def htmx_remove_sport(idx):
    config = load_config()
    sports = config.setdefault('sports', [])
    if 0 <= idx < len(sports):
        sports.pop(idx)
        save_config(config)
        _reload_controller()
    return _render_sports_list(sports)


@app.route('/htmx/favorites/add', methods=['POST'])
def htmx_add_favorite():
    sport = request.form.get('sport', '').strip().lower()
    team = request.form.get('team', '').strip().upper()
    config = load_config()
    teams = config.setdefault('favorite_teams', [])
    if sport and team:
        is_duplicate = any(
            t.get('sport', '').lower() == sport and t.get('team', '').upper() == team
            for t in teams
        )
        if not is_duplicate:
            teams.append({'sport': sport, 'team': team})
            save_config(config)
            _reload_controller()
    return _render_favorites_list(teams)


@app.route('/htmx/favorites/remove/<int:idx>', methods=['DELETE'])
def htmx_remove_favorite(idx):
    config = load_config()
    teams = config.setdefault('favorite_teams', [])
    if 0 <= idx < len(teams):
        teams.pop(idx)
        save_config(config)
        _reload_controller()
    return _render_favorites_list(teams)


@app.route('/htmx/fantasy/add', methods=['POST'])
def htmx_add_fantasy():
    sport = request.form.get('sport', '').strip().lower() or 'nfl'
    name = request.form.get('name', '').strip()
    team = request.form.get('team', '').strip().upper()
    config = load_config()
    players = config.setdefault('fantasy_players', [])
    if name and team:
        is_duplicate = any(
            p.get('name', '').lower() == name.lower()
            and (p.get('team') or '').upper() == team
            and (p.get('sport') or '').lower() == sport
            for p in players
        )
        if not is_duplicate:
            players.append({'name': name, 'team': team, 'sport': sport})
            save_config(config)
            _reload_controller()
    return _render_fantasy_list(players)


@app.route('/htmx/fantasy/remove/<int:idx>', methods=['DELETE'])
def htmx_remove_fantasy(idx):
    config = load_config()
    players = config.setdefault('fantasy_players', [])
    if 0 <= idx < len(players):
        players.pop(idx)
        save_config(config)
        _reload_controller()
    return _render_fantasy_list(players)


@app.route('/api/preview.png')
def preview_png():
    """Live PNG of the exact frame last pushed toward the real panel -
    powers the dashboard's Live Preview card. Scaled 8x with nearest-
    neighbor in MatrixDisplay.get_preview_png() so it reads as a matrix
    of LEDs rather than a blurry photo."""
    if display_controller is None or getattr(display_controller, 'matrix', None) is None:
        return jsonify({"error": "Display controller not running"}), 503
    png_bytes = display_controller.matrix.get_preview_png(scale=8)
    if png_bytes is None:
        return jsonify({"error": "No frame rendered yet"}), 503
    return Response(png_bytes, mimetype='image/png', headers={
        'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
    })


@app.route('/healthz')
def healthz():
    """Liveness check -- always returns 200 if the process is running."""
    return {'status': 'ok'}, 200


@app.route('/')
def index():
    """Main configuration page"""
    config = load_config()
    stocks_fragment = _render_ticker_list('stocks', config.get('stocks', {}).get('symbols', []))
    crypto_fragment = _render_ticker_list('crypto', config.get('crypto', {}).get('symbols', []))
    weather_fragment = _render_weather_list(config.get('weather_locations', []))
    clock_fragment = _render_clock_list(config.get('clock_locations', []))
    sports_fragment = _render_sports_list(config.get('sports', []))
    favorites_fragment = _render_favorites_list(config.get('favorite_teams', []))
    fantasy_fragment = _render_fantasy_list(config.get('fantasy_players', []))
    return render_template_string(HTML_TEMPLATE,
                                 config_json=json.dumps(config),
                                 brightness=config.get('brightness', 50),
                                 stocks_fragment=stocks_fragment,
                                 crypto_fragment=crypto_fragment,
                                 weather_fragment=weather_fragment,
                                 clock_fragment=clock_fragment,
                                 sports_fragment=sports_fragment,
                                 favorites_fragment=favorites_fragment,
                                 fantasy_fragment=fantasy_fragment)


_REMOTE_DIR = os.path.join(_script_dir, "matrix-display-remote")


@app.route('/remote')
def remote():
    """Mobile-friendly PWA remote control (mode switching, navigation,
    brightness) -- replaces the old BLE gyroscope remote."""
    return send_from_directory(_REMOTE_DIR, "index.html")


@app.route('/manifest.json')
def remote_manifest():
    return send_from_directory(_REMOTE_DIR, "manifest.json")


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    return jsonify(load_config())


@app.route('/api/save', methods=['POST'])
def save_config_api():
    """Save configuration and reload display controller"""
    try:
        config = request.json
        # stocks/crypto/weather_locations are now managed server-side by
        # the /htmx/* routes below, saved individually as each add/remove
        # happens. This bulk save still covers everything else on the page
        # (brightness, sports, favorites, fantasy, music, images config) -
        # but must not let a stale in-browser copy of the htmx-managed
        # lists overwrite what's actually on disk.
        current = load_config()
        for key in ("stocks", "crypto", "weather_locations", "clock_locations", "sports", "favorite_teams", "fantasy_players"):
            config[key] = current.get(key, config.get(key))
        if save_config(config):
            # web_config.py and the DisplayController share one process
            # since the BLE-remote refactor - call reload_config() directly
            # instead of touching a file for the update loop to notice up to
            # 2 seconds later (the old shape, from when these were separate
            # processes talking over a shared filesystem).
            try:
                if display_controller is not None:
                    display_controller.reload_config()
                    display_controller._load_image_lists()
            except Exception as reload_err:
                # Reload failed, but config was saved
                print(f"Could not trigger config reload: {reload_err}")
            
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Failed to save config"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/images/upload', methods=['POST'])
def upload_image():
    """Upload an image or GIF file"""
    try:
        print(f"Upload request received. Files: {list(request.files.keys())}")
        print(f"Form data: {dict(request.form)}")
        
        if 'file' not in request.files:
            print("ERROR: No 'file' in request.files")
            return jsonify({"success": False, "error": "No file provided"}), 400
        
        file = request.files['file']
        upload_type = request.form.get('type', 'photo')
        
        print(f"File: {file.filename}, Type: {upload_type}")
        
        if file.filename == '':
            print("ERROR: Empty filename")
            return jsonify({"success": False, "error": "No file selected"}), 400
        
        # Determine upload directory - use same logic as matrix_display_controller
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if upload_type == 'gif':
            upload_dir = os.path.join(script_dir, "assets", "gif_list")
        else:
            upload_dir = os.path.join(script_dir, "assets", "photo_list")
        
        print(f"Upload directory: {upload_dir}")
        
        # Create directory if it doesn't exist
        os.makedirs(upload_dir, exist_ok=True)
        print(f"Directory created/exists: {os.path.exists(upload_dir)}")
        
        # Secure filename and save
        filename = secure_filename(file.filename)
        filepath = os.path.join(upload_dir, filename)
        print(f"Saving to: {filepath}")
        
        file.save(filepath)
        
        # Verify file was saved
        if not os.path.exists(filepath):
            print(f"ERROR: File was not saved to {filepath}")
            return jsonify({"success": False, "error": "File save failed"}), 500
        
        print(f"File saved successfully: {filepath}, size: {os.path.getsize(filepath)} bytes")
        
        # Trigger reload of image lists - direct call, see save_config()
        try:
            if display_controller is not None:
                display_controller._load_image_lists()
        except Exception as reload_err:
            print(f"Warning: Could not reload image lists: {reload_err}")
        
        return jsonify({"success": True, "filename": filename})
    except Exception as e:
        print(f"ERROR in upload_image: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/images/list', methods=['GET'])
def list_images():
    """List all uploaded images and GIFs"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        photo_dir = os.path.join(script_dir, "assets", "photo_list")
        gif_dir = os.path.join(script_dir, "assets", "gif_list")
        
        photos = []
        gifs = []
        
        if os.path.exists(photo_dir):
            for filename in sorted(os.listdir(photo_dir)):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    photos.append(filename)
        
        if os.path.exists(gif_dir):
            for filename in sorted(os.listdir(gif_dir)):
                if filename.lower().endswith('.gif'):
                    gifs.append(filename)
        
        return jsonify({"photos": photos, "gifs": gifs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/images/delete/<type>/<filename>', methods=['DELETE'])
def delete_image(type, filename):
    """Delete an image or GIF file"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if type == 'gif':
            file_dir = os.path.join(script_dir, "assets", "gif_list")
        else:
            file_dir = os.path.join(script_dir, "assets", "photo_list")
        
        # Secure filename to prevent directory traversal
        safe_filename = secure_filename(filename)
        filepath = os.path.join(file_dir, safe_filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            
            # Trigger reload of image lists - direct call, see save_config()
            if display_controller is not None:
                display_controller._load_image_lists()
            
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "File not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    start_display_controller()
    print("Starting web configuration server on http://localhost:5000")
    print("Access from your Pi's IP address or localhost")
    app.run(host='0.0.0.0', port=5000, debug=False, load_dotenv=False)

