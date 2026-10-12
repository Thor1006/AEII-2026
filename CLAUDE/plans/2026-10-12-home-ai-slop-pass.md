# Plan: Home page "AI slop" pass

**Status:** done
**Date:** 2026-10-12

## Why
Checked the home page against the tells in "How to Avoid AI Slop in Vibe-Coded Landing Pages"
(youtube.com/watch?v=M4DNgmI7MIM, description only; the transcript was not available).
The page already avoids the worst tells: no purple gradients, no glow, no generic illustrations,
no stock pricing section, and the fonts were chosen on purpose. But it still reads like a template in four places:

1. **Uppercase tracked eyebrows** ("STEP 1", "LIVE DEMO"). The classic template label. "Step N" also repeats the `<ol>` numbering.
2. **Three identical floating cards plus four more.** The steps and reasons rows use the same shadowed tile,
   and the steps have black rounded-square icon tiles. This is the default AI landing-page grid.
3. **Text-only hero.** The most product-specific thing, the live scores demo, sits below the fold.
   The video's point: the visuals should show *this* product, not a generic layout.
4. **"Why radar" as four feature tiles.** It makes generic claims. A short comparison against camera and
   wearable options says the same thing with more substance.

## Approach
1. Hero: keep the headline, lead and CTAs, and put the live demo card directly under them, so the product shows above the fold.
   Remove the separate "Three scores" section.
2. Demo card label: sentence case "Live demo" with a small status dot. No uppercase tracking.
3. "How it works": a plain numbered list with big muted numerals and a hairline top rule.
   No cards, no shadows, no icon tiles, no "Step N" eyebrow.
4. "Why radar": a three-column comparison table (Camera / Wearables / Radar) covering privacy, setup and home use,
   with radar highlighted. Claims stay inside what the proposal says. On phones the table wraps instead of scrolling sideways, so the Radar column stays visible.
5. Leave the dashboard panel titles uppercase. They are dense UI labels, not landing-page eyebrows.
6. Add `frontend/DESIGN.md`: the short design rules (including these "don'ts") so later passes don't drift back.

## Files touched
- `frontend/src/home/Home.tsx`: restructure the sections
- `frontend/src/home/Home.module.css`: remove tile/eyebrow styles; add list, table and demo-dot styles
- `frontend/DESIGN.md`: new

## Risks / needs OK
- Copy changes on the comparison table, which the team should sign off on.

## How we'll verify
- `npm run typecheck` and `npm run build`
- Browser: home page at desktop and mobile width, light and dark; no console errors.
