# Report: Ready to train on the Windows PC

**Date:** 2026-11-15 12:05 · **Result:** ✅ done on the Mac side (⚠️ the scripts have never run on Windows) · **Plan:** [2026-11-15-train-on-windows](../plans/2026-11-15-train-on-windows.md)

## Goal
Train the model and run the rep counter on the Windows PC from the PortableSSD, because the Mac was unstable on 14 Nov.

## What changed
- `model/trnet/training.py` `pick_device`: `auto` = NVIDIA GPU (`cuda`), else Apple GPU, else CPU. `train.py` help
  text updated; the report shows the device and the torch version.
- UTF-8 on all 33 text reads and writes in `model/` and `recorder/rec/` (Windows' old code page can't write
  the reports' `≈`, `±`). On Windows, `trnet/paths.py` makes the console print UTF-8 and never crash on a character.
  `radar-lab/` was not touched (its one `open` reads plain-ASCII radar configs).
- `model/windows/setup.ps1` + `setup.cmd`:
  - finds Python 3.10+ (else says where to get it);
  - makes `model\.venv` and installs numpy and PyTorch: the CUDA build that the `nvidia-smi` driver allows,
    newest first, falling back to the CPU build;
  - prints the device and runs the tests.
- `model/windows/train.ps1` + `train.cmd <sessions> [-CopyFirst] [-Device] [-Epochs]`:
  - optional robocopy of the sessions to `model\data\sessions` first;
  - runs `train.py` and `armtrack.py`;
  - copies the new run folders to `<SSD>\truerehab-runs\`.
- The `.cmd` files bypass the execution policy for that one run only. `model/windows/.gitattributes` keeps the
  scripts byte for byte (CRLF).
- `model/tests/test_windows.py` (3 tests): the device order; an AST scan for text I/O without `encoding=`
  (checked that it catches a bare `read_text()` and `open("b", "w")`); the scripts are plain ASCII, and `.cmd` is CRLF.
- `model/README.md` "On Windows": the `git archive` command for the zip, then setup and train.

## Verified by
- `bash scripts/check_all.sh`: nothing failed (model 89 tests).
- The kit zip, built from a temporary snapshot of the working tree (branch and staging area untouched):
  - 1.8 MB; contains `model/`, `recorder/`, `radar-lab/` only (no recordings, `.venv`, `data/` or `runs/`);
  - `.cmd` keeps CRLF;
  - unpacked into a clean folder, its own tests pass: 89, 7 skipped (they need the recordings).
- Not run on Windows, and the PowerShell is not syntax-checked (no PowerShell on this Mac). No training on the Mac.

## Issues / not done
- **The first run on the PC is the real test.** The CUDA build names (`cu130` … `cu118`) are tried newest first
  against the driver. If none fits, the CPU build is installed.
- `model/windows/AGENTS.md`: written by a forked side session at the user's request (instructions and rules for an AI
  agent on the PC). It was checked against the scripts' options (they match), kept in the kit and mentioned in `model/README.md`.
- The zip for the PC must be built from a commit. Until this is committed, `git archive HEAD` would give the old code.

## Next
1. Commit (ask), then on the Mac: `git archive --format=zip -o /Volumes/PortableSSD/truerehab-train-<commit>.zip HEAD model recorder radar-lab`.
2. On the PC: unzip to `C:\truerehab`, `model\windows\setup.cmd`, then `model\windows\train.cmd E:\truerehab-sessions -CopyFirst`.

**Uncommitted work:** yes
