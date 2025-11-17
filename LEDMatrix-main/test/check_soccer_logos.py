#!/usr/bin/env python3
"""
Soccer Logo Checker and Downloader

This script checks for missing logos of major teams from supported soccer leagues
and downloads them from ESPN API if missing.

Supported Leagues:
- Premier League (eng.1)
- La Liga (esp.1) 
- Bundesliga (ger.1)
- Serie A (ita.1)
- Ligue 1 (fra.1)
- Liga Portugal (por.1)
- Champions League (uefa.champions)
- Europa League (uefa.europa)
- MLS (usa.1)
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Tuple

# Add src directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from logo_downloader import download_missing_logo, get_soccer_league_key, LogoDownloader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Major teams for each league (with their ESPN abbreviations)
MAJOR_TEAMS = {
    'eng.1': {  # Premier League
        'ARS': 'Arsenal',
        'AVL': 'Aston Villa', 
        'BHA': 'Brighton & Hove Albion',
        'BOU': 'AFC Bournemouth',
        'BRE': 'Brentford',
        'BUR': 'Burnley',
        'CHE': 'Chelsea',
        'CRY': 'Crystal Palace',
        'EVE': 'Everton',
        'FUL': 'Fulham',
        'LIV': 'Liverpool',
        'LUT': 'Luton Town',
        'MCI': 'Manchester City',
        'MUN': 'Manchester United',
        'NEW': 'Newcastle United',
        'NFO': 'Nottingham Forest',
        'SHU': 'Sheffield United',
        'TOT': 'Tottenham Hotspur',
        'WHU': 'West Ham United',
        'WOL': 'Wolverhampton Wanderers'
    },
    'esp.1': {  # La Liga
        'ALA': 'Alavés',
        'ATH': 'Athletic Bilbao',
        'ATM': 'Atlético Madrid',
        'BAR': 'Barcelona',
        'BET': 'Real Betis',
        'CEL': 'Celta Vigo',
        'ESP': 'Espanyol',
        'GET': 'Getafe',
        'GIR': 'Girona',
        'LEG': 'Leganés',
        'RAY': 'Rayo Vallecano',
        'RMA': 'Real Madrid',
        'SEV': 'Sevilla',
        'VAL': 'Valencia',
        'VLD': 'Valladolid'
    },
    'ger.1': {  # Bundesliga
        'BOC': 'VfL Bochum',
        'DOR': 'Borussia Dortmund',
        'FCA': 'FC Augsburg',
        'FCB': 'Bayern Munich',
        'FCU': 'FC Union Berlin',
        'KOL': '1. FC Köln',
        'LEV': 'Bayer Leverkusen',
        'M05': 'Mainz 05',
        'RBL': 'RB Leipzig',
        'SCF': 'SC Freiburg',
        'SGE': 'Eintracht Frankfurt',
        'STU': 'VfB Stuttgart',
        'SVW': 'Werder Bremen',
        'TSG': 'TSG Hoffenheim',
        'WOB': 'VfL Wolfsburg'
    },
    'ita.1': {  # Serie A
        'ATA': 'Atalanta',
        'CAG': 'Cagliari',
        'EMP': 'Empoli',
        'FIO': 'Fiorentina',
        'INT': 'Inter Milan',
        'JUV': 'Juventus',
        'LAZ': 'Lazio',
        'MIL': 'AC Milan',
        'MON': 'Monza',
        'NAP': 'Napoli',
        'ROM': 'Roma',
        'TOR': 'Torino',
        'UDI': 'Udinese',
        'VER': 'Hellas Verona'
    },
    'fra.1': {  # Ligue 1
        'LIL': 'Lille',
        'LYON': 'Lyon',
        'MAR': 'Marseille',
        'MON': 'Monaco',
        'NAN': 'Nantes',
        'NICE': 'Nice',
        'OL': 'Olympique Lyonnais',
        'OM': 'Olympique de Marseille',
        'PAR': 'Paris Saint-Germain',
        'PSG': 'Paris Saint-Germain',
        'REN': 'Rennes',
        'STR': 'Strasbourg'
    },
    'por.1': {  # Liga Portugal
        'ARO': 'Arouca',
        'BEN': 'SL Benfica',
        'BRA': 'SC Braga',
        'CHA': 'Chaves',
        'EST': 'Estoril Praia',
        'FAM': 'Famalicão',
        'GIL': 'Gil Vicente',
        'MOR': 'Moreirense',
        'POR': 'FC Porto',
        'PTM': 'Portimonense',
        'RIO': 'Rio Ave',
        'SR': 'Sporting CP',
        'SCP': 'Sporting CP',  # Alternative abbreviation
        'VGU': 'Vitória de Guimarães',
        'VSC': 'Vitória de Setúbal'
    },
    'uefa.champions': {  # Champions League (major teams)
        'AJX': 'Ajax',
        'ATM': 'Atlético Madrid',
        'BAR': 'Barcelona',
        'BAY': 'Bayern Munich',
        'CHE': 'Chelsea',
        'INT': 'Inter Milan',
        'JUV': 'Juventus',
        'LIV': 'Liverpool',
        'MCI': 'Manchester City',
        'MUN': 'Manchester United',
        'PSG': 'Paris Saint-Germain',
        'RMA': 'Real Madrid',
        'TOT': 'Tottenham Hotspur'
    },
    'uefa.europa': {  # Europa League (major teams)
        'ARS': 'Arsenal',
        'ATM': 'Atlético Madrid',
        'BAR': 'Barcelona',
        'CHE': 'Chelsea',
        'INT': 'Inter Milan',
        'JUV': 'Juventus',
        'LIV': 'Liverpool',
        'MUN': 'Manchester United',
        'NAP': 'Napoli',
        'ROM': 'Roma',
        'SEV': 'Sevilla'
    },
    'usa.1': {  # MLS
        'ATL': 'Atlanta United',
        'AUS': 'Austin FC',
        'CHI': 'Chicago Fire',
        'CIN': 'FC Cincinnati',
        'CLB': 'Columbus Crew',
        'DAL': 'FC Dallas',
        'DC': 'D.C. United',
        'HOU': 'Houston Dynamo',
        'LA': 'LA Galaxy',
        'LAFC': 'Los Angeles FC',
        'MIA': 'Inter Miami',
        'MIN': 'Minnesota United',
        'MTL': 'CF Montréal',
        'NSC': 'Nashville SC',
        'NYC': 'New York City FC',
        'NYR': 'New York Red Bulls',
        'ORL': 'Orlando City',
        'PHI': 'Philadelphia Union',
        'POR': 'Portland Timbers',
        'RSL': 'Real Salt Lake',
        'SEA': 'Seattle Sounders',
        'SJ': 'San Jose Earthquakes',
        'SKC': 'Sporting Kansas City',
        'TOR': 'Toronto FC',
        'VAN': 'Vancouver Whitecaps'
    }
}

def check_logo_exists(team_abbr: str, logo_dir: str) -> bool:
    """Check if a logo file exists for the given team abbreviation."""
    logo_path = os.path.join(logo_dir, f"{team_abbr}.png")
    return os.path.exists(logo_path)

def download_team_logo(team_abbr: str, team_name: str, league_code: str) -> bool:
    """Download a team logo from ESPN API."""
    try:
        soccer_league_key = get_soccer_league_key(league_code)
        logger.info(f"Downloading {team_abbr} ({team_name}) from {league_code}")
        
        success = download_missing_logo(team_abbr, soccer_league_key, team_name)
        if success:
            logger.info(f"✅ Successfully downloaded {team_abbr} ({team_name})")
            return True
        else:
            logger.warning(f"❌ Failed to download {team_abbr} ({team_name})")
            return False
    except Exception as e:
        logger.error(f"❌ Error downloading {team_abbr} ({team_name}): {e}")
        return False

def check_league_logos(league_code: str, teams: Dict[str, str], logo_dir: str) -> Tuple[int, int]:
    """Check and download missing logos for a specific league."""
    logger.info(f"\n🔍 Checking {league_code} ({LEAGUE_NAMES.get(league_code, league_code)})")
    
    missing_logos = []
    existing_logos = []
    
    # Check which logos are missing
    for team_abbr, team_name in teams.items():
        if check_logo_exists(team_abbr, logo_dir):
            existing_logos.append(team_abbr)
        else:
            missing_logos.append((team_abbr, team_name))
    
    logger.info(f"📊 Found {len(existing_logos)} existing logos, {len(missing_logos)} missing")
    
    if existing_logos:
        logger.info(f"✅ Existing: {', '.join(existing_logos)}")
    
    if missing_logos:
        logger.info(f"❌ Missing: {', '.join([f'{abbr} ({name})' for abbr, name in missing_logos])}")
    
    # Download missing logos
    downloaded_count = 0
    failed_count = 0
    
    for team_abbr, team_name in missing_logos:
        if download_team_logo(team_abbr, team_name, league_code):
            downloaded_count += 1
        else:
            failed_count += 1
    
    return downloaded_count, failed_count

def main():
    """Main function to check and download all soccer logos."""
    logger.info("⚽ Soccer Logo Checker and Downloader")
    logger.info("=" * 50)
    
    # Ensure logo directory exists
    logo_dir = "assets/sports/soccer_logos"
    os.makedirs(logo_dir, exist_ok=True)
    logger.info(f"📁 Logo directory: {logo_dir}")
    
    # League names for display
    global LEAGUE_NAMES
    LEAGUE_NAMES = {
        'eng.1': 'Premier League',
        'esp.1': 'La Liga',
        'ger.1': 'Bundesliga',
        'ita.1': 'Serie A',
        'fra.1': 'Ligue 1',
        'por.1': 'Liga Portugal',
        'uefa.champions': 'Champions League',
        'uefa.europa': 'Europa League',
        'usa.1': 'MLS'
    }
    
    total_downloaded = 0
    total_failed = 0
    total_existing = 0
    
    # Check each league
    for league_code, teams in MAJOR_TEAMS.items():
        downloaded, failed = check_league_logos(league_code, teams, logo_dir)
        total_downloaded += downloaded
        total_failed += failed
        total_existing += len(teams) - downloaded - failed
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("📈 SUMMARY")
    logger.info("=" * 50)
    logger.info(f"✅ Existing logos: {total_existing}")
    logger.info(f"⬇️  Downloaded: {total_downloaded}")
    logger.info(f"❌ Failed downloads: {total_failed}")
    logger.info(f"📊 Total teams checked: {total_existing + total_downloaded + total_failed}")
    
    if total_failed > 0:
        logger.warning(f"\n⚠️  {total_failed} logos failed to download. This might be due to:")
        logger.warning("   - Network connectivity issues")
        logger.warning("   - ESPN API rate limiting")
        logger.warning("   - Team abbreviations not matching ESPN's format")
        logger.warning("   - Teams not currently in the league")
    
    if total_downloaded > 0:
        logger.info(f"\n🎉 Successfully downloaded {total_downloaded} new logos!")
        logger.info("   These logos are now available for use in the LEDMatrix display.")
    
    logger.info(f"\n📁 All logos are stored in: {os.path.abspath(logo_dir)}")

if __name__ == "__main__":
    main()
