# Plan audit v1 — PLAN.md vs CLAUDE.md vs ENAM brief

- Date: 2026-11-14
- Audited: PLAN.md @ `fad5e79`, CLAUDE.md, DECISIONS.md (D-001–D-042), `brief/ENAM_AI_Engineer_Build_Challenge_Main.pdf`, `brief/ENAM_Build_Challenge_Reference.pdf`
- Outcome: **all recommendations (G1–G14) approved** by Ahad on 2026-11-14. Applied as DECISIONS D-043–D-056.

Legend: `{...}` = required by the ENAM brief · `[...]` = term explained · Source: **C** CLAUDE.md, **B** main brief, **R** reference doc.

## Correction to the starting assumption

The audit request said PLAN.md had no theme task. It does: **FE-7** "Visual identity: ENAM-like palette and type, dark mode" (P1) + **D-028**. The real gap: FE-7 is cuttable (cut list item 3) while CLAUDE.md step 5 treats the ENAM theme as committed; no task captures ENAM's actual colours/fonts; D-028's recommendation ("own brand, ENAM-inspired") is softer than CLAUDE.md. Status: **Partial**, not Missing.

## Gap table

| # | Requirement | Src | PLAN task (before) | Status |
|---|---|---|---|---|
| 1 | {Mobile-first, usable on phone} | B,C | FE-1, QA-7, DEL-1 | Covered |
| 2 | {Push} + {Pull} modes | B,C | §5a, §5b | Covered |
| 3 | {Portfolio 15–20, mixed sectors **and sizes**} | B,C | BE-1 (18 load) | Partial — all large/mid caps; HAL open (D-033) |
| 4 | {3–5 research stocks, may be outside portfolio} | B,C | EN-16 "demo set" | Partial — no task to finalise/precompute; ASTRAL unverified; 3 of 4 overlap portfolio |
| 5 | {Any NSE ticker} | B,C | BE-2, EN-16, QA-8 | Covered |
| 6 | {Primary sources only for pull} | B,R,C | EN-15, D-020 | Covered (but see #29) |
| 7 | {Cost efficiency: routing, caching, chunking} | B,C | EN-9, EN-10, D-022 | Covered |
| 8 | Deadline realism | C | §2 timeline | **Contradicted** — Fri 13 milestones not done; P0 ≈ 54h at plan estimates vs ~20h left |
| 9 | {Deployed link} | B,C | OPS-2, DEL-1 | Covered |
| 10 | {GitHub repo} | B,C | OPS-1 | Covered |
| 11 | {AI build history} | B,C | DEL-3, D-037 | Covered |
| 12 | {Writeup: built / decisions / left out / next} | B,C | DEL-4 | Covered |
| 13 | README | C | DEL-2 | Covered |
| 14 | ENAM values (no ITC; harm to living creatures) | C | D-010, D-033 | Partial — D-033 open, no task applies it |
| 15 | Today: 3–5 cards, routine collapsed | C,B | EN-4, FE-2 | Covered |
| 16 | Receipts on every claim | C | EN-15, FE-5 | Covered |
| 17 | localStorage settings, no accounts | C | FE-6, D-029 | Covered |
| 18 | Ranking tiers + alert boost | C | EN-3, D-015 | Covered (D-015 open) |
| 19 | {Configurable price/volume thresholds} | B,C | EN-1, FE-6, API-2 | Covered |
| 20 | {Alert on "a material announcement of a type I care about"} = category toggles | B,C | FE-6 (UI), API-2 `cats=` | Partial — no engine task applies toggles, no test |
| 21 | {Windowed digest — let me pick the period} | B,C | EN-4 | **Contradicted** — cut list item 6 drops 3d/7d |
| 22 | {Default window = last 24h} | B | D-035 recommends "last session" | **Contradicted** by D-035 recommendation |
| 23 | {Results card: Rev/EBITDA/PBT/PAT, QoQ + YoY}; maths in Python | B,C | EN-5, QA-3 | Covered |
| 24 | Verify 2 results cards vs PDFs | C | QA-4 | Covered |
| 25 | Bank stock (HDFCBANK) | C | D-018 (open), EN-5 | Partial — HDFCBANK results day would show an empty High card |
| 26 | {Management change + bio} | B,C | EN-6, D-019 | Covered |
| 27 | {Other types: one-liner or right priority} | B | EN-7 | Covered |
| 28 | Pull: business snapshot + promise tracker + bull/bear | C,B | EN-11, EN-13, EN-14 | Covered (bull/bear P1 & cuttable vs CLAUDE.md "Build") |
| 29 | Promise tracker's **actual numbers** | B,C | EN-13 (P0) needs BE-6 (P1, screener) | **Contradicted** — P0 depends on P1; screener is secondary |
| 30 | {Interaction model: experiment, show a point of view} | B | FE-9 (P2, cut first), D-011 | Partial — brief stresses it, plan cuts it first; CLAUDE.md silent |
| 31 | ENAM website colours/fonts | C step 5 | FE-7 (P1, cuttable) | Partial |
| 32 | {No AI slop: dense, beautiful} | B | FE-7 | Partial (tied to #31) |
| 33 | API keys in .env / Render env vars | C step 1 | — | **Missing** |
| 34 | Snapshot fallback | C | BE-7, QA-6, OPS-3 | Partial — no slot to refresh before submission (D-006) |
| 35 | Cost logging → README | C,B | EN-9, API-6, QA-9 | Covered |
| 36 | Tests: alerts, ranking, QoQ/YoY | C | QA-1–3 | Covered |
| 37 | Never commit .env | C | OPS-1, DEL-5 | Covered |
| 38 | CLAUDE.md folder tree / "Open decisions" section | C | PLAN adds classifier.py, symbols.py; 29 open decisions | Partial — drift |

## Gaps, options, outcome

| Gap | Options | Approved | Decision |
|---|---|---|---|
| G1 Timeline / P0 overload (#8) | A re-scope P0 to two workflows, deploy gate Sat 20:00, freeze Sun 13:00 · B keep scope, freeze Sun 15:00 · C precomputed research only (breaks {any ticker}) | A | D-043 |
| G2 Theme (#31, #32) | A new FE-11 P0 theme tokens [named colour/font settings], FE-7 polish P1 · B all FE-7 P0 · C drop ENAM theme | A | D-044 |
| G3 3d/7d on cut list (#21) | A remove from cut list · B keep 24h + 7d only | A | D-045 |
| G4 Default window (#22) | A {24h} default, auto-widen with banner if empty · B "last session" default · C strict 24h | A | D-046 |
| G5 Category toggles (#20) | A EN-18: off → Routine, on + High → alert chip, tested · B client-side hide · C drop | A | D-047 |
| G6 Bank stock (#25) | A bank-lite card (Total income / PBT / PAT, EBITDA "n/a") · B "unsupported" label · C replace HDFCBANK | A | D-048 |
| G7 Promise-tracker actuals (#29) | A reuse EN-5 results extractor (primary), delete BE-6 · B BE-6 P0 via screener · C XBRL | A | D-049 |
| G8 API keys (#33) | A OPS-6: Gemini key + Anthropic if available + smoke test · B Gemini only | A | D-050 |
| G9 Research set (#4) | A 3 stocks, ≥1 outside portfolio, all precomputed · B 4 · C 5 | A | D-051 |
| G10 Interaction experiment (#30) | A FE-9 → P1, "Brief me" via Web Speech API · B keep P2 · C chat as core | A | D-052 |
| G11 Snapshot refresh (#34) | A timeline slot Sun 13:00 + DEL-5 checkbox · B GitHub Action | A | D-053 |
| G12 EBITDA formula (CLAUDE.md vs brief) | A PBT + finance cost + D&A − other income, labelled · B as-is, labelled "incl. other income" · C show both | A | D-054 |
| G13 Portfolio sizes / HAL (#3, #14) | A replace HAL with non-defence small-cap · B keep · C replace with large-cap | A | D-055 |
| G14 CLAUDE.md ↔ PLAN drift (#28, #38) | A update CLAUDE.md (tree, decisions pointer, "(if time)", G6/G12/G13) · B record only in DECISIONS | A | D-056 |

## Note on hours after re-scope

The re-scope removes ~5h of P0 work (EN-11 → P1, EN-2 AI fallback → P2, BE-6 deleted, FE-5 merged, QA-5 trimmed) but the gaps add ~2.5h (FE-11, EN-18, OPS-6, BE-9, BE-10, bank-lite). P0 at plan estimates is still ≈ 53h. Estimates were written as hand-coding hours; with Claude Code writing the code, wall-clock is assumed to be well below that, but this is an assumption. The **Sat 20:00 deploy gate** is the real check, with second-stage cuts defined in PLAN §10.
