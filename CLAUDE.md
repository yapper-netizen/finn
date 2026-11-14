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
- {Alerts with user-configurable thresholds}: volume > 2x 20-day avg (default); daily price move beyond ±5% (default, ±3% still being decided).

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
- AI routing: Gemini Flash (cheap: classification leftovers, PDF number extraction, guidance quotes) → Claude Sonnet or Gemini Pro (strong: promised-vs-delivered verdict, bull/bear). Rules, not AI, for alerts and most classification.
- Data: yfinance (.NS / .BO) {EOD price & volume}; BSE announcements API (NSE backup) {corporate announcements}; screener.in links {annual reports, transcripts}
- Deploy: Render free tier. Keys in .env locally, environment variables on Render.
- Save a JSON snapshot of fetched data so the demo works if a site blocks us.

## Folder architecture
```
finn/
├─ CLAUDE.md, README.md, PLAN.md, DECISIONS.md, .env, .gitignore, requirements.txt, pytest.ini
├─ config.py           tickers, thresholds, category weights, model names
├─ data/               prices.py, filings.py, docs.py, symbols.py   (plumbing)
├─ engine/             alerts.py, classifier.py, ranker.py, cards.py, research.py, llm.py   (brains)
├─ api.py              FastAPI endpoints
├─ web/index.html      Today, Detail, Research, Settings screens
├─ tests/              pytest unit tests
├─ snapshot/           frozen data copy
├─ plan_revamp_v1/     plan audit record
├─ brief/              ENAM brief PDFs
└─ cache.db            AI answer cache
```

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
Timeline (D-043): deploy gate Sat 14 Nov 20:00 · code freeze Sun 15 Nov 13:00 · send ≤17:30 IST.

## Engineering standards
- Small, single-purpose functions with type hints [labels saying what data type goes in/out] and short docstrings.
- All settings (tickers, thresholds, model names) in config.py; secrets only in .env.
- Every network call: timeout, retry once, clear error message, fall back to snapshot data.
- AI outputs requested as JSON and validated before use; never trust AI for arithmetic.
- Log [print a record of] each AI call's model and token count, to report cost in the README.
- Unit tests [small automatic checks] for alerts, ranking and QoQ/YoY maths (pytest).
- A step is done only when it runs end to end and its tests pass.

## Working rules for Claude Code
- One step at a time; after each step show me how to run and check it.
- Verify at least 2 results cards against the actual filing PDF numbers.
- Never commit .env or API keys.
- Commit after each working step with a clear message.
