# Plan: Hardware procurement options

**Status:** Plan B selected; not ordered
**Date:** 2026-10-18

## Why

The team needs one shared list that separates hardware required for validation from the mutually exclusive radar choices. This avoids ordering a radar without its required power/accessories and prevents later AI sessions from assuming that both radar platforms will be purchased.

Prices below are the user's DigiKey Thailand quotations on 2026-10-18. They are recorded as quoted line totals, including the stated multi-item quantities, and must be rechecked at checkout for stock, delivery, VAT, shipping and import charges.

## Selected direction

The user selected **Plan B: AWR2944PEVM** on 2026-10-18 and clarified that **DCA1000 is excluded entirely, including deferred upgrades**. Plan A is no longer an active procurement option; it remains documented only as fallback history. The purchase is not marked ordered until an order confirmation and delivery date exist. Preserve the submitted poster's TI 76–81-GHz FMCW and Range/Doppler direction as closely as practical, while disclosing that AWR2944PEVM onboard processing plus Ethernet replaces the submitted AWR1843BOOST+DCA1000 capture workflow.

## Required MyoWare validation subset

| Item | Part | Quantity | Quoted line price | Purpose |
|---|---|---:|---:|---|
| [MyoWare 2 Muscle Sensor](https://www.digikey.co.th/en/products/detail/sparkfun-electronics/DEV-27924/26769978) | DEV-27924 | 1 | ฿1,450.73 | sEMG ground-truth/validation signal; not part of the final contactless product |
| [MyoWare Wireless Shield](https://www.digikey.co.th/en/products/detail/sparkfun-electronics/23387/22606870) | DEV-23387 | 1 | ฿898.78 | ESP32 wireless acquisition; includes a 40 mAh LiPo battery and USB-C charging/programming |
| [24 mm disposable electrodes, 10-pack](https://www.digikey.co.th/en/products/detail/sparkfun-electronics/12969/6163652) | SEN-12969 | 3 packs (30 pads) | ฿995.49 | Compatible snap electrodes for short-term EMG measurement |
| [USB-A to USB-C data cable, 2 m](https://www.digikey.co.th/en/products/detail/sparkfun-electronics/15424/10279704) | CAB-15424 | 2, only if the team does not already have suitable cables | ฿700.36 | USB 2.0 data and charging cable |

MyoWare subset excluding optional cables: **฿3,345.00**\
MyoWare subset including both quoted cables: **฿4,045.36**

### Required Raspberry Pi prototype set

The user explicitly added **Raspberry Pi 5 to REQUIRED**. Include the 8-GB Pi 5, official Active Cooler, official 27-W USB-C power supply and default 128-GB microSD storage in the full-project purchase list. The case is recommended; card reader, micro-HDMI cable, keyboard/mouse and monitor are conditional on existing equipment and headless use. NVMe/HAT is an optional alternative rather than a mandatory second storage purchase. See [complete purchase links](2026-10-18-plan-b-purchase-links.md) for one or two sources per sourced item.

The previous quoted totals do not include any of this Pi set. A full-system total is not confirmed until the team selects the accessory variants and gets checkout quotations.

### MyoWare safety and scope

- The Wireless Shield is designed to stack on the MyoWare 2 Muscle Sensor and includes its own ESP32 and LiPo battery; no separate ESP32 or battery is currently listed.
- While electrodes are attached to a person, acquire data wirelessly from the battery-powered assembly. Do not keep the wearable connected to a mains-powered computer, charger, dock or monitor.
- Disconnect electrodes before USB charging, programming or wired debugging.
- The listed electrodes and prototype are not medical diagnostic devices. Use them only under the project's approved healthy-volunteer/validation protocol.

## Plan A — Rejected for the current build; fallback history only

| Item | Part | Quantity | Quoted line price |
|---|---|---:|---:|
| [Acconeer XE125 evaluation board](https://www.digikey.co.th/en/products/detail/acconeer-ab/XE125/17883268) | XE125 | 1 | ฿4,038.35 |

Plan A estimated hardware total:

- Without optional cables: **฿7,383.35**
- With both quoted cables: **฿8,083.71**

Verified product scope: XE125 is the evaluation kit for the included XM125 module. XM125 contains the Acconeer A121 60-GHz Pulsed Coherent Radar sensor, an STM32L431 MCU and antenna; XE125 provides USB-C connection to a Windows/Linux PC. A separate A121 sensor purchase is not required.

Software implication: use the Acconeer A121/XM125 tools and SDK. This is not a DCA-style raw ADC workflow and it cannot use the AWR2944 firmware plan unchanged. Evaluate Sparse IQ/vibration output and its sample-rate/data-format limits before freezing the ML input.

### Critical poster-consistency problem with Plan A

The exact submitted `TrueRehub-RF .pdf` labels the pictured sensor `mmWave radar (77 GHz)`. More importantly, its operation flowchart names the exact original development hardware and processing path:

- `Connect AWR1843BOOST`.
- `Connect DCA1000EVM`.
- `Collect radar data (AWR1843BOOST + DCA1000EVM)`.
- `Range FFT → Doppler FFT → Range-Doppler map → CNN encoder → temporal attention → neural network`.

The poster connects that radar to micro-scale subtle-motion changes, joint/body movement patterns, overall body posture, movement quality, estimated fatigue and compensation risk. It therefore presents the radar as supporting both fine motion and broader movement/posture analysis.

XE125 uses a 60.5-GHz A121 single-channel 1-TX/1-RX radar. It conflicts with the submitted poster on frequency, manufacturer/platform, acquisition interface and processing representation. It can provide range and coherent phase/Sparse IQ for micro-motion experiments, but it cannot directly estimate angle from one board. That makes it a weak match for the poster's joint/body movement, overall-posture and compensation-risk claims. Directional posture measurements would require strong placement assumptions, an additional reference sensor, multiple radars or a radar with angular channels.

Changing from 77-GHz FMCW/4TX-4RX development to 60-GHz Pulsed Coherent/1TX-1RX also changes wavelength, antenna response, available spatial information, data representation and preprocessing. A model or `InputContract` developed from XE125 Sparse IQ cannot be presented as directly validated for the submitted 77-GHz system.

Therefore Plan A is now a **fallback feasibility platform**, not the preferred representation of the submitted AEII system. It would require a new Acconeer-specific data pipeline rather than implementing the poster's AWR1843BOOST+DCA1000 Range-Doppler pipeline. Use it only if Plan B cannot be obtained in time, disclose it as a temporary prototype substitution, narrow the demo claims to distance/repetition/micro-motion feasibility, and avoid claiming full multi-directional posture or compensation detection from XE125 alone.

Plan B is not identical to the poster either: AWR2944PEVM replaces AWR1843BOOST and the initial build omits DCA1000. However, it stays within TI's 76–81-GHz FMCW ecosystem, retains 4TX/4RX angular capability, and can produce Range/Doppler-derived outputs onboard. It is therefore the closer and more defensible emergency substitution, provided the team clearly explains that raw capture moved from DCA1000/PC processing to onboard processing plus reduced Ethernet output.

## Plan B — TI 76–81-GHz radar

| Item | Part | Quantity | Quoted line price |
|---|---|---:|---:|
| [TI AWR2944PEVM](https://www.digikey.co.th/en/products/detail/texas-instruments/AWR2944PEVM/27687246) | AWR2944PEVM | 1 | ฿30,771.38 |
| [MEAN WELL 12-V adapter](https://www.digikey.co.th/en/products/detail/mean-well-usa-inc/GST60A12-P1J/7703712) | GST60A12-P1J | 1 | ฿646.99 |

Plan B estimated hardware total:

- Without optional cables: **฿34,763.37**
- With both quoted cables: **฿35,463.73**
- Add the price of one grounded IEC C13 AC mains cord; it was not included in the quoted total.

The adapter is rated 12 V, 5 A and uses the P1J 2.1 mm × 5.5 mm center-positive barrel plug. Its current capacity exceeds the AWR2944PEVM guide's requirement of 12 V and more than 2.5 A. Its AC input is IEC 320-C14 and the mains cord is sold separately, so add a grounded IEC C13-to-local-mains cord with an appropriate Thai plug and local safety approval.

Software implication: follow [the AWR2944PEVM no-DCA plan](2026-10-18-awr2944-no-dca.md). Start with TI OOB detected objects over Ethernet; then attempt reduced Range-Doppler and selected complex Range-FFT bins. Do not promise full DCA-equivalent raw ADC capture.

## Final Plan B complete hardware list

### Order now

| Priority | Hardware | Part | Quantity | Notes |
|---|---|---|---:|---|
| Required | TI 76–81-GHz radar EVM | AWR2944PEVM | 1 | Replaces only the poster's AWR1843BOOST; keeps TI, frequency class, FMCW, 4TX/4RX and Range/Doppler capability |
| Required | 12-V, 5-A center-positive adapter | GST60A12-P1J | 1 | 2.1 mm × 5.5 mm barrel output; sufficient for the EVM |
| Required | Grounded AC mains cord | IEC C13 to grounded Thai mains plug | 1 | GST60A12-P1J has a C14 inlet and does not include this cord; buy locally if not already owned |
| Required prototype | Raspberry Pi 5, 8 GB RAM | Raspberry Pi 5 8GB | 1 | Explicitly required by the user; use notebook for initial radar development |
| Required prototype | Official Active Cooler | RPI-PI5-HAC (Cytron listing) | 1 | Choose an enclosure that fits it |
| Required prototype | Official 27-W USB-C PSU, EU plug | RPI-PD-27W-EU-W (Cytron listing) | 1 | Dedicated Pi supply, separate from the radar adapter |
| Required prototype | A2 microSD, 128 GB | Raspberry Pi A2 microSD 128GB | 1 | Default storage; NVMe/HAT remains optional |
| Required validation | MyoWare 2 Muscle Sensor | DEV-27924 | 1 | sEMG ground truth, not part of the final contactless product |
| Required validation | MyoWare Wireless Shield | DEV-23387 | 1 | Includes ESP32 and 40-mAh LiPo battery |
| Required consumable | 24-mm disposable electrodes, 10-pack | SEN-12969 | 3 packs | 30 pads total; three pads per placement gives up to ten placements |
| Conditional | USB-A to USB-C data cable, 2 m | CAB-15424 | 2 | Buy only if suitable USB-C data/charging cables are not already available; used for MyoWare, not AWR2944PEVM |

### Must be available, but do not reorder if already owned

| Hardware | Quantity | Why |
|---|---:|---|
| Windows notebook/PC with adequate storage | 1 | TI tools, firmware/debugging, Ethernet receiver, recording, AI and dashboard |
| Wired RJ45 Ethernet port | 1 | AWR2944PEVM data path to the notebook |
| USB-to-Gigabit-Ethernet adapter | 1 if needed | Only if the notebook has no wired RJ45 port |
| Available USB-A port or USB-C adapter/hub | 1 | The included AWR2944PEVM debug cable is USB-A to Micro-B |
| Stable, height-adjustable nonmetallic stand/tripod or rigid table mount | 1 | Repeatable radar height and angle; use the included TI bracket if it is adequate |

### Already included with AWR2944PEVM — do not buy duplicates before unboxing

- AWR2944P radar board with 4TX/4RX 3D waveguide antenna, onboard processing and debug/emulation.
- USB-A to Micro-B cable.
- Ethernet cable.
- Mounting brackets, standoff, screws, nuts, feet and jumpers.

### Plan B acquisition scope — no DCA1000

Do not purchase DCA1000EVM, its dedicated 5-V supply or its Samtec/LVDS capture cable for Plan B. This is a permanent scope choice for the selected plan, not a delayed purchase. Use AWR2944PEVM onboard processing and Ethernet output to the notebook, then to Raspberry Pi if performance is verified. Start with official OOB output; custom Range-Doppler and selected complex Range-FFT/phase output need firmware development and verification. Full continuous raw ADC capture is not a committed deliverable. External SSD remains useful for recordings and backups without DCA1000.

### Do not buy for the selected build

- XE125, XM125 or a separate A121 sensor.
- AWR1843BOOST unless the team deliberately returns to the original poster hardware.
- DCA1000EVM, its dedicated 5-V supply and its Samtec/LVDS capture cable, including future upgrades within Plan B.
- A separate ESP32 or LiPo battery for MyoWare; both are on the Wireless Shield.
- Do not duplicate components from a Pi kit: Pi 5 itself is now REQUIRED for the prototype, while initial acquisition still uses the Windows notebook.

## Decision comparison

| Criterion | Plan A: XE125 | Plan B: AWR2944PEVM |
|---|---|---|
| Quoted total with cables | ฿8,083.71 | ฿35,463.73 |
| Radar band | 60 GHz | 76–81 GHz |
| Matches submitted poster | **Poor: conflicts with the 77-GHz label, AWR1843BOOST, DCA1000 and the Range-Doppler acquisition path** | **Closer: same TI 76–81-GHz FMCW class and angular radar, but substitutes AWR2944PEVM and onboard processing for AWR1843BOOST+DCA1000** |
| Initial PC path | USB-C + Acconeer tools | USB for control/debug; Ethernet for supported/custom data output |
| Full DCA-style raw ADC | No | No, not without DCA1000 or separate capture hardware |
| Schedule risk | Lower cost and simpler exploration path, but creates poster/claim/model-transfer risk | Higher cost and embedded-firmware complexity; much closer to the submitted sensing architecture |

## Purchase gate

Before ordering Plan B:

1. Recheck stock and the delivery date to Thailand at checkout.
2. Confirm the team is funding Plan B; do not add XE125 by accident.
3. Confirm every included accessory and connector.
4. Save the final order confirmation and actual paid prices in a new local procurement update.
5. Change the selected option from **proposed** to **ordered** only after payment/order confirmation exists.
6. Exclude DCA1000 and its accessories from all Plan B orders; prioritize validating the onboard-processing/Ethernet output path.

## Files touched

- `CLAUDE/PROJECT.md` — record required validation hardware and both radar options.
- `CLAUDE/CONTEXT.md` — make the Plan A/Plan B choice the immediate project decision.
- `CLAUDE/DECISIONS.md` — record the two-track procurement decision.
- `CLAUDE/plans/2026-10-18-awr2944-no-dca.md` — label the existing implementation plan as Plan B.
- `CLAUDE/plans/2026-10-18-hardware-procurement-options.md` — detailed list, assumptions and totals.

## Verification

- Confirm product identities and quantities against the supplied DigiKey links.
- Confirm from the manufacturers that XE125 includes XM125/A121, the Wireless Shield includes ESP32/LiPo, and GST60A12-P1J is rated 12 V/5 A.
- Run `git diff --check` after the local documentation update.
