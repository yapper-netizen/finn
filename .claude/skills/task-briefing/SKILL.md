---
name: task-briefing
description: Write the exhaustive hand-off brief for the next FINN block (task, why, done-looks-like, decisions, needs-from-you, next, plus a context pack) and save it to briefs/. Use when the user says "brief block N", "what's next", "next task", or when starting any PLAN.md block. Also holds the full working loop (brief, decide, build, record, commit, report, next brief).
---

# Task briefing and the working loop

The user's approved routine (2026-11-15). The loop is: **brief → decide → build → record → commit → report → prompt the next brief.** Never skip a step, never build before the decisions are answered.

## Writing the brief (step 1)

1. Read PLAN.md §2 (Timeline) for the next unfinished block and its task IDs; read each task row (§4-§9) and every linked `D-NNN` in DECISIONS.md. Read `git log`, `git status`, CLAUDE.md. Check real data and code you will depend on (run a quick probe if a claim in the brief would otherwise be a guess).
2. **Two sizes.** Default (same chat and folder) = a SHORT brief: the sections below without the context pack, about one screen, shown in chat only. Write the EXHAUSTIVE hand-off brief (with the context pack) only when the user says they are changing chats: save it to `briefs/block-NN-short-name.md`, show it, and tell them to paste just one line: "Read CLAUDE.md and briefs/block-NN-....md, then wait for my decisions." Do not start building.
3. Stop and wait for the user's decisions and approval.

### Format

Simple language. New terms in [square brackets] next to them. Anything the ENAM brief requires in {curly brackets}. Concise points, but exhaustive: the user pastes this brief into a fresh chat, so it must stand alone.

**Next task: block N, TASK-IDs "name"**
**What it is**: one or two plain lines per task.
**Why now**: what it unblocks, why this order, which {brief requirement} it serves.
**What "done" looks like**: concrete, checkable bullets (PLAN's "Done when" plus specifics, how it is verified).
**Decisions to make**: every open decision in a table (2-3 options, a recommendation, the trade-off, the DECISIONS.md ID). Put ALL of them here; do not ask them one by one in chat. Say what you already probed or could not verify.
**What I need from you**: only inputs the user must supply (picks, permissions, keys, approvals).
**Process / next after this**: one line, then name the following block.
**Context pack** (what a fresh chat needs):
- Repo and live state: URLs, last commit, tests count, what is built, what is not.
- Decisions already made that constrain this block (ID + one line each).
- Constraints and gotchas learned so far (tools, environment, blocked things, free-tier limits).
- Data on hand (e.g. candidate tickers and files) and known risks.
- The user's working style and rules (copy from CLAUDE.md "Working loop" and "Hard-won rules").
- A first-message line the user can paste: "Read CLAUDE.md and briefs/block-NN-....md, then wait for my decisions."

## After the user answers (steps 2-7)

2. **Decide**: the user answers the tables. If an answer looks wrong, challenge once with a recommendation, then follow their final call.
3. **Build**: task list with `update_plan`; one step at a time; tests pass; run end to end. UI: check at 375x812 and 360x740 (no horizontal scroll, text >= 12.5px, nothing overlapping). Data: check on live data and with the network blocked.
4. **Record**: append each decision to DECISIONS.md (new D-number, never rewrite old entries); update PLAN.md rows and the decision index; update CLAUDE.md if a fact there changed.
5. **Commit**: clear message plus the Co-Authored-By line from the session. **Do not push unless asked** (a push redeploys Render).
6. **Report**: what was built, how it was verified, what is NOT verified, deviations from the brief, new decisions, how to run and check it.
7. **Prompt the next brief** with one question ("Brief block N+1?"), then wait.

## Rules

- Challenge the user if a choice looks wrong; give a recommendation, not a survey.
- Never raise hour estimates, deadline or scope worries (D-057; the user said quality first, the deadline is theirs). If a deliverable is genuinely at risk, say so in one line.
- Never ask for secrets in chat; downloads need the user's explicit OK (filename, source, size).
- State plainly what you could not verify.
