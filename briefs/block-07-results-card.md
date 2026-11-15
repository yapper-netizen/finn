# Block 7 brief: the Results card (BE-4, EN-5, API-3, QA-3, QA-4)

Paste this whole file into a fresh chat (or say: "Read CLAUDE.md and briefs/block-07-results-card.md, then wait for my decisions"). Written 2026-11-15. Suggested session model: **Opus** (PDF layouts, arithmetic checks, verification against real documents).

## 1. Next task: block 7, "Results card from the results filing PDF"

**What it is**
- **BE-4, PDF reader:** download a filing PDF, extract its text page by page (pdfplumber [PDF text library]) with page numbers, and cache it by a fingerprint of the URL.
- **EN-5, the Results card:** from the quarterly results filing, pull {Revenue, EBITDA, PBT [profit before tax], PAT [profit after tax]} for the current quarter, the previous quarter and the same quarter last year. **Python** computes {QoQ [vs previous quarter] and YoY [vs year-ago quarter]} growth, never the AI. EBITDA: use the printed figure if there is one; otherwise compute PBT + finance cost + depreciation and amortisation (D&A) - other income and label it "computed" (D-054). Banks get the bank-lite card: Total income / PBT / PAT, EBITDA "n/a for banks" (D-048).
- **API-3:** `GET /api/card/{filing_id}` returns the card JSON. The AI runs only the first time a card is opened, then the answer is cached.
- **QA-3:** unit tests for the maths (negative and zero bases, other income, units, bank-lite).
- **QA-4:** {verify at least 2 results cards, plus 1 bank card, against the actual filing PDFs, to the crore}; record the check.

**Why now**
- {Results card with QoQ and YoY} is a named build item, and results are the top "High" tier on Today: a Results filing currently shows only a title and a PDF button.
- The same extractor feeds the **Promise tracker** in block 8 (D-049: actuals come from results filings), so accuracy here decides block 8.
- It is the hardest data-quality task: real PDFs differ in layout. {Numbers must match the filings} is the done test.

**What "done" looks like**
- For every portfolio stock that has a results filing in `snapshot/filings/` (18 tickers do), plus ASTRAL: a card JSON, or an explicit `status: "could not extract"` with a reason. **Never silently wrong numbers.**
- Each metric shows value, QoQ % and YoY %, with growth computed in Python; units normalised to Rs crore.
- Every extracted number carries its page and the PDF link. A grounding check rejects any number that does not appear in that page's text.
- "computed" badge on a computed EBITDA with the formula and inputs; consolidated or standalone is labelled (D-017).
- Verification table: at least 2 non-bank cards and the HDFCBANK card compared with the PDFs, to the crore, recorded in DECISIONS.md.
- Tests: maths (QA-3) and extraction-failure cases with a fake model (QA-5 style); 86 existing tests still pass.
- Works with the network blocked (precomputed cards ship in the repo) and on the deployed Render link.
- Visible on the phone: tapping a Results card opens the card (see Decision 4), checked at 375x812 and 360x740.
- Today's priority order is untouched.

**Planned order of work** (after approval)
0. **Probe** (before any design lock-in): download 3 sample PDFs, check the text is extractable and see the layouts; check whether NSE gives a usable XBRL [machine-readable results file] link (the NSE record has `hasXbrl: true` but no URL field, unverified).
1. BE-4 reader plus page map plus tests. 2. Upgrade `engine/llm.py`: JSON schema validation and the SQLite answer cache (EN-9 pulled forward, D-026). 3. EN-5 extraction prompt, Python validation and maths (QA-3). 4. Bank-lite. 5. API-3. 6. Results screen. 7. QA-4 verification. 8. Precompute cards for the saved filings, commit under `snapshot/cards/`. Then record, commit, report.

## 2. Decisions to make

