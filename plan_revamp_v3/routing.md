# FINN architecture v3 — smart model routing

- Date: 2026-11-15 · Base: `engine/llm.py` (v1: two flags, `strong=True/False`, plus fallback) · Companion: `plan_revamp_v2/revision.md`
- {Brief: "Pick the right tool for each step… Smart model routing (cheap models for bulk extraction, a stronger model only where reasoning demands it), caching, and chunking."}
- Constraint, stated honestly: **FINN runs on free Gemini keys only.** There is no paid stronger-model key (e.g. Gemini Pro or Claude). v3 designs the router so a premium tier is a one-line config change, and ships with that tier switched off.

## 1. Where v1 stands

| Piece | v1 today | Limit |
|---|---|---|
| Tiers | `strong: bool` on each call · `config.py` CHEAP / STRONG / FALLBACK | The call site picks the model; no policy in one place |
| Failure | 503 → back off and retry; 429 → fallback model (D-088) | Strong quota runs out daily; answers silently downgrade (the screen says so) |
| Cache | SQLite, keyed by tier + schema + prompt (D-026) | Good; stays |
| Chunking | Page picking (`pick_pages`, statement pages only) | Not named in docs; stays |
| Logging | Model + tokens per call | No per-task cost summary |

## 2. v3 design: a task-based router

Each AI call names a **task**, not a model. One table in `config.py` maps task → route:

| Task | Step 0: no AI | Step 1 | Escalate to | Why |
|---|---|---|---|---|
| `classify_filing` | Rules (17 categories) | — (no AI) | — | Deterministic, free |
| `extract_numbers` (results, BS, CF, segments) | XBRL if available (probe) | cheap | strong **only if Python checks fail twice** | Bulk, copy-only; checks catch errors |
| `extract_profile` (mgmt bio) | — | cheap | — | Copy a paragraph |
| `one_liner` (Medium filings) | Category template | cheap | — | Short, quote-guarded |
| `extract_promises` | — | strong (D-081: cheap was unstable) | premium (off) | Judgment on what counts as a promise |
| `tone_score` (NvN N4) | — | cheap | — | Scored with a quote, cheap is enough |
| `judge_promises` | Python: "too early", "not checkable" | strong | premium (off) | Real reasoning over numbers |
| `bull_bear` | — | strong | premium (off) | Synthesis |
| `copilot_answer` | Python if the question is about the portfolio | cheap (retrieve + quote) | strong if the answer needs reasoning across documents | Most questions are lookups |

Rules:
1. **Cascade [try cheap first, move up only when a check fails]**: validation failure (schema, quote guard, numbers check) escalates one tier; success at a lower tier is cached and never re-asked.
2. **Quota-aware**: a 429 marks that model "resting until reset" for the process, so later calls skip it at once instead of failing first (saves ~seconds per call and quota on the fallback).
3. **Budget guard**: a per-run cap on calls (e.g. 12 for one research) and a per-day cap per tier from config; over the cap → answer from cache or say "come back tomorrow".
4. **Premium tier** (`PREMIUM_MODEL = None` by default): if a key is ever added, `extract_promises`, `judge_promises` and `bull_bear` escalate there on failure. No code change elsewhere.
5. **Cache key = task + model tier + prompt hash** (as now), so a premium answer never overwrites a cheap one silently.

## 3. What a reviewer sees

- Receipts already show "who decided" (rule / Python / cheap / strong). v3 adds **"cost of this answer"**: calls, tokens, and "0 new AI calls (cached)".
- README cost table from the token log: tokens and calls per task, share by tier, cache-hit rate.

## 4. Decisions

| # | Decision | Options | Recommendation | Trade-off |
|---|---|---|---|---|
| 1 | Scope of v3 | A: document only (writeup) / B: implement the router table + quota memory + cost per answer / C: B + premium tier wired (off) | **C** (the premium slot is ~10 lines) | B/C touch every AI call site: run the full tests and rebuild one research to check nothing moves |
| 2 | When to build it | A: last, after v2 features / B: first, so new v2 calls use tasks from day one | **B** | B avoids re-touching the new code; A keeps the first v2 change smaller |
| 3 | Escalation trigger for number extraction | A: after 2 failed Python checks / B: never (report "could not extract") | **A** | A costs a strong call on hard PDFs; B is cheaper but loses cards |
