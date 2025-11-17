#!/usr/bin/env python3
"""
Broadcast Logo Analyzer

This script analyzes broadcast channel logos to ensure we have proper logos
for every game and identifies missing or problematic logos that might show
as white boxes.

IMPORTANT: This script must be run on the Raspberry Pi where the LEDMatrix
project is located, as it needs to access the actual logo files in the
assets/broadcast_logos/ directory.

Usage (on Raspberry Pi):
    python test/analyze_broadcast_logos.py

Features:
- Checks all broadcast logos referenced in BROADCAST_LOGO_MAP
- Validates logo file existence and integrity
- Analyzes logo dimensions and transparency
- Identifies potential white box issues
- Provides recommendations for missing logos
- Generates a detailed report
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from PIL import Image, ImageStat
import logging

# Add the project root to the path so we can import from src
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Define the broadcast logo map directly (copied from odds_ticker_manager.py)
BROADCAST_LOGO_MAP = {
    "ACC Network": "accn",
    "ACCN": "accn",
    "ABC": "abc",
    "BTN": "btn",
    "CBS": "cbs",
    "CBSSN": "cbssn",
    "CBS Sports Network": "cbssn",
    "ESPN": "espn",
    "ESPN2": "espn2",
    "ESPN3": "espn3",
    "ESPNU": "espnu",
    "ESPNEWS": "espn",
    "ESPN+": "espn",
    "ESPN Plus": "espn",
    "FOX": "fox",
    "FS1": "fs1",
    "FS2": "fs2",
    "MLBN": "mlbn",
    "MLB Network": "mlbn",
    "MLB.TV": "mlbn",
    "NBC": "nbc",
    "NFLN": "nfln",
    "NFL Network": "nfln",
    "PAC12": "pac12n",
    "Pac-12 Network": "pac12n",
    "SECN": "espn-sec-us",
    "TBS": "tbs",
    "TNT": "tnt",
    "truTV": "tru",
    "Peacock": "nbc",
    "Paramount+": "paramount-plus",
    "Hulu": "espn",
    "Disney+": "espn",
    "Apple TV+": "nbc",
    # Regional sports networks
    "MASN": "cbs",
    "MASN2": "cbs",
    "MAS+": "cbs",
    "SportsNet": "nbc",
    "FanDuel SN": "fox",
    "FanDuel SN DET": "fox",
    "FanDuel SN FL": "fox",
    "SportsNet PIT": "nbc",
    "Padres.TV": "espn",
    "CLEGuardians.TV": "espn"
}

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BroadcastLogoAnalyzer:
    """Analyzes broadcast channel logos for completeness and quality."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.broadcast_logos_dir = project_root / "assets" / "broadcast_logos"
        self.results = {
            'total_mappings': len(BROADCAST_LOGO_MAP),
            'existing_logos': [],
            'missing_logos': [],
            'problematic_logos': [],
            'recommendations': []
        }
    
    def analyze_all_logos(self) -> Dict:
        """Perform comprehensive analysis of all broadcast logos."""
        logger.info("Starting broadcast logo analysis...")
        
        # Get all logo files that exist
        existing_files = self._get_existing_logo_files()
        logger.info(f"Found {len(existing_files)} existing logo files")
        
        # Check each mapping in BROADCAST_LOGO_MAP
        for broadcast_name, logo_filename in BROADCAST_LOGO_MAP.items():
            self._analyze_logo_mapping(broadcast_name, logo_filename, existing_files)
        
        # Check for orphaned logo files (files that exist but aren't mapped)
        self._check_orphaned_logos(existing_files)
        
        # Generate recommendations
        self._generate_recommendations()
        
        return self.results
    
    def _get_existing_logo_files(self) -> Set[str]:
        """Get all existing logo files in the broadcast_logos directory."""
        existing_files = set()
        
        if not self.broadcast_logos_dir.exists():
            logger.warning(f"Broadcast logos directory does not exist: {self.broadcast_logos_dir}")
            return existing_files
        
        for file_path in self.broadcast_logos_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                existing_files.add(file_path.stem)  # filename without extension
        
        return existing_files
    
    def _analyze_logo_mapping(self, broadcast_name: str, logo_filename: str, existing_files: Set[str]):
        """Analyze a single logo mapping."""
        logo_path = self.broadcast_logos_dir / f"{logo_filename}.png"
        
        if logo_filename not in existing_files:
            self.results['missing_logos'].append({
                'broadcast_name': broadcast_name,
                'logo_filename': logo_filename,
                'expected_path': str(logo_path)
            })
            logger.warning(f"Missing logo: {broadcast_name} -> {logo_filename}.png")
            return
        
        # Logo exists, analyze its quality
        try:
            analysis = self._analyze_logo_quality(logo_path, broadcast_name, logo_filename)
            if analysis['is_problematic']:
                self.results['problematic_logos'].append(analysis)
            else:
                self.results['existing_logos'].append(analysis)
        except Exception as e:
            logger.error(f"Error analyzing logo {logo_path}: {e}")
            self.results['problematic_logos'].append({
                'broadcast_name': broadcast_name,
                'logo_filename': logo_filename,
                'path': str(logo_path),
                'error': str(e),
                'is_problematic': True
            })
    
    def _analyze_logo_quality(self, logo_path: Path, broadcast_name: str, logo_filename: str) -> Dict:
        """Analyze the quality of a logo file."""
        try:
            with Image.open(logo_path) as img:
                # Basic image info
                width, height = img.size
                mode = img.mode
                
                # Convert to RGBA for analysis if needed
                if mode != 'RGBA':
                    img_rgba = img.convert('RGBA')
                else:
                    img_rgba = img
                
                # Analyze for potential white box issues
                analysis = {
                    'broadcast_name': broadcast_name,
                    'logo_filename': logo_filename,
                    'path': str(logo_path),
                    'dimensions': (width, height),
                    'mode': mode,
                    'file_size': logo_path.stat().st_size,
                    'is_problematic': False,
                    'issues': [],
                    'recommendations': []
                }
                
                # Check for white box issues
                self._check_white_box_issues(img_rgba, analysis)
                
                # Check dimensions
                self._check_dimensions(width, height, analysis)
                
                # Check transparency
                self._check_transparency(img_rgba, analysis)
                
                # Check if image is mostly empty/white
                self._check_content_density(img_rgba, analysis)
                
                return analysis
                
        except Exception as e:
            raise Exception(f"Failed to analyze image: {e}")
    
    def _check_white_box_issues(self, img: Image.Image, analysis: Dict):
        """Check for potential white box issues."""
        # Get image statistics
        stat = ImageStat.Stat(img)
        
        # Check if image is mostly white
        if img.mode == 'RGBA':
            # For RGBA, check RGB channels
            r_mean, g_mean, b_mean = stat.mean[:3]
            if r_mean > 240 and g_mean > 240 and b_mean > 240:
                analysis['issues'].append("Image appears to be mostly white")
                analysis['is_problematic'] = True
        
        # Check for completely transparent images
        if img.mode == 'RGBA':
            alpha_channel = img.split()[3]
            alpha_stat = ImageStat.Stat(alpha_channel)
            if alpha_stat.mean[0] < 10:  # Very low alpha
                analysis['issues'].append("Image is mostly transparent")
                analysis['is_problematic'] = True
    
    def _check_dimensions(self, width: int, height: int, analysis: Dict):
        """Check if dimensions are reasonable."""
        if width < 16 or height < 16:
            analysis['issues'].append(f"Very small dimensions: {width}x{height}")
            analysis['is_problematic'] = True
            analysis['recommendations'].append("Consider using a higher resolution logo")
        
        if width > 512 or height > 512:
            analysis['issues'].append(f"Very large dimensions: {width}x{height}")
            analysis['recommendations'].append("Consider optimizing logo size for better performance")
        
        # Check aspect ratio
        aspect_ratio = width / height
        if aspect_ratio > 4 or aspect_ratio < 0.25:
            analysis['issues'].append(f"Extreme aspect ratio: {aspect_ratio:.2f}")
            analysis['recommendations'].append("Consider using a more square logo")
    
    def _check_transparency(self, img: Image.Image, analysis: Dict):
        """Check transparency handling."""
        if img.mode == 'RGBA':
            # Check if there's any transparency
            alpha_channel = img.split()[3]
            alpha_data = list(alpha_channel.getdata())
            min_alpha = min(alpha_data)
            max_alpha = max(alpha_data)
            
            if min_alpha < 255:
                analysis['recommendations'].append("Logo has transparency - ensure proper background handling")
            
            if max_alpha < 128:
                analysis['issues'].append("Logo is very transparent")
                analysis['is_problematic'] = True
    
    def _check_content_density(self, img: Image.Image, analysis: Dict):
        """Check if the image has sufficient content."""
        # Convert to grayscale for analysis
        gray = img.convert('L')
        
        # Count non-white pixels (assuming white background)
        pixels = list(gray.getdata())
        non_white_pixels = sum(1 for p in pixels if p < 240)
        total_pixels = len(pixels)
        content_ratio = non_white_pixels / total_pixels
        
        if content_ratio < 0.05:  # Less than 5% content
            analysis['issues'].append(f"Very low content density: {content_ratio:.1%}")
            analysis['is_problematic'] = True
            analysis['recommendations'].append("Logo may appear as a white box - check content")
    
    def _check_orphaned_logos(self, existing_files: Set[str]):
        """Check for logo files that exist but aren't mapped."""
        mapped_filenames = set(BROADCAST_LOGO_MAP.values())
        orphaned_files = existing_files - mapped_filenames
        
        if orphaned_files:
            self.results['orphaned_logos'] = list(orphaned_files)
            logger.info(f"Found {len(orphaned_files)} orphaned logo files: {orphaned_files}")
    
    def _generate_recommendations(self):
        """Generate overall recommendations."""
        recommendations = []
        
        if self.results['missing_logos']:
            recommendations.append(f"Add {len(self.results['missing_logos'])} missing logo files")
        
        if self.results['problematic_logos']:
            recommendations.append(f"Fix {len(self.results['problematic_logos'])} problematic logos")
        
        if 'orphaned_logos' in self.results:
            recommendations.append(f"Consider mapping {len(self.results['orphaned_logos'])} orphaned logo files")
        
        # General recommendations
        recommendations.extend([
            "Ensure all logos are PNG format with transparency support",
            "Use consistent dimensions (preferably 64x64 or 128x128 pixels)",
            "Test logos on the actual LED matrix display",
            "Consider creating fallback logos for missing channels"
        ])
        
        self.results['recommendations'] = recommendations
    
    def print_report(self):
        """Print a detailed analysis report."""
        print("\n" + "="*80)
        print("BROADCAST LOGO ANALYSIS REPORT")
        print("="*80)
        
        print(f"\nSUMMARY:")
        print(f"  Total broadcast mappings: {self.results['total_mappings']}")
        print(f"  Existing logos: {len(self.results['existing_logos'])}")
        print(f"  Missing logos: {len(self.results['missing_logos'])}")
        print(f"  Problematic logos: {len(self.results['problematic_logos'])}")
        
        if 'orphaned_logos' in self.results:
            print(f"  Orphaned logos: {len(self.results['orphaned_logos'])}")
        
        # Missing logos
        if self.results['missing_logos']:
            print(f"\nMISSING LOGOS ({len(self.results['missing_logos'])}):")
            print("-" * 50)
            for missing in self.results['missing_logos']:
                print(f"  {missing['broadcast_name']} -> {missing['logo_filename']}.png")
                print(f"    Expected: {missing['expected_path']}")
        
        # Problematic logos
        if self.results['problematic_logos']:
            print(f"\nPROBLEMATIC LOGOS ({len(self.results['problematic_logos'])}):")
            print("-" * 50)
            for problematic in self.results['problematic_logos']:
                print(f"  {problematic['broadcast_name']} -> {problematic['logo_filename']}")
                if 'error' in problematic:
                    print(f"    Error: {problematic['error']}")
                if 'issues' in problematic:
                    for issue in problematic['issues']:
                        print(f"    Issue: {issue}")
                if 'recommendations' in problematic:
                    for rec in problematic['recommendations']:
                        print(f"    Recommendation: {rec}")
        
        # Orphaned logos
        if 'orphaned_logos' in self.results and self.results['orphaned_logos']:
            print(f"\nORPHANED LOGOS ({len(self.results['orphaned_logos'])}):")
            print("-" * 50)
            for orphaned in self.results['orphaned_logos']:
                print(f"  {orphaned}.png (not mapped in BROADCAST_LOGO_MAP)")
        
        # Recommendations
        if self.results['recommendations']:
            print(f"\nRECOMMENDATIONS:")
            print("-" * 50)
            for i, rec in enumerate(self.results['recommendations'], 1):
                print(f"  {i}. {rec}")
        
        print("\n" + "="*80)
    
    def save_report(self, output_file: str = "broadcast_logo_analysis.json"):
        """Save the analysis results to a JSON file."""
        output_path = self.project_root / "test" / output_file
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"Analysis report saved to: {output_path}")

def main():
    """Main function to run the broadcast logo analysis."""
    print("Broadcast Logo Analyzer")
    print("=" * 50)
    
    # Check if we're in the right directory structure
    if not (project_root / "assets" / "broadcast_logos").exists():
        print("ERROR: This script must be run from the LEDMatrix project root directory")
        print(f"Expected directory structure: {project_root}/assets/broadcast_logos/")
        print("Please run this script on the Raspberry Pi where the LEDMatrix project is located.")
        print("\nTo test the script logic locally, you can copy some logo files to the expected location.")
        return 1
    
    # Initialize analyzer
    analyzer = BroadcastLogoAnalyzer(project_root)
    
    # Run analysis
    try:
        results = analyzer.analyze_all_logos()
        
        # Print report
        analyzer.print_report()
        
        # Save report
        analyzer.save_report()
        
        # Return exit code based on issues found
        total_issues = len(results['missing_logos']) + len(results['problematic_logos'])
        if total_issues > 0:
            print(f"\n⚠️  Found {total_issues} issues that need attention!")
            return 1
        else:
            print(f"\n✅ All broadcast logos are in good condition!")
            return 0
            
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
