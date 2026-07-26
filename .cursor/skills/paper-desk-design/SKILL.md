---
name: paper-desk-design
description: >-
  Strong, human-authored visual design for the AI Stock Checker paper desk and
  any project UI. Use when editing desk templates, CSS, charts, favicons,
  landing pages, or when the user asks for design, restyle, polish, UI, UX,
  or to avoid AI-slop / generic SaaS looks.
---

# Paper Desk Design

Goal: a trading-desk interface that looks **deliberately designed by a person**, not vibe-coded SaaS or AI-template sludge.

Read [anti-patterns.md](anti-patterns.md) before large visual changes. Product tokens live in `openbb_backend/static/desk.css` (`:root`). Human brief: `DESIGN.md`.

## North star

**Editorial trading desk** — forest ink, warm metal, sharp type, quiet data.

If you strip the logo and it could be any Fintech/AI landing page, the design failed.

## Visual system (locked)

| Token | Role | Do |
|-------|------|----|
| `--bg0` / `--bg1` | Deep forest / panel | Dark-first; not pure pitch `#000` unless OLED experiment |
| `--ink` / `--muted` | Text | High contrast; never light-grey on white |
| `--accent` / `--link` | Warm brass/gold | One accent family; not purple, cyan “AI”, or neon rainbow |
| `--up` / `--down` | PnL | Soft green / clay red — readable, not neon |
| `--font-display` | Titles | Serif (Georgia stack) — type carries hierarchy |
| `--font-body` | UI | System sans — no Inter/Roboto/Poppins/Outfit as brand |
| Data figures | Numbers | Prefer `ui-monospace` / tabular nums for money & % |

**Geometry:** prefer `0–2px` radius, `1px` borders (`--line`), hierarchy via contrast and overlap — not soft neumorphism or floating glass cards.

**Texture:** optional *subtle* CSS/SVG grain on large empty fields. Never heavy WebGL for decoration.

**Motion:** 2–3 intentional moments max (e.g. countdown pulse, chart hover). Prefer CSS. Respect `prefers-reduced-motion`. Never scroll-jack, never custom blob cursors, never “sections fly in on scroll” as default.

## Layout rules

1. **One job per section** — one headline, one short support line, one primary action or data block.
2. **Say what it is** — first viewport / page head must name the product *and* the screen job (Paper Desk / Charts / Screener…). No vague hero one-liners.
3. **Cards only when they hold interaction** — if removing border/background/radius doesn’t hurt, don’t card it.
4. **No decorative bento** — dense data may use grids; do not duplicate DOM for mobile; reflow with CSS Grid.
5. **Charts are first-class** — D3 stays local (`d3.min.js`); chart chrome matches desk tokens (axes muted, series gold/green/clay).
6. **Semantic HTML + a11y** — real headings, landmarks, skip link, focus rings, `aria-current` on nav. Machine-readable structure > trend fluff.

## Stack constraints (this repo)

- Vanilla HTML/CSS/JS in `openbb_backend/templates/` + `static/` — no npm UI kits, no CDN fonts/scripts unless explicitly approved.
- Keep CSP tight; vendor assets under `static/`.
- Docker-only runtime; don’t invent host font installs.

## Workflow (every UI change)

```
Design check:
- [ ] Still editorial desk (forest + brass), not purple SaaS / cream-serif-terracotta cliché
- [ ] No items from anti-patterns.md
- [ ] Type hierarchy clear without glassmorphism
- [ ] Contrast OK; links use --link palette
- [ ] Motion optional + reduced-motion safe
- [ ] Mobile: single narrative column, no hijacked scroll
- [ ] Screenshots / desk URL smoke if visual
```

## When “trends” conflict

Prefer **Reddit fatigue signals** (usability, diversity, no AI chrome) over agency trend-chasing.

From Fireart-style 2026 notes, **borrow only**: sharp geometry, type-as-structure, light grain, semantic/MX HTML, dark-first efficiency.

**Do not borrow**: scroll theater, acid cyber palettes-as-default, trend-for-trend’s-sake brutalism that hurts scanability of a *tool*.

## Sources (context)

- Tired-of thread: https://www.reddit.com/r/web_design/comments/1sare5s/what_web_design_trends_are_you_secretly_tired_of/
- Trend survey (use selectively): https://fireart.studio/blog/the-best-web-design-trends/
