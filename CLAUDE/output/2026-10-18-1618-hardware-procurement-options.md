# Hardware procurement options update

**Date:** 2026-10-18
**Result:** Local documentation updated; not committed or pushed.

## What changed

- Added the required MyoWare 2 sensor, Wireless Shield, 30 electrodes and conditional USB cables with the user's DigiKey Thailand quotations.
- Added mutually exclusive radar options: Plan A XE125 60 GHz and Plan B AWR2944PEVM 76–81 GHz plus its 12-V supply.
- Recorded quoted subtotals and purchase gates without marking either plan ordered.
- Confirmed in the plan that XE125 includes XM125/A121 and that the MyoWare Wireless Shield includes ESP32 and a 40 mAh LiPo battery.
- Added battery-isolated MyoWare use requirements and the non-medical-device boundary.
- Updated project, context, decisions and radar/ML context so later AI sessions see both purchase options rather than assuming AWR2944PEVM is final.

## Files changed in this update

- `CLAUDE/PROJECT.md`
- `CLAUDE/CONTEXT.md`
- `CLAUDE/DECISIONS.md`
- `CLAUDE/plans/radar_ml_context.md`
- `CLAUDE/plans/2026-10-18-awr2944-no-dca.md`
- `CLAUDE/plans/2026-10-18-hardware-procurement-options.md`

## Price interpretation

The supplied prices are stored as quoted line totals. In particular, ฿995.49 is treated as the quoted line total for three ten-pad packs and ฿700.36 as the quoted line total for two cables. Final checkout totals may differ.

## Verification

- Manufacturer information confirms XE125 includes XM125/A121 and connects by USB-C.
- SparkFun information confirms DEV-23387 includes ESP32-WROOM and a 40 mAh LiPo battery.
- Manufacturer information confirms GST60A12-P1J is rated 12 V/5 A with a P1J 2.1 mm × 5.5 mm plug; final EVM fit and polarity still require a checkout/bench check.
- No source code, poster, proposal or team-note file was edited.
- No Git commit and no Git push were performed.

## Next action

The team must choose Plan A or Plan B and recheck stock, delivery and final checkout price before ordering.
