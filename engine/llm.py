"""Single entry point for every AI call: timeout, one retry, fallback, cost logging, answer cache.

The answer cache (EN-9, D-026) is a SQLite [single-file database] table keyed by a hash of the
model tier and the prompt: the same document is read by AI once. Only answers that pass the
caller's validation are stored, so a bad answer is retried next time instead of being frozen.
"""
import hashlib
import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable

from dotenv import load_dotenv
from google import genai
from google.genai import types

import config

load_dotenv(".env")


@dataclass
class LLMResult:
    """Text plus the model that actually answered and its token counts."""
    text: str
    model: str
    tokens_in: int
    tokens_out: int


@lru_cache(maxsize=1)
def _client() -> genai.Client:
    """Build a Gemini client from GEMINI_API_KEY; fail with a clear message if missing."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing: copy .env.example to .env and set it.")
    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(timeout=config.LLM_TIMEOUT_S * 1000),
    )


def _log(res: LLMResult) -> None:
    """Print one line per AI call so the README can report cost."""
    print(f"[llm] model={res.model} tokens_in={res.tokens_in} tokens_out={res.tokens_out}")


def _call_once(model: str, prompt: str, as_json: bool, schema: type | None = None) -> LLMResult:
    """One request to one model. `schema` (a pydantic class) makes the API enforce the JSON shape."""
    cfg = types.GenerateContentConfig(
        response_mime_type="application/json" if as_json else "text/plain",
        response_schema=schema,
        temperature=0.0 if as_json else None,  # extraction should give the same answer every run
    )
    r = _client().models.generate_content(model=model, contents=prompt, config=cfg)
    u = r.usage_metadata
    return LLMResult(
        text=r.text or "",
        model=model,
        tokens_in=(u.prompt_token_count or 0) if u else 0,
        tokens_out=((u.candidates_token_count or 0) + (u.thoughts_token_count or 0)) if u else 0,
    )


def _is_quota(e: Exception) -> bool:
    """Daily/minute quota used up: retrying the same model is pointless."""
    t = str(e)
    return "429" in t or "RESOURCE_EXHAUSTED" in t


def _is_overloaded(e: Exception) -> bool:
    """Temporary overload (503): worth waiting a little and trying the same model again."""
    t = str(e)
    return "503" in t or "UNAVAILABLE" in t or "overloaded" in t.lower()


def ask(prompt: str, strong: bool = False, as_json: bool = False, schema: type | None = None) -> LLMResult:
    """Call the cheap or strong model, then fall back to FALLBACK_MODEL (D-061, D-088).

    - overloaded (503): wait LLM_BACKOFF_S between tries (the strong model gets one extra try,
      because falling back to a weaker model costs answer quality)
    - quota used up (429): go straight to the fallback model
    - anything else: retry once, then fall back
    """
    model = config.STRONG_MODEL if strong else config.CHEAP_MODEL
    tries = 1 + config.RETRIES + (1 if strong else 0)
    last: Exception | None = None
    for attempt in range(tries):
        try:
            res = _call_once(model, prompt, as_json, schema)
            _log(res)
            return res
        except Exception as e:  # network, quota, overload, bad key
            last = e
            print(f"[llm] {model} failed: {type(e).__name__}: {str(e)[:160]}")
            if _is_quota(e):
                break
            if attempt + 1 < tries:
                time.sleep(config.LLM_BACKOFF_S[min(attempt, len(config.LLM_BACKOFF_S) - 1)] if _is_overloaded(e) else 1)
    if config.FALLBACK_MODEL != model:
        try:
            res = _call_once(config.FALLBACK_MODEL, prompt, as_json, schema)
            _log(res)
            return res
        except Exception as e:
            last = e
            print(f"[llm] {config.FALLBACK_MODEL} failed: {type(e).__name__}: {str(e)[:160]}")
    raise RuntimeError(f"All AI calls failed; last error: {last}")


_db_lock = threading.Lock()


def _run(sql: str, args: tuple = ()) -> list[tuple]:
    """Run one statement on the cache file (created on first use) and close it again."""
    with _db_lock:
        con = sqlite3.connect(config.LLM_CACHE_DB, timeout=10)
        try:
            with con:
                con.execute(
                    "CREATE TABLE IF NOT EXISTS llm_cache (key TEXT PRIMARY KEY, model TEXT, "
                    "text TEXT, tokens_in INTEGER, tokens_out INTEGER, created REAL)"
                )
                return con.execute(sql, args).fetchall()
        finally:
            con.close()


def cache_key(prompt: str, strong: bool, schema: type | None = None) -> str:
    """Hash of the tier, the schema name and the prompt (the prompt embeds the document text)."""
    tier = "strong" if strong else "cheap"
    name = schema.__name__ if schema else ""
    return hashlib.sha256(f"{tier}|{name}|{prompt}".encode("utf-8")).hexdigest()


def cache_get(key: str) -> LLMResult | None:
    """A stored answer, or None. A broken cache file is treated as empty."""
    try:
        rows = _run("SELECT text, model, tokens_in, tokens_out FROM llm_cache WHERE key = ?", (key,))
    except sqlite3.Error:
        return None
    return LLMResult(*rows[0]) if rows else None


def cache_put(key: str, res: LLMResult) -> None:
    """Store a validated answer; a write failure only costs a repeat call later."""
    try:
        _run(
            "INSERT OR REPLACE INTO llm_cache VALUES (?, ?, ?, ?, ?, ?)",
            (key, res.model, res.text, res.tokens_in, res.tokens_out, time.time()),
        )
    except sqlite3.Error as exc:
        print(f"[llm] cache write failed: {exc}")


def ask_json(
    prompt: str,
    strong: bool = False,
    validate: Callable[[Any], Any] | None = None,
    use_cache: bool = False,
    meta: dict[str, Any] | None = None,
    schema: type | None = None,
) -> Any:
    """Ask for JSON, parse it and (optionally) validate it; AI output is never trusted unchecked.

    `validate` takes the parsed JSON and returns the checked value or raises ValueError.
    With `use_cache`, a validated answer is stored and reused for the same prompt.
    `meta`, if given, is filled with the answering model, token counts and whether it was cached.
    """
    key = cache_key(prompt, strong, schema)
    cached = cache_get(key) if use_cache else None
    res = cached or ask(prompt, strong=strong, as_json=True, schema=schema)
    try:
        parsed = json.loads(res.text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model returned invalid JSON: {res.text[:200]}") from e
    value = validate(parsed) if validate else parsed
    # A strong-tier answer that came from the backup model is not kept, so the next run tries the
    # strong model again instead of freezing the weaker answer (10f).
    if use_cache and not cached and not (strong and res.model == config.FALLBACK_MODEL):
        cache_put(key, res)
    if meta is not None:
        meta.update(model=res.model, tokens_in=res.tokens_in, tokens_out=res.tokens_out, cached=bool(cached))
    return value
