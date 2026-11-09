# Report: the bridge no longer says "no sEMG samples for 3 s" right after a reconnect

<!-- Filename: YYYY-MM-DD-HHMM-<slug>.md -->

**Date:** 2026-11-09 15:55 · **Result:** ✅ done (pushed on branch `claude/codebase-audit-diagram-786f9c`, not merged) · **Plan:** none (found during
[Phase 1](2026-11-09-1525-phase1-honest-tests.md); the user: "Yes, fix it")

## Goal
Fix the false sEMG health error before today's Pi test.

## What changed
- **`pi-bridge/truerehab_bridge/providers/emg.py`, `health()`:**
  - for the first 3 s after a (re)connect without a sample, it says "Connected, waiting for sEMG samples…" (state
    "missing", the same state as while reconnecting);
  - only after 3 s without a sample since connecting does it say "Connected, but no sEMG samples for 3 s…" (error).
  - Before, every reconnect reset the last-sample time, and that error showed at once, until the first sample arrived.
- **`frontend/src/i18n/catalog.ts`:** the new message in Thai and Hong Kong Chinese, worded like the entries around it.
- **`pi-bridge/tests/test_emg_provider.py`:** `test_just_connected_is_waiting_not_an_error` checks three moments:
  just connected (waiting), 3.5 s with nothing (error), and samples arriving (ok).
- The radar provider doesn't have this problem: its health comes from states its reader sets, with no
  time-since-last-frame check.

## Verified by
- **The new test:**
  - passes with the fix;
  - fails on a fresh export of the last commit, with exactly the old false error.
- **The bridge suite:** 10 runs in a row, all OK (67 tests, 14 skipped without websockets).
- **The dashboard's translator:** the message comes out right in English, Thai and Hong Kong Chinese, also inside a
  joined health line.
- **`bash scripts/check_all.sh --clean`:** nothing failed; the i18n check counts 515 translation pairs, one more
  than before.

## Issues / not done
- **Not on the Pi yet.** The v0.3 set already built (`truerehab-pi-0.3.0-20261108-b1cd6f3`) doesn't have the fix. To
  include it:
  1. move the main folder's `wifi-pause-fixes` branch up to the fix's commit (the first one on this branch after
     `b1cd6f3`; it holds only the fix);
  2. rebuild the set.
- **New on GitHub's `main`:** 2 commits from the teammate (8 Nov, 23:07): presentation notes in `CLAUDE/CONTEXT.md`
  and `CLAUDE/DECISIONS.md`. `main` doesn't have v0.3. Merging v0.3 and this work into `main` will need those two
  files merged by hand (plan step 0.1).

## Next
1. To use the fix today: bring its commit into the main folder, rebuild the Pi set, then the Wi-Fi check.
2. Then plan Phase 0 (the merge, with the teammate's notes) or Phase 2.

**Uncommitted work:** none: committed on branch `claude/codebase-audit-diagram-786f9c` (the fix is its own commit) and pushed.
