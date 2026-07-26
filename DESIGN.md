# Paper Desk — Design Brief

**This file is the canonical visual identity for the paper desk.** Other agents and humans must respect it when changing UI.

Agents: also follow `.cursor/skills/paper-desk-design/SKILL.md` (ban list in `anti-patterns.md`). Desk-local pointer: `openbb_backend/DESIGN.md`.

## Intent

A small friends’ tool should feel like a **quiet editorial trading room**: ink on forest paper, brass accents, numbers you can trust — crafted, not generated.

## Palette

| Role | Token | Approx |
|------|-------|--------|
| Page | `--bg0` | `#0c1410` |
| Panel | `--bg1` | `#15241c` |
| Ink | `--ink` | `#e8efe6` |
| Muted | `--muted` | `#9aafa0` |
| Accent / metal | `--accent` | `#d4a574` |
| Links | `--link` | `#e2c49a` |
| Up / down | `--up` / `--down` | `#7dcea0` / `#e07a5f` |

One accent family. No purple SaaS, no acid cyber defaults, no cream-and-terracotta brochure kit.

## Type

- **Display:** Georgia (or similar serif) for screen titles
- **Body:** system UI sans
- **Data:** monospace / tabular figures for money and %

Typography carries hierarchy; stock “hero art” does not.

## Surface & structure

- Sharp corners (0–2px), 1px hairline borders, little or no drop shadow
- Cards only when they contain a control or a chart
- One purpose per block; name the product and the screen job immediately
- Light grain optional; no glassmorphism identity
- Motion rare; never scroll-jack; honor `prefers-reduced-motion`

## Charts

- Local D3 only (`static/d3.min.js`); series colors from the desk palette
- **Legends must wrap and stay readable** — HTML flex-wrap, not fixed SVG rows
- **Relative prices:** hover legend or chart to highlight one series (others dim); crosshair + tip with date and rebased value
- Axes muted; empty states honest; honor `prefers-reduced-motion`

## Screens

Overview · Screener · Breadth · Book · Charts · Ideas · Ops — same chrome, different job.

## What we refuse

See skill `anti-patterns.md`: AI prompt chrome everywhere, Poppins/Inter brand stacks, purple glow, reveal-on-scroll theater, vague heroes, hijacked cursors/scroll.

## References (read critically)

- Fatigue signals: [r/web_design thread](https://www.reddit.com/r/web_design/comments/1sare5s/what_web_design_trends_are_you_secretly_tired_of/)
- 2026 agency survey (borrow sharpness/type/grain/MX only): [Fireart](https://fireart.studio/blog/the-best-web-design-trends/)
