# Plan: A checksum for every recording

**Status:** done
**Date:** 2026-11-15

## Why
Asked on 15 Nov "did any file get corrupted yesterday?", the only honest answer was "every file read cleanly last
night". Nothing in a session folder can prove that a file is the same as when it was written. Sessions now move
between the Pi, the PortableSSD and this Mac, and the SSD has unmounted on its own before. A damaged `radar.bin` can
still parse (the bytes inside a frame change, the frame count doesn't), so "it loads" is not enough.

## Approach
1. **Write it when recording stops.** `SessionWriter.close()` (`recorder/rec/session.py`) writes `checksums.sha256`:
   one SHA-256 line per file in the folder, in the format macOS's own `shasum -a 256 -c` reads. Then `meta.json`
   is written last and gets its own line in a second small step (meta comes last, so its hash is taken after
   it's final). The Mac recorder and the Pi bridge both stop through this function, and the bridge closes every
   sensor's file first (`server.py` stop), so every file (radar, sEMG, IMU, markers, pose) is covered, including
   files from the Pi-only IMU code, without touching it.
2. **Add hashes to the 30 existing sessions, once.** New command `recorder/checksums.py`:
   - `add <folder or sessions dir>` writes `checksums.sha256` where it's missing. It never overwrites one.
   - `verify <folder or sessions dir>` prints per session: ok / changed file / missing file / extra file / no checksum.
   These hashes record the files **as they are today**. They can't show whether something changed before today.
3. **The check reads it.** `model/trnet/check.py`: a new `files` line: "checksums ok (N files)", or a warning
   naming the changed file. Sessions without a checksum just show "no checksum". Nothing is refused.
4. **Copying.** `recorder/README.md` gets one step: after copying sessions off the SSD or the Pi, run
   `checksums.py verify` on the copy (or `shasum -a 256 -c checksums.sha256` inside one folder).

## Files touched
- `recorder/rec/session.py` — hashes in `close()`
- `recorder/checksums.py` (new) — `add` / `verify`
- `recorder/tests/` — new tests: hashes written at close; one changed byte in `radar.bin` is caught; a missing
  file is caught; `add` never overwrites
- `model/trnet/check.py` (+ a test) — the `files` line
- `recorder/README.md`, `model/README.md` — one paragraph each

## Risks / needs OK
- **Writing to the SSD:** step 2 adds one small file to each of the 30 session folders on the PortableSSD. It
  changes no existing file. I'll ask again before running it.
- **The Pi:** the bridge only gets this with the next Pi set, and a new set must not go on until the Pi-only IMU
  work is committed (open question from 14 Nov). Until then, Pi recordings get their checksum from step 2 after
  copying, which proves only that the copy step is safe from then on.
- **Time at Stop:** hashing ~100 MB on the Pi's microSD/SSD takes about 1 s. That's fine at Stop, and it runs after
  the files are closed, so no data is lost if it's slow.
- A hash shows that a file changed, not why, and it can't repair anything. Backups are a separate question.
- Small: about 1–2 hours with tests. It's not needed for the booth, so it can also wait until after AEII.

## How we'll verify
- `bash scripts/check_all.sh` (recorder, model and pi-bridge tests)
- A fake recording through the recorder (`--sim`), then `shasum -a 256 -c checksums.sha256` in its folder passes.
  Change one byte of a copy: `verify` and `check_session.py` both name `radar.bin`.
- The bridge's own recording test (fake radar + `fake_myoware.py`) produces a folder that passes `verify`.
