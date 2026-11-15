# Instructions for an AI agent on the Windows PC (e.g. Phisit's agent)

Your job: set up the TrueRehab-RF model on this Windows PC, train it on the real recordings from the
PortableSSD, and leave the results on the SSD for the team. Use only the scripts in this folder.

## Steps
1. **Find the SSD:** in File Explorer, find the drive named `PortableSSD` and note its letter (e.g. `E:`). The
   recordings are in `<letter>:\truerehab-sessions`. If the drive isn't there, stop and tell the person.
2. **Setup (once):** from this folder, run `setup.cmd` (or `powershell -ExecutionPolicy Bypass -File setup.ps1`).
   - It needs Python 3.10 or newer. If it stops for that reason, tell the person to install Python from
     python.org. Don't install it yourself.
   - It downloads PyTorch into `model\.venv` (about 2.5 GB with an NVIDIA card, about 200 MB without). Tell the
     person about the download before you start it.
   - It must end with the model's tests passing. If it stops, report its last 30 lines and stop.
3. **Train:** `train.cmd E:\truerehab-sessions` (use the real drive letter). If the SSD has dropped out before,
   use `powershell -ExecutionPolicy Bypass -File train.ps1 -Sessions E:\truerehab-sessions -CopyFirst`.
   - This runs the training (`train.py`) and the radar rep counter (`armtrack.py`).
   - Time: about 10 min with an NVIDIA GPU, about 1–2 h on the CPU.
4. **Report:** the run folders get copied to `<letter>:\truerehab-runs\`. Give the person the paths of the
   reports (`report.md`), and quote:
   - from the training report, the "Mean over the left-out people" table and which device it used;
   - from the arm report (`arm_...`), the "All sessions together" lines.

## Rules
- **Read-only recordings:** never edit, move, rename or delete anything in `truerehab-sessions`.
- **Names:** session folders contain people's first names. Never copy them into messages, commits or anything that
  leaves this PC. Reports already use S01, S02 …
- **Install and run nothing else:** no other pip packages, no global Python changes, no system settings. Change
  no code. If something fails, report it, don't patch it.
- **Hardware:** don't touch the radar, the MyoWare or the IMU, and don't run the radar viewer
  (`sandbox/radar-live-viewer/`) or anything that opens COM ports. Training doesn't need them.
- **Git:** don't commit or push anything from this PC.
- **Scope:** it's fine to say "the model is no better than the mean". Report the numbers as they come out; the
  results are only a hint with 5 people.

## What success looks like
`setup` ends with the tests passing; `train` ends with two report paths under `truerehab-runs\`. For comparison,
the Mac's run on 14 Nov had 5 people and 687 reps, with fatigue MAE 0.193 vs 0.217 for the mean.
