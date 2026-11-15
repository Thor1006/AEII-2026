# Plan: Train the model on the Windows PC

**Status:** done
**Date:** 2026-11-15

## Why
The Mac was unstable on 14 Nov, so training (and the rep counter) should run on the Windows PC, reading the
sessions straight from the PortableSSD. exFAT works on Windows as it is.

## What I found (model/ code, 15 Nov)
- Only **numpy and PyTorch** are needed (plus the standard library). No Mac-only code in training; the DataLoader
  uses no worker processes, so Windows' process start-up rules don't matter.
- **Blocker 1, GPU:** `trnet/training.py` `pick_device` only knows Apple's GPU (`mps`) or the CPU. On Windows it
  would always use the CPU, even with an NVIDIA card. On the CPU a run that took 7 min on the Mac's GPU could take
  roughly 1–2 h (a training step was ~15× faster on the Apple GPU than on the CPU).
- **Blocker 2, text encoding:** 10 places read or write text files (`meta.json`, `report.md`, ...) without saying
  UTF-8. On Windows they would use the old Windows code page, and the reports contain characters such as `≈`, `±`
  and `—`, so writing them would crash. The Windows console can also fail to print them.
- **Paths:** the examples say `/Volumes/PortableSSD/...`. On Windows the SSD gets a drive letter
  (e.g. `E:\truerehab-sessions`). The code itself uses `pathlib`, so passing the Windows path works.

## Approach
1. **Code fixes (small, on this Mac):**
   - `pick_device`: `auto` = NVIDIA GPU (`cuda`) if there is one, else the Apple GPU, else the CPU; `--device cuda`
     allowed. `train.py` prints which one it uses.
   - `encoding="utf-8"` on the 10 text reads and writes.
   - The run report records the device (already does) and the torch version.
2. **Two PowerShell scripts in `model/windows/`:**
   - `setup.ps1`: checks Python 3.10–3.13 is installed (if not, it says where to get it and stops). It makes
     `model\.venv` and installs numpy + PyTorch: the CUDA build if `nvidia-smi` finds an NVIDIA card, else the CPU
     build. Then it runs the model's tests. The download is about 2.5 GB with CUDA (≈200 MB without). **You run
     it**, so nothing is installed without you.
   - `train.ps1 -Sessions E:\truerehab-sessions`: sets UTF-8 mode, then runs `train.py` and `armtrack.py` and
     prints where the reports are.
3. **Getting the code onto Windows, without git there:** one command on the Mac,
   `git archive` → `truerehab-train-<commit>.zip` on the SSD. It holds only `model/`, `recorder/` and `radar-lab/`
   as committed: no recordings, no `.venv`, no old runs. On Windows, unzip it to e.g. `C:\truerehab`, then run
   `setup.ps1`. (The SSD's old `AEII-2026` folder is left alone.)
4. **Results back:** each run's folder (`model\runs\...`, a few MB) goes to the SSD under `truerehab-runs\`, and
   I read the report from there. The first run on Windows rebuilds the data cache (a few minutes, once).
5. `model/README.md`: a short "On Windows" section.

## Files touched
- `model/trnet/training.py`, `model/train.py`: device choice
- the files with the 10 text reads/writes (`trnet/`, `train.py`, `armtrack.py`, `check_session.py`, `recorder/rec/session.py`)
- `model/windows/setup.ps1`, `model/windows/train.ps1` (new)
- `model/tests/`: a test that `pick_device` picks the CPU on a machine without a GPU, and that `auto` prefers cuda
- `model/README.md`

## Risks / needs OK
- **I can't test on Windows from here.** The scripts will be checked for syntax only. The first real run on the PC
  is the test, so allow 30 min for it. If `setup.ps1` stops, send me its output.
- **What I don't know about the PC:** whether it has an NVIDIA GPU, and whether Python is installed. The script
  finds out either way.
- **The zip is built from the latest commit,** so anything uncommitted isn't in it. Today the only uncommitted
  files are the 3 old PDFs.
- **If the Mac's "twitching" was the SSD dropping in and out,** the cable or the drive may be the cause, and
  Windows would see the same. Copy the SSD's sessions folder to the PC's own disk first (≈ a few GB), and train
  from the copy; `checksums.py verify` doesn't help here yet, as the old sessions have no checksums.
- The Windows radar viewer (`sandbox/radar-live-viewer/`) is not touched. Don't run it at the same time as
  training if the radar is plugged in: it doesn't matter to training, but keep one thing at a time.

## How we'll verify
- On the Mac: `bash scripts/check_all.sh` passes; the zip unpacks into a clean folder and its tests pass there.
- On Windows (you): `setup.ps1` ends with the test result line; `train.ps1` makes a report that matches the Mac's
  14 Nov run (5 people, 687 reps) within the run-to-run noise.
