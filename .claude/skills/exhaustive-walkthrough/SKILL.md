---
name: exhaustive-walkthrough
description: Give the user an exhaustive, click-by-click guide for a manual step they must do outside the terminal (get an API key, set up an account, configure a website or dashboard, edit a private file, deploy via a web UI). Use when the user asks "how do I give/get/set up X", "where do I click", "exhaustive guide", or shares a screenshot of a screen and asks what to do.
---

# Exhaustive walkthrough

Goal: the user finishes a manual step on the first try, with no guessing and no secrets exposed. Style reference: the Gemini API key guide in the FINN session (2026-11-14).

## Steps

1. **Look first.** If the user shared a screenshot, read it and name exactly what is on screen (fields, dropdown options, buttons, hidden buttons). Never describe a screen from memory.
2. **Anchor to "this screen".** Start with a section for the current screen, then "After…", then "Save/Use it", then "Finish". Use short headers.
3. **One action per numbered step.** Number continuously across sections. Each step says: what to click or type, the exact label as shown (bold), and the exact value to enter (code format).
4. **Say what to pick and what NOT to pick, with the reason.** Example: keep "Default Gemini Project"; avoid "My First Project" because billing may be attached. Name every option visible on screen.
5. **Flag buttons that are hidden or covered** (e.g. a dropdown covering the Create button) and say where it will be.
6. **Give a verification check** for risky settings (e.g. Billing Tier must say "Free tier"), and say what to do if it doesn't match: stop and tell me.
7. **Terminal commands in their own fenced block** (PowerShell on this machine), one per block, no `$` prompt. Include a check command with its expected output.
8. **Exact file format rules** for anything typed into a file: no quotes, no spaces around `=`, nothing after the value.9. **Known pitfalls** at the end, one line each with the fix (e.g. Notepad saves `.env.txt` → `ren .env.txt .env`).
10. **Finish with the handoff**: exactly what the user replies ("keys saved" plus what they saw), and what Claude does next.
## Rules

- Concise lines, no filler, but do not skip steps. Exhaustive means complete, not long-winded.
- Explain any new technical term in [square brackets] next to it (project rule in CLAUDE.md).
- Mark anything directly required by the ENAM brief in {curly brackets}.
- For purchases, billing, or account creation, state the cost and let the user do it themselves.
