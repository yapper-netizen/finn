# FINN front-end design v1 (current design)

Status: **decided 2026-11-14 (D-059)**. This is the design to build. Supersedes nothing; extends baseline `design/mockups_v0.html`.
History and rejected ideas: `design/FRONTEND_BRAINSTORM.md` (IDs below refer to it).
On hold for review: the 6-screen set and category tiers (PLAN FE-12, D-015, D-058).

Legend: {curly} = required by ENAM brief · [square] = term explained · Effort S ≤30 min, M ≤1.5h · Tier: P0 must, P1 differentiator, P2 first to cut.

## Point of view (for the writeup)
**"FINN reads everything so you read three cards, and every sentence shows its receipt."**
Today is a *triage inbox* [each item is cleared, saved or opened], not a news feed.

## Build order rule
1. Plan P0 screens (FE-1..4, 6, 11) exactly as in PLAN.md, matching mockups v0.
2. Then layer the picks below, P1 first, in the order listed per screen.
3. Behind schedule → drop P2 picks first, then M-effort picks (PLAN §10 cut list still applies).

## Screens and picks

### 1. Today (FE-2)
| ID | Pick | Effort | Tier |
|---|---|---|---|
| T6 | Severity left border on cards: High = ENAM blue, price/volume alert = red | S | P1 |
| T1 | "You're done" end state: "That's everything that matters. N routine filings hidden." | S | P1 |
| T2 | Signal strip: one dot per portfolio stock, filled if something happened in the window | S | P1 |
| T4 | "Why it moved" on alert cards: same-day filing if one exists, else "No filing explains this move" | S | P1 |
| T5 | "Brief me" pill in the header (FE-9, D-052) | — | P1 |
| **T3** | **Swipe right = clear, left = save** (seen-state, FE-10); cleared cards drop into "Cleared (N)" | **M** | P2 |

### 2. Results card (FE-3)
| ID | Pick | Effort | Tier |
|---|---|---|---|
| D4 | One-line verdict at top, rule-based (e.g. "All four lines up YoY") | S | P1 |
| D2 | Margin row: EBITDA % and PAT %, computed in Python | S | P1 |
| D3 | Tap "computed" badge → formula and inputs (D-054) | S | P1 |
| **D1** | **Mini bars: last 5 quarters per metric, pure CSS, no chart library** | **M** | P1 |

### 3. Management change (FE-3)
| ID | Pick | Effort | Tier |
|---|---|---|---|
| M1 | Tenure of outgoing person + "planned" / "sudden" flag from filing wording | S | P1 |
| M2 | "Search LinkedIn" button: opens a name search, no scraping {brief: "e.g. from LinkedIn"} | S | P1 |

### 4. Settings (FE-6)
| ID | Pick | Effort | Tier |
|---|---|---|---|
| S2 | Preset chips: Calm (±5%, 3x) / Balanced (±5%, 2x) / Watchful (±3%, 1.5x) | S | P1 |
| **S1** | **Live preview under sliders: "At ±3%: 4 alerts this week · at ±5%: 1"**, computed from cached EOD data | **M** | P1 |

### 5–6. Research and promise tracker (FE-4)
| ID | Pick | Effort | Tier |
|---|---|---|---|
| R4 | Under the search box: 3 precomputed chips (POLYCAB, PERSISTENT, ASTRAL) + recent searches | S | P0 (demo safety) |
| R1 | Credibility strip at top: "Delivered 2 of 4" as 4 coloured squares | S | P1 |
| R6 | Footer: "Sources: annual reports and concall transcripts only. No news, broker notes or model memory." {primary sources} | S | P1 |
| **R5** | **Honest loading for unknown tickers: live steps ("Finding transcripts… Reading Q3 call… Checking numbers")** | **M** | P1 |

### Push → pull link (new, closes a gap found in review)
| ID | Pick | Effort | Tier |
|---|---|---|---|
| T7 | "Research {company}" button on Results and Management screens → opens Research pre-filled | S | P1 |

### Whole app
| ID | Pick | Effort | Tier |
|---|---|---|---|
| A1 | ENAM theme tokens (FE-11): blue `#005da3`, grey `#6a6970`, white; Lato headings, Helvetica / system body | — | P0 |
| A6 | Empty states in ENAM voice: "Behind every stock is a company. Nothing changed at yours today." | S | P1 |
| A2 | Dark mode from the same tokens | S | P2 |

## Why these four M-effort picks (out of six)
| Pick | Quality gain | Brief link |
|---|---|---|
| R5 honest loading | Unknown ticker is the riskiest demo path; a live step list never looks frozen and shows the pipeline | {engine works on any NSE ticker}, {demo that doesn't run is worst}, {architecture} |
| S1 live preview | Turns two sliders into a decision aid; also settles ±3% vs ±5% (D-007) by showing both | {configurable thresholds} |
| D1 mini bars | A fund manager reads trend, not one quarter; cheap with CSS | {results card}, {density and design both count} |
| T3 swipe triage | Makes the "triage inbox" point of view tangible | {show a point of view about how an investor should interact} |

Skipped M picks: M3 employer timeline (bio text is enough), R3 promise timeline (cards already tell the story).

## Effort
S picks ≈ 16 × 20 min ≈ 5.5h · M picks ≈ 4 × 1.25h ≈ 5h · total ≈ 10h on top of P0 FE work. Estimates are advisory (D-057); the build order rule above decides what survives.

## Not in this design (parked, writeup "next steps")
Ask FINN text box · watch words on transcripts · real push notifications (D-042) · M3, R3.
