"""
Simple stock and crypto price fetcher.

Primary source is Yahoo Finance's unofficial chart endpoint (free, no key,
already the long-standing default here) - but it's undocumented and Yahoo
has throttled/changed it before with no notice. Both fetchers now fall back
to a second free, keyless source if Yahoo fails, so a Yahoo outage doesn't
just silently blank the stocks/crypto mode.
"""

import re
import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Common ticker -> CoinGecko coin id. CoinGecko's /simple/price endpoint
# needs its own id scheme, not raw tickers. Not exhaustive - covers what a
# hobbyist ticker list is likely to contain; anything unmapped just logs and
# returns None like any other fetch failure.
_COINGECKO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "DOGE": "dogecoin", "LTC": "litecoin",
    "XRP": "ripple", "ADA": "cardano", "SOL": "solana", "DOT": "polkadot",
    "MATIC": "matic-network", "BNB": "binancecoin", "USDT": "tether",
    "USDC": "usd-coin", "AVAX": "avalanche-2", "SHIB": "shiba-inu",
    "LINK": "chainlink", "ATOM": "cosmos", "XLM": "stellar", "TRX": "tron",
    "UNI": "uniswap", "ETC": "ethereum-classic", "XMR": "monero",
    "BCH": "bitcoin-cash", "ALGO": "algorand", "FIL": "filecoin",
}


def _fetch_from_yahoo(ticker: str) -> Optional[Dict[str, Any]]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    response = requests.get(url, headers=headers, timeout=5)
    response.raise_for_status()
    data = response.json()

    result = data.get("chart", {}).get("result", [{}])[0]
    meta = result.get("meta", {})
    current_price = meta.get("regularMarketPrice")
    previous_close = meta.get("previousClose")
    if current_price is None or previous_close is None:
        raise ValueError(f"Yahoo response missing price data for {ticker}")

    change = current_price - previous_close
    change_percent = (change / previous_close * 100) if previous_close else 0
    return {
        "ticker": ticker.upper(),
        "price": round(current_price, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
        "is_crypto": False,
    }


def _load_alphavantage_key() -> str:
    """Optional fallback key from config/config_secrets.json - stocks.
    alphavantage_api_key. Absent by default; the fallback simply doesn't
    activate without one (get a free key at alphavantage.co/support/#api-key,
    no card required)."""
    import json
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    secrets_path = os.path.join(script_dir, "config", "config_secrets.json")
    try:
        with open(secrets_path) as f:
            secrets = json.load(f)
        return secrets.get("stocks", {}).get("alphavantage_api_key", "")
    except Exception:
        return ""


def _fetch_stock_from_alphavantage(ticker: str) -> Optional[Dict[str, Any]]:
    """Fallback for equities when Yahoo fails. Requires a free API key -
    see _load_alphavantage_key(). Note: free tier is rate-limited (25
    requests/day as of writing), so this is a break-glass fallback, not a
    replacement for Yahoo as the everyday source."""
    api_key = _load_alphavantage_key()
    if not api_key:
        raise ValueError("No Alpha Vantage API key configured - fallback unavailable")
    response = requests.get(
        "https://www.alphavantage.co/query",
        params={"function": "GLOBAL_QUOTE", "symbol": ticker, "apikey": api_key},
        timeout=5,
    )
    response.raise_for_status()
    quote = response.json().get("Global Quote", {})
    price = quote.get("05. price")
    if not price:
        raise ValueError(f"Alpha Vantage returned no quote for {ticker} (rate-limited or invalid symbol)")
    return {
        "ticker": ticker.upper(),
        "price": round(float(price), 2),
        "change": round(float(quote.get("09. change", 0)), 2),
        "change_percent": round(float(quote.get("10. change percent", "0%").rstrip("%")), 2),
        "is_crypto": False,
    }


def _fetch_crypto_from_coingecko(ticker: str) -> Optional[Dict[str, Any]]:
    bare = re.sub(r"-USD$", "", ticker.upper())
    coin_id = _COINGECKO_IDS.get(bare)
    if not coin_id:
        raise ValueError(f"No CoinGecko id mapping for {bare!r}")
    response = requests.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true"},
        timeout=5,
    )
    response.raise_for_status()
    data = response.json().get(coin_id)
    if not data or "usd" not in data:
        raise ValueError(f"CoinGecko returned no price for {coin_id}")
    price = data["usd"]
    change_percent = data.get("usd_24h_change", 0) or 0
    change = price * change_percent / 100
    return {
        "ticker": f"{bare}-USD",
        "price": round(price, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
        "is_crypto": True,
    }


def fetch_stock_price(ticker: str) -> Optional[Dict[str, Any]]:
    """Fetch stock price - Yahoo Finance first, Stooq as a fallback."""
    try:
        return _fetch_from_yahoo(ticker)
    except Exception as e:
        logger.warning(f"Yahoo Finance failed for {ticker} ({e}), trying Alpha Vantage fallback")
    try:
        return _fetch_stock_from_alphavantage(ticker)
    except Exception as e:
        logger.error(f"Alpha Vantage fallback also failed for {ticker}: {e}")
        return None


def fetch_crypto_price(ticker: str) -> Optional[Dict[str, Any]]:
    """Fetch cryptocurrency price - Yahoo Finance first, CoinGecko as a fallback."""
    crypto_ticker = f"{ticker}-USD" if not ticker.endswith("-USD") else ticker
    try:
        result = _fetch_from_yahoo(crypto_ticker)
        if result:
            result["is_crypto"] = True
        return result
    except Exception as e:
        logger.warning(f"Yahoo Finance failed for {crypto_ticker} ({e}), trying CoinGecko fallback")
    try:
        return _fetch_crypto_from_coingecko(ticker)
    except Exception as e:
        logger.error(f"CoinGecko fallback also failed for {ticker}: {e}")
        return None
