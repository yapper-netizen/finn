# Block 10b brief: manual review of FINN against ENAM's brief (then agreed changes)

Paste into a fresh chat: "Read CLAUDE.md and briefs/block-10b-brief-review.md, then wait for my decisions." (CLAUDE.md loads by itself.) Written 2026-11-15, after the code freeze (tag `v1.0`). Suggested model: Opus (judgment, product sense, UI work).

## 1. Next task: block 10b, "Review the app against the brief, then change what the review shows"

**What it is**
- The user looks at the live app next to ENAM's brief and asks for features to add, change or remove. This chat supports that review and then builds the agreed changes.
- Step 1 (Claude, before any build): read both brief PDFs in `brief/` (`ENAM_AI_Engineer_Build_Challenge_Main.pdf`, `ENAM_Build_Challenge_Reference.pdf`) in full, and produce a **requirement-by-requirement checklist**: each requirement or grading criterion of the brief → what FINN does today (with the screen, file and decision ID) → status (done / partial / missing / deliberately left out) → a one-line suggestion. Mark brief-required items in {curly brackets}.
- Step 2: a dedicated review of **investor interaction** (the user names it a primary criterion; the brief asks to {show a point of view about how an investor should interact}). Walk the app as a fund manager would (open → Today → tap → research → settings), list friction and missed opportunities, and propose 3-5 interaction changes with effort and trade-off.
- Step 3: the user reads both, adds their own observations from using the app on a phone, and decides. Only then build, using the normal loop (tables of decisions, build, test, record, commit, report).

**Why now**
- The build is complete and frozen at `v1.0`; the deliverables (README, writeup, build history) come after this review, because the writeup must describe the final app.
- Grading is on {creativity, product sense, judgment, architecture}, {not completeness}; a deliberate interaction model is where the brief "most wants to see how you think".

**What "done" looks like**
- A checklist covering every requirement and grading line in both PDFs, with evidence (not claims); gaps and partials are honest.
- An interaction review with concrete, ranked proposals.
- The user's change list built, tested (pytest + 375x812 and 360x740 checks), recorded in DECISIONS.md, committed, pushed when the user says, and tagged `v1.1` (freeze rule D-090: changes after `v1.0` get a new tag).
- The next blocks are re-confirmed: deliverables (README, writeup, build history, repo access) then sending.

## 2. Decisions to make (to answer after the checklist; the new chat refines them)

| # | Decision | Options | Recommendation | Trade-off |
|---|---|---|---|---|
| 1 | Review format | A: Claude's checklist + interaction review first, then the user's notes / B: the user lists changes first, Claude checks them against the brief | **A** | A finds gaps the user may not see; B is faster if the user already has a list |
| 2 | Scope after review | A: only fixes and changes the review justifies, ranked by impact on the grading lines / B: anything the user wants | **A** (the user has the final call) | Keeps the freeze meaningful; avoids breaking a working demo |
| 3 | Where interaction work lands | A: Today and the sheets (what reviewers see first) / B: Research / C: both | decide after the review | Today is opened first; Research is the "pull" showcase |

## 3. What the new chat needs from the user
1. Their own notes from comparing the app with the brief on a phone (screens, wording, missing items).
2. Decisions on the review's proposals.
3. Still open from earlier blocks (not blocking the review): Android check of the live link (QA-7); UptimeRobot monitor "Up"; repo visibility (D-066); optionally a second free Gemini key (see 5.7).

## 4. Process / next after this
Review → decide → build → record → commit → (push + tag `v1.1` when the user says) → report. Then **block 11 (deliverables)**: README, writeup, AI build history, repo access; its decision table was drafted in chat (README one page with screenshots, Mermaid diagram and real-token cost table; build-history exports scrubbed + claude.ai share links; remove `brief/` PDFs from git history before making the repo public; writeup as `WRITEUP.md` + a Gmail draft the user sends). Then **block 12**: final checklist, wake Render, the user sends the email to {assessment@enam.com}, subject {"IIT Delhi – AI Engineer - 2027"}.

