"""Tests for engine/llm.py: retry, fallback and JSON validation (no network)."""
import pytest

import config
from engine import llm
from engine.llm import LLMResult


def _ok(model: str, text: str = "OK") -> LLMResult:
    return LLMResult(text=text, model=model, tokens_in=3, tokens_out=2)


def test_cheap_call_uses_cheap_model(monkeypatch):
    monkeypatch.setattr(llm, "_call_once", lambda m, p, j, s=None: _ok(m))
    assert llm.ask("hi").model == config.CHEAP_MODEL


def test_strong_overloaded_waits_retries_then_falls_back(monkeypatch):
    seen: list[str] = []
    waits: list[float] = []

    def fake(model, prompt, as_json, schema=None):
        seen.append(model)
        if model == config.STRONG_MODEL:
            raise RuntimeError("503 UNAVAILABLE")
        return _ok(model)

    monkeypatch.setattr(llm, "_call_once", fake)
    monkeypatch.setattr(llm.time, "sleep", waits.append)
    res = llm.ask("hi", strong=True)
    assert seen == [config.STRONG_MODEL] * (2 + config.RETRIES) + [config.FALLBACK_MODEL]
    assert waits == list(config.LLM_BACKOFF_S[: len(waits)]) and waits     # backed off, not 1 s
    assert res.model == config.FALLBACK_MODEL


def test_quota_exhausted_goes_straight_to_fallback(monkeypatch):
    seen: list[str] = []

    def fake(model, prompt, as_json, schema=None):
        seen.append(model)
        if model == config.STRONG_MODEL:
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return _ok(model)

    monkeypatch.setattr(llm, "_call_once", fake)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    assert llm.ask("hi", strong=True).model == config.FALLBACK_MODEL
    assert seen == [config.STRONG_MODEL, config.FALLBACK_MODEL]


def test_all_failures_raise_clear_error(monkeypatch):
    def boom(model, prompt, as_json, schema=None):
        raise RuntimeError("down")

    monkeypatch.setattr(llm, "_call_once", boom)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="All AI calls failed"):
        llm.ask("hi")


def test_ask_json_parses_and_rejects_bad_json(monkeypatch):
    monkeypatch.setattr(llm, "_call_once", lambda m, p, j, s=None: _ok(m, '{"a": 1}'))
    assert llm.ask_json("x") == {"a": 1}
    monkeypatch.setattr(llm, "_call_once", lambda m, p, j, s=None: _ok(m, "not json"))
    with pytest.raises(ValueError):
        llm.ask_json("x")
