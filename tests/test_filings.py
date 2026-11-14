"""Tests for data/symbols.py and data/filings.py (no network)."""
from datetime import date

import pytest

import config
from data import filings
from data.symbols import normalise, resolve


def _raw(seq: str, when: str = "09-Nov-2026 17:12:15", title: str = "Board meeting") -> dict:
    return {"seq_id": seq, "an_dt": when, "attchmntText": title, "desc": "Board Meeting",
            "attchmntFile": f"https://x/{seq}.pdf"}


# --- symbol resolver ---
def test_normalise_strips_suffix_and_case():
    assert normalise(" tcs.ns ") == "TCS"
    assert normalise("INFY.BO") == "INFY"


def test_resolve_known_ticker():
    c = resolve("tcs")
    assert c.symbol == "TCS" and "Tata Consultancy" in c.name and c.isin.startswith("INE")


def test_resolve_all_portfolio_and_research():
    for t in config.PORTFOLIO + config.RESEARCH_EXTRA:
        assert resolve(t).symbol == t


@pytest.mark.parametrize("bad", ["XYZ123", "", "   "])
def test_resolve_rejects_invalid(bad):
    with pytest.raises(ValueError):
        resolve(bad)


# --- parsing ---
def test_parse_filing_maps_fields():
    f = filings.parse_filing(_raw("1"))
    assert f == {"id": "1", "date": "2026-11-09T17:12:15", "title": "Board meeting",
                 "category": "Board Meeting", "subcategory": "", "pdf_url": "https://x/1.pdf"}


def test_parse_filings_dedupes_skips_bad_and_sorts_newest_first():
    rows = [_raw("1", "09-Nov-2026 10:00:00"), _raw("1", "09-Nov-2026 10:00:00"),
            {"seq_id": "2"}, _raw("3", "10-Nov-2026 09:00:00")]
    out = filings.parse_filings(rows)
    assert [f["id"] for f in out] == ["3", "1"]


# --- fetch: live, snapshot, merge ---
@pytest.fixture
def snap_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SNAPSHOT_DIR", str(tmp_path))
    monkeypatch.setattr(filings.time, "sleep", lambda s: None)
    return tmp_path


def test_live_fetch_saves_snapshot(snap_dir, monkeypatch):
    monkeypatch.setattr(filings, "_fetch_nse", lambda s, a, b: [_raw("1")])
    out, src = filings.fetch_filings("TCS", 7, today=date(2026, 11, 14))
    assert src == "NSE" and len(out) == 1
    assert filings.load_snapshot("TCS")[0]["id"] == "1"


def test_snapshot_used_when_nse_fails_and_window_applied(snap_dir, monkeypatch):
    monkeypatch.setattr(filings, "_fetch_nse", lambda s, a, b: [_raw("1", "09-Nov-2026 10:00:00"),
                                                                _raw("2", "01-Oct-2026 10:00:00")])
    filings.fetch_filings("TCS", 60, today=date(2026, 11, 14))

    def boom(s, a, b):
        raise requests_error()

    monkeypatch.setattr(filings, "_fetch_nse", boom)
    out, src = filings.fetch_filings("TCS", 7, today=date(2026, 11, 14))
    assert src == "snapshot" and [f["id"] for f in out] == ["1"]


def test_error_when_nse_fails_and_no_snapshot(snap_dir, monkeypatch):
    def boom(s, a, b):
        raise requests_error()

    monkeypatch.setattr(filings, "_fetch_nse", boom)
    with pytest.raises(RuntimeError, match="Could not load filings"):
        filings.fetch_filings("TCS", 7)


def test_invalid_ticker_raises_value_error(snap_dir):
    with pytest.raises(ValueError):
        filings.fetch_filings("XYZ123")


def requests_error() -> Exception:
    return RuntimeError("403 blocked")
