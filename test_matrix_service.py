#!/usr/bin/env python3
"""
Minimal test script to verify RGB matrix works when run as a service
"""

import time
import sys
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image, ImageDraw

print("Initializing RGB Matrix...")

options = RGBMatrixOptions()
options.rows = 32
options.cols = 64
options.chain_length = 1
options.parallel = 1
# Try different mappings - test which one works
# Common: 'regular', 'adafruit-hat', 'adafruit-hat-pwm', 'adafruit-rgb-matrix-pi'
options.hardware_mapping = 'adafruit-hat'  # Changed to match service
options.brightness = 100

try:
    matrix = RGBMatrix(options=options)
    offscreen_canvas = matrix.CreateFrameCanvas()
    
    print("Matrix initialized. Testing colors...")
    
    # Test RED
    print("Showing RED...")
    img = Image.new('RGB', (64, 32), color=(255, 0, 0))
    offscreen_canvas.SetImage(img)
    offscreen_canvas = matrix.SwapOnVSync(offscreen_canvas)
    time.sleep(3)
    
    # Test GREEN
    print("Showing GREEN...")
    img = Image.new('RGB', (64, 32), color=(0, 255, 0))
    offscreen_canvas.SetImage(img)
    offscreen_canvas = matrix.SwapOnVSync(offscreen_canvas)
    time.sleep(3)
    
    # Test BLUE
    print("Showing BLUE...")
    img = Image.new('RGB', (64, 32), color=(0, 0, 255))
    offscreen_canvas.SetImage(img)
    offscreen_canvas = matrix.SwapOnVSync(offscreen_canvas)
    time.sleep(3)
    
    # Test WHITE
    print("Showing WHITE...")
    img = Image.new('RGB', (64, 32), color=(255, 255, 255))
    offscreen_canvas.SetImage(img)
    offscreen_canvas = matrix.SwapOnVSync(offscreen_canvas)
    time.sleep(3)
    
    print("Test complete. Display should have shown RED, GREEN, BLUE, WHITE.")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

