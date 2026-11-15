# FINN v2 — revision plan (review against ENAM's brief, then refinement and creative additions)

- Date: 2026-11-15 · Base: tag `v1.0` (`7ad9849`) · Block 10b
- Read with: `brief/ENAM_AI_Engineer_Build_Challenge_Main.pdf` (**B**), `brief/ENAM_Build_Challenge_Reference.pdf` (**R**), DECISIONS.md (D-001..D-091)
- Companion: `plan_revamp_v3/routing.md` (architecture v3: smart model routing)
- Legend: `{...}` = brief requires it · `[...]` = term explained · Status: ✅ done · 🟡 partial · ❌ missing · ⏸ deliberately left out

---

## 1. Requirement-by-requirement checklist

### 1a. Product and data (B pages 1-2)

| # | Brief line | FINN today (screen · file · decision) | Status | Suggestion |
|---|---|---|---|---|
| 1 | {Mobile-first agent, Push + Pull} | Today tab = push, Research tab = pull · `web/index.html` | ✅ | — |
| 2 | {Filter, not aggregate: "burying everything else, beautifully"} | High = card, Medium = one-liner, Low = "Routine (N)" · `ranker.py` D-065 | ✅ | Show *what was buried and why* in one tap (already collapsed; add the reason, e.g. "ESOP allotment = routine") |
| 3 | {"Reach for through the day", saves time} | One-time view; no "since you last looked" state | 🟡 | "Seen" state + "New since 09:14" divider (§3) |
| 4 | {Portfolio 15-20, mixed sectors and sizes} | 18 stocks, large to small (VIJAYA) · CLAUDE.md | ✅ | — |
| 5 | {3-5 research stocks, may be outside portfolio} | POLYCAB, PERSISTENT, ASTRAL (outside) · D-051 | ✅ | — |
| 6 | {Engine works on any NSE ticker} | Live background run, tested HAVELLS/NAUKRI/PAGEIND · `research_jobs.py` | 🟡 | Works, but search has **no typeahead, no recents, results lost on Render restart** (§5, your note) |
| 7 | {EOD price & volume} | yfinance `.NS`, snapshot fallback · `data/prices.py` | ✅ | — |
| 8 | {Corporate announcements, classified} | NSE API, 17-category rule classifier · `classifier.py` D-063 | ✅ | — |
| 9 | {Fundamentals: annual reports + concall transcripts} | Transcripts ✅ + results filings ✅; **annual reports not read** | 🟡 | Results filings already hold balance sheet, cash flow and segments (verified in `.cache/pages`); AR only for "what the company does" (§4.1) |

### 1b. Push (B page 2)

| # | Brief line | FINN today | Status | Suggestion |
|---|---|---|---|---|
| 10 | {Windowed digest, 24h default, user picks period} | 24h / 3d / 7d picker; empty → widen + banner · D-046 | ✅ | Custom range ("since Friday") is cheap; low value |
| 11 | {Prioritised; routine collapsed or hidden} | ✅ as #2 | ✅ | — |
| 12 | {Alert: material announcement of a type I care about} | Category toggles; on + High → "alert" chip · D-047 | ✅ | Per-stock watch (e.g. "pledging only for DIXON") — P2 |
| 13 | {Alert: volume > ~2× avg, price beyond ±X%, configurable} | Sliders + presets, ±3% / 2× defaults · D-077 | ✅ | Live preview "at ±5% you'd have seen 2 this week" (S1, never built) |
| 14 | {"Tell me the moment"} | EOD only; no real notifications · D-042 | ⏸ | Say "as of close 15:30 IST" on hero; writeup states it |
| 15 | {Management change → bio of incoming person (e.g. LinkedIn)} | Profile quote from SEBI annexure, key-role badge · `mgmt.py` D-087 | ✅ | Add "Search LinkedIn" link (brief says enrichment is "completely fine" on push) — M2, never built |
| 16 | {Results → Revenue, EBITDA, PBT, PAT, QoQ and YoY} | Bottom sheet, Python maths, checked to the paisa · D-054/D-089 | ✅ | Add 5-quarter mini-trend per row (D1) |
| 17 | {Every other type: one-line summary or right priority. "That judgment is the point."} | Medium = **title only** (EN-7), "why it matters" = title only (EN-8) | 🟡 | Rule-based "why it matters" line per category + cheap-model one-liner for Medium (§3) |

