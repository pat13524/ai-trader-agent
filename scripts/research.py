import os
import requests
import json
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

ALPACA_KEY = os.getenv("APCA_API_KEY_ID")
ALPACA_SECRET = os.getenv("APCA_API_SECRET_KEY")
BASE_URL = os.getenv("APCA_BASE_URL")

def get_bars(symbol, timeframe="1Day", limit=60):
    """Fetch historical price bars for a symbol."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }
    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
    # Use 90 calendar days to ensure ~60 trading days across weekends/holidays
    start = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    params = {
        "timeframe": timeframe,
        "limit": limit,
        "start": start,
        "adjustment": "raw"
    }
    response = requests.get(url, headers=headers, params=params)
    return response.json()

def get_account():
    """Get current portfolio status."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }
    url = f"{BASE_URL}/v2/account"
    response = requests.get(url, headers=headers)
    return response.json()

def get_positions():
    """Get all open positions."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }
    url = f"{BASE_URL}/v2/positions"
    response = requests.get(url, headers=headers)
    return response.json()

def get_news(symbol):
    """Get recent news for a symbol."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }
    url = f"https://data.alpaca.markets/v1beta1/news"
    params = {
        "symbols": symbol,
        "limit": 5,
        "sort": "desc"
    }
    response = requests.get(url, headers=headers, params=params)
    return response.json()

def get_bulk_bars(symbols, timeframe="1Day", limit=60):
    """Fetch bars for multiple symbols in one API call, handling pagination."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }
    start = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    url = "https://data.alpaca.markets/v2/stocks/bars"
    
    all_bars = {}
    next_page_token = None

    while True:
        params = {
            "symbols": ",".join(symbols),
            "timeframe": timeframe,
            "limit": limit,
            "start": start,
            "adjustment": "raw"
        }
        if next_page_token:
            params["page_token"] = next_page_token

        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        for sym, bars in data.get("bars", {}).items():
            if sym not in all_bars:
                all_bars[sym] = []
            all_bars[sym].extend(bars)

        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break

    return {"bars": all_bars}


def get_latest_quotes(symbols):
    """Get real-time latest quotes for a list of symbols."""
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }
    url = "https://data.alpaca.markets/v2/stocks/quotes/latest"
    params = {"symbols": ",".join(symbols)}
    response = requests.get(url, headers=headers, params=params)
    return response.json()



if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "account"
    symbol = sys.argv[2] if len(sys.argv) > 2 else None

    if action == "bars" and symbol:
        print(json.dumps(get_bars(symbol)))
    elif action == "bulk":
        with open("watchlist.json") as f:
            wl = json.load(f)
        symbols = [s["symbol"] for s in wl["watchlist"]]
        print(json.dumps(get_bulk_bars(symbols)))
    elif action == "quotes":
        with open("watchlist.json") as f:
            wl = json.load(f)
        symbols = [s["symbol"] for s in wl["watchlist"]]
        print(json.dumps(get_latest_quotes(symbols)))
    elif action == "news" and symbol:
        print(json.dumps(get_news(symbol)))
    elif action == "positions":
        print(json.dumps(get_positions()))
    else:
        print(json.dumps(get_account()))