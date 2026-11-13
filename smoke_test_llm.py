"""OPS-6 smoke test: one tiny call per model. Run: py smoke_test_llm.py"""
import config
from engine.llm import ask

for label, strong in (("cheap", False), ("strong", True)):
    r = ask("Reply with exactly: OK", strong=strong)
    asked = config.STRONG_MODEL if strong else config.CHEAP_MODEL
    note = "" if r.model == asked else f"  (FELL BACK from {asked})"
    print(f"{label}: {r.text.strip()[:40]!r} via {r.model}{note}")
