# FINN front-end brainstorm

Status: options for Ahad to pick. Chosen items move to PLAN.md (FE tasks) and DECISIONS.md (one entry each).
Baseline: `design/mockups_v0.html` (six screens, 13 Nov). Improve incrementally, don't redesign.
Time budget: deploy gate Sat 14 Nov 20:00 (D-043). Every idea below has an effort tag; pick at most ~3h of extras.

Legend: {curly} = required by ENAM brief · [square] = term explained · Effort S ≤30 min, M ≤1.5h, L >1.5h.

---

## 1. Research findings (what to borrow)

| Source | What they do | What FINN takes |
|---|---|---|
| ENAM website | Blue `#005da3`, grey `#6a6970`, white; Helvetica Light body, Lato Bold headings; short parallel taglines: "Behind every stock is a Company", "Value Based. Vision Led." | Theme tokens (FE-11). Calm, sparse, serious tone. Taglines as empty-state copy. |
| Robinhood Cortex Digests | AI explains *why a stock moved*, shown on the stock page; ~1M users | "Why it moved" line on alert cards, but **only from filings**, else "No filing explains this move" (honest > guessed) |
| Perplexity Finance | Answer left, sources at the bottom, cell-level citations (filing + page per number) | Every number and quote tappable → receipt sheet. Matches D-041 receipts. |
| Hudson Labs test of Perplexity | Perplexity found correct guidance in only 2 of 8 Apple quarters | Our edge: verified quotes, "claim dropped if quote not found" (D-041). Say this in the writeup. |
| Quartr | Long-press to highlight transcript passages; keyword alerts on calls | "Watch words" idea (§3, P2). |
| Koyfin | AI call summary split into metrics / guidance / risks / Q&A | Promise tracker sections mirror this split. |
| Bottom-sheet guidance (Material, Eleken) | Sheets keep context, unlike full-page modals; swipe-down to dismiss | All detail views open as bottom sheets over Today, not new pages. |

## 2. Point of view (one line for the writeup)
**"FINN reads everything so you read three cards, and every sentence shows its receipt."**
Interaction model {show a point of view}: *triage inbox* [like email: each item is cleared, saved, or opened], not a news feed.

## 3. Ideas, by screen (pick by number)

### Today (FE-2) — baseline screen 1
| # | Idea | Why | Effort |
|---|---|---|---|
| T1 | **"You're done" end state**: after the cards, a line "That's everything that matters. 7 routine filings hidden." | Makes "filter, not feed" visible; closure | S |
| T2 | **Signal strip** at the top: one row of 18 dots, one per stock, coloured if something happened | Whole portfolio at a glance in one line | S |
| T3 | **Swipe to clear / save** a card (seen-state, FE-10) | Triage inbox POV; gestures feel native on phone | M |
| T4 | **"Why it moved"** on alert cards: links to a same-day filing if any, else says none | Borrowed from Cortex, but primary-source honest | S |
| T5 | **Brief me** button (FE-9, already decided D-052) as a pill in the header with a waveform while speaking | Already planned; this is placement | — |
| T6 | Severity left-border on cards (High = ENAM blue, alert = red) instead of only chips | Scannable in 2 seconds | S |

### Detail — results card (FE-3) — baseline screen 2
| # | Idea | Why | Effort |
|---|---|---|---|
| D1 | **Mini bar per metric**: 5 tiny bars (last 5 quarters) next to each row | Trend without a chart library | M |
| D2 | **Margin row** (EBITDA % and PAT %) under the table, computed in Python | Margins matter more than absolute numbers to a fund manager | S |
| D3 | **"Computed" badge** tap → shows the formula and inputs (D-054) | Trust; shows judgment | S |
| D4 | **One-line verdict** at the top: "Strong quarter: all four lines up YoY" (rule-based, not AI) | Reads in 3 seconds | S |

### Detail — management change (FE-3) — baseline screen 3
| # | Idea | Why | Effort |
|---|---|---|---|
| M1 | **Tenure line**: outgoing person's years in role, "planned" vs "sudden" flag from filing wording | The real question a PM asks | S |
| M2 | **"Search LinkedIn" button** (opens a name search, no scraping) | {brief: "e.g. from LinkedIn"}, safe | S |
| M3 | Timeline dot strip: previous employers from the brief profile | Visual bio | M |

