# Anti-patterns — ban list

Synthesized from [r/web_design “tired of”](https://www.reddit.com/r/web_design/comments/1sare5s/what_web_design_trends_are_you_secretly_tired_of/) (high-signal comments) plus common AI-site tells. If a change matches any row, redesign.

## Instant AI / template tells

| Ban | Why |
|-----|-----|
| Purple → indigo gradients, glow orbs, “AI aurora” | Default generative look |
| Cream `#F4F1EA` + terracotta + generic serif brochure | Other common AI cluster |
| Inter / Roboto / Arial / Poppins / Outfit as *brand* | Homogenized SaaS voice |
| Soft glass: `rgba(255,255,255,0.3)` + `backdrop-filter: blur` as identity | 5+ years of “special” that isn’t |
| Stat strips, pill clusters, icon rows, floating badges on heroes | Dashboard cosplay |
| Vague hero: pretty type, no product/job stated | Looks expensive, communicates nothing |
| AI prompt box chrome on every screen | Fatigue #1 in that thread (~200 ups) |
| Cookie-cutter bento portfolio grids | Dense on desktop, broken narrative on mobile |

## Motion & interaction fatigue

| Ban | Why |
|-----|-----|
| Scroll hijacking / custom scroll speed (Lando-Norris clones) | Feels laggy; hostile on mobile & for elders |
| Sections reveal-on-scroll as default (“site feels slow”) | Impatience + a11y harm |
| Text flying in from edges while scrolling | Theater over information |
| Sticky ads / parallax that follows the eye while reading | Creepy; bad a11y |
| Custom fat cursors with delay | Breaks precision clicking |
| Auto popups / stacked mobile modals | Bounce |

## Form & content UX

| Ban | Why |
|-----|-----|
| Email → Next → *then* password | Hostile login pattern |
| Light grey body on white / low contrast muted text | Unreadable |
| Dynamic lazy content that blocks scanning | User waits to *read* |
| Over-unified “everything looks like Figma template” | Lose personal character |

## Still allowed (with restraint)

- **One** intentional accent motion (hover, chart focus, countdown)
- Sharp 1px borders and near-zero radius (tactile, not soft-UI)
- Subtle grain on large fields
- Serif display + monospace data (editorial desk)
- Dark-first palette for OLED comfort — keep ink contrast high
- Real charts (D3) over stock hero photography
