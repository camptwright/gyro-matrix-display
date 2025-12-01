# Matrix Display Controller with Gyroscopic Control

A comprehensive sports, stocks, weather, and clock matrix display system controlled via a gyroscopic ESP32-S3 Feather controller. Optimized for Raspberry Pi 3B with Adafruit RGB Matrix Bonnet and 32x64 RGB LED Matrix (6mm pitch).

## Features

- **Multiple Display Modes:**
  - Clock with multiple time zones
  - Sports scores and games
  - Stocks and cryptocurrency prices
  - Weather information
  - Brightness control

- **Gyroscopic Control:**
  - Button cycles through modes: Clock → Sports → Stocks → Weather → Brightness → Clock
  - Gesture-based navigation for each mode
  - Bluetooth Low Energy (BLE) communication

- **Web Configuration Interface:**
  - Configure favorites/areas for each mode
  - Adjust brightness
  - Manage time zones, sports, stocks, crypto, and weather locations

## Hardware Requirements

- Raspberry Pi 3B
- Adafruit RGB Matrix Bonnet
- Adafruit 6mm pitch 32x64 RGB LED Matrix display
- Adafruit ESP32-S3 Feather
- MPU6050 Gyroscope/Accelerometer
- Button (connected to D9 on ESP32)

## Installation

**For detailed installation instructions, see [INSTALL.md](INSTALL.md)**

### Quick Start

1. **Transfer files to your Pi:**
   ```bash
   scp -r * pi@raspberrypi.local:~/matrix-display/
   ```

2. **SSH into your Pi:**
   ```bash
   ssh pi@raspberrypi.local
   cd ~/matrix-display
   ```

3. **Run the setup script:**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

4. **Install RGB Matrix Library:**
   ```bash
   cd ~
   git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
   cd rpi-rgb-led-matrix
   make -C python
   sudo make -C python install
   cd ~/matrix-display
   ```

5. **Install Python dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

6. **Configure via web interface:**
   ```bash
   python3 web_config.py
   # Then open http://localhost:5000 in a browser
   ```

7. **Enable auto-start:**
   ```bash
   sudo systemctl enable matrix-display.service
   sudo systemctl enable web-config.service
   sudo systemctl start matrix-display.service
   sudo systemctl start web-config.service
   ```

### Upload ESP32 Controller Code

Upload `arduino_controller.py` to your ESP32-S3 Feather using Arduino IDE. Install these libraries:
- NimBLE-Arduino
- Adafruit MPU6050
- Adafruit Unified Sensor
- Adafruit BusIO

## Configuration

### Web Configuration Interface (Recommended)

Access the web interface at `http://your-pi-ip:5000` or `http://localhost:5000` from the Pi.

Configure:
- Clock locations (time zones)
- Sports favorites
- Stock tickers
- Cryptocurrency tickers
- Weather locations
- Brightness level

### Manual Configuration

Edit `config.json` directly. The system will create a default config on first run.

## Usage

### Gesture Controls

**Clock Mode:**
- LEFT FLICK = Previous time zone
- RIGHT FLICK = Next time zone

**Sports Mode:**
- UP FLICK = Next sport
- DOWN FLICK = Previous sport
- RIGHT FLICK = Next game (same sport)
- LEFT FLICK = Previous game (same sport)

**Stocks/Crypto Mode:**
- LEFT FLICK = Previous ticker
- RIGHT FLICK = Next ticker

**Weather Mode:**
- LEFT FLICK = Previous weather location
- RIGHT FLICK = Next weather location

**Brightness Mode:**
- LEFT FLICK = Decrease brightness
- RIGHT FLICK = Increase brightness

### Button Control

Press the button on the ESP32 controller to cycle through modes:
Clock → Sports → Stocks → Weather → Brightness → Clock

## File Structure

```
.
├── arduino_controller.py      # ESP32-S3 Feather controller code
├── receiver.py                # BLE receiver and gesture handler
├── matrix_display_controller.py # Main display controller
├── web_config.py              # Web configuration interface
├── matrix-display.service      # Systemd service for display
├── web-config.service         # Systemd service for web interface
├── requirements.txt           # Python dependencies
├── config.json                # Configuration file (auto-generated)
└── README.md                  # This file
```

## Troubleshooting

### Display Not Working

1. Check that the RGB Matrix Bonnet is properly connected
2. Verify GPIO slowdown setting (should be 2 for Pi 3B)
3. Check brightness setting (may be too low)
4. Review logs: `sudo journalctl -u matrix-display.service -f`

### Bluetooth Connection Issues

1. Ensure Bluetooth is powered on: `sudo bluetoothctl power on`
2. Check if device is discoverable
3. Review logs: `sudo journalctl -u matrix-display.service -f`

### Web Interface Not Accessible

1. Check if service is running: `sudo systemctl status web-config.service`
2. Verify port 5000 is not blocked by firewall
3. Review logs: `sudo journalctl -u web-config.service -f`

## Performance Optimization for Pi 3B

The system is optimized for Raspberry Pi 3B with:
- Reduced refresh rate (60 Hz)
- GPIO slowdown of 2
- Efficient update intervals
- Lightweight display rendering

## License

This project is provided as-is for educational and personal use.

## Credits

Built using examples from:
- LEDMatrix project
- Adafruit RGB Matrix libraries
- rpi-rgb-led-matrix by hzeller

