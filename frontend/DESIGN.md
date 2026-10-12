# TrueRehab-RF design rules

Short rules for anyone (human or AI) changing the UI. Tokens live in `src/styles/theme.css`, so change them there and not inline.

## Look
- Neutral greys plus **one** blue accent (`--accent`). Status colours (`--good/--warn/--bad`) are for status only.
- Font: Inter (Latin) + Noto Sans Thai. Weights 400/500, and 600 only for small dense labels.
- Flat surfaces. Rounded corners come from `--radius` / `--radius-sm`. Floating shadow (`--float`) only on things that really float: the nav, the demo card, popovers and dashboard panels.
- Gradients only for data (heatmap and colour-map legends). Never decorative.

## Landing page (`src/home/`)
- Show the product: the live demo sits right under the hero, above the fold.
- Copy is plain and specific to rehab and radar. Short sentences. No hype words.
- Claims must match the proposal. Never imply diagnosis or replacing the physio.

## Don't (the usual AI-template tells)
- Uppercase, letter-spaced "eyebrow" labels above headings ("STEP 1", "FEATURES"). Dense dashboard panel titles are the one exception.
- Rows of identical shadowed feature cards with icon tiles. Use a list, a table, or the real product instead.
- Glows, blurred colour blobs, purple/neon gradients, glassmorphism.
- Decorative status pills ("New", "Beta", "AI-powered"). A pill must show real state, such as the connection status.
- Stock or generic illustrations. Use real radar output (heatmap, scores) or nothing.
- Emoji as icons.
