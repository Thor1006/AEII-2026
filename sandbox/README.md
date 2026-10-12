# sandbox: FMCW chain + ML example (no hardware)

Learning code. Everything runs on **simulated** radar data. The radar config is an example, not the real AWR1843 profile.

```bash
python3 sandbox/fmcw_chain.py     # radar chain demo  -> sandbox/out/fmcw_chain_demo.png
python3 sandbox/ml_example.py     # ML example (~1 min) -> sandbox/out/ml_example.png
```
Needs: numpy, matplotlib, torch (already installed in your global Python 3.14).

## What's in here
| File | What it does |
|---|---|
| `fmcw_chain.py` | Config → simulated body (8 point reflectors, breathing, compensation knobs) → range FFT → static removal → Doppler FFT → range-azimuth → CFAR → micro-Doppler → phase displacement. Prints self-checks. |
| `ml_example.py` | 8 simulated subjects × 3 classes (correct / shoulder elevation / trunk lean) × 8 reps → hand-crafted features + logistic regression vs a small CNN, both trained with AdamW and evaluated leave-one-subject-out. |

## Results of the first run (2026-10-07)
- Chain self-checks pass: the micro-Doppler tracks hand velocity (MAE 0.06 m/s, under one 0.17 m/s bin), the phase method recovers 8 mm breathing (corr 1.00), and CFAR finds the body at ~1 m.
- ML (LOSO macro-F1): majority 0.17 · logistic regression 0.46 · CNN 0.61.
  - **Trunk lean** is detected almost perfectly (62/64 with the CNN).
  - **Shoulder elevation is indistinguishable from correct form.** With the radar in front at chest height, the shoulder moving *up* barely changes its *distance* (~1 cm per rep). The radar's strong axes are range and Doppler, and vertical motion isn't on them. This is a real design finding, not a bug. Next experiments: use the elevated TX1 antennas (elevation angle), or mount the radar higher/lower.

## Learning map: concept → where it is in the code
Roughly in the order to learn them.

| # | Concept | Code | What to understand |
|---|---|---|---|
| 1 | Complex numbers, I/Q, phase | `simulate`, `phase_displacement` | Why a signal is `amp * exp(j*phase)`, what `np.angle` and `np.unwrap` do |
| 2 | FFT, windowing, bins → physical units | `range_fft`, `RANGE_AXIS`, `VEL_AXIS` | What one FFT bin means; why Hann windows; zero-padding ≠ resolution |
| 3 | FMCW basics: chirp, beat frequency, slope | config block, `simulate` | f_beat = 2SR/c; how S, B, f_s set range resolution and max range |
| 4 | Doppler from phase across chirps | `doppler_fft` | Δφ = 4πvT_c/λ; why TDM-MIMO uses 3·T_c |
| 5 | Clutter / static removal | `remove_static` | Why the mean over chirps removes walls, and why it also kills breathing |
| 6 | Antenna arrays, angle FFT, virtual array | `VIRT_POS`, `AZIMUTH_IDX`, `range_azimuth` | Why 3 TX × 4 RX = 12 virtual antennas, but only 8 in azimuth |
| 7 | Detection: CFAR | `ca_cfar` | Adaptive threshold vs fixed threshold |
| 8 | Time–frequency: spectrogram / micro-Doppler | `micro_doppler` | Why per-frame Doppler FFTs stacked over time form a spectrogram |
| 9 | Phase-based vibration sensing | `phase_displacement` | µm precision from phase; sample rate limits (25 fps → max 12.5 Hz) |
| 10 | Feature engineering | `features` in `ml_example.py` | Turning images into physically meaningful numbers |
| 11 | CNN basics: conv, pooling, BatchNorm, dropout | `SmallCNN` | What each layer does to a 76×48 image |
| 12 | Training: AdamW, cosine LR, class weights, early stopping, augmentation | `train`, `augment` | Weight decay vs overfitting; why early-stop on a *validation* subject |
| 13 | Evaluation: LOSO, macro-F1, confusion matrix | `loso`, `macro_f1` | Why a random split would lie about accuracy |

### Good sources
- TI training: *Introduction to mmWave Sensing: FMCW Radars* (Sandeep Rao's video series) covers 3–6.
- TI white paper: *The fundamentals of millimeter wave sensors*.
- OpenRadar (`mmwave` Python package) docs and notebooks, for real-data examples.
- PyTorch tutorial: *Training a Classifier*, for 11–12.

## Things to try (each one teaches something)
1. Set `S` so B ≈ 4 GHz → watch range resolution go from 9.8 to ~3.75 cm and the range-time image sharpen.
2. Drop `N_LOOPS` to 16 → velocity resolution gets coarse and micro-Doppler blurs.
3. Raise `noise` in `simulate` to 3.0 → see when CFAR and the classifier break.
4. Make shoulder elevation visible: add an elevation-angle feature using the TX1 antennas (indices 4–7), or move the radar to z = −0.5.
5. Swap `AdamW` for plain `SGD(lr=1e-2)` → compare how training behaves.
