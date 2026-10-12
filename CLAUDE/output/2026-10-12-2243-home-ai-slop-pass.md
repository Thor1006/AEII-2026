# Report: Home page "AI slop" pass

<!-- Filename: YYYY-MM-DD-HHMM-<slug>.md -->

**Date:** 2026-10-12 22:43 · **Result:** ✅ done · **Plan:** [2026-10-12-home-ai-slop-pass](../plans/2026-10-12-home-ai-slop-pass.md)

## Goal
Check the home page against the tells in "How to Avoid AI Slop in Vibe-Coded Landing Pages" (youtube.com/watch?v=M4DNgmI7MIM) and fix the ones that apply.

## What changed
- `frontend/src/home/Home.tsx`
  - The live demo now sits directly under the hero, above the fold, and the separate "Three scores" section is gone.
  - "How it works" is a plain numbered list. No cards and no icon tiles.
  - "Why radar" is a Camera / Wearables / Radar comparison table instead of four feature tiles.
- `frontend/src/home/Home.module.css`
  - Removed the uppercase eyebrow labels ("STEP N", "LIVE DEMO") and the tile styles.
  - Added the list, table and live-dot styles.
  - On phones the table wraps, so the Radar column stays visible.
- `frontend/DESIGN.md` (new): the design rules and a "don't" list, so later edits don't drift back.
- Kept on purpose: the uppercase titles on the dashboard panels, which are dense UI labels.

## Verified by
- `npm run typecheck` and `npm run build` pass.
- Browser at 1280×900 (light) and 375×812 (dark): no console errors and no horizontal page scroll.
- The table fits in 327px on a phone.
- Pushed as `1f2dea1`.

## Issues / not done
- The video's transcript wasn't available, so the check used only the "tells" listed in its description.
- The team hasn't signed off on the comparison table wording. I wrote that copy.
- I didn't check the selected states of the Session/Technical toggle and the start screen.

## Next
1. Get team sign-off on the home page copy, including the comparison table.

**Uncommitted work:** no (except this wrap-up's own doc updates)
