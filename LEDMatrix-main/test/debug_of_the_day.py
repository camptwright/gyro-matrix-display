#!/usr/bin/env python3
"""
Debug script for OfTheDayManager issues
Run this on the Raspberry Pi to diagnose the problem

Usage:
1. Copy this file to your Raspberry Pi
2. Run: python3 debug_of_the_day.py
3. Check the output for any errors or issues

This script will help identify why the OfTheDayManager is not loading data files.
"""

import json
import os
import sys
from datetime import date

def debug_of_the_day():
    print("=== OfTheDayManager Debug Script ===")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    
    # Check if we're in the right directory
    if not os.path.exists('config/config.json'):
        print("ERROR: config/config.json not found. Make sure you're running from the LEDMatrix root directory.")
        return
    
    # Load the actual config
    try:
        with open('config/config.json', 'r') as f:
            config = json.load(f)
        print("✓ Successfully loaded config.json")
    except Exception as e:
        print(f"ERROR loading config.json: {e}")
        return
    
    # Check of_the_day configuration
    of_the_day_config = config.get('of_the_day', {})
    print(f"OfTheDay enabled: {of_the_day_config.get('enabled', False)}")
    
    if not of_the_day_config.get('enabled', False):
        print("OfTheDay is disabled in config!")
        return
    
    categories = of_the_day_config.get('categories', {})
    print(f"Categories configured: {list(categories.keys())}")
    
    # Test each category
    today = date.today()
    day_of_year = today.timetuple().tm_yday
    print(f"Today is day {day_of_year} of the year")
    
    for category_name, category_config in categories.items():
        print(f"\n--- Testing category: {category_name} ---")
        print(f"Category enabled: {category_config.get('enabled', True)}")
        
        if not category_config.get('enabled', True):
            print("Category is disabled, skipping...")
            continue
        
        data_file = category_config.get('data_file')
        print(f"Data file: {data_file}")
        
        # Test path resolution
        if not os.path.isabs(data_file):
            if data_file.startswith('of_the_day/'):
                file_path = os.path.join(os.getcwd(), data_file)
            else:
                file_path = os.path.join(os.getcwd(), 'of_the_day', data_file)
        else:
            file_path = data_file
        
        file_path = os.path.abspath(file_path)
        print(f"Resolved path: {file_path}")
        print(f"File exists: {os.path.exists(file_path)}")
        
        if not os.path.exists(file_path):
            print(f"ERROR: Data file not found at {file_path}")
            continue
        
        # Test JSON loading
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"✓ Successfully loaded JSON with {len(data)} items")
            
            # Check for today's entry
            day_key = str(day_of_year)
            if day_key in data:
                item = data[day_key]
                print(f"✓ Found entry for day {day_of_year}: {item.get('title', 'No title')}")
            else:
                print(f"✗ No entry found for day {day_of_year}")
                # Show some nearby entries
                nearby_days = [k for k in data.keys() if k.isdigit() and abs(int(k) - day_of_year) <= 5]
                print(f"Nearby days with entries: {sorted(nearby_days)}")
                
        except Exception as e:
            print(f"ERROR loading JSON: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n=== Debug complete ===")

if __name__ == "__main__":
    debug_of_the_day()
