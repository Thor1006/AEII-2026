# Plan: CNN frame encoder (input definition can change)

**Status:** done
**Date:** 2026-10-08

## Why
`radar_ml_context.md` says the next task is a reusable CNN frame encoder: one shared feature extractor that later feeds temporal attention and several small task heads. We have no real recordings or chirp config yet, so the encoder must not lock in an input shape too early. In particular, it must work on range-Doppler frames now **and** on micro-Doppler or range-time windows later. Those are what Phases 1–3 likely need, and Phase 2 (muscle micro-vibration) may need them too. The heads will be TrueRehab's (fatigue, movement quality, compensation), not presence/range/behavior from the context doc.

## Approach
1. **Input definition (`InputContract` dataclass).** It records:
   - the view name (`range_doppler`, `micro_doppler`, `range_time`, ...)
   - the axis meaning and sizes `[C, H, W]`
   - units and scaling (default: log-magnitude dB, clipped at a −40 dB floor, then mapped to [0, 1], the same as the sandbox `to_image`)
   - dtype
   - the missing-data policy: lost packets give a NaN-free tensor plus an optional mask channel. They are never silently filled with zeros.

   The contract is saved with the weights. Preprocessing stays outside the encoder.
2. **Encoder settings (`FrameEncoderConfig` dataclass):**
   - `in_channels`
   - stage widths (default `16, 32, 64, 128`)
   - number of blocks per stage
   - norm type: default **GroupNorm**, because batches will be small and frames get folded into the batch dimension later. BatchNorm stays available.
   - dropout
   - `embed_dim` (default 128)
3. **`FrameEncoder(cfg)` module:**
   - conv → norm → ReLU blocks, downsampling with max-pool only while the dimension is still above a minimum size, so small Doppler axes don't shrink to nothing
   - adaptive average pooling → linear projection → `[B, E]`
   - it checks the input rank, channel count and minimum size, and raises clear errors
4. **`encode_sequence(x)` method:** turns `[B, T, C, H, W]` into `[B, T, E]` by folding T into the batch dimension. This keeps it compatible with the later temporal block.
5. **Saving and loading:** `save(dir)` writes `weights.pt`, `encoder_config.json` and `input_contract.json`. `load(dir)` rebuilds the model and refuses to load if the config doesn't match.
6. **Check script (`check_encoder.py`)** runs all the checks listed under "How we'll verify".
7. **Temporary probe on the existing sandbox data.** Put the encoder plus a linear head into the sandbox's synthetic compensation task (3 classes, leave-one-subject-out, or LOSO) and compare it with `SmallCNN` and the majority-class baseline. It runs on synthetic data only, so it shows the pipeline works, not that the radar features are any good.

**Out of scope for now:** temporal attention, the real fatigue/quality/compensation heads, calibration, live capture, and the oversized-model timing experiment. Those come only after a baseline exists.

## Files touched
- `sandbox/Encoder_0.1/frame_encoder.py` (new): `InputContract`, `FrameEncoderConfig`, `FrameEncoder`, save/load.
- `sandbox/Encoder_0.1/check_encoder.py` (new): the verification script.
- `sandbox/Encoder_0.1/README.md` (new): the input definition, how to run the checks, and what's still undecided.
- `sandbox/ml_example.py` is not edited. The probe lives in `sandbox/Encoder_0.1/encoder_probe.py` and imports from it.

## Risks / needs OK
- **Where the code lives:** decided 2026-10-08 — `sandbox/Encoder_0.1/` (user choice), not the `truerehab-rf/` layout yet.
- **The input is still a guess.** Defaults follow the sandbox (one log-magnitude channel). The real AWR1843 config may change H, W and C. The design allows for that, but the defaults will need revisiting.
- The micro-vibration and phase signal for Phase 2 may be 1D rather than 2D. This encoder won't cover that. It would need its own small 1D branch later.
- Uses only torch and numpy, which are already installed (torch 2.14.1, MPS available). No installs. Nothing touches hardware.

## How we'll verify
- Output shape is `[B, E]` for several input sizes (e.g. 64×32, 128×64, 112×48). An input below the minimum size gives a clear error.
- `encode_sequence` matches running the encoder frame by frame, to within float tolerance.
- Outputs are finite, and every parameter gets a non-zero gradient after one backward pass.
- Prints the parameter count and the rough activation memory for a reference batch.
- CPU and MPS outputs match to within tolerance, with a forward/backward timing for each.
- The model can overfit a tiny synthetic batch (loss drops to about 0), which is a learning sanity check.
- Save, then load, gives identical outputs. Loading with a config that doesn't match fails.
- Sandbox probe: LOSO macro-F1 is printed next to `SmallCNN` and the majority baseline, clearly labelled **synthetic**.
