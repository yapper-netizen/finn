"""FINN web API (FastAPI): serves the app page and the Today data. Run: py -m uvicorn api:app

Every error comes back as JSON {error, fallback_used}, never a crash page (API-7).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

import config
from data import filings as filings_mod
from engine import cards
from engine.brief import brief_me
from data.symbols import resolve as resolve_symbol, search as search_symbols
from data.clock import ist_now
from data.events import EventsCache
from engine import askfinn, copilot, financials
from engine.pulse import build_pulse
from engine import profile as profile_mod
from engine.research import ENGINE_VERSION
from engine.research_jobs import ResearchJobs, list_stored, stored as stored_research
from engine.feed import FeedCache, company_name
from engine.today import build_today

WEB_INDEX = Path(__file__).parent / "web" / "index.html"
card_prebuilder = cards.CardPrebuilder()
research_jobs = ResearchJobs()
events_cache = EventsCache()
feed_cache = FeedCache(on_loaded=card_prebuilder.enqueue_from)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start loading live data as soon as the server boots, so the first visit is fast."""
    feed_cache.refresh_async()
    yield


app = FastAPI(title="FINN", lifespan=lifespan)


def error_response(message: str, status: int = 400, fallback_used: bool = False) -> JSONResponse:
    """The one error shape every endpoint uses."""
    return JSONResponse({"error": message, "fallback_used": fallback_used}, status_code=status)


@app.exception_handler(RequestValidationError)
async def _bad_input(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:]) or "request"
    return error_response(f"Invalid {field}: {first.get('msg', 'bad value')}.")


@app.exception_handler(Exception)
async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
    print(f"[api] unexpected error on {request.url.path}: {type(exc).__name__}: {exc}")
    return error_response("Something went wrong on the server. Please retry.", 500)


@app.get("/health")
def health() -> dict:
    """Render's health check; also says whether live data has finished its first load."""
    return {"status": "ok", "data_ready": feed_cache.ready, "last_error": feed_cache.last_error,
            "cards_prebuild": card_prebuilder.enabled, "cards_built": len(card_prebuilder.built)}


