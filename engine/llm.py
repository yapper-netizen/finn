"""Single entry point for every AI call: timeout, one retry, fallback, and cost logging."""
import json
import os
import time
from dataclasses import dataclass
from functools import lru_cache

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


def _call_once(model: str, prompt: str, as_json: bool) -> LLMResult:
    """One request to one model."""
    cfg = types.GenerateContentConfig(
        response_mime_type="application/json" if as_json else "text/plain"
    )
    r = _client().models.generate_content(model=model, contents=prompt, config=cfg)
    u = r.usage_metadata
    return LLMResult(
        text=r.text or "",
        model=model,
        tokens_in=(u.prompt_token_count or 0) if u else 0,
        tokens_out=((u.candidates_token_count or 0) + (u.thoughts_token_count or 0)) if u else 0,
    )


def ask(prompt: str, strong: bool = False, as_json: bool = False) -> LLMResult:
    """Call the cheap or strong model; retry once, then fall back to FALLBACK_MODEL."""
    model = config.STRONG_MODEL if strong else config.CHEAP_MODEL
    chain = [model] * (1 + config.RETRIES)
    if strong and config.FALLBACK_MODEL != model:
        chain.append(config.FALLBACK_MODEL)
    last: Exception | None = None
    for m in chain:
        try:
            res = _call_once(m, prompt, as_json)
            _log(res)
            return res
        except Exception as e:  # network, quota, bad key: try the next link in the chain
            last = e
            print(f"[llm] {m} failed: {type(e).__name__}: {str(e)[:160]}")
            time.sleep(1)
    raise RuntimeError(f"All AI calls failed; last error: {last}")


def ask_json(prompt: str, strong: bool = False) -> dict | list:
    """Ask for JSON and validate that it parses; AI output is never trusted unchecked."""
    res = ask(prompt, strong=strong, as_json=True)
    try:
        return json.loads(res.text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model returned invalid JSON: {res.text[:200]}") from e
