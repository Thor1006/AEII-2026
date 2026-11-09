# Report: git check, a map of every file, and an optimization plan

<!-- Filename: YYYY-MM-DD-HHMM-<slug>.md -->

**Date:** 2026-11-08 23:55 · **Result:** ✅ done (check and map; the optimization plan waits for your OK) ·
**Plan:** [plans/2026-11-08-codebase-optimization.md](../plans/2026-11-08-codebase-optimization.md) (proposed)

## Goal
The user asked for three things:
- "check the git then come back and tell me what's not in the right shape";
- "a diagram to cooperate each file to each part and link those block part into a full system diagram";
- "an optimization solution to the whole code base".

## What changed
- **System map page:** "TrueRehab-RF System Map", https://claude.ai/artifact/LY2VUitK2dgooDYfjaW4FD. It's private: teammates
  can't open it until you share it from the page's Share menu.
  - All 353 files on `main`, plus the 6 that exist only on the v0.3 branch, each in exactly one of 12 parts.
  - Figure 1 shows how data moves. Figure 2 shows which Python parts borrow each other's code.
  - Every file gets a one-line role and, where it applies, a flag from this check. A search box finds any file.
- **`CLAUDE/plans/2026-11-08-codebase-optimization.md`** (new, status proposed).
- **This report**, and `CLAUDE/CONTEXT.md`.
- **Git:** this worktree's branch `claude/codebase-audit-diagram-786f9c` was moved forward from `main` (`3eb5887`) to the
  v0.3 tip (`b1cd6f3`). Then these notes sit on top of v0.3's CONTEXT.md and won't conflict with it. No new commit,
  nothing pushed.
- **No code changed.**

## Not in shape: git
| What | Evidence | Plan step |
|---|---|---|
| New work not on main | `wifi-pause-fixes` (Pi set v0.3, `b1cd6f3`, 27 files) is pushed but not merged: 1 commit ahead of `main`. Your main folder is on that branch. | 0.1 |
| Old worktree with unsaved work | `.claude/worktrees/project-build-setup-c2eb20`, branch at `ff70b11` (17 Oct), 39 commits behind `main`, none ahead. Untracked: `truerehab-rf/` (1.4 MB: bridge, dashboard, docs, tests) and a plan; `.claude/launch.json` edited. | 0.2 |
| Old stash | `stash@{0}`, 4 Nov 21:51, "IMU local edits (two buses, clone driver) before syncing 660e66d": 3 IMU files. The rewrite `8e5b6db` replaced them. | 0.3 |
| Big file with a typo | `TrueRehub-RF .pdf`, 10.9 MB, added on 3 Nov by the teammate: more than half of the 18 MB of git data. Not on the read-only list. | 0.4 |
| Line endings | No `.gitattributes`. `message-2.txt` is CRLF, and a teammate commits from Windows. | 0.5 |
| Generated files in git | `sandbox/out/sim_dataset.npz` (2.3 MB); `model/calib/real_stats.json` (~300 KB per recalibration); 10 PNG outputs | leave; don't add more |
| Nothing checks a push | No CI; every check is run by hand. | 3.20 |

Fine:
- 55 commits on `main`, in a straight line apart from two sync merges. Authors: Thor1006 (48) and KINKIN-007 (10).
- No secrets file was ever committed; only the two `wifi_secrets.example.h`.
- `git count-objects` reports "garbage": it is this worktree's empty `refs` folder, made by the app. Harmless.

## Not in shape: tests
Run on 8 Nov around 23:30, with the main folder's venvs, on this worktree (`main`) and on a clean copy of the v0.3
branch (`git archive`).

| Suite | `main` | v0.3 branch |
|---|---|---|
| model | 65 pass, 7 skipped (real recordings not here), **1 fail**; 70 s | not changed on v0.3 |
| recorder | 13 pass, **1 error** | 15 pass, **1 error** (same) |
| pi-bridge | 41 pass, 10 skipped, **1 error** | 44 pass, 10 skipped, **1 error** (same) |
| radar-lab, Encoder 0.1 | 6/6, 17/17 | not changed |
| Windows viewer packets, room map, Drive geometry | 17/17, 11/11, 11/11 | not changed |
| frontend | typecheck, i18n (512 pairs), session report, HMAC, auth, build: all pass | all pass, plus the new playout check (514 pairs) |

The 3 problems are in the tests, not in the product code. Each one depends on what this Mac has:
- **model `test_synth` (sync):** it passes in your main folder, where the recordings are, and fails on a clean copy
  (pose sync 16.5 ms off, limit 15).
  - Measured on 12 fake people without the recordings: median 3.3 ms, max 16.5 ms, 2 of 12 over the limit.
  - Half a 30-fps webcam frame is 16.7 ms, so the limit is tighter than the camera allows.
  - The fake radar background and the webcam delay share one random stream. So the result flips with the files on
    disk.
