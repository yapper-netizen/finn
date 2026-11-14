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

# Filing categories -> tier (D-015, D-065). High = card + detail; Medium = one-line summary;
# Low = collapsed into "Routine (N)". Test: would a long-term fund manager change a view?
CATEGORY_TIER: dict[str, str] = {
    "results": "High", "management_change": "High", "m_and_a": "High",
    "litigation": "High", "credit_rating": "High", "pledging": "High",
    "fund_raise": "Medium", "capex": "Medium", "dividend": "Medium", "bonus_split": "Medium",
    "insider_trading": "Medium", "order_win": "Medium",
    "board_outcome": "Medium",  # board outcome with no detail in the title: never hide it (D-065)
    "earnings_call": "Low", "investor_meetings": "Low", "agm_egm": "Low",
    "postal_ballot": "Low", "press_release": "Low", "unclassified": "Low",
}
TIER_ORDER: dict[str, int] = {"High": 0, "Medium": 1, "Low": 2}
# Per-category toggles (D-047): every category is on by default; the Settings screen overrides.
DEFAULT_TOGGLES: dict[str, bool] = {c: True for c in CATEGORY_TIER}

# Digest windows (hours) and the default shown on Today (D-046).
WINDOWS_HOURS: dict[str, int] = {"24h": 24, "3d": 72, "7d": 168}
DEFAULT_WINDOW = "24h"
IST_OFFSET_HOURS = 5.5  # filing timestamps are India time; servers (Render) run UTC

# Live data cache and API limits (D-067, D-031).
CACHE_TTL_S = 900          # data older than this is refreshed in the background (15 min)
FEED_WORKERS = 4           # parallel fetches; low on purpose, the exchange is not ours
WARM_WAIT_S = 25           # how long a first request waits for the initial load before using snapshots
PRICE_PCT_RANGE = (0.1, 50.0)   # allowed values for the price-move threshold (percent)
VOLUME_X_RANGE = (1.0, 20.0)    # allowed values for the volume multiple

# AI models (D-009, D-060: free tier only). Swap a model with a one-line change here.
CHEAP_MODEL = "gemini-3.5-flash-lite"   # bulk: classification leftovers, PDF numbers, quotes
STRONG_MODEL = "gemini-3.5-flash"       # reasoning (thinks before answering): promise verdicts, bull/bear
FALLBACK_MODEL = "gemini-3.1-flash-lite"  # used if the strong model is capped or fails (D-061)
LLM_TIMEOUT_S = 60
