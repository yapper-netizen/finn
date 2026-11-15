"""Rule-based filing classifier (EN-2, D-014/D-043): NSE label + title keywords, no AI.

NSE's own label is precise for some filings ("Credit Rating") but vague for ~40% ("Updates",
"General Updates", "Press Release", "Outcome of Board Meeting"), so those are read by title.
First matching rule wins; order matters. Unmatched -> 'unclassified'.
"""
from __future__ import annotations

import re
from typing import NamedTuple

import config


class Rule(NamedTuple):
    category: str
    desc: str | None = None      # regex on NSE's label; None = any
    title: str | None = None     # regex on the filing title; None = any
    not_desc: str | None = None  # label must NOT match this


def _r(*a, **k) -> Rule:
    return Rule(*a, **k)


_OUTCOME = r"outcome of (the )?(board )?meeting"
_RESULTS_TEXT = r"financial results|financial statements|un-?audited|audited"
_FUND = r"\bqip\b|qualified institutions|preferential|rights issue|fund ?-?rais|raising of funds|non-?convertible debenture|\bncds?\b|\bipo\b|initial public offer"
_MNA = r"acqui|merger|amalgamat|business transfer|\bstake\b|divest|slump sale|demerger|joint venture"
_MGMT = r"appointment of|resignation of|resigns?\b|cessation of|change in (senior )?management|steps? down|re-?appointment of"
_ORDER = r"order (win|worth|inflow|book)|\b(bags?|wins?|secures?) .{0,40}(order|contract)|letter of (award|intent)|receipt of (an? )?order|new orders?"
_CAPEX = r"capex|capital expenditure|capacity expansion|new plant|manufacturing facility|commission(ing|ed)|greenfield|brownfield|commercial production"
_LIT = r"\bnclt\b|\bnclat\b|high court|supreme court|show.?cause|penalty|insolvency|adjudicat"

# Order matters: routine labels first (so they never misfire on title words), then precise
# labels, then title keywords for the vague labels.
RULES: list[Rule] = [
    # 1. Routine labels
    _r("unclassified", desc=r"^trading window"),
    _r("unclassified", desc=r"^(esop|options to purchase)"),
    _r("unclassified", desc=r"copy of newspaper|^certificate under sebi|^committee meeting|^amendment to aoa|^corrigendum|^statement of deviation|^monitoring agency|verification"),
    _r("postal_ballot", title=r"postal ballot"),
    _r("agm_egm", desc=r"^shareholders meeting"),
    _r("agm_egm", title=r"annual general meeting|extra-?ordinary general meeting|\bagm\b|\begm\b"),
    _r("earnings_call", desc=r"^analysts?/institutional", title=r"transcript|earnings call|audio recording|conference call|con\.? ?call"),
    _r("investor_meetings", desc=r"^analysts?/institutional|^investor presentation"),
    # 2. Precise labels
    _r("pledging", title=r"pledg|encumbranc"),
    _r("credit_rating", desc=r"^credit rating"),
    _r("litigation", desc=r"^corporate insolvency"),
    # Generic "orders passed" notices (mostly tax/GST) carry no detail in the title: keep them
    # in Routine unless the title shows a serious matter (D-065; EN-19 would read the PDF).
    _r("litigation", desc=r"^action\(s\) (taken|initiated)", title=_LIT),
    _r("unclassified", desc=r"^action\(s\) (taken|initiated)"),
    _r("management_change", desc=r"^(change in management|change in director|resignation|appointment|retirement|cessation|demise|change in auditors|change in company secretary)"),
    _r("order_win", desc=r"^bagging"),
    _r("m_and_a", desc=r"^(acquisition|scheme of arrangement|sale or disposal)"),
    _r("dividend", desc=r"^dividend"),
    _r("dividend", desc=r"^record date", title=r"dividend"),
    _r("insider_trading", desc=r"^trading plan"),
    _r("capex", desc=r"^commencement of commercial"),
    _r("fund_raise", desc=r"^(allotment|issue) of securities", title=_FUND),
    _r("unclassified", desc=r"^(allotment|issue) of securities|^record date"),
    # 3. Title keywords for vague labels (Updates, General Updates, Press Release, Outcome ...)
    _r("results", desc=_OUTCOME, title=_RESULTS_TEXT),
    _r("press_release", title=r"financial results|financial statements|quarterly report|earnings (release|update)"),
    _r("unclassified", title=r"limited review|report of auditors|auditor'?s? report|store opening"),
    _r("litigation", title=_LIT),
    _r("management_change", title=_MGMT),
    _r("m_and_a", title=_MNA),
    _r("dividend", title=r"dividend"),
    _r("bonus_split", title=r"\bbonus\b|stock split|sub-?division of"),
    _r("fund_raise", title=_FUND),
    _r("order_win", title=_ORDER),
    _r("capex", title=_CAPEX),
    _r("earnings_call", title=r"transcript|earnings call|audio recording"),
    _r("investor_meetings", title=r"analyst|investor (meet|conference)"),
    # 4. Defaults by label
    _r("board_outcome", desc=_OUTCOME),
    _r("press_release", desc=r"^press release"),
]

_COMPILED = [
    (
        r.category,
        re.compile(r.desc, re.I) if r.desc else None,
        re.compile(r.title, re.I) if r.title else None,
        re.compile(r.not_desc, re.I) if r.not_desc else None,
    )
    for r in RULES
]


def classify(filing: dict) -> str:
    """Return one category key (a key of config.CATEGORY_TIER) for a filing dict.

    `kind_override` wins: set when FINN read the PDF and found results inside a filing whose
    title said only "Outcome of Board Meeting" (D-087).
    """
    if filing.get("kind_override") in config.CATEGORY_TIER:
        return filing["kind_override"]
    desc = (filing.get("category") or "").strip()
    title = (filing.get("title") or "").strip()
    for category, d, t, nd in _COMPILED:
        if d is not None and not d.search(desc):
            continue
        if t is not None and not t.search(title):
            continue
        if nd is not None and nd.search(desc):
            continue
        return category
    return "unclassified"


def tier_of(category: str) -> str:
    """High / Medium / Low for a category (unknown categories are Low)."""
    return config.CATEGORY_TIER.get(category, "Low")
