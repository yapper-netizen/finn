---
name: task-briefing
description: Brief the next FINN task in the user's approved 6-part format (task, why, done-looks-like, decisions, needs-from-you, next) before planning or building. Use when the user asks "what's next", "next task", "explain the next block", or when starting any PLAN.md block.
---

# Task briefing

Use this before planning or building any PLAN.md block. Goal: the user understands the task and can decide before any code is written. Flow: **explain → plan → decide → approve → build.**

## Steps

1. Read PLAN.md §2 (Timeline) to find the next unfinished block and its task IDs. Read each task's row in §4–§9 and any linked `D-NNN` entries in DECISIONS.md. Check `git log` and the working tree so you don't redo finished work.
2. Write the brief using exactly the sections below. Do not start building.
3. Stop and wait for the user's decisions and approval.

## Format

Simple language. Explain new terms in [square brackets] next to them. Mark anything required by the ENAM brief in {curly brackets}. Concise, short points.

**Next task: block N, TASK-ID "name"**

**What it is** — one or two plain lines.

**Why we're doing it now** — what it unblocks, why this order, which {brief requirement} it serves.

**What "done" looks like** — concrete, checkable bullets (copy the "Done when" from PLAN.md and add specifics).

**Decisions to make** — table of 2-3 options with a recommendation and trade-off. Name the DECISIONS.md ID. If nothing is open, say so.

**What I need from you** — only inputs the user must supply (keys, picks, approvals). If nothing, say so.

**Process / next after this** — one line: explain, plan, decide, approve, build; then name the following block.

## Rules

- Challenge the user if a choice looks wrong; give a recommendation, not a survey.
- Never raise hour estimates or scope worries (D-057); if something becomes too complicated or a deliverable looks at risk, flag it in chat only.
- Record each decision the user makes by appending to DECISIONS.md (never rewrite old entries).
