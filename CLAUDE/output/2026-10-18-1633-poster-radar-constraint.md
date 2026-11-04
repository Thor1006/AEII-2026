# Submitted-poster radar constraint review

**Date:** 2026-10-18
**Result:** Poster reviewed read-only; local planning documents updated; not committed or pushed.

## Poster evidence

The submitted `TrueRehub-RF .pdf` labels the pictured sensor `mmWave radar (77 GHz)`. Its innovation diagram connects that radar to micro-scale/subtle-motion changes, joint and body movement patterns, and overall body posture.

Its operation flowchart also explicitly states:

- `Connect AWR1843BOOST`.
- `Connect DCA1000EVM`.
- `Collect radar data (AWR1843BOOST + DCA1000EVM)`.
- Range FFT, Doppler FFT and Range-Doppler map before the CNN/temporal model.

The dashboard section claims outputs including movement quality, estimated fatigue, compensation level, compensation risk, a Range-Doppler map, movement signal and recommendations. These claims make preserving a TI 76–81-GHz multi-antenna path more defensible than changing to a 60.5-GHz single-channel platform.

## Consequence for Plan A

XE125/A121 is 60.5 GHz and single-channel 1TX/1RX. It can provide distance and coherent phase/Sparse IQ, but cannot directly estimate angle. It therefore conflicts with the poster's frequency, named TI hardware, DCA capture path and Range-Doppler architecture, and is a weak direct implementation of the broader joint/body movement, posture and compensation-risk claims. Its signal representation and any trained model are not automatically transferable to the submitted system.

Plan A remains useful only as a disclosed fallback feasibility platform with narrowed claims such as distance, repetition and micro-motion exploration.

## Consequence for Plan B

AWR2944PEVM operates at 76–81 GHz and has 4TX/4RX angular capability, making it much closer to the printed frequency, TI platform and combined micro/macro sensing claims. It still replaces the poster's AWR1843BOOST and initially omits DCA1000, so the team must disclose that raw host capture was replaced by onboard processing plus reduced Ethernet output. It remains a schedule risk and does not provide automatic DCA-equivalent raw ADC without separate capture hardware.

## Files changed

- `CLAUDE/plans/2026-10-18-hardware-procurement-options.md`
- `CLAUDE/CONTEXT.md`
- `CLAUDE/DECISIONS.md`

## Preserved files

- `TrueRehub-RF .pdf` was not modified. Verified SHA-256: `8CE8F004A761C0CCB6CF7C7D9863FA6F03BCBEA47BF66937FBB556CD48D2676B`.
- The alternate `AEII 2026. TrueRehab-RF Poster.pdf` copy was also not modified.
- `T-Proposal-Radar (1).docx` and `message-2.txt` were not modified.
- No Git commit or push was performed.
