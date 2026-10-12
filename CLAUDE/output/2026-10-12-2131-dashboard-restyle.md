# Report: Dashboard restyle (palette, fonts, floating rounded UI)

**Date:** 2026-10-12 21:31 · **Result:** ✅ done · **Plan:** [2026-10-12-dashboard-restyle](../plans/2026-10-12-dashboard-restyle.md)

## Goal
Make the dashboard look less like generic "AI" styling: Microsoft/Fluent-style neutrals with one blue accent, Inter font, floating cards, consistent rounded rectangles, no gradients.

## What changed
- `frontend/src/styles/theme.css` — new light/dark tokens (Fluent greys, blue accent, muted good/warn/bad, blue-led chart series), `--radius` 16px / `--radius-sm` 10px, `--float` layered shadow, `--font-sans` = Inter + Noto Sans Thai.
- `frontend/src/main.tsx` — imports bundled font files (Inter 400/500 latin, Noto Sans Thai 400/500 thai).
- `frontend/package.json`, `package-lock.json` — added `@fontsource/inter`, `@fontsource/noto-sans-thai` (about 66 KB of woff2).
- `frontend/src/components/Panel.module.css`, `shell/StartScreen.module.css`, `shell/shell.module.css`, `App.module.css` — floating cards (`--float`), pills and small radii unified onto the two radius tokens; banners and session bar became rounded floating cards; popup menu uses `--float`.
- `frontend/src/App.tsx` — radar logo is now an inline SVG (was CSS radial gradients).
- A "liquid glass" attempt (blur + gradient glows) was built and then removed on request ("no gradients").

## Verified by
`npm run typecheck` and `npm run build` pass. Browser pane (mock bridge + Vite): start screen in dark, demo session in light and dark, no console errors, fonts reported loaded (Inter 400/500, Noto Sans Thai 400). Not checked: light mode after the last shape change, wide desktop width, real Thai text on screen, contrast numbers.

## Issues / not done
- Heatmap colour ramps in `src/lib/colormaps.ts` are still smooth colour blends (data colouring, not CSS gradients); left alone.
- Round dots, spinner, "i" buttons and thin progress bars stay round on purpose.
- Fonts come from npm packages; Anthropic Sans can't be used (proprietary).

## Next
1. Check light mode and a wide window once more; fix anything off.
2. Resume the paused pi-bridge task (see CONTEXT.md).

**Uncommitted work:** no (this report and the CLAUDE/ updates are new; the code is pushed, commit `65c8d3a`)
