# Encoder_0.1 — CNN frame encoder (sandbox)

A reusable PyTorch CNN that turns one processed radar frame into one embedding vector. It's the shared front end for later stages: temporal attention, then the fatigue / movement-quality / compensation heads. Plan: [`CLAUDE/plans/2026-10-08-frame-encoder.md`](../../CLAUDE/plans/2026-10-08-frame-encoder.md).

```bash
python3 sandbox/Encoder_0.1/check_encoder.py    # 17 sanity checks, ~10 s
```

```bash
python3 sandbox/Encoder_0.1/encoder_probe.py    # LOSO probe on simulated data, ~1 min
```
Needs numpy and torch, plus matplotlib for the sandbox data. Everything here is **synthetic or random data**.

## Files
| File | What it does |
|---|---|
| `frame_encoder.py` | `InputContract`, `FrameEncoderConfig`, `FrameEncoder` (with `encode_sequence`, `save`, `load`) |
| `check_encoder.py` | Shapes, input rejection, sequence = per-frame, finite outputs, gradients, size, CPU vs MPS, tiny-batch overfit, save/load |
| `encoder_probe.py` | Encoder + linear head on the `ml_example.py` compensation task, compared with `SmallCNN` |

## Input contract
```
frames     [B, C, H, W]     -> encoder(x)              -> [B, E]
sequences  [B, T, C, H, W]  -> encoder.encode_sequence -> [B, T, E]
```
- **H, W can be anything ≥ `min_size` (4).** Between stages, an axis is halved only while it stays ≥ `min_size`, so a short Doppler axis survives.
- **The encoder doesn't know which view it's looking at.** An `InputContract` records the view (range-Doppler / micro-Doppler / range-time / ...), the axes, the shape, units, scaling, dtype and the missing-data policy. It's saved with the weights, and `load(expected_contract=...)` refuses a mismatch.
- **Preprocessing stays outside.** The default scaling copies the sandbox: log-magnitude dB, minus the peak, clipped at −40 dB, mapped to [0, 1].
- **Missing data:** the input must be finite, and NaN is rejected. Gaps must be flagged upstream, never silently filled with zeros. An optional last channel can act as a validity mask (`mask_channel=True`).

## Architecture (defaults)
Four stages with widths 16 → 32 → 64 → 128. Each stage is conv3×3 → GroupNorm → ReLU, with max-pool between stages. Then global average pool → dropout 0.1 → linear → **E = 128**.
- 113,904 parameters (0.46 MB).
- GroupNorm instead of BatchNorm because our batches will be small and frames get folded into the batch for sequences. `norm="batch"` is available.

## Results (2026-10-08, this Mac)
- `check_encoder.py`: **17/17 pass**.
  - CPU vs MPS max difference 6e-7.
  - forward+backward for a batch of 32 at 128×64: CPU ~51 ms, MPS ~5 ms.
  - about 63 MB of activations.
- `encoder_probe.py` (LOSO macro-F1, 8 simulated subjects):

| Model | Params | Macro-F1 |
|---|---|---|
| majority class | – | 0.17 |
| sandbox `SmallCNN` | 23,715 | 0.58 ± 0.08 |
| FrameEncoder v0.1 + linear | 114,291 | 0.59 ± 0.06 |

Both models are effectively tied. Both detect trunk lean perfectly (64/64), and **both confuse shoulder elevation with correct form**. That matches the sandbox finding: vertical shoulder motion barely changes range or Doppler with a front-mounted radar at chest height. A bigger encoder doesn't fix missing information in the input. The fix is in the sensing setup (elevation angle, radar height). The probe only proves the plumbing. It says nothing about real radar data.

## Still open (don't treat the defaults as decided)
- The real AWR1843 chirp config sets H, W and C. Revisit the defaults once there is a real capture.
- Which view(s) to feed it. One channel or several (e.g. range-Doppler + mask)?
- `E = 128` is a starting point.
- The Phase 2 muscle micro-vibration signal may be **1D phase over time**. This 2D encoder doesn't cover it, and it would need a separate 1D branch.
- Not built yet: temporal attention, the real task heads, calibration, live capture, the oversized-model timing experiment.
