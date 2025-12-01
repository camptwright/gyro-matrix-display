#!/usr/bin/env python3
"""
Simple test script to verify RGB matrix display is working
"""

import sys
import time

try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    print(f"Error importing libraries: {e}")
    sys.exit(1)

print("Testing RGB Matrix Display...")
print("==============================")

try:
    # Setup matrix
    print("Configuring matrix options...")
    options = RGBMatrixOptions()
    options.rows = 32
    options.cols = 64
    options.chain_length = 1
    options.parallel = 1
    options.hardware_mapping = 'adafruit-hat-pwm'  # For pins 4/18 connection
    options.brightness = 70  # Increased brightness for better visibility
    options.pwm_bits = 10
    options.pwm_lsb_nanoseconds = 150
    options.led_rgb_sequence = 'RGB'
    options.gpio_slowdown = 2  # Important for Pi 3B
    options.disable_hardware_pulsing = True  # Avoid root requirement
    options.show_refresh_rate = False
    options.limit_refresh_rate_hz = 60
    
    print(f"Matrix config: {options.rows}x{options.cols}, brightness={options.brightness}, gpio_slowdown={options.gpio_slowdown}")
    print("Creating matrix...")
    matrix = RGBMatrix(options=options)
    print(f"Matrix created: {matrix.width}x{matrix.height}")
    
    print("Creating frame canvas...")
    canvas = matrix.CreateFrameCanvas()
    print("Canvas created successfully")
    
    print("Creating test image...")
    img = Image.new('RGB', (matrix.width, matrix.height))
    draw = ImageDraw.Draw(img)
    print(f"Image created: {img.size}")
    
    # Test 1: Red screen
    print("\nTest 1: Red screen (3 seconds)...")
    draw.rectangle([0, 0, matrix.width-1, matrix.height-1], fill=(255, 0, 0))
    canvas.SetImage(img)
    canvas = matrix.SwapOnVSync(canvas)  # Capture return value
    print("Red screen displayed")
    time.sleep(3)
    
    # Test 2: Green screen
    print("Test 2: Green screen (3 seconds)...")
    draw.rectangle([0, 0, matrix.width-1, matrix.height-1], fill=(0, 255, 0))
    canvas.SetImage(img)
    canvas = matrix.SwapOnVSync(canvas)  # Capture return value
    print("Green screen displayed")
    time.sleep(3)
    
    # Test 3: Blue screen
    print("Test 3: Blue screen (3 seconds)...")
    draw.rectangle([0, 0, matrix.width-1, matrix.height-1], fill=(0, 0, 255))
    canvas.SetImage(img)
    canvas = matrix.SwapOnVSync(canvas)  # Capture return value
    print("Blue screen displayed")
    time.sleep(3)
    
    # Test 4: White screen
    print("Test 4: White screen (2 seconds)...")
    draw.rectangle([0, 0, matrix.width-1, matrix.height-1], fill=(255, 255, 255))
    canvas.SetImage(img)
    canvas = matrix.SwapOnVSync(canvas)  # Capture return value
    print("White screen displayed")
    time.sleep(2)
    
    # Test 5: White text on black
    print("Test 5: White text (3 seconds)...")
    draw.rectangle([0, 0, matrix.width-1, matrix.height-1], fill=(0, 0, 0))
    try:
        font = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
    except:
        font = ImageFont.load_default()
    draw.text((10, 10), "TEST", font=font, fill=(255, 255, 255))
    canvas.SetImage(img)
    canvas = matrix.SwapOnVSync(canvas)  # Capture return value
    print("Text displayed")
    time.sleep(3)
    
    # Clear
    print("Clearing display...")
    draw.rectangle([0, 0, matrix.width-1, matrix.height-1], fill=(0, 0, 0))
    canvas.SetImage(img)
    canvas = matrix.SwapOnVSync(canvas)  # Capture return value
    
    print("\n✓ Display test complete!")
    print("If you saw colors and text, your display is working correctly.")
    
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    print("\nTroubleshooting tips:")
    print("1. Make sure you're running as root or have proper permissions")
    print("2. Check that the Adafruit Bonnet is properly connected")
    print("3. Verify the power adapter is providing enough current (4000mA+)")
    print("4. Try running with sudo: sudo python3 test_display.py")
    print("5. Check dmesg for hardware errors: dmesg | tail -20")
    sys.exit(1)

