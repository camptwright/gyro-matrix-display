#!/usr/bin/env python3
"""
Web Configuration Interface for Matrix Display
Runs on localhost to configure favorites/areas for each mode
"""

from flask import Flask, render_template_string, request, jsonify
import json
import os
import time
from pathlib import Path
from werkzeug.utils import secure_filename

app = Flask(__name__)
# Make config path absolute - try to use same directory as matrix_display_controller.py
# First try to find matrix_display_controller.py and use its directory
_script_dir = os.path.dirname(os.path.abspath(__file__))
# Check if we're in the matrix-display directory
if os.path.basename(_script_dir) == 'matrix-display' or os.path.exists(os.path.join(_script_dir, 'matrix_display_controller.py')):
    CONFIG_FILE = os.path.join(_script_dir, "config.json")
else:
    # Fallback: try common locations
    possible_paths = [
        "/home/raspberrypi/matrix-display/config.json",
        os.path.join(_script_dir, "config.json"),
        "config.json"
    ]
    CONFIG_FILE = possible_paths[0]  # Default to Pi path
    for path in possible_paths:
        if os.path.exists(path) or os.path.exists(os.path.dirname(path)):
            CONFIG_FILE = path
            break

print(f"Web config service using config file: {CONFIG_FILE}")


def load_config():
    """Load configuration from JSON file"""
    default_config = {
        "brightness": 50,
        "timezone": "America/New_York",
        "clock_locations": [],
        "sports": [],
        "favorite_teams": [],
        "stocks": [],
        "crypto": [],
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


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Matrix Display Configuration</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-tertiary: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --accent-primary: #6366f1;
            --accent-secondary: #8b5cf6;
            --accent-hover: #4f46e5;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --border: #475569;
            --shadow: rgba(0, 0, 0, 0.3);
        }
        
        body.light-mode {
            --bg-primary: #ffffff;
            --bg-secondary: #f8fafc;
            --bg-tertiary: #e2e8f0;
            --text-primary: #0f172a;
            --text-secondary: #64748b;
            --accent-primary: #6366f1;
            --accent-secondary: #8b5cf6;
            --accent-hover: #4f46e5;
            --border: #cbd5e1;
            --shadow: rgba(0, 0, 0, 0.1);
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            padding: 20px;
            min-height: 100vh;
            transition: background 0.3s ease, color 0.3s ease;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: var(--bg-secondary);
            border-radius: 16px;
            box-shadow: 0 20px 60px var(--shadow);
            padding: 40px;
            border: 1px solid var(--border);
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid var(--border);
        }
        
        h1 {
            color: var(--text-primary);
            font-size: 2.5em;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .theme-toggle {
            background: var(--bg-tertiary);
            border: 2px solid var(--border);
            color: var(--text-primary);
            padding: 12px 24px;
            border-radius: 50px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .theme-toggle:hover {
            background: var(--accent-primary);
            border-color: var(--accent-primary);
            color: white;
            transform: translateY(-2px);
        }
        
        .section {
            margin-bottom: 40px;
            padding: 24px;
            background: var(--bg-tertiary);
            border-radius: 12px;
            border: 1px solid var(--border);
            transition: all 0.3s ease;
        }
        
        .section:hover {
            border-color: var(--accent-primary);
            box-shadow: 0 4px 20px var(--shadow);
        }
        
        .section h2 {
            color: var(--text-primary);
            margin-bottom: 16px;
            font-size: 1.75em;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .form-group {
            margin-bottom: 16px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            color: var(--text-secondary);
            font-weight: 500;
            font-size: 0.95em;
        }
        
        input, select {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid var(--border);
            border-radius: 8px;
            font-size: 14px;
            background: var(--bg-secondary);
            color: var(--text-primary);
            transition: all 0.3s ease;
        }
        
        input:focus, select:focus {
            outline: none;
            border-color: var(--accent-primary);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }
        
        button {
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            margin-right: 10px;
            margin-top: 10px;
            transition: all 0.3s ease;
            box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
        }
        
        button:active {
            transform: translateY(0);
        }
        
        button.danger {
            background: linear-gradient(135deg, var(--danger), #dc2626);
            box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
        }
        
        button.danger:hover {
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
        }
        
        .item-list {
            margin-top: 16px;
        }
        
        .item {
            background: var(--bg-secondary);
            padding: 16px;
            margin-bottom: 12px;
            border-radius: 8px;
            border: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.3s ease;
        }
        
        .item:hover {
            border-color: var(--accent-primary);
            transform: translateX(4px);
        }
        
        .item-info {
            flex: 1;
            color: var(--text-primary);
        }
        
        .item-actions {
            display: flex;
            gap: 10px;
        }
        
        .brightness-control {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        
        .brightness-slider {
            flex: 1;
            height: 8px;
            border-radius: 4px;
            background: var(--bg-secondary);
            outline: none;
            -webkit-appearance: none;
        }
        
        .brightness-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
        }
        
        .brightness-slider::-moz-range-thumb {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            cursor: pointer;
            border: none;
            box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
        }
        
        .brightness-value {
            font-size: 1.4em;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            min-width: 60px;
            text-align: right;
        }
        
        .success {
            background: linear-gradient(135deg, var(--success), #059669);
            color: white;
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
            font-weight: 600;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        }
        
        .error {
            background: linear-gradient(135deg, var(--danger), #dc2626);
            color: white;
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
            font-weight: 600;
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
        }
        
        .mode-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 12px;
        }
        
        .mode-grid button {
            margin: 0;
            padding: 16px;
            font-size: 16px;
        }
        
        .nav-grid {
            display: grid;
            grid-template-columns: repeat(3, 90px);
            gap: 8px;
            justify-content: center;
            margin-top: 20px;
        }
        
        .nav-grid button {
            margin: 0;
            padding: 20px;
            font-size: 24px;
        }
        
        .nav-center {
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--bg-secondary);
            border: 2px solid var(--border);
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            color: var(--text-secondary);
            letter-spacing: 1px;
        }
        
        .info-text {
            font-size: 0.9em;
            color: var(--text-secondary);
            margin-bottom: 16px;
            line-height: 1.6;
        }
        
        .save-button {
            background: linear-gradient(135deg, var(--success), #059669);
            font-size: 18px;
            padding: 18px 40px;
            box-shadow: 0 4px 16px rgba(16, 185, 129, 0.3);
        }
        
        .save-button:hover {
            box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎮 Matrix Display</h1>
            <button class="theme-toggle" onclick="toggleTheme()">
                <span id="themeIcon">🌙</span>
                <span id="themeText">Dark Mode</span>
            </button>
        </div>
        
        <div id="message"></div>
        
        <!-- Quick Mode Control -->
        <div class="section">
            <h2>⚡ Quick Mode Control</h2>
            <p class="info-text">
                Instantly switch display modes with these quick buttons.
            </p>
            <div class="mode-grid">
                <button onclick="changeMode('clock')">🕐 Clock</button>
                <button onclick="changeMode('sports')">🏈 Sports</button>
                <button onclick="changeMode('fantasy')">⭐ Fantasy</button>
                <button onclick="changeMode('stocks')">📈 Stocks</button>
                <button onclick="changeMode('weather')">🌤️ Weather</button>
                <button onclick="changeMode('music')">🎵 Music</button>
                <button onclick="changeMode('images')">🖼️ Images</button>
            </div>
        </div>
        
        <!-- Navigation Control -->
        <div class="section">
            <h2>🎮 Navigation Control</h2>
            <p class="info-text">
                Navigate within the current mode:
            </p>
            <div class="info-text" style="font-size: 0.85em; line-height: 1.8;">
                <strong>Sports:</strong> ↕️ Switch sports, ↔️ Switch games<br>
                <strong>Stocks:</strong> ↕️ Toggle stocks/crypto, ↔️ Navigate tickers<br>
                <strong>Images:</strong> ↕️ Toggle photos/GIFs, ↔️ Navigate images<br>
                <strong>Fantasy:</strong> ↕️ Switch sports, ↔️ Navigate players<br>
                <strong>Weather:</strong> ↕️ Switch locations<br>
                <strong>Clock:</strong> ↕️ Switch time zones
            </div>
            <div class="nav-grid">
                <div></div>
                <button onclick="navigate('up')">⬆️</button>
                <div></div>
                <button onclick="navigate('left')">⬅️</button>
                <div class="nav-center">NAV</div>
                <button onclick="navigate('right')">➡️</button>
                <div></div>
                <button onclick="navigate('down')">⬇️</button>
                <div></div>
            </div>
        </div>
        
        <!-- Brightness Control -->
        <div class="section">
            <h2>💡 Brightness</h2>
            <div class="brightness-control">
                <label>Brightness Level:</label>
                <input type="range" id="brightness" min="0" max="100" value="{{ brightness }}" 
                       class="brightness-slider" oninput="updateBrightnessSlider(this.value)" 
                       onchange="setBrightnessInstant(this.value)">
                <span class="brightness-value" id="brightnessValue">{{ brightness }}%</span>
            </div>
        </div>
        
        <!-- Clock Locations -->
        <div class="section">
            <h2>🕐 Clock Locations (Time Zones)</h2>
            <div class="form-group">
                <label>Location Name:</label>
                <input type="text" id="clockName" placeholder="e.g., New York">
            </div>
            <div class="form-group">
                <label>Time Zone:</label>
                <select id="clockTimezone">
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
            <button onclick="addClockLocation()">Add Location</button>
            <div class="item-list" id="clockList"></div>
        </div>
        
        <!-- Sports -->
        <div class="section">
            <h2>🏈 Sports</h2>
            <div class="form-group">
                <label>Sport Name:</label>
                <input type="text" id="sportName" placeholder="e.g., NBA, NFL, MLB">
            </div>
            <div class="form-group">
                <label>Team/League ID (optional):</label>
                <input type="text" id="sportId" placeholder="e.g., team abbreviation">
            </div>
            <button onclick="addSport()">Add Sport</button>
            <div class="item-list" id="sportsList"></div>
        </div>
        
        <!-- Favorite Teams -->
        <div class="section">
            <h2>⭐ Favorite Sports Teams</h2>
            <p class="info-text">
                Add your favorite teams to see their games first in sports mode. Games involving your favorite teams will be shown in a separate "Favorites" section.
            </p>
            <div class="form-group">
                <label>League/Sport:</label>
                <select id="favoriteSport">
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
                <input type="text" id="favoriteTeam" placeholder="e.g., LAL, Patriots, Yankees" style="text-transform: uppercase;">
            </div>
            <button onclick="addFavoriteTeam()">Add Favorite Team</button>
            <div class="item-list" id="favoritesList"></div>
        </div>
        
        <!-- Fantasy Players -->
        <div class="section">
            <h2>🏆 Fantasy Players</h2>
            <div class="form-group">
                <label>
                    <input type="checkbox" id="fantasyEnabled" onchange="updateFantasyEnabled()">
                    Enable Fantasy Mode
                </label>
            </div>
            <p class="info-text">
                Add players to track their stats in fantasy mode. Supports NFL, NBA, and NHL. Use up/down flicks to cycle through sports, left/right to navigate players within each sport.
            </p>
            <div class="form-group">
                <label>Sport:</label>
                <select id="fantasySport">
                    <option value="nfl">NFL</option>
                    <option value="nba">NBA</option>
                    <option value="nhl">NHL</option>
                </select>
            </div>
            <div class="form-group">
                <label>Player Name:</label>
                <input type="text" id="fantasyPlayerName" placeholder="e.g., Patrick Mahomes, Travis Kelce">
            </div>
            <div class="form-group">
                <label>Team Abbreviation:</label>
                <input type="text" id="fantasyTeam" placeholder="e.g., KC, BUF, SF" style="text-transform: uppercase;">
            </div>
            <button onclick="addFantasyPlayer()">Add Fantasy Player</button>
            <div class="item-list" id="fantasyPlayersList"></div>
        </div>
        
        <!-- Stocks -->
        <div class="section">
            <h2>📈 Stocks</h2>
            <div class="form-group">
                <label>
                    <input type="checkbox" id="stocksEnabled" onchange="updateStocksEnabled()">
                    Enable Stocks/Crypto Mode
                </label>
            </div>
            <div class="form-group">
                <label>Stock Ticker:</label>
                <input type="text" id="stockTicker" placeholder="e.g., AAPL, MSFT, GOOGL" style="text-transform: uppercase;">
            </div>
            <button onclick="addStock()">Add Stock</button>
            <div class="item-list" id="stocksList"></div>
        </div>
        
        <!-- Crypto -->
        <div class="section">
            <h2>₿ Cryptocurrency</h2>
            <div class="form-group">
                <label>Crypto Ticker:</label>
                <input type="text" id="cryptoTicker" placeholder="e.g., BTC, ETH, DOGE" style="text-transform: uppercase;">
            </div>
            <button onclick="addCrypto()">Add Crypto</button>
            <div class="item-list" id="cryptoList"></div>
        </div>
        
        <!-- Weather Locations -->
        <div class="section">
            <h2>🌤️ Weather Locations</h2>
            <div class="form-group">
                <label>
                    <input type="checkbox" id="weatherEnabled" onchange="updateWeatherEnabled()">
                    Enable Weather Mode
                </label>
            </div>
            <div class="form-group">
                <label>Location Name:</label>
                <input type="text" id="weatherName" placeholder="e.g., New York">
            </div>
            <div class="form-group">
                <label>City:</label>
                <input type="text" id="weatherCity" placeholder="e.g., New York">
            </div>
            <div class="form-group">
                <label>State/Country:</label>
                <input type="text" id="weatherState" placeholder="e.g., NY, US">
            </div>
            <div class="form-group">
                <label>OpenWeatherMap API Key:</label>
                <input type="text" id="weatherApiKey" placeholder="Your API key">
            </div>
            <button onclick="addWeatherLocation()">Add Location</button>
            <div class="item-list" id="weatherList"></div>
        </div>
        
        <!-- Music Configuration -->
        <div class="section">
            <h2>🎵 Music (Spotify/YouTube Music)</h2>
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
                    <option value="ytm">YouTube Music</option>
                </select>
            </div>
            <div class="form-group">
                <label>Polling Interval (seconds):</label>
                <input type="number" id="musicPollingInterval" min="1" max="10" value="2">
            </div>
            <p class="info-text" style="margin-top: 10px;">
                Note: Spotify credentials must be configured in <code style="background: var(--bg-secondary); padding: 2px 8px; border-radius: 4px; font-size: 0.9em;">config/config_secrets.json</code>
            </p>
        </div>
        
        <!-- Images/GIFs Upload -->
        <div class="section">
            <h2>🖼️ Images & GIFs</h2>
            <p class="info-text">
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
        
        <div style="text-align: center; margin-top: 40px;">
            <button onclick="saveConfig()" class="save-button">
                💾 Save Configuration
            </button>
        </div>
    </div>
    
    <script>
        let config = {{ config_json|safe }};
        
        // Theme management
        function toggleTheme() {
            const body = document.body;
            const themeIcon = document.getElementById('themeIcon');
            const themeText = document.getElementById('themeText');
            
            if (body.classList.contains('light-mode')) {
                body.classList.remove('light-mode');
                themeIcon.textContent = '🌙';
                themeText.textContent = 'Dark Mode';
                localStorage.setItem('theme', 'dark');
            } else {
                body.classList.add('light-mode');
                themeIcon.textContent = '☀️';
                themeText.textContent = 'Light Mode';
                localStorage.setItem('theme', 'light');
            }
        }
        
        // Load saved theme preference
        function loadTheme() {
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme === 'light') {
                document.body.classList.add('light-mode');
                document.getElementById('themeIcon').textContent = '☀️';
                document.getElementById('themeText').textContent = 'Light Mode';
            }
        }
        
        function showMessage(text, isError = false) {
            const msg = document.getElementById('message');
            msg.textContent = text;
            msg.className = isError ? 'error' : 'success';
            msg.style.display = 'block';
            setTimeout(() => {
                msg.style.display = 'none';
            }, 3000);
        }
        
        function updateBrightnessSlider(value) {
            document.getElementById('brightnessValue').textContent = value + '%';
            config.brightness = parseInt(value);
        }
        
        async function setBrightnessInstant(value) {
            try {
                const response = await fetch('/api/brightness/set', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ brightness: parseInt(value) })
                });
                const result = await response.json();
                if (result.success) {
                    showMessage(`Brightness set to ${value}%`);
                } else {
                    showMessage('Error setting brightness: ' + result.error, true);
                }
            } catch (error) {
                showMessage('Error setting brightness: ' + error, true);
            }
        }
        
        async function changeMode(mode) {
            try {
                const response = await fetch('/api/mode/change', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: mode })
                });
                const result = await response.json();
                if (result.success) {
                    showMessage(`Mode changed to: ${mode}`);
                } else {
                    showMessage('Error changing mode: ' + result.error, true);
                }
            } catch (error) {
                showMessage('Error changing mode: ' + error, true);
            }
        }
        
        async function navigate(direction) {
            try {
                const response = await fetch('/api/navigate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ direction: direction })
                });
                const result = await response.json();
                if (result.success) {
                    // Don't show toast for navigation - too frequent
                    console.log(`Navigated: ${direction}`);
                } else {
                    showMessage('Error navigating: ' + result.error, true);
                }
            } catch (error) {
                showMessage('Error navigating: ' + error, true);
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
            // Clock locations
            const clockList = document.getElementById('clockList');
            clockList.innerHTML = config.clock_locations.map((item, idx) => `
                <div class="item">
                    <div class="item-info">
                        <strong>${item.name}</strong> - ${item.timezone}
                    </div>
                    <div class="item-actions">
                        <button class="danger" onclick="removeItem('clock_locations', ${idx})">Remove</button>
                    </div>
                </div>
            `).join('');
            
            // Sports
            const sportsList = document.getElementById('sportsList');
            sportsList.innerHTML = config.sports.map((item, idx) => `
                <div class="item">
                    <div class="item-info">
                        <strong>${item.name}</strong>${item.id ? ' - ' + item.id : ''}
                    </div>
                    <div class="item-actions">
                        <button class="danger" onclick="removeItem('sports', ${idx})">Remove</button>
                    </div>
                </div>
            `).join('');
            
            // Stocks
            const stocksList = document.getElementById('stocksList');
            stocksList.innerHTML = config.stocks.map((item, idx) => `
                <div class="item">
                    <div class="item-info">
                        <strong>${item}</strong>
                    </div>
                    <div class="item-actions">
                        <button class="danger" onclick="removeItem('stocks', ${idx})">Remove</button>
                    </div>
                </div>
            `).join('');
            
            // Crypto
            const cryptoList = document.getElementById('cryptoList');
            cryptoList.innerHTML = config.crypto.map((item, idx) => `
                <div class="item">
                    <div class="item-info">
                        <strong>${item}</strong>
                    </div>
                    <div class="item-actions">
                        <button class="danger" onclick="removeItem('crypto', ${idx})">Remove</button>
                    </div>
                </div>
            `).join('');
            
            // Weather
            const weatherList = document.getElementById('weatherList');
            weatherList.innerHTML = config.weather_locations.map((item, idx) => `
                <div class="item">
                    <div class="item-info">
                        <strong>${item.name}</strong> - ${item.city}, ${item.state}
                    </div>
                    <div class="item-actions">
                        <button class="danger" onclick="removeItem('weather_locations', ${idx})">Remove</button>
                    </div>
                </div>
            `).join('');
            
            // Favorite Teams
            if (!config.favorite_teams) {
                config.favorite_teams = [];
            }
            const favoritesList = document.getElementById('favoritesList');
            if (favoritesList) {
                favoritesList.innerHTML = config.favorite_teams.map((item, idx) => `
                    <div class="item">
                        <div class="item-info">
                            <strong>${item.team}</strong> - ${item.sport.toUpperCase()}
                        </div>
                        <div class="item-actions">
                            <button class="danger" onclick="removeItem('favorite_teams', ${idx})">Remove</button>
                        </div>
                    </div>
                `).join('');
            }
            
            // Fantasy Players
            if (!config.fantasy_players) {
                config.fantasy_players = [];
            }
            const fantasyPlayersList = document.getElementById('fantasyPlayersList');
            if (fantasyPlayersList) {
                fantasyPlayersList.innerHTML = config.fantasy_players.map((item, idx) => `
                    <div class="item">
                        <div class="item-info">
                            <strong>${item.name}</strong> - ${item.team || 'N/A'} (${item.sport ? item.sport.toUpperCase() : 'NFL'})
                        </div>
                        <div class="item-actions">
                            <button class="danger" onclick="removeItem('fantasy_players', ${idx})">Remove</button>
                        </div>
                    </div>
                `).join('');
            }
            
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
        
        function addClockLocation() {
            const name = document.getElementById('clockName').value.trim();
            const timezone = document.getElementById('clockTimezone').value;
            if (!name) {
                showMessage('Please enter a location name', true);
                return;
            }
            config.clock_locations.push({ name, timezone });
            document.getElementById('clockName').value = '';
            renderLists();
        }
        
        function addSport() {
            const name = document.getElementById('sportName').value.trim();
            const id = document.getElementById('sportId').value.trim();
            if (!name) {
                showMessage('Please enter a sport name', true);
                return;
            }
            config.sports.push({ name, id: id || null });
            document.getElementById('sportName').value = '';
            document.getElementById('sportId').value = '';
            renderLists();
        }
        
        function addStock() {
            const ticker = document.getElementById('stockTicker').value.trim().toUpperCase();
            if (!ticker) {
                showMessage('Please enter a stock ticker', true);
                return;
            }
            if (config.stocks.includes(ticker)) {
                showMessage('Stock already added', true);
                return;
            }
            config.stocks.push(ticker);
            document.getElementById('stockTicker').value = '';
            renderLists();
        }
        
        function addCrypto() {
            const ticker = document.getElementById('cryptoTicker').value.trim().toUpperCase();
            if (!ticker) {
                showMessage('Please enter a crypto ticker', true);
                return;
            }
            if (config.crypto.includes(ticker)) {
                showMessage('Crypto already added', true);
                return;
            }
            config.crypto.push(ticker);
            document.getElementById('cryptoTicker').value = '';
            renderLists();
        }
        
        function addWeatherLocation() {
            const name = document.getElementById('weatherName').value.trim();
            const city = document.getElementById('weatherCity').value.trim();
            const state = document.getElementById('weatherState').value.trim();
            const apiKey = document.getElementById('weatherApiKey').value.trim();
            if (!name || !city || !state) {
                showMessage('Please fill in all weather location fields', true);
                return;
            }
            config.weather_locations.push({ name, city, state, api_key: apiKey });
            document.getElementById('weatherName').value = '';
            document.getElementById('weatherCity').value = '';
            document.getElementById('weatherState').value = '';
            renderLists();
        }
        
        function addFavoriteTeam() {
            if (!config.favorite_teams) {
                config.favorite_teams = [];
            }
            const sport = document.getElementById('favoriteSport').value.trim().toLowerCase();
            const team = document.getElementById('favoriteTeam').value.trim().toUpperCase();
            if (!sport || !team) {
                showMessage('Please select a league and enter a team name/abbreviation', true);
                return;
            }
            // Check for duplicates
            const isDuplicate = config.favorite_teams.some(item => 
                item.sport.toLowerCase() === sport.toLowerCase() && 
                item.team.toUpperCase() === team.toUpperCase()
            );
            if (isDuplicate) {
                showMessage('This team is already in your favorites', true);
                return;
            }
            config.favorite_teams.push({ sport, team });
            document.getElementById('favoriteTeam').value = '';
            renderLists();
        }
        
        function addFantasyPlayer() {
            if (!config.fantasy_players) {
                config.fantasy_players = [];
            }
            const sport = document.getElementById('fantasySport').value.trim().toLowerCase();
            const name = document.getElementById('fantasyPlayerName').value.trim();
            const team = document.getElementById('fantasyTeam').value.trim().toUpperCase();
            if (!name) {
                showMessage('Please enter a player name', true);
                return;
            }
            if (!team) {
                showMessage('Please enter a team abbreviation', true);
                return;
            }
            // Check for duplicates
            const isDuplicate = config.fantasy_players.some(item => 
                item.name.toLowerCase() === name.toLowerCase() && 
                item.team && item.team.toUpperCase() === team.toUpperCase() &&
                item.sport && item.sport.toLowerCase() === sport.toLowerCase()
            );
            if (isDuplicate) {
                showMessage('This player is already in your fantasy list', true);
                return;
            }
            config.fantasy_players.push({ name, team, sport: sport || 'nfl' });
            document.getElementById('fantasyPlayerName').value = '';
            document.getElementById('fantasyTeam').value = '';
            renderLists();
        }
        
        function removeItem(listName, index) {
            config[listName].splice(index, 1);
            renderLists();
        }
        
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
        
        // Initialize
        loadTheme();
        renderLists();
        loadImageLists();
    </script>
</body>
</html>
"""


REMOTE_APP_PATH = os.path.join(_script_dir, 'matrix-display-remote', 'index.html')

@app.route('/remote')
def remote_app():
    """Mobile-friendly remote control (use matrix-display.local:5000/remote)"""
    if os.path.exists(REMOTE_APP_PATH):
        with open(REMOTE_APP_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Remote app not found</h1><p>Ensure matrix-display-remote/index.html exists.</p>", 404

@app.route('/manifest.json')
def remote_manifest():
    """PWA manifest for Add to Home Screen"""
    manifest_path = os.path.join(_script_dir, 'matrix-display-remote', 'manifest.json')
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            from flask import Response
            return Response(f.read(), mimetype='application/json')
    return jsonify({"name": "Matrix Remote"}), 404

@app.route('/healthz')
def healthz():
    """Liveness check -- always returns 200 if the process is running."""
    return {'status': 'ok'}, 200


@app.route('/')
def index():
    """Main configuration page"""
    config = load_config()
    return render_template_string(HTML_TEMPLATE, 
                                 config_json=json.dumps(config),
                                 brightness=config.get('brightness', 50))


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    return jsonify(load_config())


@app.route('/api/save', methods=['POST'])
def save_config_api():
    """Save configuration and reload display controller"""
    try:
        config = request.json
        if save_config(config):
            # Try to reload display controller config
            try:
                import signal
                import os
                # Send SIGHUP to matrix-display service to reload config
                # Or use a simpler approach: touch a reload file
                reload_file = "/tmp/matrix_display_reload"
                with open(reload_file, 'w') as f:
                    f.write(str(time.time()))
                os.chmod(reload_file, 0o666)
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
        
        # Trigger reload of image lists
        reload_file = "/tmp/matrix_display_reload"
        try:
            with open(reload_file, 'w') as f:
                f.write(str(time.time()))
            os.chmod(reload_file, 0o666)
        except Exception as reload_err:
            print(f"Warning: Could not create reload file: {reload_err}")
        
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
            
            # Trigger reload of image lists
            reload_file = "/tmp/matrix_display_reload"
            with open(reload_file, 'w') as f:
                f.write(str(time.time()))
            os.chmod(reload_file, 0o666)
            
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "File not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/mode/change', methods=['POST'])
def change_mode():
    """Immediately change the display mode without full config reload"""
    try:
        data = request.json
        mode = data.get('mode')
        
        if not mode:
            return jsonify({"success": False, "error": "Mode parameter required"}), 400
        
        # Valid modes
        valid_modes = ['clock', 'sports', 'fantasy', 'stocks', 'weather', 'music', 'images', 'brightness']
        if mode not in valid_modes:
            return jsonify({"success": False, "error": f"Invalid mode. Must be one of: {', '.join(valid_modes)}"}), 400
        
        # Write mode change to a separate, high-priority file
        mode_file = "/tmp/matrix_display_mode"
        with open(mode_file, 'w') as f:
            f.write(mode)
        os.chmod(mode_file, 0o666)
        
        # Also trigger standard reload as backup
        reload_file = "/tmp/matrix_display_reload"
        with open(reload_file, 'w') as f:
            f.write(str(time.time()))
        os.chmod(reload_file, 0o666)
        
        return jsonify({"success": True, "mode": mode})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/brightness/set', methods=['POST'])
def set_brightness():
    """Immediately change the brightness without full config reload"""
    try:
        data = request.json
        brightness = data.get('brightness')
        
        if brightness is None:
            return jsonify({"success": False, "error": "Brightness parameter required"}), 400
        
        try:
            brightness = int(brightness)
            if brightness < 0 or brightness > 100:
                return jsonify({"success": False, "error": "Brightness must be between 0 and 100"}), 400
        except ValueError:
            return jsonify({"success": False, "error": "Brightness must be a number"}), 400
        
        # Update config file with new brightness
        config = load_config()
        config['brightness'] = brightness
        save_config(config)
        
        # Write brightness change to a separate file for immediate response
        brightness_file = "/tmp/matrix_display_brightness"
        with open(brightness_file, 'w') as f:
            f.write(str(brightness))
        os.chmod(brightness_file, 0o666)
        
        return jsonify({"success": True, "brightness": brightness})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/navigate', methods=['POST'])
def navigate():
    """Send navigation command (up/down/left/right) to the display"""
    try:
        data = request.json
        direction = data.get('direction')
        
        if not direction:
            return jsonify({"success": False, "error": "Direction parameter required"}), 400
        
        # Valid directions
        valid_directions = ['up', 'down', 'left', 'right']
        if direction not in valid_directions:
            return jsonify({"success": False, "error": f"Invalid direction. Must be one of: {', '.join(valid_directions)}"}), 400
        
        # Write navigation command to a file for immediate response
        nav_file = "/tmp/matrix_display_nav"
        with open(nav_file, 'w') as f:
            f.write(direction)
        os.chmod(nav_file, 0o666)
        
        return jsonify({"success": True, "direction": direction})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    print("Starting web configuration server on http://localhost:5000")
    print("Access from your Pi's IP address or localhost")
    app.run(host='0.0.0.0', port=5000, debug=False)

