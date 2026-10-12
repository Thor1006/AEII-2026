# AEII 2026 — Radar ML context and glossary

Purpose: give Claude the vocabulary and working context from the AEII-1 discussion. **Immediate next task: build the encoder first.** This document describes a proposed design, not a completed system. Example dimensions, probabilities, classes, and buffer durations are illustrative.

## 1. Project goal and current direction

Build a radar sensing prototype that turns radar measurements into useful structured predictions: target/person presence, range, movement or radial velocity, and eventually behavior/activity. A shared neural network representation should support several small output modules in one forward pass.

The proposed model is a CNN frame encoder followed by a temporal attention block and task-specific heads. The discussion also called this “Jev-inspired”: sensor state in, structured decisions out. That is a conceptual analogy, not a claim about Jev's architecture or a requirement to reproduce its training method.

An experiment of interest is whether a larger, deliberately overparameterized model reaches useful predictions sooner in **wall-clock time**. This is a hypothesis to measure, not an assumption that larger is better. Start with ordinary supervised learning; assess calibration after useful predictions exist.

## 2. Hardware context

| Component | Role |
|---|---|
| TI mmWave radar EVM | Texas Instruments millimeter-wave radar evaluation module; transmits radar signals and samples reflected signals. Exact board, antenna layout, firmware, and chirp configuration remain unspecified. |
| DCA1000EVM | Capture adapter receiving compatible TI radar LVDS data and streaming it over Ethernet to the host. It is not the ML model or the radar sensor itself. |
| MacBook Pro | Intended host for recording, preprocessing, visualization, and PyTorch development. Chip and memory capacity are not specified; confirm MPS availability on the actual machine. |

The LVDS-to-Ethernet capture path is documented in [TI's DCA1000 guide](https://www.ti.com/lit/ug/spruij4a/spruij4a.pdf); its UDP transport is described in [TI's CLI developer guide](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/1023/TI_5F00_DCA1000EVM_5F00_CLI_5F00_Software_5F00_DeveloperGuide.pdf). Radar configuration/control is a separate path from receiving samples. Mac capture/control software still needs to be implemented or verified; do not assume TI tooling runs natively on macOS.

## 3. Two separate pipelines

### Data collection: preserve measurements for later reprocessing

```text
TI radar EVM → LVDS → DCA1000EVM → Gigabit Ethernet → Mac UDP receiver
  → reorder/check packets → reconstruct ADC byte stream → save raw data
  → offline decode/I-Q reconstruction → range FFT → Doppler FFT
  → optional angle processing → labeled training examples → PyTorch training
```

Keep the raw ADC data so preprocessing can change without recollecting everything. For each session, save `adc.bin`, `radar_config.json`, `metadata.json`, `timestamps.csv`, `labels.csv`, and a packet-loss/quality log. Record byte layout, sample format, antenna/chirp settings, timing meaning, and label alignment. A `.bin` file alone is insufficient to interpret the capture reliably.

A live range/range-Doppler preview can consume a separate queue; visualization must not block the receiver or disk writer. Preserve and flag gaps explicitly rather than silently treating missing samples as valid zeros. Split training/validation/test data by independent sessions or subjects as appropriate; overlapping windows from one recording must not leak across splits.

### Real prototype: process and respond with low latency

```text
Radar acquisition → same preprocessing used for training → frame tensors
  → CNN frame encoder → recent embedding sequence → temporal attention
  → shared representation → presence/range/movement/behavior heads
  → calibrated scores or uncertainty information → decision logic → application
```

The final acquisition path is undecided: it might retain DCA1000 during development or use supported processed radar output. A model trained on one representation cannot automatically accept the other.

Keep a bounded rolling buffer in RAM; discard old data during normal operation. In hybrid development mode, save selected raw windows around errors or interesting events for debugging and retraining. A “past 5 s + future 2 s” capture is only an example; collecting future data requires waiting after the trigger.

## 4. Signal and transport glossary

| Term | Meaning in this project |
|---|---|
| Raw ADC | Digitized analog-to-digital converter samples of the radar receiver's baseband signal, before FFTs or learned features. “Raw” still requires decoding the configured packing/interleaving. |
| I/Q | In-phase and quadrature components, often represented as complex samples `I + jQ`, preserving amplitude and phase. Confirm complex versus real sampling and device-specific ordering. |
| LVDS | Low-voltage differential signaling: the high-speed electrical link carrying samples from the radar EVM to DCA1000. |
| UDP | User Datagram Protocol: sends Ethernet/IP datagrams without guaranteed delivery or ordering. |
| Packet ordering/loss | Use capture sequence numbers/byte counters to reconstruct the stream, detect missing, duplicate, or out-of-order packets, and mark affected data. An Ethernet packet is not necessarily a whole radar frame. |
| FMCW / chirp | Frequency-modulated continuous-wave radar uses frequency sweeps called chirps. Their timing and slope determine how samples map to range and velocity. |
| Frame | A configured group of chirps; the per-frame CNN input is a processed map derived from that group. |
| Range FFT | Fast Fourier transform across samples within a chirp (“fast time”); converts beat-frequency information into range bins using the radar configuration. |
| Doppler FFT | FFT across suitably arranged repeated chirps (“slow time”), usually per range bin; estimates Doppler frequency and hence radial velocity. Multi-transmitter chirps require correct grouping. |
| Angle processing | Uses relative phase across antenna channels to estimate direction, often with beamforming or an angle FFT. Depends on antenna geometry and calibration; optional initially. |
| Range-Doppler map | A grid of reflection magnitude/power indexed by range and Doppler/radial velocity bins. Often log-scaled for the model. It is not a camera image, and Doppler measures motion toward/away from the radar, not full 3D speed. |
| Preprocessing | Decode, arrange samples, window/FFT, optionally remove clutter, scale and normalize. Record every setting and reuse it during inference. |

