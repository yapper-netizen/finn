import pandas as pd

from engine.alerts import check_alerts


def make_df(closes: list[float], volumes: list[int]) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=len(closes), freq="B")
    return pd.DataFrame({"Date": dates, "Close": closes, "Volume": volumes})


def test_no_alert_on_quiet_day():
    df = make_df([100.0] * 25 + [101.0], [1000] * 25 + [1200])
    assert check_alerts("X", df) == []


def test_price_alert_up_and_down():
    up = check_alerts("X", make_df([100.0] * 25 + [106.0], [1000] * 26))
    down = check_alerts("X", make_df([100.0] * 25 + [94.0], [1000] * 26))
    assert [a["type"] for a in up] == ["price"] and up[0]["value"] == 6.0
    assert [a["type"] for a in down] == ["price"] and down[0]["value"] == -6.0


def test_price_exactly_at_threshold_does_not_fire():
    assert check_alerts("X", make_df([100.0] * 25 + [103.0], [1000] * 26)) == []  # default is ±3% (D-077)


def test_volume_alert_uses_prior_20_days_only():
    # Last day is 3x the average of the previous 20 days.
    df = make_df([100.0] * 26, [1000] * 25 + [3000])
    alerts = check_alerts("X", df)
    assert [a["type"] for a in alerts] == ["volume"]
    assert alerts[0]["value"] == 3.0


def test_both_alerts_can_fire():
    df = make_df([100.0] * 25 + [110.0], [1000] * 25 + [5000])
    assert {a["type"] for a in check_alerts("X", df)} == {"price", "volume"}


def test_short_history_skips_volume_check():
    df = make_df([100.0] * 5, [1000] * 4 + [9000])
    assert check_alerts("X", df) == []


def test_custom_thresholds():
    df = make_df([100.0] * 25 + [104.0], [1000] * 26)
    assert check_alerts("X", df, price_move_pct=3.0)[0]["type"] == "price"
