# FINN — project context for Claude Code

Act as a senior AI engineer building a production-minded prototype: clean, tested, cost-aware, and easy for a reviewer to read.

## Who I am
- Ahad Nardekar, B.Tech Civil, IIT Delhi.
- Explain any new technical term in [square brackets] right next to it.
- Mark anything directly required by the ENAM brief/reference doc in {curly brackets}.
- Concise, short points. Give 2-3 options before asking me to decide. Challenge me if I'm wrong.

## The assignment (ENAM Holdings AI Engineer Build Challenge)
- Build FINN: {a mobile-first AI agent for a stock investor}. Core idea: a filter, not a feed.
- {Push}: app tells the investor what changed, unasked. {Pull}: investor asks for research on a company.
- {Portfolio of 15-20 NSE/BSE stocks, mixed sectors and sizes}; {3-5 extra research stocks, can be outside portfolio}.
- {Engine must work on any NSE ticker} — they may test one we didn't pick.
- Graded on {creativity, product sense, judgment, architecture}, not completeness. {A demo that doesn't run is the worst outcome.}
- {Primary sources only for pull research: annual reports + concall transcripts. No news, broker notes, or model's outside knowledge.}
- {Free tiers are enough}; {bonus for cost efficiency: cheap model for bulk, strong model for reasoning, caching}.
- Deadline: {Sun 15 Nov 2026}. Plan to submit by 18:00 IST.

## Deliverables — {one email to assessment@enam.com, subject "IIT Delhi – AI Engineer - 2027"}
1. {Working prototype usable on a phone} (deployed link)
2. {GitHub repo}
3. {AI build history} (Claude Code sessions + claude.ai chat share links)
4. {Writeup in email body: what was built, key decisions and trade-offs, what was left out, next steps}

## Users and product point of view
- Users: ENAM's own investment team. ENAM = Mumbai principal investment group, long-term, bottom-up fundamental research.
- ENAM avoids intoxication, gambling, harm to living creatures → keep such stocks out of the demo portfolio (e.g. drop ITC).
- App opens on "Today": every High-tier filing as a card (uncapped, D-065), Medium as one-liners, routine filings collapsed into one row.
- Research answers = scorecards with receipts (every claim links to its source quote/page).
- No user accounts; settings saved in browser localStorage.
- {Interaction experiment}: cards-first Today + "Brief me" (3-sentence summary of Today, read aloud via the browser's free text-to-speech). See D-052.

## Ranking rule ("what matters")
Test: would a long-term fund manager change a hold/buy/sell view because of this?
- High (top card + detail): results, management_change, M&A, litigation, credit_rating, pledging
- Medium (one-line summary): fund_raise, capex, dividend, bonus_split, insider_trading, order wins
- Low (collapse to "Routine (N)"): call notices, investor meetings, AGM/EGM, postal ballot, unclassified
- Boost to top if the same stock also crossed a price/volume alert that day.
- {Alerts with user-configurable thresholds}: volume > 2x 20-day avg (default); daily price move beyond ±3% (default, D-077).

## Build scope
Build:
- {Windowed digest} ({24h default} / 3d / 7d picker), prioritised, routine collapsed. If 24h is empty, widen to the last day with filings and show a banner (D-046).
- {Triggered alerts}: volume, price, category toggles (toggle off → Routine; toggle on + High → "alert" chip, D-047)
- {Results card: Revenue, EBITDA, PBT, PAT with QoQ and YoY}. If EBITDA isn't printed, compute PBT + finance cost + D&A − other income and label it "computed" (D-054). Growth % computed in Python, not by the AI. Banks: Total income / PBT / PAT, EBITDA "n/a for banks" (D-048).
- {Management change card with incoming person's bio} — use the "brief profile" in the exchange filing, no LinkedIn scraping.
- Pull: "Promise tracker" ({narrative vs numbers}, last 4 quarters: Delivered / Partial / Missed with quote; actual numbers from results filings, D-049) + business snapshot (if time) + bull vs bear (if time).
Skip (state in writeup): real push notifications, intraday data, logins, full bank metrics (NII, asset quality), the other 5 research views.

## Tech stack
- Python + FastAPI [library for building the API] — backend and serves the frontend (one deployment)
- SQLite [single-file database] as cache: each document processed by AI once
- Frontend: single HTML page, Tailwind CSS + Alpine.js, mobile-first
- AI routing (D-060, D-061; free tier only, no billing): cheap = `gemini-3.5-flash-lite` (PDF number extraction, quotes, leftovers), strong = `gemini-3.5-flash` (it thinks: promised-vs-delivered verdicts, bull/bear), fallback = `gemini-3.1-flash-lite`. All calls go through `engine/llm.py` (retry once, fallback, token log). Model names live in `config.py`; Google retires models often, so re-run `py smoke_test_llm.py` when a call 404s. Rules, not AI, for alerts and classification.
- Data: yfinance (.NS) {EOD price & volume}; **NSE corporate-announcements API** {corporate announcements} (BSE's API blocks scripts, D-063/D-064); the same NSE API gives {concall transcripts} and results filings for research (D-079); when a transcript filing is only a cover letter, FINN follows the PDF link inside it to the company's own site (https, public host, PDF only)
- Deploy: Render free tier, live at https://finn-viku.onrender.com (`render.yaml`, Python 3.12.8 pinned, auto-deploys on every push to main, UptimeRobot pings /health every 5 min). Keys in .env locally; GEMINI_API_KEY is set in the Render dashboard (live cards and live research).
- Save a JSON snapshot of fetched data so the demo works if a site blocks us (committed under `snapshot/`; Render's disk is wiped on restart).

## Folder architecture
```
finn/
├─ CLAUDE.md, PLAN.md, DECISIONS.md, README.md (to write), .env (ignored), .env.example, .gitignore
├─ requirements.txt (runtime, what Render installs), requirements-dev.txt (+ pytest, httpx), pytest.ini, render.yaml
├─ config.py           tickers, thresholds, category tiers, model names, cache and API limits
├─ data/               prices.py, filings.py, symbols.py, clock.py, docs.py (PDF text), research_docs.py (transcripts + results finder), equity_list.csv
├─ engine/             alerts, classifier, ranker, digest, feed (cache), today, brief (Brief me), llm, quotes (quote guard), results (card extractor), mgmt (management card), cards, research (promise tracker, bull/bear), research_jobs
├─ api.py              FastAPI: /, /health, /api/digest, /api/config, /api/card/{id}, /api/research/{ticker}
├─ web/index.html      one file: Today (+ results sheet), Research (scorecard, receipts, bull/bear), Settings; look in design/DESIGN_2.md
├─ tests/              178 pytest tests (no network)
├─ snapshot/           frozen prices, filings, results cards, research (3 stocks), committed
├─ design/             DESIGN_1.md (screens), DESIGN_2.md (look), previews and brainstorm history
├─ briefs/             one hand-off brief per block (see Working loop)
├─ refresh_snapshot.py, run_filings.py, run_digest.py, run_alerts.py, run_cards.py, run_research.py, smoke_test_llm.py   (scripts)
├─ plan_revamp_v1/     plan audit record
└─ brief/              ENAM brief PDFs (private repo for now, D-066)
```
Run: `py -m uvicorn api:app --port 8000` (or the `finn-api` entry in `.claude/launch.json` via preview_start) · tests: `py -m pytest -q` · `py run_digest.py 7d` · cards: `py run_cards.py` (`--save` rebuilds `snapshot/cards/` from the cached AI answers).
Before the code freeze (D-078, D-090): `py refresh_snapshot.py` (prices, filings, new cards, research only if new documents), check `git status snapshot/`, run the tests, commit. Frozen at tag `v1.0`: fixes only after it. New results filings are also prebuilt in the background on the server when GEMINI_API_KEY is set.
Research: `py run_research.py POLYCAB --save` rebuilds `snapshot/research/POLYCAB.json` (AI answers cached in cache.db; a new ticker costs ~7 AI calls, 1-3 min).

## Draft portfolio (verify each loads in yfinance; no ITC)
RELIANCE, HDFCBANK, TCS, INFY, PIDILITIND, LT, BHARTIARTL, SUNPHARMA, ASIANPAINT, TITAN, DMART, TRENT, POLYCAB, DIXON, PERSISTENT, VIJAYA (Vijaya Diagnostic, small-cap, replaced HAL, D-062), DEEPAKNTR, IRCTC
Research set (D-051): POLYCAB, PERSISTENT, ASTRAL (outside portfolio) — all precomputed

## Plan
Detailed task plan: PLAN.md. All choices (open and decided): DECISIONS.md — append an entry whenever a choice is made.
1. Repo + keys + Claude Code; prices + alerts working
2. Filings pipeline + ranking
3. Results card, bio card, promise tracker
4. Frontend screens + deploy to Render, test on real phone
5. ENAM website colours/fonts, edge cases, README, writeup
6. Send email

## Open decisions
All open and decided choices live in DECISIONS.md (index in PLAN.md §13). Don't duplicate them here.
Timeline (D-043): code freeze Sun 15 Nov 13:00 · send ≤17:30 IST. **Do not raise deadline or hours worries** (D-057, and the user said so on 2026-11-15: that is theirs to manage; quality first, no compromise). Flag a real risk to a deliverable in one line, nothing more.

## Engineering standards
- Small, single-purpose functions with type hints [labels saying what data type goes in/out] and short docstrings.
- All settings (tickers, thresholds, model names) in config.py; secrets only in .env.
- Every network call: timeout, retry once, clear error message, fall back to snapshot data.
- AI outputs requested as JSON and validated before use; never trust AI for arithmetic.
- Log [print a record of] each AI call's model and token count, to report cost in the README.
- Unit tests [small automatic checks] for alerts, ranking and QoQ/YoY maths (pytest).
- A step is done only when it runs end to end and its tests pass.

## Working loop (every block; the user's approved routine, 2026-11-15)
1. **Brief.** When the user says "brief block N" (or "what's next"), use the `task-briefing` skill. **Default = short brief** (same chat, same folder): the 6 sections (task, why, done-looks-like, decisions as tables with a recommendation, needs-from-you, next), no context pack, about one screen. Put every decision in the tables; do NOT ask the options one by one in chat first. **Only when the user says they are changing chats ("hand-off brief")**: add the context pack (repo and live state, decisions already made, constraints, gotchas, data, risks), save it as `briefs/block-NN-name.md`, and give them the one line to paste: "Read CLAUDE.md and briefs/block-NN-name.md, then wait for my decisions." (CLAUDE.md loads in every chat by itself.)
2. **Decide.** The user answers the decision tables and approves. If an answer looks wrong, challenge it once with a recommendation, then follow their final call.
3. **Build.** Keep the task list (`update_plan`); one step at a time; tests pass; run it end to end. UI work: check at 375x812 and 360x740 (no horizontal scroll, text >= 12.5px, nothing overlapping). Data work: check on live data and with the network blocked.
4. **Record.** Append each decision to DECISIONS.md (new D-number, never rewrite old entries), update PLAN.md rows and the decision index, update this file if a fact here changed.
5. **Commit** with a clear message and the Co-Authored-By line. **Do not push unless asked**: pushing redeploys Render.
6. **Report** what was done: built, how it was verified, what is NOT verified, deviations from the brief, new decisions, how to run and check it.
7. **Prompt the next brief** with one question ("Brief block N+1?"). Then wait.

## Hard-won rules for Claude Code
- Windows + PowerShell: use `py`, not `python`. Local Python is 3.14, Render runs 3.12.8: keep code 3.12-compatible.
- Never work around a site's protection (BSE 403, Bloomberg bot check) or the machine's policies (the permission check blocked browser-fingerprint spoofing; Windows Application Control blocks DLLs in temp venvs). Report it and offer options.
- Downloading any file needs the user's explicit OK first: state filename, source and size.
- Never commit .env or API keys; never print key values; the user pastes keys into .env themselves.
- Verify at least 2 results cards against the actual filing PDF numbers (to the crore), plus 1 bank card.
- Terms in [square brackets], brief-required items in {curly brackets}; concise; 2-3 options with a recommendation; challenge the user if they are wrong.
- Commit after each working step with a clear message.