- **recorder `test_pose`:** errors when the git-ignored 9.4 MB pose model isn't downloaded.
- **pi-bridge `test_protocol`:** an import error without websockets. The 9 other websocket tests skip properly.

Not run:
- Phisit's backend tests: fastapi isn't installed.
- The Windows viewer's HTTP test: it needs that viewer running.
- The firmware builds: no `arduino-cli` on PATH. The only firmware change since the 5 Nov builds is v0.3's
  `myoware_record`, which its report says compiled.

Static scan of all 92 Python files: no syntax errors, 3 unused imports.

## Not in shape: structure
- **Path tricks instead of packages:** `model/trnet/paths.py`, `pi-bridge/truerehab_bridge/repo.py`,
  `recorder/rec/radar_lab.py` and `deploy/pi/selftest.py` add each other's folders to `sys.path`.
- **A viewer used as a library:** the recorder and the bridge `from view import …` (`radar-lab/view.py`) to start and
  stop the radar. `view` is a generic name to find on a path.
- **Protocol 1.2 is written twice** (`protocol.ts` 342 lines, `protocol.py` 337 lines). Nothing checks that they
  match.
- **Two TI radar parsers:** `radar-lab/radarlab`, and the Windows demo's own in `sandbox/radar-live-viewer/server.py`.
- **Two boot-service files:** `pi-bridge/truerehab-bridge.service` and `deploy/pi/truerehab-bridge.service.in`.
- **Four venvs:**
  - model 13 MB, pi-bridge 47 MB, recorder 275 MB, radar-lab 289 MB;
  - three of them use the Mac's global Python 3.14 packages (PyTorch 2.14.1, numpy 2.5.3);
  - only pi-bridge, `deploy/pi` and Phisit list their requirements;
  - no Mac venv has websockets: that's by choice, it lives in the SSD's test venv.
- **Two dashboards:** `frontend/` (React 18) and `Phisit/` (React 19). Still an open question.
- **Large single files:**
  - the IMU firmware, 1,487 lines;
  - `trnet/synth.py`, 647 lines; `check_bridge.py`, 645 lines;
  - the i18n catalog, 88 KB, inside a 356-KB JavaScript bundle.

## Not in shape: docs and records
- `model/README.md` still says "battery + Bluetooth" for the MyoWare; it uses Wi-Fi since 7 Nov.
- `recorder/README.md` still says:
  - "MyoWare sEMG (Bluetooth)" in its diagram;
  - "Not compiled or run yet";
  - "MyoWare record sketch: not run on hardware yet".
  It ran over Wi-Fi on 7 Nov.
- The mock server's header says protocol 1.1.
- `deploy/pi/config.pi.toml` has sEMG off "until the MyoWare runs firmware/myoware_record". It does since 7 Nov.
- `CONTEXT.md` called v0.3 "uncommitted". It is committed and pushed; fixed in this update.
- 8 plan statuses are out of date:
  - `2026-10-05-ml-plan-and-stack` and `2026-10-07-fmcw-sandbox`: still "approved";
  - `2026-10-10-multi-kit-identity`: "proposed" since 10 Oct;
  - `2026-10-11-easier-ui-and-pi-bridge` and `2026-10-12-kit-pairing-key`: still "untested";
  - `2026-10-18-awr2944-no-dca` and `2026-10-18-hardware-procurement-options`: "not ordered";
  - `2026-11-08-points-and-finer-heatmap`: "built", which isn't a template status.

## Speed (nothing urgent)
- The pipeline takes 0.53 s per 75-s session.
- The network takes 0.32 ms per frame on the Mac GPU, against a frame every 16.7 ms.
- The radar ran at 60 fps with 0 missing.
- v0.3 already made the dashboard stream 5× lighter.
- The model suite's 70 s is mostly one test. The Pi's speed isn't measured yet.

## Verified by
- **Git:**
  - `git status`, `branch -a -vv`, `worktree list`, `stash list/show`, `count-objects`, `log --graph --all`;
  - scans of all history for big files and secret file names.
- **Tests:**
  - every suite on both copies;
  - the model failure run again with and without the recordings: pass, then fail;
  - the 12-person sync spread.
- **Map:**
  - the generator fails if a file isn't in exactly one part: 359 = 353 + 6;
  - both figures were drawn to PNG with Quick Look and checked by eye. One fix: issue badges only on each part's main
    box.

## Issues / not done
- Nothing is fixed yet: the plan waits for your OK.
- The map is a snapshot of 8 Nov. Its generator is in this session's scratchpad until plan step 17 puts it in the repo.

## Next
1. Read the map and this report. Then choose where to start in the plan. Phase 0 needs your yes for each git step.
2. Tomorrow's v0.3 Pi check comes first; merging v0.3 into `main` (step 0.1) follows it.

**Uncommitted work:** none: committed on 2026-11-09 with the Phase 1 work on branch `claude/codebase-audit-diagram-786f9c`, and pushed.
