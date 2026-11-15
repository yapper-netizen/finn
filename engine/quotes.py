"""Quote guard (EN-15, D-041, D-083): is this quote really in the document, and on which page?

Shared by research (promises, bull/bear) and management cards. A quote is accepted if it is
verbatim after normalising, or a >=90% fuzzy match that changes no number.
"""
from __future__ import annotations

import difflib
import re

import config


def norm(text: str) -> str:
    """Lowercase, re-join words split by a line-break hyphen, keep letters and digits only."""
    t = re.sub(r"-\s*\n\s*", "", (text or "").lower())
    t = t.replace("’", "'").replace("‘", "'")
    return " ".join(re.findall(r"[a-z0-9]+", t))


def quote_score(quote: str, page_text: str) -> float:
    """How well a quote matches somewhere in a page: 1.0 = verbatim (after normalising)."""
    q, page = norm(quote), norm(page_text)
    if not q:
        return 0.0
    if q in page:
        return 1.0
    qw, pw = q.split(), page.split()
    n = len(qw)
    if n < 4 or len(pw) < n:
        return 0.0
    best = 0.0
    matcher = difflib.SequenceMatcher(autojunk=False)
    matcher.set_seq2(q)
    first = set(qw[:3])
    for start in range(0, len(pw) - n + 1):
        if pw[start] not in first and start % 3:   # cheap skip: try likely starts, plus every 3rd word
            continue
        matcher.set_seq1(" ".join(pw[start:start + n]))
        if matcher.real_quick_ratio() < best or matcher.quick_ratio() < best:
            continue
        best = max(best, matcher.ratio())
        if best >= 0.99:
            break
    return best


def verify_quote(quote: str, pages: list[str], hint_page: int | None) -> tuple[int | None, float]:
    """(1-based page where the quote is found, score); page is None if below QUOTE_MATCH_MIN.

    The model's page is tried first; if the quote is on another page, that page is cited instead.
    """
    q = norm(quote)
    for i, text in enumerate(pages):          # fast path: verbatim on some page
        if q and q in norm(text):
            return i + 1, 1.0
    q_nums = set(re.findall(r"[0-9]+", q))     # a fuzzy match may never change a number
    order = list(range(len(pages)))
    if hint_page and 1 <= hint_page <= len(pages):
        order.remove(hint_page - 1)
        order.insert(0, hint_page - 1)
    best_page, best = None, 0.0
    for i in order:
        if not q_nums <= set(re.findall(r"[0-9]+", norm(pages[i]))):
            continue
        s = quote_score(quote, pages[i])
        if s > best:
            best_page, best = i + 1, s
        if s >= 0.99:
            break
    return (best_page, best) if best >= config.QUOTE_MATCH_MIN else (None, best)
