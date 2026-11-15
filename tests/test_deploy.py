"""Deploy-readiness tests (OPS-2/3) and the offline test (QA-6). No network."""
from datetime import datetime
from pathlib import Path

import pytest

import config
from data import filings as filings_mod
from data import prices as prices_mod
from engine.feed import load_all
from engine.today import build_today

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 11, 14, 12, 0, 0)


def test_offline_everything_blocked_app_still_serves_snapshot(monkeypatch):
    """QA-6: with every live source failing, the digest still renders from the saved snapshot."""
    def dead(*args, **kwargs):
        raise ConnectionError("network down")

    monkeypatch.setattr(filings_mod, "_fetch_nse", dead)
    monkeypatch.setattr(prices_mod, "_fetch_one", dead)
    monkeypatch.setattr(filings_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(prices_mod.time, "sleep", lambda s: None)

    data = load_all()
    assert data.fallback_used is True
    assert set(data.prices) == set(config.PORTFOLIO)          # every stock has saved prices
    today = build_today(data, window="7d", now=NOW)
    assert today["fallback_used"] is True
    assert today["counts"]["total"] > 0 and today["cards"]    # saved filings produce cards


def test_snapshot_folder_ships_with_the_repo():
    """OPS-3: Render's free disk is wiped on restart, so the data must be committed."""
    for ticker in config.PORTFOLIO:
        assert (ROOT / "snapshot" / "prices" / f"{ticker}.json").exists(), ticker
        assert (ROOT / "snapshot" / "filings" / f"{ticker}.json").exists(), ticker


def test_render_blueprint_is_complete_and_has_no_secrets():
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "startCommand: uvicorn api:app --host 0.0.0.0 --port $PORT" in text
    assert "healthCheckPath: /health" in text
    assert "plan: free" in text and "PYTHON_VERSION" in text
    assert "AIza" not in text                                    # no API key pasted into the file


def test_runtime_requirements_are_lean_and_secrets_are_ignored():
    runtime = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    for dev_only in ("pytest", "httpx"):
        assert dev_only not in runtime
    for needed in ("fastapi", "uvicorn", "yfinance", "pandas", "requests"):
        assert needed in runtime
    assert ".env" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_app_imports_and_exposes_health():
    import api

    paths = {r.path for r in api.app.routes}
    assert {"/health", "/", "/api/digest"} <= paths


@pytest.mark.parametrize("module", ["api", "engine.research", "engine.mgmt", "engine.cards", "engine.research_jobs",
                                    "run_research", "run_cards", "refresh_snapshot"])
def test_every_entry_point_imports_on_its_own(module):
    """A fresh interpreter per module: catches circular imports that a shared test session hides."""
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-c", f"import {module}"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-500:]