### 1c. Pull (B page 2, R §2-4)

| # | Brief menu item | FINN today | Status | v2 plan (your picks marked ★) |
|---|---|---|---|---|
| 18 | Business snapshot | — | ❌ | ★ Segment revenue mix from results filings + business description from transcript/AR (§4.2) |
| 19 | Financial snapshot | — | ❌ | ★ KPI tiles: revenue, EBITDA %, PAT %, ROE, ROCE, D/E (§4.2) |
| 20 | Trajectory | — | ❌ | ★ Multi-year + 6-quarter charts (§4.3) |
| 21 | Balance sheet | — | ❌ | ★ Visual balance sheet + working-capital clock (§4.4) |
| 22 | Cash quality | — | ❌ | Recommend folding into ★ Balance sheet (same filing page; R calls it a red flag) |
| 23 | {Narrative vs numbers — "the kind of thing we value most"} | Promise tracker, 4 quarters, receipts · D-080..D-086 | 🟡 | ★ Deepen: segment-level judging, say-do chart, tone vs numbers, topic drift (§4.5) |
| 24 | Guidance | Implicit in promise extraction | ⏸ (your call) | Free by-product: a "Guidance only" filter inside NvN, no new view |
| 25 | Bull vs bear | 3 + 3, each with a receipt · D-084 | ✅ | Link each point to the view that proves it |
| 26 | {Primary sources only; no model outside knowledge} | Quote guard, receipts, "who decided" · D-041/D-083 | ✅ | Keep; make it visible ("Read: 5 calls, 6 filings. Not used: news, broker notes, model memory") |

### 1d. Interaction, bar, cost, scope (B page 3)

| # | Brief line | FINN today | Status | Suggestion |
|---|---|---|---|---|
| 27 | {Experiment: chat, voice, copilot, dashboard, "more than the obvious"} | Cards-first Today + "Brief me" read aloud · D-052/D-091 | 🟡 | One experiment so far; §6 proposes a stated POV with 2-3 modes |
| 28 | {Point of view on how an investor should interact} | Implicit (triage inbox, D-FB §2), not stated in-app | 🟡 | State it on first open + in writeup (§6.1) |
| 29 | {No AI slop: concise, beautiful, interactive; density and design} | ENAM look, receipts, no generic text · D-074 | ✅ | New views must stay dense: charts > paragraphs |
| 30 | {Right tool per step; free tiers; bonus for routing, caching, chunking} | Rules → cheap → strong, SQLite answer cache, page picking · D-060/D-061 | ✅ | Architecture v3 router (separate doc) + in-app "cost of this answer" |
| 31 | {Thin-but-working; demo that doesn't run is worst} | Snapshot fallback, offline test QA-6 | ✅ | Every new view needs a snapshot for the 3 research stocks |
| 32 | {Deliverables: prototype link, repo, AI build history, writeup} | Link live; repo private; history + writeup = block 11 | 🟡 | Block 11 (unchanged) |

### 1e. Reference doc terms not yet used (R §4) — these are cues, see §2

Auditor's qualification · contingent liabilities · related-party transactions · ROCE/ROE · FCF · working-capital cycle · D/E. None appear in FINN today. Three are detectable cheaply from results filings (auditor's opinion, D/E, FCF, WC cycle).

---

## 2. Hidden cues in the brief (close reading)