### Research (FE-4) — baseline screens 5 and 6
| # | Idea | Why | Effort |
|---|---|---|---|
| R1 | **Credibility score** at the top: "Delivered 2 of 4 promises" as 4 coloured squares | One glance answers "do I trust management?" | S |
| R2 | **Receipt bottom sheet**: quote highlighted, document name, page, "Open PDF" | {primary sources}; D-041 | already FE-4 |
| R3 | **Promise timeline**: vertical line, one node per quarter, chip per promise | Narrative vs numbers as a story | M |
| R4 | **Recent searches + 3 precomputed chips** (POLYCAB, PERSISTENT, ASTRAL) under the search box | Reviewer gets an instant result; unknown ticker still works | S |
| R5 | **Honest loading**: steps shown live ("Finding transcripts… Reading Q3 call… Checking numbers") | Unknown ticker takes time; shows the pipeline (architecture signal) | M |
| R6 | **"What we didn't use"** footer: "No news, broker notes or model memory" | {primary sources only} made visible | S |

### Settings (FE-6) — baseline screen 4
| # | Idea | Why | Effort |
|---|---|---|---|
| S1 | **Live preview**: "At ±3%, 4 alerts this week; at ±5%, 1" under the slider | Makes {configurable thresholds} meaningful; also settles D-007 by showing it | M |
| S2 | **Preset chips**: Calm / Balanced / Watchful | One tap instead of two sliders | S |
| S3 | "Cost so far" row: AI calls and ₹ spent (from logs) | {cost efficiency bonus} shown in-product | S |

### Whole app
| # | Idea | Why | Effort |
|---|---|---|---|
| A1 | **ENAM theme tokens** (FE-11, decided D-044): blue `#005da3`, grey `#6a6970`, Lato headings, Helvetica/system body | Already P0 | — |
| A2 | Dark mode via the same tokens | Investors read at night; cheap with tokens | S |
| A3 | Skeleton loaders [grey placeholder shapes] everywhere (FE-1) | {demo that doesn't run is worst}: never a blank screen | already FE-1 |
| A4 | PWA install (FE-8) | Opens like an app on the reviewer's phone | already FE-8 |
| A5 | Haptic tick on swipe (Vibration API [browser's free buzz function], Android only) | Feels native | S |
| A6 | Empty states using ENAM-style lines: "Behind every stock is a company. Nothing changed at yours today." | Brand voice, no slop | S |

### Parked (P2, write up as "next steps")
- Ask FINN text box on Today (my idea, not ENAM's; D-052 chose Brief me instead).
- Watch words: alert when a chosen word appears in a filing or transcript (Quartr-style).
- Real push notifications (D-042 out of scope).

## 4. Recommended picks (≈2.5h on top of planned FE work)
T1, T2, T4, T6 · D2, D3, D4 · M1, M2 · R1, R4, R6 · S2 · A2, A6
Skip for time: T3, D1, M3, R3, R5, S1 (all M effort).

## 5. Process
1. Ahad picks numbers here.
2. Claude redraws the six screens as `design/mockups_v1.html` with the picks (v0 stays for history).
3. Review on a phone-size view; iterate to v2 only if needed.
4. Copy chosen items into PLAN.md FE task rows; one DECISIONS.md entry ("D-058 front-end picks").
5. Build `web/index.html` from the latest mockup.

## Sources
- ENAM website and stylesheet: https://www.enam.com
- Robinhood Cortex Digests: https://robinhood.com/us/en/support/articles/cortex-digests
- Robinhood Q1 2026 usage figure: https://qnow.quantisnow.com/insight/robinhood-reports-first-quarter-2026-results-6518464
- Perplexity Finance review: https://techpoint.africa/guide/perplexity-finance-review/
- Hudson Labs vs Perplexity guidance test: https://www.hudson-labs.com/post/10-alternatives-to-perplexity-ai
- Quartr transcript highlighting: https://quartr.com/features/transcript-highlighting
- Koyfin transcript platforms: https://www.koyfin.com/blog/top-earnings-call-transcripts-platforms
- Bottom sheets: https://www.eleken.co/blog-posts/bottom-sheet-ui and https://m1.material.io/components/bottom-sheets.html
