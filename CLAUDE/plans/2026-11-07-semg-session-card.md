# Plan: an sEMG result card in the dashboard's Session view

**Status:** proposed
**Date:** 2026-11-07

## Why
The user: "can you also make the dashboard show sEMG result?", then chose "Session view card".
Today sEMG only shows as raw charts in the Technical view (envelope, median frequency).

## What the card shows ("Muscle (sEMG)", Session view, next to "How it's going")
1. **Muscle working now:** a bar from the live envelope, scaled to this session's own range (quiet level → strongest
   so far). Words: "Resting" / "Working".
2. **Fatigue sign:** the median frequency now vs. the start of the session, e.g. **"−12 % since the start"**:
   - start = median of the first ~10 s of median-frequency values after Start (only working windows arrive);
   - now = median of the last ~5 s of values;
   - words (placeholders, like the model's labels): under 5 % "Steady", 5–10 % "Starting to tire",
     over 10 % "Tiring". The model's labels count a 20 % drop as full fatigue.
3. **Small trend line** of the median frequency over the session, with the start level marked.
4. **Honest states:** "Waiting for movement" (no values yet), "No sEMG sensor" (not announced / device off,
   with the bridge's own message). A note: "Measured from sEMG, not the AI model".

Without a running session, the start level is taken from the first values after connecting.

## Where
- `frontend/src/state/semg.ts` (new): the numbers above from the store's `emg_env` / `emg_mdf` buffers, as pure
  functions; reset at session start.
- `frontend/src/widgets/SemgWidget.tsx` (new) + register in `widgets/index.ts`; add the panel to the Session view in
  `dashboard.config.ts` (layout: next to "How it's going").
- Texts in English, Thai and Traditional Chinese (`catalog.ts`); `check-i18n` asserts for the new messages.
- The aux buffer may need to hold a whole session of median-frequency values (4/s): check `historyLength` and raise
  it for that channel only if needed.

## Test / verify
- Unit checks of `semg.ts` in the existing node check style (start level, drop %, reset, no data).
- Typecheck, `check-i18n`.
- Browser: the real bridge + `fake_myoware.py` (its fake muscle tires rep by rep, so the drop should grow), in all
  3 languages; then a screenshot. If the user wears the real MyoWare at that time, also with the real board.
- Commit and push as one chunk.

## Risks / limits
- The words and thresholds are placeholders (need a physiotherapist), like the model's labels.
- Median frequency only means something with good electrode contact and during movement.
- No new protocol fields; the bridge is unchanged.
