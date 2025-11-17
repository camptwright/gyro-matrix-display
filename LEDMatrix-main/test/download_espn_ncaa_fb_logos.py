#!/usr/bin/env python3
"""
Script to download all NCAA Football team logos from ESPN API
and update the all_team_abbreviations.txt file with current ESPN abbreviations.
"""

import os
import requests
import json
from pathlib import Path
import time

def create_logo_directory():
    """Create the ncaaFBlogos directory if it doesn't exist."""
    logo_dir = Path("test/ncaaFBlogos")
    logo_dir.mkdir(parents=True, exist_ok=True)
    return logo_dir

def fetch_teams_data():
    """Fetch team data from ESPN API."""
    url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching teams data: {e}")
        return None

def download_logo(url, filepath, team_name):
    """Download a logo from URL and save to filepath."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        print(f"✓ Downloaded: {team_name} -> {filepath.name}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to download {team_name}: {e}")
        return False

def normalize_abbreviation(abbreviation):
    """Normalize team abbreviation to lowercase for filename."""
    return abbreviation.lower()

def update_abbreviations_file(teams_data, abbreviations_file_path):
    """Update the all_team_abbreviations.txt file with current ESPN abbreviations."""
    print(f"\nUpdating abbreviations file: {abbreviations_file_path}")
    
    # Read existing file
    existing_content = []
    if os.path.exists(abbreviations_file_path):
        with open(abbreviations_file_path, 'r', encoding='utf-8') as f:
            existing_content = f.readlines()
    
    # Find the NCAAF section
    ncaaf_start = -1
    ncaaf_end = -1
    
    for i, line in enumerate(existing_content):
        if line.strip() == "NCAAF":
            ncaaf_start = i
        elif ncaaf_start != -1 and line.strip() and not line.startswith("  "):
            ncaaf_end = i
            break
    
    if ncaaf_start == -1:
        print("Warning: Could not find NCAAF section in abbreviations file")
        return
    
    if ncaaf_end == -1:
        ncaaf_end = len(existing_content)
    
    # Extract teams from ESPN data
    espn_teams = []
    for team_data in teams_data:
        team = team_data.get('team', {})
        abbreviation = team.get('abbreviation', '')
        display_name = team.get('displayName', '')
        
        if abbreviation and display_name:
            espn_teams.append((abbreviation, display_name))
    
    # Sort teams by abbreviation
    espn_teams.sort(key=lambda x: x[0])
    
    # Create new NCAAF section
    new_ncaaf_section = ["NCAAF\n"]
    for abbreviation, display_name in espn_teams:
        new_ncaaf_section.append(f"  {abbreviation} => {display_name}\n")
    new_ncaaf_section.append("\n")
    
    # Reconstruct the file
    new_content = (
        existing_content[:ncaaf_start] + 
        new_ncaaf_section + 
        existing_content[ncaaf_end:]
    )
    
    # Write updated file
    with open(abbreviations_file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_content)
    
    print(f"✓ Updated abbreviations file with {len(espn_teams)} NCAAF teams")

def main():
    """Main function to download all NCAA FB team logos and update abbreviations."""
    print("Starting NCAA Football logo download and abbreviations update...")
    
    # Create directory
    logo_dir = create_logo_directory()
    print(f"Created/verified directory: {logo_dir}")
    
    # Fetch teams data
    print("Fetching teams data from ESPN API...")
    data = fetch_teams_data()
    
    if not data:
        print("Failed to fetch teams data. Exiting.")
        return
    
    # Extract teams
    teams = []
    try:
        sports = data.get('sports', [])
        for sport in sports:
            leagues = sport.get('leagues', [])
            for league in leagues:
                teams = league.get('teams', [])
                break
    except (KeyError, IndexError) as e:
        print(f"Error parsing teams data: {e}")
        return
    
    print(f"Found {len(teams)} teams")
    
    # Download logos
    downloaded_count = 0
    failed_count = 0
    
    for team_data in teams:
        team = team_data.get('team', {})
        
        # Extract team information
        abbreviation = team.get('abbreviation', '')
        display_name = team.get('displayName', 'Unknown')
        logos = team.get('logos', [])
        
        if not abbreviation or not logos:
            print(f"⚠ Skipping {display_name}: missing abbreviation or logos")
            continue
        
        # Get the default logo (first one is usually default)
        logo_url = logos[0].get('href', '')
        if not logo_url:
            print(f"⚠ Skipping {display_name}: no logo URL")
            continue
        
        # Create filename
        filename = f"{normalize_abbreviation(abbreviation)}.png"
        filepath = logo_dir / filename
        
        # Skip if already exists
        if filepath.exists():
            print(f"⏭ Skipping {display_name}: {filename} already exists")
            continue
        
        # Download logo
        if download_logo(logo_url, filepath, display_name):
            downloaded_count += 1
        else:
            failed_count += 1
        
        # Small delay to be respectful to the API
        time.sleep(0.1)
    
    print(f"\nDownload complete!")
    print(f"✓ Successfully downloaded: {downloaded_count} logos")
    print(f"✗ Failed downloads: {failed_count}")
    print(f"📁 Logos saved in: {logo_dir}")
    
    # Update abbreviations file
    abbreviations_file_path = "assets/sports/all_team_abbreviations.txt"
    update_abbreviations_file(teams, abbreviations_file_path)

if __name__ == "__main__":
    main()
