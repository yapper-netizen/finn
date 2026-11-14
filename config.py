"""Central settings for FINN: tickers, thresholds. Secrets live in .env, never here."""

# Portfolio of 18 NSE stocks (no ITC: ENAM avoids intoxication-linked businesses).
PORTFOLIO: list[str] = [
    "RELIANCE", "HDFCBANK", "TCS", "INFY", "PIDILITIND", "LT",
    "BHARTIARTL", "SUNPHARMA", "ASIANPAINT", "TITAN", "DMART", "TRENT",
    "POLYCAB", "DIXON", "PERSISTENT", "VIJAYA", "DEEPAKNTR", "IRCTC",
]

# Extra research-only stocks (ASTRAL is outside the portfolio).
RESEARCH_EXTRA: list[str] = ["ASTRAL"]

# yfinance suffixes: ".NS" = NSE, ".BO" = BSE. NSE is primary, BSE the fallback.
PRIMARY_SUFFIX = ".NS"
FALLBACK_SUFFIX = ".BO"

# Price history window (calendar days) fetched from yfinance.
HISTORY_DAYS = 60

# Alert thresholds (user-configurable later via Settings screen).
VOLUME_MULTIPLE = 2.0      # alert if volume > 2x the 20-day average
VOLUME_AVG_WINDOW = 20     # trading days used for the average
PRICE_MOVE_PCT = 5.0       # alert if daily close-to-close move beyond +/-5%

# Network behaviour for every external call.
REQUEST_TIMEOUT_S = 15
RETRIES = 1

# Frozen copy of fetched data, used if a data source is down.
SNAPSHOT_DIR = "snapshot"

# Corporate filings (D-064): NSE announcements API (BSE's API blocks scripts, D-063).
NSE_ANNOUNCEMENTS_URL = "https://www.nseindia.com/api/corporate-announcements"
NSE_REFERER = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
FILINGS_DAYS = 7                       # default look-back window (days)
EQUITY_LIST_CSV = "data/equity_list.csv"  # NSE's list of listed symbols, refreshed by hand

# AI models (D-009, D-060: free tier only). Swap a model with a one-line change here.
CHEAP_MODEL = "gemini-3.5-flash-lite"   # bulk: classification leftovers, PDF numbers, quotes
STRONG_MODEL = "gemini-3.5-flash"       # reasoning (thinks before answering): promise verdicts, bull/bear
FALLBACK_MODEL = "gemini-3.1-flash-lite"  # used if the strong model is capped or fails (D-061)
LLM_TIMEOUT_S = 60