## 5. Model, training, and operation glossary

| Term | Meaning in this project |
|---|---|
| Tensor | Numeric array supplied to the network, with explicitly defined dimensions, units, and normalization. |
| CNN | Convolutional neural network: reuses learned local filters across a grid, combining local radar patterns into features. |
| Encoder | Converts an input into learned features rather than final answers. Here **frame encoder** means the CNN; **full encoder** may later mean CNN plus temporal processing. |
| Temporal attention block | Learns relationships among embeddings from multiple frames. Needs time/order information; live inference must use only available frames. Attention weights are not confidence scores. |
| Shared representation / embedding | A learned vector used by multiple tasks. Individual coordinates usually have no fixed physical meaning. Per-frame embeddings precede temporal processing; the shared sequence representation follows it. |
| Head | Small output network for one task: e.g., presence logit, activity class scores, or range estimate. Classification scores become probabilities through sigmoid/softmax; regression outputs need units. |
| Multi-task learning | Train one shared encoder and several heads with a weighted combination of task losses. Mask missing or inapplicable labels, such as range when no target exists. Shared training can help, but tasks can also interfere. |
| Loss / target loss | Training objective measuring prediction error; a target loss is a predefined threshold. Examples: binary cross-entropy for presence, cross-entropy for classes, and regression loss for range. |
| Confidence | A score intended to reflect prediction reliability. A softmax probability or extra “confidence head” is not automatically trustworthy. Define confidence per task rather than assuming one universal score. |
| Calibration | Agreement between predicted probabilities and observed frequencies: among predictions near 0.8, approximately 80% should be correct for the defined event. Evaluate on held-out data; temperature scaling is one possible post-training method. Sensor/antenna calibration is a separate concept. |
| Ring buffer | Fixed-capacity rolling memory storage; new samples overwrite the oldest. Can store raw samples, maps, or embeddings, each with different memory costs. |
| Hard-example collection | Preserve failures, uncertain cases, unusual scenes, and false positives with verified labels, then use them to improve training. Keep an independent evaluation set. |
| PyTorch / MPS | PyTorch builds and trains the neural network. Apple's Metal Performance Shaders backend (`mps`) can run supported operations on compatible Mac GPUs; check availability and operation support, retaining a CPU baseline. See [PyTorch MPS documentation](https://docs.pytorch.org/docs/stable/notes/mps.html). |
| Model size / overparameterization | Size includes parameter count, computation, and activation memory. Overparameterization means more trainable capacity than needed to fit the data; it may ease optimization but increases resource use and can overfit. |
| Batch size | Number of training examples processed together per optimization step. One example may contain multiple frames. It affects memory, throughput, and optimization; larger batches are not automatically faster to useful accuracy. |
| Time-to-target-loss | Elapsed wall-clock time until a predefined, comparable validation loss threshold is reached. Use identical data splits, preprocessing, objective/weights, and evaluation schedule; state whether timing includes setup. Synchronize asynchronous GPU work when measuring. Report runs that never reach the threshold, plus task accuracy/error and inference latency. |

## 6. Immediate next task: build the encoder first

**Scope now: implement and validate a reusable CNN frame encoder in PyTorch.** Temporal attention, full multi-task heads, calibration, and live acquisition integration are later stages.

Suggested initial interface, subject to the actual data:

```text
one batch of processed frames: [B, C, R, D]
  → convolution blocks → spatial pooling → projection
per-frame embeddings:         [B, E]

later, a sequence: [B, T, C, R, D] → shared frame encoder → [B, T, E]
```

`B` = batch size; `C` = input channels; `R` = range bins; `D` = Doppler bins; `T` = frames per sequence; `E` = embedding width. One log-magnitude channel and an embedding width of 128–256 are possible starting choices, not agreed specifications. Raw ADC would require a different input contract and potentially a different encoder.

1. Confirm the board/configuration, available data, map dimensions, channel definition, scaling, normalization, and missing-data policy. Use explicitly labeled synthetic tensors only for interface checks if recordings are unavailable.
2. Implement configurable CNN blocks, pooling, and a fixed-width embedding output. Keep preprocessing separate and document the input contract.
3. Verify shapes, finite outputs, gradient flow, parameter count, memory use, and CPU/MPS execution on the actual Mac.
4. When labeled recordings exist, attach one temporary simple head and check learning on a tiny subset, then evaluate on independent held-out recordings. Shape checks alone do not establish useful radar features.
5. Save the encoder weights together with architecture and preprocessing configuration. Compare larger versions only after establishing a measurable baseline.

For Claude: begin with this encoder module and its input/output contract. Do not invent sensor specifications, label sets, achieved accuracy, or deployment constraints. Keep later temporal and task modules compatible with its embeddings.
