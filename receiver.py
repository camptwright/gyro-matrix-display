#!/usr/bin/env python3
"""
BLE Receiver for Gyroscopic Controller
Receives gesture events from Arduino controller (gesture detection handled on device)
"""

import asyncio
import sys
import os
import time
from uuid import UUID
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakBluetoothNotAvailableError

# Import display controller
try:
    from matrix_display_controller import DisplayController
except ImportError:
    print("Error: Could not import DisplayController")
    sys.exit(1)

# BLE Configuration
NUS_SERVICE = UUID("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
NUS_TX = UUID("6e400003-b5a3-f393-e0a9-e50e24dcca9e")
DEVICE_HINTS = ["imu controller", "imu raw (ble uart)", "imu controller (ble uart)"]

# Mode management
MODES = ["clock", "sports", "stocks", "weather", "brightness"]

# Global display controller
display_controller: DisplayController = None

def ensure_display_controller():
    global display_controller
    if display_controller is None:
        try:
            display_controller = DisplayController()
            # Start display update loop in background thread
            import threading
            def run_display():
                try:
                    display_controller.run()
                except Exception as e:
                    print(f"Error in display loop: {e}")
                    import traceback
                    traceback.print_exc()
            
            display_thread = threading.Thread(target=run_display, daemon=True, name="display-update")
            display_thread.start()
            print("Display controller initialized and update loop started")
        except Exception as e:
            print(f"Error initializing display controller: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

# Gesture handlers
def handle_clock_gesture(direction: str):
    if direction == "left":
        display_controller.prev_clock_location()
    elif direction == "right":
        display_controller.next_clock_location()

def handle_sports_gesture(direction: str, axis: str):
    print(f"[SPORTS HANDLER] axis={axis}, direction={direction}")
    if axis == "pitch":  # up/down
        if direction == "up":
            print("[SPORTS] Calling next_sport()")
            display_controller.next_sport()
        elif direction == "down":
            print("[SPORTS] Calling prev_sport()")
            display_controller.prev_sport()
    elif axis == "yaw":  # left/right
        if direction == "left":
            print("[SPORTS] Calling prev_game()")
            display_controller.prev_game()
        elif direction == "right":
            print("[SPORTS] Calling next_game()")
            display_controller.next_game()
    else:
        print(f"[SPORTS HANDLER] Unknown axis: {axis}")

def handle_stocks_gesture(direction: str):
    if direction == "left":
        display_controller.prev_ticker()
    elif direction == "right":
        display_controller.next_ticker()

def handle_weather_gesture(direction: str):
    if direction == "left":
        display_controller.prev_weather_location()
    elif direction == "right":
        display_controller.next_weather_location()

def handle_brightness_gesture(direction: str):
    if direction == "left":
        display_controller.brightness_down()
    elif direction == "right":
        display_controller.brightness_up()

async def main():
    # Initialize display controller immediately (don't wait for BLE connection)
    ensure_display_controller()
    
    # Give display controller a moment to initialize
    await asyncio.sleep(0.5)
    
    # Current mode - set immediately so display shows something
    current_mode = "clock"
    display_controller.set_mode(current_mode)
    # Force an immediate update to show the display
    try:
        display_controller.update()
        print("Display initialized and showing clock mode")
    except Exception as e:
        print(f"Error in initial display update: {e}")
    print(f"Starting in mode: {current_mode}")
    print("Note: Display is active. BLE connection will be established in background.")
    
    # State for connection monitoring
    last_data_time = time.time()
    
    # BLE connection
    device = None
    client = None
    
    def on_notify(_, data: bytearray):
        nonlocal current_mode, last_data_time
        
        try:
            line = data.decode("utf-8").strip()
        except Exception as e:
            print(f"Error decoding BLE data: {e}")
            return
        
        last_data_time = time.time()
        
        # Handle button press
        if line.startswith("BUTTON,PRESS"):
            try:
                current_index = MODES.index(current_mode)
                next_index = (current_index + 1) % len(MODES)
                current_mode = MODES[next_index]
                display_controller.set_mode(current_mode)
                print(f"[BUTTON] Mode changed to: {current_mode}")
            except Exception as e:
                print(f"Error handling button press: {e}")
            return
        
        # Handle gesture events from Arduino
        if line.startswith("GESTURE,"):
            try:
                parts = line.split(",")
                if len(parts) >= 3:
                    axis = parts[1]  # "pitch" or "yaw"
                    direction = parts[2]  # "left", "right", "up", "down"
                    
                    print(f"[GESTURE] {axis} {direction} (mode: {current_mode})")
                    
                    # Route gesture to appropriate handler based on current mode
                    if current_mode == "clock":
                        if axis == "yaw":
                            handle_clock_gesture(direction)
                    elif current_mode == "sports":
                        print(f"[SPORTS] Handling {axis} {direction} gesture")
                        handle_sports_gesture(direction, axis)
                    elif current_mode == "stocks":
                        if axis == "yaw":
                            handle_stocks_gesture(direction)
                    elif current_mode == "weather":
                        if axis == "yaw":
                            handle_weather_gesture(direction)
                    elif current_mode == "brightness":
                        if axis == "yaw":
                            handle_brightness_gesture(direction)
                    else:
                        print(f"[GESTURE] Unknown mode: {current_mode}")
            except Exception as e:
                print(f"Error handling gesture: {e}")
                import traceback
                traceback.print_exc()
            return
        
        # Ignore other messages (like "ready" or raw data if still being sent)
        if line and not line.startswith("ready"):
            print(f"[DEBUG] Received: {line}")
    
    # Connect to BLE device with persistent scanning
    print("Scanning for BLE device...")
    device = None
    scan_attempts = 0
    max_scan_attempts = 60  # Try for up to 5 minutes (60 * 5 seconds)
    
    while device is None and scan_attempts < max_scan_attempts:
        try:
            # Use longer timeout for better discovery
            devices = await BleakScanner.discover(timeout=10.0)
            for d in devices:
                name_lower = (d.name or "").lower()
                if any(hint.lower() in name_lower for hint in DEVICE_HINTS):
                    device = d
                    break
            
            if device:
                print(f"Found device: {device.name} [{device.address}]")
                break
            else:
                scan_attempts += 1
                if scan_attempts % 6 == 0:  # Every 30 seconds
                    print(f"Device not found. Still scanning... (attempt {scan_attempts}/{max_scan_attempts})")
                await asyncio.sleep(5)
        except BleakBluetoothNotAvailableError:
            print("Bluetooth not available. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Error scanning: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
    
    # Connect and subscribe (if device was found)
    if device:
        print(f"Connecting to {device.name} [{device.address}]...")
        while True:
            try:
                client = BleakClient(device.address)
                await client.connect(timeout=10.0)
                
                if client.is_connected:
                    print("Connected. Subscribing to notifications...")
                    await client.start_notify(NUS_TX, on_notify)
                    print("Listening for gestures... Press Ctrl+C to quit.")
                    break
                else:
                    print("Connection failed. Retrying in 5 seconds...")
                    await asyncio.sleep(5)
            except Exception as e:
                print(f"Connection error: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)
    else:
        print(f"WARNING: Could not find device after {max_scan_attempts} attempts.")
        print("The controller may need to be reset. Will continue scanning in main loop...")
        # Create a dummy client object so the main loop can handle reconnection
        client = None
    
    # Main loop - keep connection alive and monitor with auto-reconnect
    try:
        last_check = time.time()
        reconnect_delay = 2.0  # Start with 2 second delay
        max_reconnect_delay = 30.0  # Max 30 seconds between reconnect attempts
        reconnect_in_progress = False
        
        while True:
            await asyncio.sleep(0.1)
            
            # Check connection every 5 seconds
            if time.time() - last_check > 5.0:
                last_check = time.time()
                if (not client or not client.is_connected) and not reconnect_in_progress:
                    reconnect_in_progress = True
                    print(f"Connection lost. Reconnecting in {reconnect_delay:.1f}s...")
                    try:
                        await client.disconnect()
                    except:
                        pass
                    
                    # Exponential backoff for reconnection
                    await asyncio.sleep(reconnect_delay)
                    
                    # Try to reconnect
                    try:
                        print("Scanning for BLE device...")
                        devices = await BleakScanner.discover(timeout=5.0)
                        found_device = None
                        for d in devices:
                            name_lower = (d.name or "").lower()
                            if any(hint.lower() in name_lower for hint in DEVICE_HINTS):
                                found_device = d
                                break
                        
                        if found_device:
                            print(f"Found device: {found_device.name} [{found_device.address}]")
                            client = BleakClient(found_device.address)
                            await client.connect(timeout=10.0)
                            
                            if client.is_connected:
                                print("Reconnected. Subscribing to notifications...")
                                await client.start_notify(NUS_TX, on_notify)
                                reconnect_delay = 2.0  # Reset delay on successful reconnect
                                reconnect_in_progress = False
                                print("Listening for gestures...")
                            else:
                                print("Reconnection failed, will retry...")
                                reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
                                reconnect_in_progress = False
                        else:
                            print("Device not found, will retry...")
                            reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
                            reconnect_in_progress = False
                    except Exception as e:
                        print(f"Reconnection error: {e}. Will retry...")
                        reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
                        reconnect_in_progress = False
            
            # Check for stale data (no updates in 10 seconds) - but only warn once per 10 second period
            if time.time() - last_data_time > 10.0:
                # Only print warning once, then reset to avoid spam
                if not hasattr(main, '_last_warning_time'):
                    main._last_warning_time = 0
                current_time = time.time()
                if current_time - main._last_warning_time > 10.0:
                    print("Warning: No data received in 10 seconds")
                    main._last_warning_time = current_time
                    last_data_time = current_time  # Reset to avoid immediate re-warning
    
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        if client and client.is_connected:
            await client.stop_notify(NUS_TX)
            await client.disconnect()
        print("Disconnected.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
