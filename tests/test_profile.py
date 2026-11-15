"""Company profile (D-094): relevance filter, AI sentences kept only with a verified passage. No network."""
from fastapi.testclient import TestClient

from engine import profile as P

FILLER = "Thank you all for joining the call today and for your continued interest. " * 8
PAGES = [
    "Disclaimer: forward looking statements. " * 20,
    FILLER + "We are India's largest maker of wires and cables, selling through 4,500 dealers and distributors across the country.",
    FILLER + "Our FMEG segment makes fans, lights and switches for homes, and grew fastest this quarter.",
    FILLER + "Question and answer session with analysts about pricing and copper costs.",
]


class Out:
    def __init__(self, sentences, segments=()):
        self.sentences = [P.Item(**s) for s in sentences]
        self.segments = [P.SegmentItem(**s) for s in segments]


def stub_ask(sentences, segments=()):
    calls = []

    def ask(prompt, **kw):
        calls.append(prompt)
        assert "[page 2]" in prompt and "ONLY the earnings-call text" in prompt
        return Out(sentences, segments)
    return ask, calls


RESEARCH = {"ticker": "XYZ", "company": "XYZ Ltd",
            "sources": {"transcripts": [{"label": "Q2 FY27 earnings call", "pdf_url": "https://nsearchives.nseindia.in/x.pdf"}]}}


def test_relevance_filter_prefers_business_pages():
    idx = P.pick_pages(PAGES, budget=2000)
    assert 1 in idx and 2 in idx and 0 not in idx
    assert P.page_score(PAGES[1]) > P.page_score(PAGES[3])


def test_numbers_must_come_from_the_quote():
    assert P.numbers_supported("It sells through 4,500 dealers.", "selling through 4,500 dealers and distributors")
    assert not P.numbers_supported("It has 6,000 dealers.", "selling through 4,500 dealers and distributors")


def test_build_keeps_only_verified_sentences():
    ask, calls = stub_ask(
        [{"text": "The company makes wires and cables and sells them through 4,500 dealers.",
          "quote": "largest maker of wires and cables, selling through 4,500 dealers and distributors", "page": 2},
         {"text": "Its fans and lights business grew fastest.",
          "quote": "Our FMEG segment makes fans, lights and switches for homes, and grew fastest", "page": 9},   # wrong page: found on 3
         {"text": "It is the most admired brand in Asia.", "quote": "the most admired brand in the whole of Asia today", "page": 2},   # not in text
         {"text": "It has 9,000 dealers.", "quote": "selling through 4,500 dealers and distributors across the country", "page": 2}],  # invented number
        [{"name": "FMEG", "text": "Fans, lights and switches.", "quote": "makes fans, lights and switches for homes", "page": 3}])
    out = P.build(RESEARCH, ["Wires and Cables", "FMEG"], ask=ask, pages_loader=lambda u: PAGES)
    assert [s["receipt"]["page"] for s in out["sentences"]] == [2, 3]
    assert out["dropped"] == 2 and out["status"] == "ready" and out["segments"][0]["name"] == "FMEG"
    assert out["sentences"][0]["receipt"]["doc"] == "Q2 FY27 earnings call"
    assert "Wires and Cables, FMEG" in calls[0]


def test_build_without_readable_transcript_raises():
    import pytest
    with pytest.raises(LookupError):
        P.build(RESEARCH, ask=stub_ask([])[0], pages_loader=lambda u: ["", " "])


def test_research_set_profiles_are_committed_and_backed():
    import config
    for t in config.RESEARCH_SET:
        d = P.stored(t)
        assert d and d["status"] == "ready" and len(d["sentences"]) >= 2, t
        assert all(s["receipt"]["quote"] and s["receipt"]["page"] for s in d["sentences"])


def test_api_profile_precomputed_and_needs_research(monkeypatch):
    import api
    c = TestClient(api.app)
    r = c.get("/api/profile/POLYCAB")
    assert r.status_code == 200 and r.json()["sentences"]
    monkeypatch.setattr(api.profile_mod, "stored", lambda s: None)
    monkeypatch.setattr(api, "stored_research", lambda s: None)
    r = c.get("/api/profile/TCS")
    assert r.status_code == 409 and "not ready" in r.json()["error"]
