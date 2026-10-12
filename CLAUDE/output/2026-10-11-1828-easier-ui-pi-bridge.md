# Report: Easier dashboard + Pi bridge (protocol 1.1)

**Date:** 2026-10-11 18:28 · **Result:** ⚠️ partial (paused by user before Python testing) · **Plan:** [2026-10-11-easier-ui-and-pi-bridge.md](../plans/2026-10-11-easier-ui-and-pi-bridge.md)

## Goal
Make the dashboard easy to set up and read, and make sure the Pi sends everything the web needs.

## What changed
- **Protocol 1.1** (`frontend/src/sensor/protocol.ts`, `codec.ts`): `hello` + manifest (radar views, scores, aux channels with device links, events, actions, commands), `command`/`ack`, richer `status` (devices, session, CPU temp, viewers), `kitId`/`sessionId` in the envelope. v1 senders still work.
- **Frontend:**
  - start screen with three cards (Pi / demo / recording) and "More options"
  - auto-connect when the page is served by the bridge or opened with `?pi=`
  - recent addresses; plain-language "can't reach the Pi" checklist
  - connection pill ("Signal good"), device strip, session bar (start form, timer, markers, stop confirmation)
  - Session/Technical views; ⓘ explainers on every panel
  - stream-health and connection widgets; labels come from the manifest (`state/describe.ts`)
- **Mock** (`mockData.ts`, `mock-server/server.ts`): hello, sessions, commands, `BREAK=nohello|badframe|noscores` modes. Fixed a bug where side effects were sent out of sequence order and showed as 2 false "lost" messages per command.
- **New `pi-bridge/` (Python)** covers:
  - server: hello/status/commands, per-viewer buffers, provider supervision
  - static web server + `/truerehab-bridge.json`
  - providers: synthetic, Arduino serial, radar template
  - `check_bridge.py` conformance checker, unit tests, example config, systemd unit, README

## Verified by
- `npm run typecheck` + `npm run build` pass.
- Browser (mock bridge):
  - start screen renders; an unreachable address shows the help checklist
  - `?pi=localhost` connects with no typing; name and devices come from `hello`
  - Start session → ack → session bar and rep target update, fatigue resets
  - Technical view: all 8 streams arriving, connection numbers shown
- Sequence-gap script: no gaps after the ordering fix.

## Issues / not done
- **Python side not run at all.** Packages (websockets, numpy, pyserial) were not installed; the user paused here. Only a syntax parse was done. Unit tests, bridge startup, `check_bridge.py` (incl. against `BREAK=` modes) and the bridge-served page are untested.
- Not checked: phone width of the new screens, dark mode of the new screens, Replay/Arduino on the new start screen.

## Next
1. With OK: `python3 -m venv pi-bridge/.venv && pi-bridge/.venv/bin/pip install -r pi-bridge/requirements.txt`.
2. Run `python -m unittest discover -s tests`, start the bridge, run `check_bridge.py --commands` against it and against `npm run mock` (+ each `BREAK=` mode, which must FAIL).
3. `npm run build`, open `http://localhost:8080` from the bridge: it must connect by itself. Check phone width.

**Uncommitted work:** yes, not a git repo.