| Cue (B/R wording, paraphrased) | What it signals | What FINN should do |
|---|---|---|
| "filtering… burying everything else, **beautifully**" | Burying is a feature to design, not a footnote | Show the count and the reason for each bury |
| "a product they **reach for through the day**" | Return visits, not a once-a-day report | "Since you last looked" + seen state |
| "what changed **and why you should care**" | Every pushed item needs a *why* line | EN-8 "why it matters" (gap #17) |
| "**I decide** what 'unusual' means and the app **watches**" | User control + a sense of an agent on watch | Live preview on sliders; "watching 18 stocks" heartbeat |
| "so I **instantly** know who they are and **where they came from**" | Previous employer is the headline, not a paragraph | Lead the mgmt card with "ex-CFO, Havells" style line |
| "a **first cut**" of results | Speed and a verdict, not a full model | Keep the one-line verdict on top |
| "**That judgment is the point**" (other types) | They grade the tiering itself | Show the tier rule on tap ("why is this Medium?") |
| "Treat them as a **menu**… how **deep** you go" | Depth beats breadth | Go deep on NvN; do the rest as dense visuals |
| "summarising vs **analysing** management… what we **value most**" | NvN is the scoring centre of Pull | Most v2 effort here (your internship area) |
| "**Differentiated signal lives in primary data**" | They want the discipline visible | "Not used" footer; every number tappable |
| "Push-side enrichment… **completely fine**" | Using LinkedIn/company site for bios is allowed | Add the LinkedIn search link; keep research strict |
| "**try more than the obvious**", "a **point of view**" | One button is thin; they want an opinion | §6 |
| "**not a model filling a template**" | Generic AI prose is penalised | Rules + numbers; AI only where it reasons |
| "**Pick the right tool for each step**… part of what we're evaluating" | Routing is graded | Show "who decided: rule / Python / cheap / strong" (exists in receipts) + v3 |
| "routing, caching, **and chunking**" | They name chunking explicitly | Name our page-picking as chunking in README |
| "**We may point it at a company you didn't pick**" | Live test of a random ticker | Typeahead, fast first answer, stored results |
| "We **run lean** — small team, **high-conviction**, **lives with the outcomes**" | Concentrated book; decisions get revisited | Thesis line per stock; FINN flags filings that touch it (§6, idea X3) |
| R lists **auditor's qualification, contingent liabilities, RPTs** | Forensic red flags matter to them | "Red flags" strip in research (auditor opinion is in every results filing) |
| R: "persistent profit **without matching cash** is a red flag" | Cash conversion is a named test | Cash conversion bar in Balance sheet view |
| "make it **easy for us to try on a phone**" | Friction at first open costs points | QR code in email, PWA install, instant precomputed demo |

---

## 3. Push side v2 (refinements)

| # | Area | Idea | Brief link | Effort |
|---|---|---|---|---|
| P1 | {Windowed digest} | **"Since you last looked"**: seen state in localStorage, divider "New since 09:14", hero says "2 new" | "through the day" | S |
| P2 | {Windowed digest} | **Why-buried on tap**: Routine row expands with the rule ("AGM notice → routine") | "burying beautifully" | S |
| P3 | {Other types} | **"Why it matters" line** per card from rules (e.g. pledging: "Promoter pledge up to 12% of holding — risk signal"); Medium one-liners from the cheap model, quote-guarded | gap #17 | M |
| P4 | {Triggered alerts} | **Live threshold preview** under sliders: "±3% → 4 alerts in 7 days; ±5% → 1" (Python over the price snapshot) | "I decide what unusual means" | S |
| P5 | {Triggered alerts} | **Alert explains itself**: "Volume 3.1× its 20-day average; no filing explains it" vs linked filing | Cortex idea, honest | S (partly built) |
| P6 | {Management change} | Headline line "Joins from X, was Y" + **Search LinkedIn** button + outgoing person's tenure and "planned / sudden" from wording | "where they came from"; enrichment allowed | S |
| P7 | {Quarter results} | **5-quarter mini-bars** per row; **margin row**; tap a number → page image crop of the filing | first cut + receipts | M |
| P8 | {Quarter results} | **"Versus what they promised"**: if research exists for the stock, the results card shows the matching promise and its new verdict | links push to pull — strongest product idea | M |
| P9 | New, from R | **Red-flag chips** on results: auditor's review not "unmodified", D/E jump, CFO negative (from the same filing) | R §4 cues | M |

Recommendation: P1, P2, P4, P6, P8 (high signal per hour). P3 and P9 after the research data layer exists (they reuse it).

---

## 4. Pull side v2 (research) — brainstorm

### 4.1 Where the numbers come from (all primary, mostly already downloaded)

| Need | Primary source | Already fetched? | Note |
|---|---|---|---|
| Quarterly P&L, 6 quarters | NSE results filings | ✅ (`research_docs.py`) | Same extractor as results cards |
| Segment revenue + segment result | Segment table in the same results filing (Ind AS 108 [accounting rule that makes companies report each business line]) | ✅ pages cached; not extracted | Unlocks business snapshot **and** segment-level promise judging |
| Balance sheet (Mar and Sep) | "Statement of Assets and Liabilities" in Q2 and Q4 results (SEBI LODR Reg 33 [listing rule requiring half-yearly balance sheet]) | ✅ verified in `.cache/pages` | 2 snapshots a year |
| Cash flow (H1 and full year) | Cash flow statement in Q2 and Q4 results | ✅ verified | CFO, capex, FCF, cash conversion |
| Multi-year trajectory (3-4 yrs) | Older Q4 results (each shows 2 full years) | ❌ needs 1-2 extra NSE PDFs per stock | Widen look-back; cheap |
| What the company does | Annual report "business overview", or the opening remarks of the latest call | Transcript ✅ / AR ❌ | Transcript avoids a new source; AR needs your download OK |
| Auditor's opinion | Limited review / audit report pages in results | ✅ | Rule-based: "unmodified" or not |

Big point for the writeup: **every new view comes from documents FINN already reads for results cards**: one extraction, many views (cost + architecture story).

### 4.2 Business snapshot + Financial snapshot (★)

- **Business snapshot**: one sentence of what they do (quoted, with receipt) + **segment mix bar** (100% stacked bar, one row per quarter, so mix *shift* is visible) + segment margin chips.
- **Financial snapshot**: 6 tiles: Revenue (TTM [trailing twelve months]), EBITDA margin, PAT margin, ROE, ROCE, D/E. Each tile has a 6-quarter sparkline and a tap → formula + source page. All maths in Python.

### 4.3 Trajectory (★) — visual ideas

| # | Visual | What it shows | Why it's unusual |
|---|---|---|---|
| V1 | **Growth-vs-margin path** [connected scatter: x = revenue growth YoY, y = EBITDA margin, one dot per quarter joined in time order] | Is the company growing *and* keeping margins, or buying growth? | One picture answers "what's growing, what's compressing" from B |
| V2 | **Slope chart** [two columns, FY-3 and FY latest, a line per metric] | Which lines rose or fell over 3 years | Readable on a 360px phone |
| V3 | **Small-multiple sparklines** (revenue, EBITDA, PAT, segments) on one shared time axis | Trend at a glance | Dense, no chart library |
| V4 | **Divergence bars**: revenue growth vs PAT growth per quarter | Operating leverage [profit growing faster than sales] or its loss | Directly answers "compressing" |

Recommendation: V1 (signature chart) + V3.

### 4.4 Balance sheet + cash quality (★) — visual ideas

| # | Visual | What it shows |
|---|---|---|
| B1 | **Mirror bars**: left = what it owns (fixed assets, inventory, receivables, cash), right = what funds it (equity, debt, payables), Mar vs Sep | Funding structure at a glance |
| B2 | **Working-capital clock** [a dial: inventory days + receivable days − payable days = cash cycle days] with last year's hand ghosted | "A lengthening cycle quietly drains cash" (R) |
| B3 | **Profit-to-cash waterfall**: PAT → + D&A → − working capital → CFO → − capex → FCF | "Do profits turn into cash?" (B) |
| B4 | **Cash conversion gauge**: CFO ÷ PAT, half-year by half-year, red below 70% | R's named red flag |
| B5 | **Red-flags strip**: auditor opinion, D/E trend, contingent liabilities if in the filing | R §4 terms |

Recommendation: B1 + B2 + B3 (B4 is a number on B3).

### 4.5 Narrative vs numbers (★) — deepen (your internship area)

| # | Idea | What changes | Effort |
|---|---|---|---|
| N1 | **Segment-level judging** | Promises like "cables to grow 20%" get judged against the segment table. Fixes the honest gap: ASTRAL 0 of 13 judged, POLYCAB 2 of 12 | M (needs §4.1 segments) |
| N2 | **Say-do chart** [dumbbell: hollow dot = promised target, filled dot = delivered, line between] one row per promise | The four-quarter story in one picture | S once N1 exists |
| N3 | **Credibility meter**: "Delivered 3 · Partial 2 · Missed 1 of 6 judged" as squares, plus "7 too early" greyed | Answers "do I trust management?" in one glance | S |
| N4 | **Tone vs numbers**: per quarter, how confident management sounded (cheap model scores the opening remarks, −2..+2, with the quote) vs actual YoY growth; divergence highlighted | "Where the story and the financials diverge" literally | M |
| N5 | **Topic drift**: themes management stressed each quarter (from the transcript, quoted); a theme that **disappears** is flagged ("Q1-Q3 talked about exports; silent in Q4") | Analysts value what management stops saying | M |
| N6 | **Analyst pressure**: top 3 topics analysts pushed on in Q&A this quarter | B: "what analysts are pressing on" (R §2) | S-M |
| N7 | **Guidance filter** | Shows only explicit headline guidance (growth, margin, capex): covers the Guidance menu item for free | S |

Recommendation: N1 → N2 → N3 → N7 first (core, judged on numbers), then N4 or N5 as the creative one.

### 4.6 Research screen layout

| Option | How it reads |
|---|---|
| A. **One scroll + sticky section chips** (Snapshot · Trajectory · Balance sheet · Narrative · Bull/Bear) | Fast skim on a phone; chips jump; recommended |
| B. Tabs inside Research | Cleaner, but hides sections |
| C. Swipeable "story" cards (one view per card) | Novel, worse for comparing |

---

## 5. Research search fixes (your notes; these are bugs)

| Issue | Today | Fix |
|---|---|---|
| No suggestions while typing ("IR" → IRCTC, IRFC, IREDA, IRB, Indian Bank…) | Exact symbol only · `data/symbols.py` | `/api/symbols?q=` searching symbol **and** company name over the 2,635-row NSE list; prefix match first, portfolio and researched stocks ranked first |
| No recent searches | Only 3 fixed chips | Recents in localStorage (last 6), with status (ready / running) |
| A 2-7 min research is not kept | Kept in `.cache/research/` **until Render restarts** (deploy or restart wipes the disk); never listed | (a) list everything stored on the server ("Researched here": IRCTC, HAVELLS…), (b) the browser also keeps each finished result (~30 KB) so it survives restarts on that phone, (c) `py run_research.py T --save` still promotes one to `snapshot/` permanently |

---

## 6. Interaction model — brainstorm

### 6.1 Proposed point of view (one line for the writeup)
**"Glance, triage, ask."** FINN gives a 10-second glance (dashboard/Brief me), a 2-minute triage (Today cards, cleared as read), and grounded answers on demand (copilot inside every card and research view). Never a blank chat box as the front door: the investor's time goes to *decisions*, not prompts.

### 6.2 Modes to experiment with

| # | Mode | Concrete version for FINN | Grounding rule | Effort |
|---|---|---|---|---|
| I1 | **Copilot in context** | "Ask about this" on a results card / research view; 3 suggested questions ("Why did EBITDA margin fall?" "What did they promise on cables?"); answer only from the documents already loaded, with receipts; refuses otherwise | Same quote guard | M |
| I2 | **Chat (Ask FINN)** | Global box: "Which of my stocks had a pledge change this week?" → routed: portfolio questions answered by Python over the digest; company questions → research | Rules first, AI only to parse the question | M |
| I3 | **Voice** | Extend Brief me: hold-to-talk question (browser speech recognition, free; Chrome/Android good, iOS partial) → same router as I2 → spoken answer | — | S on top of I2 |
| I4 | **Dashboard ("Pulse")** | A glance screen; examples in 6.3 | Python only | M |
| I5 | **Triage gestures** | Swipe right = seen, left = pin to "Watch"; Today counts down to "You're done" | — | M |
| I6 | **Morning stories** | Today as full-screen story cards (tap through, like Instagram stories), auto-advanced while Brief me reads | — | M |

### 6.3 Dashboard examples (pick 1-2)

| # | Dashboard | What it shows | Visual |
|---|---|---|---|
| DB1 | **Portfolio heatmap** | 18 tiles sized by equal weight, coloured by today's move, ring if a filing landed | Treemap [nested rectangles] |
| DB2 | **Event calendar** | Upcoming board meetings, results dates, record dates, AGMs (all from filings already fetched) | Week strip; "next 14 days" |
| DB3 | **Earnings-season grid** | Rows = stocks, columns = Rev/EBITDA/PAT YoY, cells coloured; filled as results land | Heat table |
| DB4 | **Management credibility league** | Each researched stock's say-do score side by side | Ranked bars |
| DB5 | **Risk radar** | Pledging, litigation, rating actions, auditor flags, unusual volume across the book | Dot matrix (stock × risk) |
| DB6 | **Volume-vs-move scatter** | Today's price move vs volume multiple per stock; quadrant "big move, big volume" | Scatter with threshold lines from Settings |

Recommendation: DB1 + DB2 as the "Pulse" glance (DB2 is forward-looking, which Today is not); DB6 doubles as the live threshold preview.

### 6.4 Something they haven't thought of

| # | Idea | Why |
|---|---|---|
| X1 | **Push meets pull**: a new results card shows "they promised 15% growth in cables; delivered 11% → Missed" (P8) | Joins the two halves of the brief; nobody else will |
| X2 | **"What would change my mind"**: each bull/bear point names the number to watch; FINN watches it and flags the filing that moves it | Turns research into a standing alert |
| X3 | **Thesis line** per stock (one sentence, localStorage); filings that touch it get a "thesis" chip | "High-conviction, lives with the outcomes" |

---

## 7. Decisions for you

| # | Decision | Options | Recommendation | Trade-off |
|---|---|---|---|---|
| 1 | Research views in v2 | A: your ★ set (Business + Financial snapshot, Trajectory, Balance sheet, NvN deepened) + cash folded into Balance sheet / B: A without cash / C: A + Guidance as its own view | **A** (Guidance as an NvN filter, N7) | Cash is nearly free from the same page and R names it a red flag; a separate Guidance view would repeat NvN |
| 2 | Data for the new views | A: results filings already fetched (+ 1-2 older Q4 PDFs per stock for multi-year) / B: A + annual reports from NSE / C: try NSE XBRL [machine-readable filing data] first | **A**, with a 30-min XBRL probe (C) because it would remove AI from number extraction | B adds a new download source (needs your OK, large PDFs); A covers everything except long business text |
| 3 | "What the company does" text | A: quoted from the latest call's opening remarks / B: annual report / C: skip | **A** | Primary and already downloaded; AR is richer but slower |
| 4 | NvN depth | A: N1+N2+N3+N7 / B: A + N4 tone vs numbers / C: A + N5 topic drift / D: all | **B** (tone vs numbers is your internship angle; most "creative") | Each extra is one cheap-model call per transcript, cached |
| 5 | Charts | A: hand-built inline SVG [vector drawing in the page] / B: Chart.js / C: ECharts | **A** | Unique and light; B/C faster to draw but look stock |
| 6 | Research layout | A: one scroll + sticky chips / B: tabs / C: story cards | **A** | — |
| 7 | Interaction modes | A: Copilot in context (I1) + Pulse dashboard (I4: DB1+DB2) / B: A + chat and voice (I2+I3) / C: Triage gestures + stories (I5+I6) | **A**, then I3 voice if time (it reuses Brief me) | A is grounded and shows a POV; global chat risks slop |
| 8 | Push refinements | Pick from P1-P9 | **P1, P2, P4, P6, P8** | P8 needs research for the stock (3 precomputed + any stored) |
| 9 | Search persistence | A: server list + browser copy + `--save` to snapshot / B: free external DB (e.g. Turso/Supabase) / C: server only | **A** | B survives everything but adds a service and a key |
| 10 | Order of work | A: 10c search fixes → 10d data layer → 10e views → 10f NvN → 10g interaction → 10h push → v3 router / B: interaction first | **A** (each step ships alone; fixes first because a reviewer may type a random ticker) | — |

## 8. Proposed blocks (after your decisions)

| Block | Content | Done when |
|---|---|---|
| 10c | Typeahead, recents, stored research list + browser copy | "IR" lists IRCTC/IRFC/…; IRCTC result reopens instantly after a server restart on the same phone |
| 10d | Financial-statement extractor: segments, balance sheet, cash flow, older Q4s; Python ratios; checks like results cards | 3 research stocks + 1 bank verified against the PDF pages |
| 10e | Business + Financial snapshot, Trajectory, Balance sheet (SVG) | 375×812 and 360×740 pass; snapshots committed |
| 10f | NvN: segment judging, say-do chart, credibility meter, guidance filter, tone vs numbers | Judged count rises for ASTRAL/POLYCAB; every point has a receipt |
| 10g | Copilot in context + Pulse dashboard (+ voice) | Grounded refusals tested |
| 10h | Push P1, P2, P4, P6, P8 | Tests + phone checks |
| v3 | Router code per `plan_revamp_v3/routing.md` | Token log shows each tier's share |
| tag | `v1.1` | Pushed when you say |
