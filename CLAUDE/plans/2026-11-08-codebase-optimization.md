# Plan: optimize the whole codebase (git, tests, structure, environments)

<!-- Filename: YYYY-MM-DD-<slug>.md -->

**Status:** Phase 1 done (2026-11-09, [report](../output/2026-11-09-1525-phase1-honest-tests.md); approved by the user: "Yes, Phase 1"; item 6 done without changing the generator, see the report). Phases 0, 2 and 3 still proposed. Found on the way and fixed with the user's OK: the bridge's sEMG health showed a false "no samples for 3 s" right after each reconnect ([report](../output/2026-11-09-1555-semg-health-fix.md)). New for step 0.1: GitHub's `main` has 2 teammate commits (presentation notes in CONTEXT.md and DECISIONS.md) that v0.3 lacks, so that merge needs those two files merged by hand.
**Date:** 2026-11-08

## Why
The user asked: "check the git then come back and tell me what's not in the right shape", a diagram of every file in
its part, and "an optimization solution to the whole code base". The audit is in the
[report](../output/2026-11-08-2355-git-audit-system-map.md). The map of all 359 files is the page
"TrueRehab-RF System Map" (https://claude.ai/artifact/LY2VUitK2dgooDYfjaW4FD).

**Speed is not the problem.** The data pipeline takes 0.53 s for a 75-s session. The network takes 0.32 ms per frame
on the Mac GPU, and a frame arrives every 16.7 ms. The radar ran at 60 fps with 0 missing frames.

What costs time and risk:
1. **Git:** new work sits on a branch, and an old worktree and a stash hold forgotten work. A 10.9 MB PDF with a
   misspelled name is in git.
2. **Tests that pass only on this Mac:** 3 tests fail or error on a fresh copy. They depend on git-ignored files or on a
   package that isn't installed.
3. **Parts wired by path tricks:**
   - model, recorder and bridge push each other onto `sys.path`;
   - the radar's start/stop lives in a viewer script;
   - the WebSocket protocol is written twice by hand.
4. **Environments:** four venvs (~625 MB) lean on this Mac's global Python. model, recorder and radar-lab list no
   requirements, so nobody else can rebuild them.
5. **Drift:**
   - two READMEs still describe the MyoWare on Bluetooth;
   - there are two boot-service files;
   - eight plan statuses are out of date.

AEII is on 19–20 Nov at HKCEC. So the phases are ordered by risk. Phases 0–2 don't change what the radar, the bridge
or the dashboard do. Phase 3 changes how the Pi set installs, so it waits until after the event.

## Approach

### Phase 0: git housekeeping (with you, ~20 min; each step needs your yes)
1. **Merge Pi set v0.3 (`wifi-pause-fixes`) into `main`.** Best after tomorrow's Pi check; on the Mac its checks
   already pass. Then switch the main folder back to `main`.
2. **Old worktree `claude/project-build-setup-c2eb20`** (17 Oct, 39 commits behind):
   - it holds an untracked `truerehab-rf/` prototype (1.4 MB), an untracked plan and an edited `.claude/launch.json`;
   - you choose: copy it to the SSD, commit it to its own branch and push, or delete it;
   - then remove the worktree and its branch.
3. **Stash from 4 Nov** ("IMU local edits … before syncing 660e66d"): the IMU rewrite (`8e5b6db`) replaced it.
   I show you its diff; drop it on your OK.
4. **`TrueRehub-RF .pdf`** (10.9 MB, added by the teammate on 3 Nov):
   - ask the teammate what it is;
   - if it's a newer poster or proposal, rename it without the typo and the space, and add it to the read-only list;
   - don't rewrite history: the teammate would have to clone again.
5. **`.gitattributes`:** LF for text, CRLF only for `.ps1`, binary for pdf/docx/png/npz. Then commits from Windows
   can't flip line endings.

### Phase 1: tests that give the same answer on any computer (~1–2 h)
6. **`model/tests/test_synth.py`, `test_pipeline_finds_the_planned_reps_and_delays`.** Measured on 12 fake people
   without the recordings: the pose sync error has a median of 3.3 ms but reaches 16.5 ms; 2 of 12 exceed the 15-ms limit.
   - Half a webcam frame at 30 fps is 16.7 ms, so 15 ms is tighter than the camera allows.
   - Whether the test passes depends on random draws, and those change when the recordings are on disk: the fake radar
     background and the webcam delay share one random stream.
   - Fix: give the background its own random stream, and set the limit from the pose frame time (half a frame plus
     the jitter).
7. **`recorder/tests/test_pose.py`:** skip with a reason when the pose model file isn't downloaded. It already skips
   without mediapipe.
8. **`pi-bridge/tests/test_protocol.py`:** skip with a reason when websockets isn't installed, like the 9 other bridge
   tests that need it.
9. **One command for every check: `scripts/check_all.sh`.**
   - It runs each suite with its own Python, then the front-end checks and the build.
   - It prints one table at the end.
   - `--clean` runs everything on a fresh `git archive` copy, so local data can't hide a failure. That is how #6 was
     found.
10. **Make `test_overfits_a_tiny_batch` fast** without weakening what it checks. It took 41 of the suite's 53 s on
    5 Nov; the suite now takes 70 s.

### Phase 2: remove drift risks, small and safe (~2–3 h; fine before the event)
11. **Radar control into the library.**
    - Move `open_serial`, `cli_send`, `send_cfg` and `stop_radar` from `radar-lab/view.py` to
      `radar-lab/radarlab/control.py`.
    - view.py, the recorder and the bridge import them from there.
    - Same functions, same bytes sent to the radar.
12. **Protocol twin check.** A test reads the version, message types and command names from
    `frontend/src/sensor/protocol.ts` and `pi-bridge/truerehab_bridge/protocol.py`. It fails when they differ.
13. **One boot service.** Keep `deploy/pi/truerehab-bridge.service.in`, which the installer uses. Remove
    `pi-bridge/truerehab-bridge.service` and point its README at the template.
14. **Leftovers skipped on 5 Nov:**
    - `model/demo.py` reuses `trnet/inference.py`;
    - remove `_quiet()` in `trnet/contract.py` and the ResourceWarning filter in `model/tests/_util.py`;
    - remove 3 unused imports.
15. **Docs:**
    - `model/README.md` and `recorder/README.md`: the MyoWare uses Wi-Fi since 7 Nov, and the record sketch has run;
    - the mock server's header: protocol 1.2;
    - the sEMG default in `deploy/pi/config.pi.toml`: you decide, on or off.
16. **Plan statuses:** close or correct the 8 plans listed in the report.
17. **Keep the map current.** Put the map generator in the repo as `scripts/system_map.py`, so the page can be rebuilt
    after changes.

### Phase 3: after AEII, installable parts, one environment, CI (~½ day + a Pi set re-test)
18. **Packages instead of path tricks.**
    - A `pyproject.toml` for radarlab, rec, trnet and truerehab_bridge, installed in editable mode.
    - Remove the four `sys.path` inserts.
    - `build_bundle.py` and `install.sh` install the same packages on the Pi.
    - Rebuild the set as v0.4 and re-test it from the SSD.
19. **One dev environment.** A single repo `.venv` from a pinned `requirements-dev.txt` replaces the four venvs. A
    teammate sets up with one command. Installs need your OK and a place (Mac or SSD).
20. **CI.** A GitHub Actions workflow runs `check_all.sh --clean` on every push, with CPU PyTorch. It would have caught
    #6 the day it appeared.

### Not proposed
- Rewriting git history to drop the PDF: it breaks the teammate's clone.
- Merging `Phisit/` into `frontend/`: a team decision, still open.
- Changing the Windows viewer's own parser: it's the teammate's verified demo. Offer `radarlab` only if they want it.
- Speed work on the Pi before a Pi has run the bridge.

## Files touched
- **Phase 0:** `.gitattributes` (new). The rest is git only: branches, the old worktree, the stash.
- **Phase 1:**
  - `model/tests/test_synth.py`, `model/trnet/synth.py` (separate random stream for the background);
  - `model/tests/test_dataset_train.py`, `recorder/tests/test_pose.py`, `pi-bridge/tests/test_protocol.py`;
  - `scripts/check_all.sh` (new).
- **Phase 2:**
  - `radar-lab/radarlab/control.py` (new), `radar-lab/view.py`, `recorder/rec/radar_lab.py`,
    `pi-bridge/truerehab_bridge/providers/radar.py`;
  - `pi-bridge/tests/test_protocol_twins.py` (new);
  - `pi-bridge/truerehab-bridge.service` (removed), `pi-bridge/README.md`;
  - `model/demo.py`, `model/trnet/contract.py`, `model/tests/_util.py`, `model/trnet/inference.py`,
    `recorder/pose_check.py`, `sandbox/Encoder_0.1/frame_encoder.py`;
  - `model/README.md`, `recorder/README.md`, `frontend/mock-server/server.ts`, `deploy/pi/config.pi.toml`;
  - 8 files in `CLAUDE/plans/`;
  - `scripts/system_map.py` (new).
- **Phase 3:**
  - `pyproject.toml` files (new), `requirements-dev.txt` (new);
  - `model/trnet/paths.py`, `pi-bridge/truerehab_bridge/repo.py`, `recorder/rec/radar_lab.py`;
  - `deploy/pi/build_bundle.py`, `deploy/pi/install.sh`, the READMEs' setup sections;
  - `.github/workflows/checks.yml` (new).

## Risks / needs OK
- **Phase 0** changes branches and pushes to GitHub. Your yes for each step, and I explain each git command first.
- **Can't be undone:** deleting the old worktree's folder or the stash. Only after you've looked.
- **#11** touches how the recorder and the bridge start and stop the radar.
  - Check it with the simulated radar tests, then one real start/stop each (power first, then USB).
  - No flashing, and no change to any radar profile.
- **Phase 3** changes how the Pi set installs. Only after AEII, and only after v0.4 passes `selftest.py` and
  `check_bridge` from the SSD.
- Nothing in this plan flashes firmware or changes the radar configuration.

## How we'll verify
- **Every phase:** `check_all.sh` on this folder and with `--clean`, all green.
- **Phase 0:**
  - `git log main..wifi-pause-fixes` prints nothing;
  - `git worktree list` shows only active worktrees;
  - `git stash list` is empty.
- **Phase 2:** one real radar start/stop with the recorder, and one with the bridge.
- **Phase 3:** Pi set v0.4 from the SSD passes `selftest.py` and `check_bridge`; CI is green on GitHub.
