#!/bin/bash

# Script to update systemd service files with the correct username
# Run this from the matrix-display directory on your Pi

set -e

# Get the actual user (even if running with sudo)
if [ -n "$SUDO_USER" ]; then
    ACTUAL_USER="$SUDO_USER"
else
    ACTUAL_USER=$(whoami)
fi

# Get the home directory
USER_HOME=$(eval echo ~$ACTUAL_USER)

echo "Detected user: $ACTUAL_USER"
echo "Home directory: $USER_HOME"
echo "Current directory: $(pwd)"

# Check if we're in the right directory
if [ ! -f "matrix-display.service" ]; then
    echo "Error: matrix-display.service not found in current directory"
    echo "Please run this script from the matrix-display directory"
    exit 1
fi

# Create temporary service files with correct paths
echo "Updating matrix-display.service..."
sed "s|User=.*|User=$ACTUAL_USER|g; s|Group=.*|Group=$ACTUAL_USER|g; s|/home/[^/]*/matrix-display|$USER_HOME/matrix-display|g; s|Environment=USER=.*|Environment=USER=$ACTUAL_USER|g; s|Environment=HOME=.*|Environment=HOME=$USER_HOME|g" matrix-display.service > /tmp/matrix-display.service.tmp

if [ -f "web-config.service" ]; then
    echo "Updating web-config.service..."
    sed "s|User=.*|User=$ACTUAL_USER|g; s|/home/[^/]*/matrix-display|$USER_HOME/matrix-display|g" web-config.service > /tmp/web-config.service.tmp
fi

# Copy to systemd directory
echo "Installing service files..."
sudo cp /tmp/matrix-display.service.tmp /etc/systemd/system/matrix-display.service

if [ -f "/tmp/web-config.service.tmp" ]; then
    sudo cp /tmp/web-config.service.tmp /etc/systemd/system/web-config.service
fi

# Clean up
rm /tmp/matrix-display.service.tmp
if [ -f "/tmp/web-config.service.tmp" ]; then
    rm /tmp/web-config.service.tmp
fi

# Reload systemd
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo ""
echo "Service files updated successfully!"
echo ""
echo "To start the services:"
echo "  sudo systemctl start matrix-display.service"
echo "  sudo systemctl start web-config.service"
echo ""
echo "To check status:"
echo "  sudo systemctl status matrix-display.service"
echo "  sudo systemctl status web-config.service"

