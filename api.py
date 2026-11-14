"""FINN web API (FastAPI): serves the app page and the Today data. Run: py -m uvicorn api:app

Every error comes back as JSON {error, fallback_used}, never a crash page (API-7).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

import config
from engine.feed import FeedCache
from engine.today import build_today

WEB_INDEX = Path(__file__).parent / "web" / "index.html"
feed_cache = FeedCache()


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
    return {"status": "ok", "data_ready": feed_cache.ready, "last_error": feed_cache.last_error}


@app.get("/")
def index():
    """The app page."""
    if not WEB_INDEX.exists():
        return error_response("App page not built yet.", 404)
    return FileResponse(WEB_INDEX)


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
    return build_today(feed_cache.get(), window=window, price=price, volume=volume, off=off_set)
