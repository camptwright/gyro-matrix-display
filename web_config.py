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
        "weather_locations": [],
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
        print(f"Config contents: sports={len(config.get('sports', []))}, stocks={len(config.get('stocks', []))}, crypto={len(config.get('crypto', []))}, weather={len(config.get('weather_locations', []))}")
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
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 30px;
        }
        h1 {
            color: #333;
            margin-bottom: 30px;
            text-align: center;
        }
        .section {
            margin-bottom: 40px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .section h2 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.5em;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #555;
            font-weight: 500;
        }
        input, select {
            width: 100%;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        input:focus, select:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            background: #667eea;
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
            background: #5568d3;
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
            background: white;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 5px;
            border: 1px solid #ddd;
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
            color: #667eea;
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
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 Matrix Display Configuration</h1>
        
        <div id="message"></div>
        
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
            <h2>Sports</h2>
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
        
        <!-- Stocks -->
        <div class="section">
            <h2>Stocks</h2>
            <div class="form-group">
                <label>Stock Ticker:</label>
                <input type="text" id="stockTicker" placeholder="e.g., AAPL, MSFT, GOOGL" style="text-transform: uppercase;">
            </div>
            <button onclick="addStock()">Add Stock</button>
            <div class="item-list" id="stocksList"></div>
        </div>
        
        <!-- Crypto -->
        <div class="section">
            <h2>Cryptocurrency</h2>
            <div class="form-group">
                <label>Crypto Ticker:</label>
                <input type="text" id="cryptoTicker" placeholder="e.g., BTC, ETH, DOGE" style="text-transform: uppercase;">
            </div>
            <button onclick="addCrypto()">Add Crypto</button>
            <div class="item-list" id="cryptoList"></div>
        </div>
        
        <!-- Weather Locations -->
        <div class="section">
            <h2>Weather Locations</h2>
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
        
        <!-- Favorite Teams -->
        <div class="section">
            <h2>Favorite Sports Teams</h2>
            <p style="font-size: 0.9em; color: #666; margin-bottom: 15px;">
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
        
        <!-- Music Configuration -->
        <div class="section">
            <h2>Music (Spotify/YouTube Music)</h2>
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
        
        function removeItem(listName, index) {
            config[listName].splice(index, 1);
            renderLists();
        }
        
        async function saveConfig() {
            try {
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
        renderLists();
        loadImageLists();
    </script>
</body>
</html>
"""


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


if __name__ == '__main__':
    print("Starting web configuration server on http://localhost:5000")
    print("Access from your Pi's IP address or localhost")
    app.run(host='0.0.0.0', port=5000, debug=False)

