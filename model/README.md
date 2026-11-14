# model/ — radar-only network and its data pipeline (untrained)

Everything from a recorder session folder to scores and a recommendation, plus fake data, so all of it can be
built and tested **without sensors**: at home, at school, anywhere with this Mac.

> **Fake data tests the code, never the model.** A good score on `trnet.synth` sessions means the pipeline
> works end to end. It says nothing about real radar: the fake person, fatigue, compensation and arm
> "tremor" are invented. Only real recordings can show what the radar can see.

## Setup (once)

PyTorch 2.14.1 and numpy are already installed in this Mac's Python. The folder's own `.venv` reuses them, so
nothing is downloaded. It already exists. To make it again (e.g. on another Mac that has PyTorch):

```bash
python3 -m venv --system-site-packages .venv
```

Run the commands below from inside `model/`.

## Commands

Run all tests (73, about 30 s, no sensors needed; `bash scripts/check_all.sh` from the repo root runs every part's checks):

```bash
.venv/bin/python -m unittest discover -s tests
```

Check a recording straight after you make it (it prints what's fine, what to look at, and what it can train):

```bash
.venv/bin/python check_session.py ../recorder/data/sessions/<session folder>
```

Check every recording:

```bash
.venv/bin/python check_session.py --all
```

Train and test on 6 fake people (makes them once in `data/fake_v2`, the fake-data version; ~3 minutes on the Apple GPU):

```bash
.venv/bin/python train.py --fake 6
```

Train and test on real recordings (only sessions that pass the check are used; needs at least 3 people):

```bash
.venv/bin/python train.py --sessions ../recorder/data/sessions
```

Each left-out person is tested by a model that never saw them. To decide when to stop training, `--val` picks:
`person` (a whole other person; needs 3+ people) or `sessions` (every other person trains, and the last session of
each validates; needs 2+ sessions for someone). The default `auto` uses `sessions` below 5 people, because with 3
people a whole validation person leaves only one person to train on. Reports show people as S01, S02 … (names are
printed once on screen, never saved), the label spread per person, and a tiny ridge model on a few hand-made
radar numbers next to the network (if even that beats the mean, the radar carries the information).

Count curls from the radar alone (no learning, no wearable) and score them against the IMU's reps
(`trnet/armtrack.py`; report in `runs/arm_<date>_<time>/`):

```bash
.venv/bin/python armtrack.py --sessions /Volumes/PortableSSD/truerehab-sessions
```

It finds the arm's range from the radar (the range whose Doppler velocity repeats at curl pace), integrates that
velocity into an arm signal with no unit, and cuts reps from it with the IMU's own rep rule. On the 19 sessions of
10–14 Nov it counted 537 reps where the IMU counted 537. It can't give degrees or tell the top of a curl from the
bottom (Doppler sees speed toward the radar, not the angle). Its few fixed numbers were chosen on those same
sessions. For the dashboard: `export_dashboard.py --session <folder> --radar-arm`.

Measure the real recordings again (after new real sessions, so the fake data copies them):

```bash
.venv/bin/python -m trnet.calibrate
```

### Watch it work

Show the trained network on a fake person it never saw, as a stand-alone page
(`runs/demo/index.html`):

```bash
.venv/bin/python demo.py --person F06
```

Make a recording that the dashboard (`frontend/`) plays with the network's radar maps, scores, reps and advice:

```bash
.venv/bin/python export_dashboard.py --person F06
```

Then run `npm run dev` in `frontend/` and open the link it prints
(`http://localhost:5173/?replay=/replays/<session>.ndjson`). `--session <folder>` exports a real recording instead;
it has to pass the session check.

Reports go to `runs/<date>_<time>/report.md`; check reports to `runs/checks/`. `data/` and `runs/` are
git-ignored. The fake sessions take ~270 MB and the cache ~60 MB. Delete them any time with
`rm -rf data runs` (inside `model/`).

## What a recording needs (the protocol the pipeline expects)

1. Subject **code** (`S01`, `S02`…), never a name; the recorder refuses anything else (`TEST` for trials). Raw video
   off unless the person agreed in writing.
2. Stand still for **5 s**: this is the reference for the radar levels and the shoulder position.
3. Press **`s`**, then do **3 quick shoulder shrugs**. They are used to line up the sensors' clocks.
4. **Elbow flexion sets**: press **space** at the start of each rep. Rest at least 8 s between sets.
5. MyoWare on **battery, over Wi-Fi** (`--emg tcp://truerehab-myoware.local:3334`) while on a person (SparkFun: never
   with USB plugged in).
6. Run `check_session.py` right away, and `recorder/link_report.py` for the Wi-Fi sensors.

## How it works

| Step | File | What it does |
|---|---|---|
| Contract | `trnet/contract.py` | Input shapes, saved with the weights; loading refuses a mismatch (`v1`; older `v0-draft` files still load) |
| Radar | `trnet/radar.py` | Frames → 60-fps grid (gaps masked), angle FFT, magnitude + phase change, range-Doppler |
| Ground truth | `trnet/truth.py` | sEMG median frequency, IMU forearm angle, pose angles (training only) |
| Shrug sync | `trnet/sync.py` | Each sensor's leftover offset against the radar from the 3 shrugs |
| Reps | `trnet/reps.py` | Reps from the elbow angle (pose, else IMU), sets, smoothness (SPARC); without either, from the sEMG envelope's bursts (then only fatigue can be labelled) |
| Labels | `trnet/labels.py` | Fatigue, quality, 3 compensation flags, next-rep risk; **placeholder thresholds** |
| Pipeline | `trnet/pipeline.py` | One session → all of the above |
| Check | `trnet/check.py`, `check_session.py` | Usable or not, and why |
| Dataset | `trnet/dataset.py` | One sample = one set + the session's first 3 reps; cached `.npz`; leave one subject out |
| Network | `trnet/network.py` | 239,803 parameters (below) |
| Training | `trnet/training.py`, `train.py` | Masked losses, early stopping, per-person report vs the baseline |
| Rules | `trnet/recommend.py` | Continue / correct posture / reduce load or ROM / rest / see physio |
| Calibration | `trnet/calibrate.py` → `calib/real_stats.json` | Measured noise and timing of the real recordings |
| Fake data | `trnet/synth.py` | Fake sessions in the exact recorder format |

**Radar input per frame** (contract `v1`, 2026-11-08; 64 range bins at the recording's step: 5.94 cm with
`fullmap_awr2x44p.cfg`, 3.88 cm with the finer `fullmap_fine_awr2x44p.cfg`; 60.00 fps):
- `H [4, 64, 32]`:
  - channel 1 is the angle-FFT magnitude. The 8 azimuth antennas sit at their real columns `0,2,7,9,3,5,10,12`; 32 angle bins (zero-padded) locate peaks finely, the real resolution stays ~9°.
  - channel 2 is the phase change since the last frame (only in cells within 30 dB of the session level; 0 after a gap).
  - channels 3 and 4 are the radar's own detected points (TLV 1/7) of the last 15 frames (0.25 s) on the same grid: **height** (SNR-weighted mean z ÷ 1 m) and **presence** (points ÷ 4). The heatmap has no height of its own; the points do.
  - The points agree with the heatmap: on the real recordings, still points sit +11 dB above the rest of their range row (`check_session.py` reports it). But a still target's height jitters ±0.16–0.25 m per frame, so a 2–5-cm shrug may not show in the height layer: the real sessions decide.
- `D [1, 64, 16]`: range-Doppler magnitude.
- A rep is 128 frames (2.13 s). Longer reps are cropped around their peak.
- Reps from sEMG alone (no camera, no IMU) are a fallback: curls need a short pause between them, or they merge into one burst.

**Network:**

| Part | Parameters |
|---|---|
| Stem A (heatmap, 4 → 16 channels; pools 32 angle bins to 8) | 2,944 |
| Stem B (range-Doppler, 1 → 16 channels) | 2,512 |
| Shared CNN trunk: 128 numbers per frame | 109,600 |
| Within-rep dilated Conv1d (sees ~0.9 s), attention pooling, + duration and rest | 86,849 |
| Baseline `[v, v − mean(first 3 reps)]` → causal GRU over reps | 37,248 |
| Heads (6 outputs) + training-only extra head (4) | 650 |

Run `use_phase=False` in the contract to switch the phase channel off and compare (Stem A loses 144 weights); `use_points=False` drops the two point layers (288 weights), `angle_bins=16` the finer grid (no weights).

**Labels** (thresholds in `PLACEHOLDER_THRESHOLDS`, to agree with a physiotherapist):
- **Fatigue:** MDF drop vs the first 3 reps, where a 20 % drop = 1.0. The MDF is smoothed over 3 reps, because one 2-s rep scatters ~5 %.
- **Quality:** ROM, peak speed and smoothness, each compared with the first 3 reps.
- **Compensation flags:**
  - shrug: the shoulder rises more than 2 cm beyond baseline;
  - lean: the trunk leans more than 10° beyond baseline;
  - reduced ROM: under 80 % of baseline.
- **Next-rep risk:** any compensation flag in the next 3 reps of the same set.
- **Missing sensor:** its labels are masked, never set to 0.

## Measured on this Mac (2026-11-05)

- **Real radar:**
  - 60.00 fps, 0 missing frames in 1,792;
  - the 8 static-heatmap values per range bin are antennas, not angles;
  - the two empty-room recordings differ by up to 38 dB in some bins (the setup changed between them);
  - one recording differs from itself by up to 4.8 dB between its halves.
- **Real IMU:**
  - 136 s of still data from 4 real sessions. 2 others (`imu_fw_sim*`) are the firmware's simulation mode and are skipped.
  - Noise ~0.001 g and ~0.07 °/s; |acc| reads 1.10 g because the accelerometer isn't calibrated yet.
  - Wi-Fi adds a median 15.3 ms, with about one ~1.1-s pause per minute.
- **Fake vs real:**
  - noise floor within 0.5 dB on average;
  - frame timing and Wi-Fi delay copied from the real sequences;
  - IMU noise within 20 %.
- **Shrug sync on fake sessions:** IMU within 5 ms of the truth. The pose's 60-ms webcam delay is found within one
  webcam frame (33 ms). Re-measured 2026-11-09:
  - saved-statistics radar background, 40 fake people: error 5 ms (median), 17 ms (90 %), 29 ms at worst;
  - real empty-room background, 20 fake people: 16 ms at worst.
- **Speed:**
  - one frame through the CNN: 0.32 ms on the Apple GPU, 0.87 ms on CPU (a frame arrives every 16.7 ms);
  - a training step is 15× faster on the Apple GPU;
  - Raspberry Pi speed is not measured.
- **Fake training run (6 people, leave one out):**

  | Head | Model | Baseline |
  |---|---|---|
  | Fatigue MAE | 0.25 | 0.32 |
  | Quality MAE | 0.045 | 0.048 |
  | Shrug F1 | 0.53 | 0.39 |
  | Lean F1 | 0.63 | 0.42 |
  | Risk F1 | 0.57 | 0.28 |
  | Reduced-ROM F1 | 0.41 | 0.41 (not better) |

  This only shows that the plumbing works.

## Not done / open

- **Not trained on real data:** there are no real sessions with a person yet. The first full session (radar, MyoWare, IMU and webcam with the protocol above) is the next step.
- **Placeholders:** all thresholds, and the rules' numbers.
- **The `v1` contract isn't frozen.** With T = 128, 58 % of the fake reps (2.0–2.9 s) get cropped, so decide T after the first real session; the check reports how many reps get cropped.
- **sEMG and pose are not calibrated** (textbook values). Rerun the calibration after real sessions.
- **Radar left/right and antenna order** are not verified on the board. A consistent order still trains.
- **Unproven:** fatigue from radar.
- **Out of scope:** ONNX/Pi export and dashboard wiring.
