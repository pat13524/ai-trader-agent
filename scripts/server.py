import os
import json
import glob
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request
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

WATCHLIST_PATH  = os.path.join(os.path.dirname(__file__), "..", "watchlist.json")
JOURNAL_DIR     = os.path.join(os.path.dirname(__file__), "..", "journal")
HEARTBEAT_PATH  = os.path.join(os.path.dirname(__file__), "..", "heartbeat.json")

def load_watchlist():
    with open(WATCHLIST_PATH) as f:
        data = json.load(f)
    return data["watchlist"]

def alpaca_get(url, params=None):
    r = requests.get(url, headers=DATA_HEADERS, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

# ── MARKET STATUS ──
@app.route("/api/market-status")
def market_status():
    return jsonify(alpaca_get(f"{BASE_URL}/v2/clock"))

# ── ACCOUNT ──
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

# ── POSITIONS ──
@app.route("/api/positions")
def positions():
    return jsonify(alpaca_get(f"{BASE_URL}/v2/positions"))

# ── PORTFOLIO HISTORY (for P&L chart timeframes) ──
@app.route("/api/portfolio-history")
def portfolio_history():
    period    = request.args.get("period", "1D")
    # Auto-select resolution based on period
    timeframe_map = {
        "1D":  "5Min",
        "1W":  "1H",
        "1M":  "1D",
        "3M":  "1D",
        "6M":  "1D",
        "1A":  "1D",
        "3A":  "1D",
    }
    timeframe = timeframe_map.get(period, "1D")
    data = alpaca_get(
        f"{BASE_URL}/v2/account/portfolio/history",
        params={"period": period, "timeframe": timeframe, "extended_hours": "true"}
    )
    timestamps = data.get("timestamp", [])
    equity     = data.get("equity", [])
    # Pair them up, filter nulls
    points = [
        {"t": ts, "v": eq}
        for ts, eq in zip(timestamps, equity)
        if eq is not None and eq > 0
    ]
    return jsonify({"points": points, "timeframe": timeframe, "period": period})

# ── DAILY BARS (with pagination) ──
@app.route("/api/bars")
def bars():
    symbols  = [s["symbol"] for s in load_watchlist()]
    syms_str = ",".join(symbols)
    start    = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")

    all_bars = {}
    next_page_token = None

    while True:
        params = {
            "symbols":    syms_str,
            "timeframe":  "1Day",
            "limit":      60,
            "start":      start,
            "adjustment": "raw"
        }
        if next_page_token:
            params["page_token"] = next_page_token

        data = alpaca_get("https://data.alpaca.markets/v2/stocks/bars", params=params)

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
            "open":       last["o"],
            "high":       last["h"],
            "low":        last["l"],
            "close":      last["c"],
            "volume":     last["v"],
            "prev_close": prev,
            "change_pct": change_pct,
            "ma20":       ma20,
            "ma50":       ma50,
            "closes":     closes[-30:],
        }
    return jsonify(result)

# ── INTRADAY BARS (for 1-day sparklines) ──
@app.route("/api/intraday-bars")
def intraday_bars():
    symbols  = [s["symbol"] for s in load_watchlist()]
    syms_str = ",".join(symbols)
    # Get today's bars from market open
    now   = datetime.now(timezone.utc)
    start = now.strftime("%Y-%m-%dT09:30:00-04:00")

    all_bars = {}
    next_page_token = None

    while True:
        params = {
            "symbols":   syms_str,
            "timeframe": "15Min",
            "start":     start,
            "limit":     50,
        }
        if next_page_token:
            params["page_token"] = next_page_token

        data = alpaca_get("https://data.alpaca.markets/v2/stocks/bars", params=params)

        for sym, bar_list in data.get("bars", {}).items():
            if sym not in all_bars:
                all_bars[sym] = []
            all_bars[sym].extend(bar_list)

        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break

    result = {}
    for sym, bar_list in all_bars.items():
        if bar_list:
            result[sym] = [b["c"] for b in bar_list]

    return jsonify(result)

# ── WATCHLIST ──
@app.route("/api/watchlist")
def watchlist():
    return jsonify(load_watchlist())

# ── JOURNAL ──
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

# ── ORDERS ──
@app.route("/api/orders")
def orders():
    data = alpaca_get(f"{BASE_URL}/v2/orders",
                      params={"status": "all", "limit": 20, "direction": "desc"})
    return jsonify(data)

# ── ROUTINE STATUS (reads heartbeat.json written by agent) ──
@app.route("/api/routine-status")
def routine_status():
    try:
        with open(HEARTBEAT_PATH) as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify({
            "morning_research": None,
            "trading_session":  None,
            "end_of_day":       None,
        })

if __name__ == "__main__":
    print("\n  Trading Agent Server → http://localhost:5000")
    print("  Open dashboard.html in your browser\n")
    app.run(debug=False, port=5000)