## 5. Context pack

### 5.1 Repo and live state (2026-11-15)
- Live app: https://finn-viku.onrender.com (Render free, Singapore, Python 3.12.8, auto-deploys on every push to `main`). GitHub: private `yapper-netizen/finn`. Tag `v1.0` = commit `7ad9849` (code freeze). Tests: 178 pass (`py -m pytest -q`), no network.
- Run locally: `py -m uvicorn api:app --port 8000` (or `preview_start` with `finn-api`). Keys in `.env` (GEMINI_API_KEY); Render has its own key in its dashboard.
- Scripts: `py refresh_snapshot.py` (freeze refresh), `py run_cards.py [--save]`, `py run_research.py TICKER [--save]`, `py run_digest.py 7d`, `py smoke_test_llm.py`.

### 5.2 What FINN does today, mapped to the brief (verify each against the PDFs in step 1)
- **Push / Today** ({windowed digest}, {24h default / 3d / 7d}): hero card "N things matter" + signal strip of all 18 stocks; every High-tier filing as a ranked card (results, management change, M&A, litigation, credit rating, pledging; D-065), Medium as one-liners ("Also filed"), routine collapsed "Routine (N)"; empty 24h widens to the last day with filings, with a banner (D-046). Rule-based classifier (17 categories), no AI. Files: `engine/classifier.py`, `ranker.py`, `digest.py`, `today.py`, `web/index.html`.
- **Alerts** ({configurable thresholds}): price move beyond ±3% (default, D-077) and volume > 2× 20-day average; "Unusual moves" cards for moves with no filing; same-day move flag on filing cards; Settings sliders and presets; category toggles ({material announcement of a type I care about}: off → Routine). Settings saved in the browser (localStorage), no accounts.
- **Results card** ({Revenue, EBITDA, PBT, PAT with QoQ and YoY}): tap a Results card → bottom sheet. PDF text → cheap model copies printed rows → Python checks column dates, unit, every number printed on the cited page, column order, cross-checks; Python computes growth, crore conversion, computed EBITDA (labelled, formula shown; D-054), margins, a one-line verdict. Banks: Total income / PBT / PAT, EBITDA "n/a for banks" (D-048). Consolidated first, labelled standalone fallback (D-017). QA-4: 6 cards (IRCTC, TITAN, ASIANPAINT, LT, DIXON, HDFCBANK) + PERSISTENT checked against page IMAGES, match to the paisa (D-077, D-089). 20 results cards precomputed in `snapshot/cards/`; new filings prebuilt in the background (D-078). Results filed as a bare "Outcome of Board Meeting" are detected and promoted (PERSISTENT, TRENT; D-089). Files: `engine/results.py`, `cards.py`, `data/docs.py`.
- **Management change card** ({incoming person's background}): from the filing's own SEBI annexure only; name, date, role and verbatim profile quote checked against the PDF; "Key role" badge (CEO/MD/CFO/Chair...); 25 cards precomputed (D-087). File: `engine/mgmt.py`.
- **"Brief me"** (interaction experiment, D-052/D-091): button on Today's hero, three sentences from the digest (Python templates, no AI), read aloud by the browser's speech engine, sentence highlighted while read.
- **Pull / Research** ({any NSE ticker}, {primary sources only}): search box + 3 precomputed stocks (POLYCAB, PERSISTENT, ASTRAL outside the portfolio; D-051). Promise tracker ({narrative vs numbers}, last ~4 quarters): 5 earnings-call transcripts + 6 results filings from NSE (cover letters' PDF links followed to the company site, D-079); promises extracted with verbatim quotes (fuzzy ≥90%, numbers exact, quote must state the target, D-083/D-086); Python facts from results cards; Python decides "Too early" / "Not checkable" (company-level revenue/margin/profit only, D-082); one strong-model call gives Delivered / Partial / Missed with fact ids (D-080). Bull vs bear, 3+3, each with a verified quote or filing figure (D-084). Receipt sheet on every claim (quote, page link, figures used, who decided). Unknown tickers run live in the background with progress steps (2-5 min); tested HAVELLS, NAUKRI, PAGEIND (Render). Files: `engine/research.py`, `research_jobs.py`, `quotes.py`, `data/research_docs.py`.
- **Resilience**: every network call has timeout + retry + snapshot fallback; whole-app offline test (QA-6); API errors are JSON `{error, fallback_used}`; UptimeRobot keeps Render awake.
- **Look**: ENAM colours and fonts, hero card + ribbon cards + header "Filing" button, floating tab bar (Today / Research / Settings), light mode only (D-074; `design/DESIGN_2.md`, screens in `design/DESIGN_1.md`).

### 5.3 Known gaps and limits (honest list for the review)
- Promise tracker judges few promises for companies that guide by segment (ASTRAL 0 judged of 13, POLYCAB 2 of 12, PERSISTENT 1 of 11); reading the segment tables in results filings is the main next step (D-082, D-086).
- Strong model `gemini-3.5-flash` hit its free daily quota (429) on both keys; recent research steps were answered by the backup model and the screen says so (D-088, D-090). A second free key or the daily reset fixes it.
- Not built: dark mode, PWA install, swipe triage, "seen" state, live threshold preview, business snapshot (annual reports not read), the other research views, real push notifications, intraday data, full bank metrics, OCR for scanned PDFs (DEEPAKNTR, MARUTI cards say "could not extract").
- Medium-tier one-line summaries (EN-7) and "why it matters" lines (EN-8) are titles only.
- Model promise selection varies when prompts change (answers cached, so stable for a fixed prompt).

### 5.4 Decisions that constrain changes (see DECISIONS.md for all, D-001..D-091)
- D-065/D-074: Today keeps the brief's priority order (no day grouping); every High filing is a card.
- D-043/D-057: thin-but-working over broad-but-broken; no deadline talk.
- D-060/D-061/D-081: free Gemini only; cheap `gemini-3.5-flash-lite` for bulk, strong `gemini-3.5-flash` for promise extraction, verdicts, bull/bear; fallback `gemini-3.1-flash-lite`.
- D-041/D-083/D-086: no claim without a verified receipt.
- D-090: after `v1.0`, changes are re-tagged (`v1.1`).

### 5.5 Constraints and gotchas
- Windows + PowerShell: `py`, not `python`; keep code 3.12-compatible (Render). Writing Python through bash heredocs has corrupted `\b` in regexes into backspace characters twice: prefer the Edit tool for regex edits and check with `grep -c $'\x08'`.
- Circular imports: `engine/quotes.py` holds the quote guard; a test imports every entry point in a fresh interpreter.
- UI checks: 375x812 and 360x740, no horizontal scroll, text ≥12.5px, taps ≥44px, ribbon/date must not overlap; the browser pane's screenshots sometimes crop at the right edge: measure with JS (scrollWidth, element rects) before believing a screenshot.
- Free-tier AI: 503 "high demand" spells and daily 429 quotas; `engine/llm.py` backs off on 503 and skips to the fallback on 429; batch scripts pace calls.
- Downloads need the user's OK (NSE archive PDFs already approved; company-site transcript PDFs approved for ASTRAL). Never commit `.env` or keys. Never work around site protections. Do not push unless asked; pushing redeploys Render.

### 5.6 Data on hand
- `snapshot/`: prices and filings for 19 stocks (+ WIPRO/MARUTI files from earlier probes), 50 cards, research for 3 stocks. `cache.db` (local, ignored) holds every AI answer. `.cache/` (ignored) holds PDF page text.

### 5.7 The user and the routine
- Ahad Nardekar, IIT Delhi (B.Tech Civil). Concise points; explain terms in [square brackets]; brief-required items in {curly brackets}; 2-3 options with a recommendation; challenge when wrong; quality first; no deadline or hours worries.
- Loop (CLAUDE.md "Working loop"): brief → decide → build → record → commit → report → prompt the next brief. Decisions go in tables, never asked one by one. Skill: `.claude/skills/task-briefing`.
