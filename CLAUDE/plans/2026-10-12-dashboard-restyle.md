# Plan: Dashboard restyle (Fluent-style palette, Inter, floating rounded UI)

**Status:** done
**Date:** 2026-10-12

## Why
The teal-on-dark look read as generic "AI". The user picked a Microsoft/Fluent-like direction, then asked for Inter, floating shadows, consistent rounded rectangles and no gradients.

## Approach
1. Swap all colour tokens in `theme.css` (light and dark) to Fluent-style neutrals + one blue accent.
2. Bundle Inter and Noto Sans Thai via `@fontsource` packages (user approved the install).
3. Add `--float` shadow, larger radii; apply to panels, header, cards, banners, session bar.
4. Replace gradient-drawn logo with SVG; remove the short-lived glass effect.

## Files touched
- `frontend/src/styles/theme.css`, `main.tsx`, `App.tsx`, `App.module.css`, `components/Panel.module.css`, `shell/StartScreen.module.css`, `shell/shell.module.css`, `package.json`, `package-lock.json`

## Risks / needs OK
- Installing npm packages (approved by the user).

## How we'll verify
- Typecheck, build, and screenshots in the browser pane (done; see the report).
