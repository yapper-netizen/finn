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
PRICE_MOVE_PCT = 3.0       # alert if daily close-to-close move beyond +/-3% (D-007, D-077)

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

# Filing PDFs and results cards (BE-4, EN-5, D-077).
CACHE_DIR = ".cache"                   # local, git-ignored: page text and computed cards
PDF_ALLOWED_HOSTS = {"nsearchives.nseindia.in", "archives.nseindia.com", "www.bseindia.com"}
PDF_TIMEOUT_S = 60
PDF_MAX_BYTES = 30 * 2**20             # 30 MB; results PDFs seen so far are 1-10 MB
LLM_CACHE_DB = "cache.db"              # SQLite answer cache: each document is read by AI once (D-026)
CARDS_DIR = "snapshot/cards"           # precomputed cards, committed so the demo works offline
CARD_ENGINE_VERSION = 1                # bump to invalidate cached cards after an extractor change
MAX_STATEMENT_CHARS = 14000            # text sent to the model (one statement page, maybe two)

# Background card building (D-078): when the feed finds a new results filing, build its card
# once, one at a time, paced for the free Gemini tier. Off if GEMINI_API_KEY is not set.
CARD_PREBUILD = True
CARD_PREBUILD_PACE_S = 10              # pause between builds (free tier allows a few calls a minute)
CARD_PREBUILD_MAX_TRIES = 2            # per filing per server run; a failed build is retried once

# Research / promise tracker (block 8, D-079..D-086).
RESEARCH_SET: list[str] = ["POLYCAB", "PERSISTENT", "ASTRAL"]   # precomputed (D-051)
RESEARCH_QUARTERS = 5                  # transcripts kept: the latest + 4 whose promises can be judged
RESEARCH_LOOKBACK_DAYS = 560           # ~18 months of filings covers 5 quarters plus the year-ago data
RESEARCH_DIR = "snapshot/research"     # precomputed research, committed
TRANSCRIPT_MAX_CHARS = 26000           # keyword-picked pages sent per transcript (D-021 = A)
QUOTE_MATCH_MIN = 0.90                 # fuzzy match a quote must reach to count as verified (D-041)
RESEARCH_PACE_S = 6                    # pause between AI calls in a research run (free tier)
# Promise extraction model (D-081): the cheap model gave different promise lists run to run on the
# same transcript (dropped, merged or mis-dated commitments); the strong model is steadier. The
# cheap model still reads every results filing (the bulk of the pages).
RESEARCH_EXTRACT_STRONG = True
LLM_BACKOFF_S = (4, 12)                # waits between tries when a model is overloaded (503) (D-088)