@app.get("/")
def index():
    """The app page."""
    if not WEB_INDEX.exists():
        return error_response("App page not built yet.", 404)
    return FileResponse(WEB_INDEX)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Browsers ask for this by habit; the page declares its own icon, so answer 'nothing here'."""
    return Response(status_code=204)


@app.get("/api/config")
def api_config() -> dict:
    """Defaults and choices the Settings screen needs (windows, thresholds, categories)."""
    return {
        "windows": list(config.WINDOWS_HOURS),
        "default_window": config.DEFAULT_WINDOW,
        "defaults": {"price": config.PRICE_MOVE_PCT, "volume": config.VOLUME_MULTIPLE},
        "ranges": {"price": config.PRICE_PCT_RANGE, "volume": config.VOLUME_X_RANGE},
        "categories": [{"key": k, "tier": v} for k, v in config.CATEGORY_TIER.items()],
        "portfolio": config.PORTFOLIO,
        "research_set": config.RESEARCH_SET,
    }


@app.get("/api/digest")
def api_digest(
    window: str = config.DEFAULT_WINDOW,
    price: float = Query(config.PRICE_MOVE_PCT, ge=config.PRICE_PCT_RANGE[0], le=config.PRICE_PCT_RANGE[1]),
    volume: float = Query(config.VOLUME_MULTIPLE, ge=config.VOLUME_X_RANGE[0], le=config.VOLUME_X_RANGE[1]),
    off: str = "",
):
    """Today data. `off` = comma-separated categories the user switched off (go to Routine)."""
    if window not in config.WINDOWS_HOURS:
        return error_response(f"Unknown window '{window}'. Use one of: {', '.join(config.WINDOWS_HOURS)}.")
    off_set = {c.strip() for c in off.split(",") if c.strip()}
    unknown = sorted(off_set - set(config.CATEGORY_TIER))
    if unknown:
        return error_response(f"Unknown categories: {', '.join(unknown)}.")
    data = feed_cache.get()
    data = replace(data, filings=cards.apply_promotions(data.filings))   # board outcomes holding results (D-087)
    payload = cards.attach_summaries(build_today(data, window=window, price=price, volume=volume, off=off_set))
    payload["brief"] = brief_me(payload)   # "Brief me": 3 sentences, templates only (D-091)
    return payload


def _find_filing(filing_id: str) -> dict | None:
    """A filing by NSE id: from the live feed, else from the saved snapshots (incl. research stocks)."""
    for f in cards.apply_promotions(feed_cache.get().filings):
        if f.get("id") == filing_id:
            return f
    for ticker in config.PORTFOLIO + config.RESEARCH_EXTRA:
        for f in filings_mod.load_snapshot(ticker) or []:
            if f.get("id") == filing_id:
                return {**f, "ticker": ticker, "company": company_name(ticker)}
    return None


@app.get("/api/card/{filing_id}")
def api_card(filing_id: str):
    """Results card for a filing (API-3). Precomputed cards answer at once; a new filing is read
    by AI the first time it is opened (10-40 s) and kept, so the next open is instant."""
    if not cards.valid_id(filing_id):
        return error_response("Unknown filing id.", 404)
    card = cards.stored_card(filing_id)
    if card:
        return card
    filing = _find_filing(filing_id)
    if filing is None:
        return error_response("Unknown filing id.", 404)
    try:
        card = cards.get_card(filing)
    except ValueError as exc:
        return error_response(str(exc), 400)
    if card.get("retryable"):
        return JSONResponse({**card, "error": card["reason"], "fallback_used": False}, status_code=503)
    return card


@app.get("/api/symbols")
def api_symbols(q: str = Query("", max_length=40)) -> dict:
    """Typeahead for the Research search (D-100): NSE symbols and company names matching `q`.

    Each row says whether the stock is in the portfolio and whether research is ready to open.
    """
    ready = {r["ticker"] for r in list_stored()}
    prefer = frozenset(config.PORTFOLIO) | frozenset(config.RESEARCH_SET) | frozenset(ready)
    return {"query": q, "results": [
        {"ticker": c.symbol, "company": c.name, "portfolio": c.symbol in config.PORTFOLIO, "ready": c.symbol in ready}
        for c in search_symbols(q, prefer=prefer)]}


@app.get("/api/research")
def api_research_list() -> dict:
    """Research this server can open at once: precomputed + earlier live runs (D-100)."""
    return {"engine_version": ENGINE_VERSION, "stored": list_stored()}


@app.get("/api/financials/{ticker}")
def api_financials(ticker: str):
    """Statements, ratios and checks from NSE XBRL (block 10d, D-093). No AI.

    Precomputed stocks answer from `snapshot/financials/`; any other ticker is built on request
    (13 small XBRL files, ~10-30 s) and kept. NSE down → clear JSON error, never a crash.
    """
    try:
        symbol = resolve_symbol(ticker).symbol
    except ValueError as exc:
        return error_response(str(exc), 404)
    try:
        return financials.get(symbol)
    except LookupError as exc:
        return error_response(str(exc), 404)
    except Exception as exc:  # network: say so; nothing cached to fall back on
        return error_response(f"Could not read {symbol}'s results data from NSE right now: {str(exc)[:160]}",
                              503, fallback_used=False)


@app.get("/api/profile/{ticker}")
def api_profile(ticker: str):
    """'What the company does' (D-094): AI-written from the latest transcript, every sentence backed.

    Needs the stock's research (it names the transcripts). One cheap AI call, then kept.
    """
    try:
        symbol = resolve_symbol(ticker).symbol
    except ValueError as exc:
        return error_response(str(exc), 404)
    done = profile_mod.stored(symbol)
    if done:
        return done
    research = stored_research(symbol)
    if not research:
        return error_response(f"Research for {symbol} is not ready yet.", 409)
    try:
        fin = financials.stored(symbol)
        segs = [s["name"] for s in fin["quarters"][0].get("segments", [])] if fin and fin.get("quarters") else []
        result = profile_mod.build(research, segs)
    except LookupError as exc:
        return error_response(str(exc), 404)
    except Exception as exc:  # AI quota or network: the rest of the research still shows
        return error_response(f"Could not write the company profile right now: {str(exc)[:160]}", 503)
    profile_mod.save(result)
    return result


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=copilot.MAX_QUESTION)
    ticker: str | None = Field(default=None, max_length=20)
    filing_id: str | None = Field(default=None, max_length=40)
    portfolio: bool = False


def _ask_company(question: str, symbol: str) -> dict:
    """Copilot for one stock: figures (stored, else built from XBRL) + research if FINN has it."""
    fin = financials.stored(symbol)
    if fin is None:
        try:
            fin = financials.get(symbol)          # any NSE ticker: ~6 s of XBRL, kept
        except Exception:
            fin = None                            # NSE down: the AI path still works from the calls
    return copilot.ask_stock(question, symbol, stored_research(symbol), fin)


@app.post("/api/ask")
def api_ask(body: AskIn):
    """Copilot (D-107): ask about one stock (`ticker`) or one results filing (`filing_id`).

    Rules → Python figures → grounded cheap-model answer with verified citations; refuses otherwise.
    """
    if body.portfolio:
        try:
            data = feed_cache.get()
            pulse = build_pulse(data, events_cache.get(list(config.PORTFOLIO)), ist_now().date())
            return askfinn.ask_portfolio(body.question, data.filings, pulse, ist_now().replace(tzinfo=None),
                                         company_asker=_ask_company)
        except Exception as exc:
            return error_response(f"FINN could not answer right now: {str(exc)[:160]}", 503)
    try:
        if body.filing_id:
            card = cards.stored_card(body.filing_id)
            if not card or card.get("kind") != "results":
                return error_response("Open the results card first; FINN answers from its figures and pages.", 404)
            return copilot.ask_filing(body.question, card)
        if not body.ticker:
            return error_response("Say which stock (ticker) or filing the question is about.", 400)
        symbol = resolve_symbol(body.ticker).symbol
    except ValueError as exc:
        return error_response(str(exc), 404)
    try:
        return _ask_company(body.question, symbol)
    except Exception as exc:  # AI quota or network: say so plainly
        return error_response(f"FINN could not answer right now: {str(exc)[:160]}", 503)


@app.get("/api/pulse")
def api_pulse() -> dict:
    """Pulse (D-107): portfolio heatmap rows, move vs volume, and the next 14 days of events.

    Prices and filings come from the same cache as Today; events from NSE in the background,
    the saved list answering meanwhile (or when NSE blocks us).
    """
    data = feed_cache.get()
    return build_pulse(data, events_cache.get(list(config.PORTFOLIO)), ist_now().date())


@app.get("/api/research/{ticker}")
def api_research(ticker: str):
    """Promise tracker + bull vs bear for any NSE ticker (API-4, EN-16).

    Precomputed stocks answer at once (status "ready"). Any other ticker starts a live run in the
    background; the page polls this endpoint and shows the steps until status is "ready"/"error".
    """
    try:
        result = research_jobs.request(ticker)
    except ValueError as exc:
        return error_response(str(exc), 404)
    return result
