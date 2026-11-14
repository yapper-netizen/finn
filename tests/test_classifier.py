"""Classifier tests: accuracy on the hand-checked sample plus rule spot-checks."""
import json
from pathlib import Path

import pytest

import config
from engine.classifier import classify, tier_of

SAMPLE = json.loads(Path("tests/sample_labels.json").read_text(encoding="utf-8"))


def f(category: str, title: str = "") -> dict:
    return {"category": category, "title": title}


def test_sample_accuracy_at_least_90_percent():
    right = sum(classify({"category": s["nse_category"], "title": s["title"]}) == s["label"] for s in SAMPLE)
    assert len(SAMPLE) == 50
    assert right / len(SAMPLE) >= 0.90, f"{right}/50"


def test_every_category_has_a_tier_and_labels_are_valid():
    assert set(config.CATEGORY_TIER.values()) <= set(config.TIER_ORDER)
    assert {s["label"] for s in SAMPLE} <= set(config.CATEGORY_TIER)


@pytest.mark.parametrize("category,title,expected", [
    ("Outcome of Board Meeting", "X has submitted to the Exchange, the financial results for the period ended September 30, 2026.", "results"),
    ("Outcome of Board Meeting", "Outcome of Board Meeting held on September 02, 2026.", "board_outcome"),
    ("Credit Rating", "Credit Rating", "credit_rating"),
    ("Bagging/Receiving of orders/contracts", "", "order_win"),
    ("Press Release", 'a press release dated X, titled "Financial results for the quarter"', "press_release"),
    ("Updates", "Pledge of shares by promoter", "pledging"),
    ("Updates", "Repayment of Commercial Paper", "unclassified"),
    ("Updates", "Board approved payment of interim dividend of Rs. 5", "dividend"),
    ("Action(s) taken or orders passed", "Action(s) taken or orders passed", "unclassified"),
    ("Action(s) taken or orders passed", "Order of NCLT regarding the company", "litigation"),
    ("Analysts/Institutional Investor Meet/Con. Call Updates", "Transcript of earnings call", "earnings_call"),
    ("Analysts/Institutional Investor Meet/Con. Call Updates", "Schedule of analyst meet", "investor_meetings"),
    ("Updates", "Infosys wins order from client", "order_win"),
    ("Updates", "Six researchers win the Infosys Prize awarded by the Foundation", "unclassified"),
    ("Trading Window", "Closure of trading window", "unclassified"),
    ("General Updates", "something unexpected", "unclassified"),
])
def test_rules(category, title, expected):
    assert classify(f(category, title)) == expected


def test_tiers_follow_d015():
    assert tier_of("results") == "High" and tier_of("dividend") == "Medium"
    assert tier_of("investor_meetings") == "Low" and tier_of("made_up") == "Low"
