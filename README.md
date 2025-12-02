# RGB Matrix Display Controller

A Raspberry Pi-based RGB LED matrix display system that shows sports scores, weather, stocks, music, and more. Controlled via a gyroscopic Arduino/ESP32 controller with Bluetooth Low Energy (BLE) communication.

## Features

- **Sports Scores**: Real-time scores for NFL, NBA, MLB, NHL, NCAA, and more
- **Weather**: Current conditions and forecasts
- **Stocks & Crypto**: Real-time price updates
- **Music**: Spotify integration showing current track, artist, and album art
- **Clock**: Time, date, and calendar display
- **Web Configuration**: Flask-based web interface for easy setup
- **Gesture Control**: Navigate modes using gyroscopic gestures via BLE controller

## Hardware Requirements

- Raspberry Pi (tested on Pi 4)
- RGB LED Matrix (32x32 or compatible)
- Adafruit RGB Matrix HAT or compatible driver
- ESP32 or Arduino with gyroscope for gesture control (optional)

## Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd matrix-display
   ```

2. **Install RGB Matrix library:**
   ```bash
   git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
   cd rpi-rgb-led-matrix
   make
   cd python
   sudo python3 setup.py install
   cd ../..
   ```

3. **Install Python dependencies:**
   ```bash
   pip3 install -r requirements.txt --break-system-packages
   ```

4. **Set up configuration:**
   ```bash
   cp config/config.template.json config/config.json
   cp config/config_secrets.template.json config/config_secrets.json
   # Edit config.json and config_secrets.json with your settings
   ```

5. **Authenticate Spotify (if using music mode):**
   ```bash
   python3 src/authenticate_spotify.py
   ```

6. **Install systemd services:**
   ```bash
   sudo cp matrix-display.service /etc/systemd/system/
   sudo cp web-config.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable matrix-display.service
   sudo systemctl enable web-config.service
   sudo systemctl start matrix-display.service
   sudo systemctl start web-config.service
   ```

## Configuration

### Web Interface

Access the web configuration interface at `http://<PI_IP>:5000` to:
- Enable/disable display modes
- Configure sports teams to follow
- Set up stock/crypto tickers
- Configure weather location
- Enable music mode and set polling interval

### Manual Configuration

Edit `config/config.json` directly for advanced settings:
- Display modes and rotation
- API endpoints
- Display preferences
- Cache settings

## Usage

### Display Modes

Navigate between modes using gesture controls:
- **Clock**: Time and date
- **Sports**: Rotating sports scores
- **Weather**: Current conditions
- **Stocks**: Stock and crypto prices
- **Music**: Current Spotify track with album art

### Gesture Controls

- **Tilt Left/Right**: Navigate between modes
- **Tap**: Select/confirm
- **Shake**: Return to clock

## Project Structure

```
matrix-display/
├── matrix_display_controller.py  # Main controller
├── receiver.py                    # BLE receiver for gestures
├── web_config.py                 # Web configuration interface
├── sports_fetcher.py             # Sports API integration
├── stock_fetcher.py              # Stock/crypto API integration
├── weather_fetcher.py            # Weather API integration
├── display_assets.py             # Asset loader for logos/icons
├── arduino_controller.ino        # Arduino firmware (reference)
├── requirements.txt              # Python dependencies
├── config/                       # Configuration files
│   ├── config.template.json
│   └── config_secrets.template.json
├── src/                          # Display managers
│   ├── music_manager.py          # Spotify music display
│   ├── clock.py                  # Clock display
│   ├── weather_manager.py        # Weather display
│   ├── stock_manager.py          # Stock display
│   └── ...                       # Other managers
└── assets/                       # Logos, fonts, icons
    ├── fonts/
    ├── sports/
    ├── stocks/
    └── weather/
```

## API Keys Required

- **OpenWeatherMap**: For weather data (free tier available)
- **Spotify**: For music mode (requires Spotify Premium)
- **ESPN**: Sports scores (no key required)
- **Yahoo Finance**: Stock/crypto prices (no key required)

## Troubleshooting

- **Display not working**: Check RGB matrix library installation and GPIO connections
- **BLE not connecting**: Verify ESP32 MAC address in `receiver.py`
- **Music not showing**: Ensure Spotify is authenticated and music is playing
- **Web interface not accessible**: Check firewall and service status

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

