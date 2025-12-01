#!/bin/bash
# Setup script for Matrix Display Controller

# Don't exit on error - we'll handle errors explicitly
set +e

echo "Matrix Display Controller Setup"
echo "================================"

# Get the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ] || ! grep -q "Raspberry Pi" /proc/device-tree/model; then
    echo "Warning: This script is designed for Raspberry Pi"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install Python dependencies
echo "Installing Python dependencies..."

# Check if we should use venv or system packages
if [ "$1" == "--venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    echo "Virtual environment created. Activate with: source venv/bin/activate"
    echo ""
    echo "IMPORTANT: Update systemd service files to use venv python:"
    echo "  sudo sed -i 's|/usr/bin/python3|/home/pi/matrix-display/venv/bin/python3|g' /etc/systemd/system/matrix-display.service"
    echo "  sudo sed -i 's|/usr/bin/python3|/home/pi/matrix-display/venv/bin/python3|g' /etc/systemd/system/web-config.service"
    echo "  sudo systemctl daemon-reload"
else
    echo "Installing to system (using --break-system-packages)..."
    if ! pip3 install --break-system-packages -r requirements.txt 2>&1; then
        echo ""
        echo "✗ Installation failed with --break-system-packages"
        echo ""
        echo "Trying to install python3-venv and use virtual environment instead..."
        sudo apt install -y python3-venv
        
        if [ $? -eq 0 ]; then
            echo "Creating virtual environment..."
            python3 -m venv venv
            source venv/bin/activate
            pip install -r requirements.txt
            
            if [ $? -eq 0 ]; then
                echo "✓ Virtual environment created and packages installed"
                echo ""
                echo "IMPORTANT: Update systemd service files to use venv python:"
                echo "  sudo sed -i 's|/usr/bin/python3|/home/pi/matrix-display/venv/bin/python3|g' /etc/systemd/system/matrix-display.service"
                echo "  sudo sed -i 's|/usr/bin/python3|/home/pi/matrix-display/venv/bin/python3|g' /etc/systemd/system/web-config.service"
                echo "  sudo systemctl daemon-reload"
            else
                echo "✗ Failed to install packages in virtual environment"
                exit 1
            fi
        else
            echo "✗ Failed to install python3-venv"
            echo ""
            echo "Please install manually:"
            echo "  sudo apt install -y python3-venv"
            echo "  ./setup.sh --venv"
            exit 1
        fi
    else
        echo "✓ Python packages installed successfully"
    fi
fi

# Re-enable exit on error for the rest
set -e

# Make scripts executable
echo "Making scripts executable..."
chmod +x receiver.py
chmod +x matrix_display_controller.py
chmod +x web_config.py

# Create config.json if it doesn't exist
if [ ! -f config.json ]; then
    echo "Creating default config.json..."
    cat > config.json << EOF
{
  "brightness": 50,
  "timezone": "America/New_York",
  "clock_locations": [],
  "sports": [],
  "stocks": [],
  "crypto": [],
  "weather_locations": []
}
EOF
fi

# Install systemd services
echo "Installing systemd services..."
sudo cp matrix-display.service /etc/systemd/system/
sudo cp web-config.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable services (but don't start yet - user may want to configure first)
echo "Services installed. To enable and start:"
echo "  sudo systemctl enable matrix-display.service"
echo "  sudo systemctl enable web-config.service"
echo "  sudo systemctl start matrix-display.service"
echo "  sudo systemctl start web-config.service"

# Check if RGB matrix library is installed
echo ""
echo "Checking for RGB matrix library..."
if python3 -c "import rgbmatrix" 2>/dev/null; then
    echo "✓ RGB matrix library found"
else
    echo "✗ RGB matrix library not found"
    echo "  Install with:"
    echo "    cd ~"
    echo "    git clone https://github.com/hzeller/rpi-rgb-led-matrix.git"
    echo "    cd rpi-rgb-led-matrix"
    echo "    make -C python"
    echo "    sudo make -C python install"
fi

# Check Bluetooth
echo ""
echo "Checking Bluetooth..."
if command -v bluetoothctl &> /dev/null; then
    echo "✓ bluetoothctl found"
    echo "  Ensure Bluetooth is powered on: sudo bluetoothctl power on"
else
    echo "✗ bluetoothctl not found"
fi

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Configure your settings via web interface: http://localhost:5000"
echo "2. Upload arduino_controller.py to your ESP32-S3 Feather"
echo "3. Enable and start services (commands shown above)"
echo "4. Check status: sudo systemctl status matrix-display.service"

