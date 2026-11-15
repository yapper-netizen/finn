"""Research search (D-100): typeahead ranking, stored-research list, endpoints. No network."""
import json

from fastapi.testclient import TestClient

import api
from data.symbols import search
from engine import research as R
from engine import research_jobs as J


def syms(q: str, prefer: frozenset[str] = frozenset()) -> list[str]:
    return [c.symbol for c in search(q, prefer=prefer)]


def test_prefix_lists_matching_symbols_and_prefers_portfolio():
    got = syms("ir", prefer=frozenset({"IRCTC"}))
    assert got[0] == "IRCTC" and {"IRFC", "IREDA", "IRB", "IRCON"} <= set(got)


def test_exact_symbol_comes_first_and_names_match():
    assert syms("TCS")[0] == "TCS"
    assert syms("indian hotels")[0] == "INDHOTEL"          # company name, not symbol
    assert "IRCTC" in syms("indian railway")
    assert syms("polycab.ns") == ["POLYCAB"]              # suffix cleaned like resolve()


def test_initials_match_and_empty_input():
    assert "IRCTC" in syms("IRCT")
    assert syms("") == [] and syms("   ") == []
    assert len(search("a", limit=5)) == 5


def _write(folder, ticker, version=R.ENGINE_VERSION, at="2026-11-15T10:00:00", status="ready"):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{ticker}.json").write_text(json.dumps(
        {"ticker": ticker, "company": ticker + " Ltd", "status": status, "engine_version": version,
         "generated_at": at, "latest_quarter": "Q2 FY27"}), encoding="utf-8")


def test_list_stored_precomputed_first_then_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(J.config, "RESEARCH_DIR", str(tmp_path / "snap"))
    monkeypatch.setattr(J.config, "CACHE_DIR", str(tmp_path / "cache"))
    _write(tmp_path / "snap", "POLYCAB")
    _write(tmp_path / "cache" / "research", "IRCTC", at="2026-11-15T09:00:00")
    _write(tmp_path / "cache" / "research", "HAVELLS", at="2026-11-15T11:00:00")
    _write(tmp_path / "cache" / "research", "POLYCAB", at="2026-11-15T12:00:00")   # snapshot copy wins
    _write(tmp_path / "cache" / "research", "OLD", version=-1)                    # stale engine: hidden
    rows = J.list_stored()
    assert [r["ticker"] for r in rows] == ["POLYCAB", "HAVELLS", "IRCTC"]
    assert rows[0]["precomputed"] and not rows[1]["precomputed"]


def test_api_symbols_and_research_list(tmp_path, monkeypatch):
    monkeypatch.setattr(J.config, "RESEARCH_DIR", str(tmp_path / "snap"))
    monkeypatch.setattr(J.config, "CACHE_DIR", str(tmp_path / "cache"))
    _write(tmp_path / "cache" / "research", "IRFC")
    c = TestClient(api.app)
    j = c.get("/api/symbols", params={"q": "IR"}).json()
    rows = {r["ticker"]: r for r in j["results"]}
    assert rows["IRFC"]["ready"] and not rows["IREDA"]["ready"]
    assert j["results"][0]["ticker"] in ("IRCTC", "IRFC")                     # portfolio / stored first
    assert rows["IRCTC"]["portfolio"]
    assert c.get("/api/symbols", params={"q": ""}).json()["results"] == []
    lst = c.get("/api/research").json()
    assert lst["engine_version"] == R.ENGINE_VERSION and [r["ticker"] for r in lst["stored"]] == ["IRFC"]