| # | Decision | Options | Recommendation | Trade-off |
|---|---|---|---|---|
| 1 | **D-016** Source of the numbers | A: PDF text, cheap model extracts JSON, Python validates (arithmetic cross-checks, each number must appear in the page text) / B: XBRL only / C: screener.in table (secondary) / D: A cross-checked against B or C | **A with Python self-checks.** Add an XBRL or screener cross-check only if the probe shows it is easy | XBRL access is untested, screener is not a primary source ({primary sources}); A relies on extraction quality across layouts, hence the checks. This revises the earlier "D" recommendation because XBRL is unverified |
| 2 | **D-017** Consolidated vs standalone | A: consolidated, fall back to standalone with a label / B: standalone / C: show both with a toggle | **A** | Many filings print standalone first; the label avoids confusion; C costs more UI |
| 3 | **New** Where precomputed cards live (cache.db is in `.gitignore`; Render's disk is wiped on restart) | A: committed JSON under `snapshot/cards/` plus a local, ignored SQLite AI cache / B: commit `cache.db` / C: compute on demand only | **A** | Small, reviewable, works offline and on Render; C is slow and exposed to free-tier model overload |
| 4 | **New** Results screen (PLAN has FE-3 in block 8; this block only specifies the API) | A: bottom sheet that opens when you tap a Results card: table, QoQ/YoY coloured, "computed" badge, page link / B: full-screen detail page / C: JSON endpoint only, screen in block 8 | **A** (same sheet pattern as Research receipts, FE-4) | A pulls the results part of FE-3 forward so the card is visible and checkable on a phone now |
| 5 | **D-007** Default alert thresholds (Today's "Unusual moves" is empty at the defaults) | A: price +/-5%, volume 2x / B: +/-3%, 2x / C: +/-3%, 1.5x | **B** (+/-3% shows PIDILITIND -3.4% on current data; the brief's wording leaves defaults open) | A is quietest and invisible unless Settings is changed; C fires more on real days |
| 6 | **New** Who verifies QA-4 | A: I read the PDFs, build the comparison table, you spot-check at least one card / B: you verify all | **A** | B is slowest and, with A, still independent for the card you check |
| 7 | **New** Verification set (all have Q2 FY27 results in saved data) | A: IRCTC (12 Nov, simplest) + TITAN (5 Nov) + HDFCBANK bank card (17 Oct) / B: A plus ASIANPAINT or LT (harder layouts) / C: your picks | **B** | More layouts tested early; extra PDFs to download |

## 3. What I need from you
1. Your picks for Decisions 1 to 7 (a one-line reply like "1A 2A 3A 4A 5B 6A 7B" is enough).
2. **Explicit OK to download sample results PDFs** from NSE's archive (`nsearchives.nseindia.in`) for the probe and tests. The filenames are in the saved filing records, e.g. `IRCTC_12112026173058_Outcomeofboardmeeting12112026.pdf`, `TITAN_05112026165028_SEoutcomeQ227.pdf`, `HDFCBANK_17102026135520_OutcomeofBMResults_17oct2026.pdf`. I will list exact names and sizes before downloading. They are for local testing only; I will not commit PDFs unless you say so.
3. Approval to build. Say separately if you want a push at the end (a push redeploys Render).
4. A quick spot-check of one verified card against its PDF (if Decision 6 = A).

## 4. Process / next after this
Process: decide, approve, build (7 steps above), record in DECISIONS.md, commit, report, then "Brief block 8?". **Next block 8** (Sun 07:00 to 12:00 in the plan): the Promise tracker, concall transcripts, grounding guard, Research screen, research endpoint, the 3 precomputed research stocks (POLYCAB, PERSISTENT, ASTRAL), plus FE-3/FE-4. The strong model matters more there.

## 5. Context pack (everything a fresh chat needs)

**Repo and live state (2026-11-15)**
- Live app: https://finn-viku.onrender.com (Render free, Singapore, Python 3.12.8, auto-deploys on every push to `main`). UptimeRobot monitor `finn` should ping `https://finn-viku.onrender.com/health` every 5 minutes (the user fixed a typo; confirm it shows Up).
- GitHub: private repo `yapper-netizen/finn`, branch `main`. Local `main` is ahead of GitHub by the commits since `eae13f1` (docs only). Pushing redeploys Render.
- Tests: 86 pass (`py -m pytest -q`). Run the app: `py -m uvicorn api:app --port 8000` or `preview_start` with `finn-api` (`.claude/launch.json`).
- Built so far: AI keys + `engine/llm.py` (OPS-6) · NSE filings fetcher + symbol resolver + VIJAYA swap (BE-2, BE-3, BE-10) · rule classifier, ranker, toggles, windowed digest (EN-2/3/4/18; 96% on a user-approved 50-filing sample) · FastAPI `/`, `/health`, `/api/digest`, `/api/config` with a stale-while-revalidate cache and snapshot fallback (API-1/2/7) · front end Today/Settings/Research stub in the final look (`design/DESIGN_2.md`) · deploy (OPS-1/2/3).
- Not built: results/management cards, research, promise tracker, `docs.py`, cards.py, research.py, README, writeup, "Brief me", dark mode, snapshot refresh script (BE-7, due at the Sun 13:00 code freeze), Android check (QA-7), repo visibility (D-066: private now; make public or invite assessment@enam.com before sending; `brief/` has ENAM's PDFs).

**Code you will touch or reuse**
- `data/filings.py`: filing dict `{id (NSE seq_id), date (IST ISO), title, category (NSE label), subcategory "", pdf_url, ticker, company}`. `data/symbols.py`: `resolve()` from the shipped `data/equity_list.csv` (works for any NSE ticker).
- `engine/classifier.py`: category `results` = NSE "Outcome of Board Meeting" whose title says "financial results / statements / audited". `engine/feed.py`: cached live feed (`FeedCache`, snapshot fallback). `engine/today.py`, `engine/ranker.py`, `engine/digest.py`: Today payload. `engine/llm.py`: `ask(prompt, strong=False, as_json=False)` and `ask_json` (retry once, fallback model, token log; JSON parse only, no schema validation or cache yet).
- `config.py`: all settings, `CHEAP_MODEL = gemini-3.5-flash-lite`, `STRONG_MODEL = gemini-3.5-flash`, `FALLBACK_MODEL = gemini-3.1-flash-lite`. `api.py`: thin routes, errors always `{error, fallback_used}`. `web/index.html`: Alpine app, cards from `data.cards`, icons in `ICONS`. A Results card on Today has the ribbon "Results", the "Filing" header button (opens the PDF) and the title.

**Data on hand**
- 20 results filings in `snapshot/filings/` for 18 tickers: ASIANPAINT, ASTRAL, BHARTIARTL, DEEPAKNTR, DIXON, DMART, HDFCBANK, INFY, IRCTC, LT, MARUTI, PIDILITIND, POLYCAB, RELIANCE, SUNPHARMA, TCS, TITAN, VIJAYA. No results filing found in saved data for PERSISTENT or TRENT. Latest: IRCTC 12 Nov, TITAN/BHARTIARTL/ASTRAL 5 Nov, VIJAYA 3 Nov, others 8 Oct to 30 Oct. HDFCBANK is the bank (17 Oct).
- All PDFs are on `nsearchives.nseindia.in`. Filenames show very different shapes ("Outcome of Board Meeting", "UFR", "QuickResults", an LT "PAM" file, a TCS cover letter): expect layout variety. NSE's announcement records have `hasXbrl: true` but no XBRL URL field.

**Decisions already made that constrain this block**
- D-049 actuals for the promise tracker come from results filings, so one extractor serves two features · D-054 EBITDA computed as PBT + finance cost + D&A - other income, labelled "computed" · D-048 bank-lite card · D-065 every High filing is a card, priority order is kept (a brief deliverable; the day-grouped timeline was rejected for that reason, D-074) · D-060/D-061 free Gemini only: cheap `gemini-3.5-flash-lite`, strong `gemini-3.5-flash`, fallback `gemini-3.1-flash-lite` (Pro and 2.5 models are gone for new keys; 3.6 to 3.8 were overloaded) · D-063/D-064 NSE API, not BSE · D-067 API cache design · D-074 final look and type rules · D-075 Render deploy.
- Engineering standards (CLAUDE.md): never trust AI for arithmetic; AI outputs requested as JSON and validated; every AI call logs model and token count; every network call has a timeout, one retry, a clear error and a snapshot fallback; small typed functions.

**Gotchas learned**
- Windows and PowerShell: use `py`, not `python`. Local Python 3.14, Render 3.12.8: keep code 3.12-compatible. Add `pdfplumber` to `requirements.txt` (runtime); Render's first build with it is the real test.
- Render free has about 512 MB RAM: process PDFs one at a time, do not load whole archives.
- Never work around a protection: BSE's API returns 403, Bloomberg shows a bot check, the permission check blocked browser-fingerprint spoofing, Windows Application Control blocks some DLLs in temp venvs. Report and offer options.
- Free Gemini models return 503/504 under load; the fallback chain handles it, but plan for a card to fail gracefully and retry later.
- UI checks: 375x812 and 360x740, no horizontal scroll, text at least 12.5px, no overlap; there is a type-scale rule in `design/DESIGN_2.md`.
- Never commit `.env` or print keys; downloads need the user's explicit OK; do not push unless asked.

**The user and the routine**
- Ahad Nardekar, IIT Delhi (B.Tech Civil), building FINN for the ENAM AI Engineer Build Challenge. Concise points; explain terms in [square brackets]; mark brief-required items in {curly brackets}; give 2-3 options with a recommendation; challenge them if they are wrong; **do not raise deadline or hours worries** (quality first, the deadline is theirs, D-057).
- The loop (CLAUDE.md "Working loop"): brief (all decisions in tables, nothing asked one by one) then decide, build, record, commit, report what was done and what is NOT verified, then prompt the next brief. Skill: `.claude/skills/task-briefing`.
