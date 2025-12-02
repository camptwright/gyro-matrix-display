"""
Simple stock and crypto price fetcher
Uses free APIs like Alpha Vantage or Yahoo Finance
"""

import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def fetch_stock_price(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Fetch stock price using Yahoo Finance API (free, no key)
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
        
    Returns:
        Dictionary with price data or None
    """
    try:
        # Yahoo Finance API (free, no key required)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        result = data.get('chart', {}).get('result', [{}])[0]
        meta = result.get('meta', {})
        
        current_price = meta.get('regularMarketPrice', 0)
        previous_close = meta.get('previousClose', 0)
        change = current_price - previous_close
        change_percent = (change / previous_close * 100) if previous_close else 0
        
        return {
            'ticker': ticker.upper(),
            'price': round(current_price, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'is_crypto': False
        }
        
    except Exception as e:
        logger.error(f"Error fetching stock price for {ticker}: {e}")
        return None


def fetch_crypto_price(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Fetch cryptocurrency price
    
    Args:
        ticker: Crypto ticker (e.g., 'BTC-USD')
        
    Returns:
        Dictionary with price data or None
    """
    try:
        # Use same Yahoo Finance API with crypto ticker
        crypto_ticker = f"{ticker}-USD" if not ticker.endswith('-USD') else ticker
        return fetch_stock_price(crypto_ticker)
        
    except Exception as e:
        logger.error(f"Error fetching crypto price for {ticker}: {e}")
        return None

