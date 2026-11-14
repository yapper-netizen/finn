# FINN front-end design v2 (current design)

Status: **decided 2026-11-15 (D-074).** Visual skin for every screen. Supersedes the look in `DESIGN_1.md`; the screen list, picks and build order in DESIGN_1 still apply.
How it was chosen: six galleries and app references, 6 side-by-side directions (`previews_v1.html`), then 4 rounds of switchable skins on the live app (D-069 to D-073). History is in DECISIONS.md.

## One-line description
A gradient **hero card** (big count + signal dots), then **ribbon cards** in strict priority order, each with a compact **header file button**. Light mode only.

## Why this look
- **Priority order is a brief deliverable** ({the app must rank what matters}). Cards are a flat list in the order the API returns: tier, then "stock also moved that day", then newest. A timeline or day grouping was tried (D-072, D-073) and rejected because it can reorder or split that ranking.
- Concise delivery stays: one ribbon (what kind), one ticker (which company), one title (what happened), one button (the source).

## Anatomy of a filing card (`article.card`)
1. **Ribbon strip** (tinted band, 46px): ribbon tag flush left = filing type (blue; red for a move chip), date with a calendar icon flush right.
2. **Header row**: category icon tile · ticker (17px bold) and company (14px) · **header button** (62px, "Filing", arrow badge) that opens the source PDF.
3. **Title** (18px bold): what the filing says.
4. **Optional line** (15px): e.g. "The stock also moved on the day of this filing."
The first card ("lead") has a pale-blue background and border. Alert cards (price / volume, no filing) use the same shell: big number + gauge instead of a title, and the button is "Limit" (opens Settings).

## Tokens
- Colour (ENAM, read from enam.com): primary `#005da3`, bright `#2e7ab4`, deep `#004172`, grey `#6a6970`; alert red `#b3261e` (our own). Page: soft blue glow on `#f4f8fd → #e6edf6`.
- Type: headings Lato 700/900; body Helvetica Neue / system. Scale: hero numeral 66px, hero label 25px, stat number 38px (its label 16px, so ratio ≤ 2.4), card title 18px, ticker 17px, body 15–16px, meta/date/company 14px, chips and section labels 13px, tab labels 12.5px. Nothing under 12.5px.
- Depth: cards radius 20px with a 3-layer shadow and an inset top highlight; hero card radius 28px with a radial highlight; floating rounded tab bar.
- Icons: 24 outline category icons plus calendar, doc, sliders, arrow (inline SVG in `ICONS`). Every date carries a calendar icon.

## Rules for new screens (results card, management change, research)
- Reuse the shell: ribbon strip, tile, header button, title, then the screen's own content. Numbers never sit beside labels smaller than half their size.
- Every number or claim that has a source gets a button or link to it.
- Never drop below the type scale above; check at 375px and 360px (no horizontal scroll, ribbon and date must not overlap).

## Not built (yet)
Dark mode, "Brief me" (FE-9), swipe triage, live threshold preview (S1), PWA install. Detail screens and Research (FE-3, FE-4) still to be built in this style.
