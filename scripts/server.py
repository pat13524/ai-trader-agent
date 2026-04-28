import os
import json
import glob
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

ALPACA_KEY    = os.getenv("APCA_API_KEY_ID")
ALPACA_SECRET = os.getenv("APCA_API_SECRET_KEY")
BASE_URL      = os.getenv("APCA_BASE_URL")

DATA_HEADERS = {
    "APCA-API-KEY-ID":     ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
}

WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "..", "watchlist.json")
JOURNAL_DIR    = os.path.join(os.path.dirname(__file__), "..", "journal")

def load_watchlist():
    with open(WATCHLIST_PATH) as f:
        data = json.load(f)
    return data["watchlist"]

def alpaca_get(url, params=None):
    r = requests.get(url, headers=DATA_HEADERS, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

@app.route("/api/market-status")
def market_status():
    data = alpaca_get(f"{BASE_URL}/v2/clock")
    return jsonify(data)

@app.route("/api/account")
def account():
    data = alpaca_get(f"{BASE_URL}/v2/account")
    return jsonify({
        "portfolio_value": data.get("portfolio_value"),
        "cash":            data.get("cash"),
        "buying_power":    data.get("buying_power"),
        "equity":          data.get("equity"),
        "last_equity":     data.get("last_equity"),
        "daytrade_count":  data.get("daytrade_count"),
    })

@app.route("/api/positions")
def positions():
    data = alpaca_get(f"{BASE_URL}/v2/positions")
    return jsonify(data)

@app.route("/api/bars")
def bars():
    symbols  = [s["symbol"] for s in load_watchlist()]
    syms_str = ",".join(symbols)
    start    = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")

    all_bars = {}
    next_page_token = None

    while True:
        params = {
            "symbols": syms_str, "timeframe": "1Day", "limit": 60,
            "start": start, "adjustment": "raw"
        }
        if next_page_token:
            params["page_token"] = next_page_token

        data = alpaca_get(
            "https://data.alpaca.markets/v2/stocks/bars",
            params=params
        )

        for sym, bar_list in data.get("bars", {}).items():
            if sym not in all_bars:
                all_bars[sym] = []
            all_bars[sym].extend(bar_list)

        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break

    result = {}
    for sym, bar_list in all_bars.items():
        if not bar_list:
            continue
        closes     = [b["c"] for b in bar_list]
        last       = bar_list[-1]
        prev       = bar_list[-2]["c"] if len(bar_list) >= 2 else last["c"]
        ma20       = round(sum(closes[-20:]) / min(len(closes), 20), 2)
        ma50       = round(sum(closes[-50:]) / min(len(closes), 50), 2)
        change_pct = round((last["c"] - prev) / prev * 100, 2) if prev else 0
        result[sym] = {
            "open": last["o"], "high": last["h"],
            "low":  last["l"], "close": last["c"],
            "volume": last["v"], "prev_close": prev,
            "change_pct": change_pct, "ma20": ma20, "ma50": ma50,
        }
    return jsonify(result)

@app.route("/api/watchlist")
def watchlist():
    return jsonify(load_watchlist())

@app.route("/api/journal")
def journal():
    files = sorted(glob.glob(os.path.join(JOURNAL_DIR, "*.md")), reverse=True)
    entries = []
    for f in files[:10]:
        date = os.path.basename(f).replace(".md", "")
        with open(f, encoding="utf-8") as fh:
            content = fh.read()
        entries.append({"date": date, "content": content})
    return jsonify(entries)

@app.route("/api/orders")
def orders():
    data = alpaca_get(f"{BASE_URL}/v2/orders",
                      params={"status": "all", "limit": 20, "direction": "desc"})
    return jsonify(data)

if __name__ == "__main__":
    print("\n  Trading Agent Server → http://localhost:5000")
    print("  Open dashboard.html in your browser\n")
    app.run(debug=False, port=5000)
