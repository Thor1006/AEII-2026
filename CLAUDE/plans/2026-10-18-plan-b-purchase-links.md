# Plan B purchase links — complete hardware sourcing

**Status:** done (sourcing list only; no orders placed)
**Date:** 2026-10-18
**Selected architecture:** AWR2944PEVM onboard processing -> Ethernet -> notebook; Raspberry Pi 5 is REQUIRED for the prototype.
**Excluded:** DCA1000 and all dedicated DCA accessories, including future upgrades.

## How to read this list

User-selected parts stay fixed. Newly sourced accessory models are purchase candidates, not orders or a claim that they were named on the submitted poster. Buy one choice per row. Required means required for the full project/prototype, not necessarily needed before the first notebook capture. Conditional/optional items do not become required merely because a link exists.

Links were found through supplier/manufacturer pages. Prices, stock and delivery must be checked on the exact selected variant at checkout. The four original prices below are the user's quoted LINE TOTALS, not a refreshed quotation. Some DigiKey direct-page reads failed, so manufacturer pages were used to verify identities; no current inventory claim is made from those failed reads. Overseas sources are marked.

## 1. User-selected MyoWare items

| Hardware / exact part | Qty | Priority | Purchase links | Recorded quoted line total |
|---|---:|---|---|---:|
| MyoWare 2 Muscle Sensor — DEV-27924 | 1 | Required validation | [DigiKey Thailand](https://www.digikey.co.th/en/products/detail/sparkfun-electronics/DEV-27924/26769978) / [SparkFun, overseas](https://www.sparkfun.com/myoware-2-muscle-sensor.html) | ฿1,450.73 |
| MyoWare Wireless Shield — DEV-23387 (DigiKey lists 23387) | 1 | Required validation | [DigiKey Thailand](https://www.digikey.co.th/en/products/detail/sparkfun-electronics/23387/22606870) / [SparkFun, overseas](https://www.sparkfun.com/myoware-2-0-wireless-shield.html) | ฿898.78 |
| Disposable electrodes, 24 mm — SEN-12969 | 3 ten-pad packs | Required consumable | [DigiKey Thailand](https://www.digikey.co.th/en/products/detail/sparkfun-electronics/12969/6163652) / [SparkFun, overseas](https://www.sparkfun.com/disposable-surface-emg-ecg-ekg-electrode-24mm-10-pack.html) | ฿995.49 for three packs |
| Reversible USB-A to USB-C data cable, 2 m — CAB-15424 | 2 if missing | Conditional | [DigiKey Thailand](https://www.digikey.co.th/en/products/detail/sparkfun-electronics/15424/10279704) / [SparkFun, overseas](https://www.sparkfun.com/reversible-usb-a-to-c-cable-2m.html) | ฿700.36 for two cables |

Thirty electrodes means thirty pads, not thirty three-pad placements. The Wireless Shield includes ESP32 and LiPo; do not buy a second ESP32/battery just to operate MyoWare. A separate logger can be useful for IMU only. Disconnect electrodes before USB charging/programming; acquire body-attached sEMG using the battery-powered wireless assembly.

## 2. REQUIRED Raspberry Pi prototype set

| Hardware / chosen specification | Qty | Priority | Purchase links | Selection note |
|---|---:|---|---|---|
| Raspberry Pi 5 — 8 GB RAM | 1 | Required prototype | [Cytron Thailand](https://th.cytron.io/p-raspberry-pi-5-with-8gb-ram) / [Arduitronics Thailand](https://www.arduitronics.com/product/5989/%E0%B8%88%E0%B8%B1%E0%B8%94%E0%B8%AA%E0%B9%88%E0%B8%87%E0%B8%9F%E0%B8%A3%E0%B8%B5-raspberry-pi-5-%E0%B9%81%E0%B8%A3%E0%B8%A1-8gb-%E0%B8%82%E0%B8%AD%E0%B8%87%E0%B9%81%E0%B8%97%E0%B9%89-made-in-uk-2) | Select 8 GB and board-only when buying accessories separately; not CM5, Pi 4 or an AI-HAT bundle |
| Official Raspberry Pi Active Cooler — Cytron RPI-PI5-HAC | 1 | Required cooling for selected Pi setup | [Cytron Thailand](https://th.cytron.io/p-raspberry-pi-5-heatsink-and-active-cooler) / [Official specification](https://www.raspberrypi.com/products/active-cooler/) | Includes its heatsink/fan; match the enclosure |
| Official Raspberry Pi 27-W USB-C PSU, EU plug — Cytron RPI-PD-27W-EU-W | 1 | Required Pi power | [Cytron Thailand](https://th.cytron.io/p-raspberry-pi-usb-c-pd-power-delivery-27w-psu-eu-white) / [Official specification](https://www.raspberrypi.com/products/27w-power-supply/) | This powers Pi, not the 12-V radar; its USB-C cable is integral |
| Raspberry Pi A2 microSD — select 128 GB | 1 | Required default storage | [Cytron Thailand](https://th.cytron.io/c-raspberry-pi-5-accessories/p-raspberry-pi-a2-microsd) / [128-GB MakerDisk alternative, Arduitronics](https://www.arduitronics.com/product/6128/128gb-raspberry-pi-approved-makerdisk-usd-with-rpi-os) | Choose one; verify capacity and OS image before use |

### Pi accessories, conditional or optional

| Hardware / candidate model | Qty | Priority | Purchase links | Note |
|---|---:|---|---|---|
| Waveshare PI5-CASE-B acrylic case | 1 | Recommended enclosure | [Waveshare, overseas](https://www.waveshare.com/product/pi5-case-b.htm) / [The Pi Hut Active Cooler case, overseas alternative](https://thepihut.com/collections/latest-raspberry-pi-products/products/case-for-raspberry-pi-5-and-active-cooler) | Both explicitly accommodate the official Active Cooler. Neither is a local-delivery promise |
| Cytron CA-USB-USD-CT microSD reader | 1 if absent | Conditional setup | [Cytron Thailand](https://th.cytron.io/c-development-tools/p-usb2p0-cytron-microsd-card-reader-writer) | Listed for up to 128 GB; suitable for the default 128-GB choice, not a blanket 256-GB guarantee |
| Micro-HDMI to full-size HDMI — Cytron WR-HDMI-MICRO | 1 if using monitor | Conditional display | [Cytron Thailand](https://th.cytron.io/c-accessories-for-rpi-4/p-micro-hdmi-to-standard-hdmi-cable) | The link's category says Pi 4; the cable type is also appropriate for Pi 5 |
| Official M.2 HAT+ with 256-GB MakerDisk NVMe | 1 set | Optional storage alternative | [Cytron Thailand](https://th.cytron.io/p-raspberry-pi-md2-hat-plus-with-makerdisk-ssd-256) / [Official HAT installation/compatibility](https://www.raspberrypi.com/news/using-m-2-hat-with-raspberry-pi-5/) | Buy instead of the default storage path if chosen; the acrylic case above is not confirmed to fit this HAT |
| Logitech MK120 USB keyboard/mouse combo | 1 set if absent | Conditional setup | [JIB Thailand](https://www.jib.co.th/web/product/readProduct/56219) | Borrow/reuse first |
| Monitor / HDMI TV | 1 if using local display | Reuse existing | Use an existing HDMI monitor/TV; no new monitor model selected | A display can be omitted when using remote access |

The Pi board is now REQUIRED in the project BOM. Starting radar development on the notebook before Pi setup remains valid. No Pi packages were installed by this sourcing task.

## 3. Radar and development hardware

| Hardware / exact part or candidate | Qty | Priority | Purchase links | Note |
|---|---:|---|---|---|
| TI AWR2944PEVM | 1 | Required, fixed Plan B radar | [DigiKey Thailand](https://www.digikey.co.th/en/products/detail/texas-instruments/AWR2944PEVM/27687246) / [Mouser](https://eu.mouser.com/en/ProductDetail/Texas-Instruments/AWR2944PEVM?qs=jcD%2FCkGBYeMzI58hrdXJcw%3D%3D) | Select PEVM, not AWR2944EVM or the bare AWR2944P IC |
| MEAN WELL GST60A12-P1J | 1 | Required radar power | [DigiKey Thailand](https://www.digikey.co.th/en/products/detail/mean-well-usa-inc/GST60A12-P1J/7703712) | 12 V, 5 A, center positive, 2.1 x 5.5 mm barrel; AC cord separate |
| Grounded TIS mains plug to IEC C13, 1 sq.mm. | 1 if absent | Required mains cable | [HomeNet48 Thailand](https://www.homenet48.com/product/39842/ac-power-tis-c13-1sqmm) / [1.5-sq.mm. alternative](https://www.homenet48.com/product/42271/ac-power-tis-c13-15sqmm) | Choose one; grounded Thai mains end, C13 equipment end |
| Windows notebook / PC | 1 | Required development | Use the team's existing Windows notebook/PC | No new computer selected without knowing existing equipment |
| USB-to-Gigabit-Ethernet — TP-Link UE300 (USB-A) | 1 if notebook lacks RJ45 | Conditional | [JIB Thailand](https://www.jib.co.th/web/product/readProduct/87181/2/) / [USB-C alternative UE300C, manufacturer](https://www.tp-link.com/th/home-networking/usb-ethernet-adapter/ue300c/) | Select by notebook port; UE300C link is manufacturer information, not a confirmed retailer listing |
| UGREEN 20841 USB-C to four USB-A 3.0 ports | 1 if needed | Conditional hub | [UGREEN Thailand](https://www.ugreen.co.th/product/20841-slim-4-in-1-usb-c-to-4-ports-usb-3-0-hub-adapter/11000826690001380) | This hub does not add Ethernet; notebook USB-C is required |
| USB-A to Micro-B data cable — Cytron WR-USB-UB | 0-1 extra | Included cable + conditional extra | [Cytron Thailand](https://th.cytron.io/p-usb-micro-b-cable) | Radar kit includes one; additional debug connection may require another |
| CAT6 RJ45 cable — SparkFun CAB-08915, 3 ft | 0-1 extra | Included cable + conditional spare | [SparkFun, overseas](https://www.sparkfun.com/cat-6-cable-3ft.html) | Use the TI included cable first; ordinary Cat5e/Cat6 RJ45 is sufficient |
| Adjustable stand/tripod — candidate Ulanzi MT-44 B | 1 dedicated radar stand | Required stable positioning | [ZoomCamera Thailand](https://www.zoomcamera.net/shop/tripods-gimbals/tripods-supports/ulanzi-mt-44-b-2-in-1-selfie-stick-tripod/) | Stand candidate only; must verify stability with board and cables and provide a board adapter |
| Radar board adapter, M3 screws/standoffs | 1 set | Required mounting implementation | Use the TI included bracket, screws and spacers first; [kit contents](https://www.ti.com/tool/AWR2944PEVM) | A camera tripod mount is not automatically a direct PCB mount. No unverified universal plate SKU selected |
| External SSD — Samsung T7 1 TB, MU-PC1T0T/WW | 1 | Recommended recordings/backup | [JIB Thailand](https://www.jib.co.th/web/product/readProduct/41677/1TB-PORTABLE-SSD--%E0%B9%80%E0%B8%AD%E0%B8%AA%E0%B9%80%E0%B8%AD%E0%B8%AA%E0%B8%94%E0%B8%B5%E0%B8%9E%E0%B8%81%E0%B8%9E%E0%B8%B2--SAMSUNG-T7--GRAY---MU-PC1T0T-WW-) / [Samsung Thailand](https://www.samsung.com/th/memory-storage/portable-ssd/portable-ssd-t7-1tb-gray-mu-pc1t0t-ww/) | Backup candidate; do not infer availability from the model listing |

## 4. IMU validation and logger — optional/conditional until the protocol is chosen

| Hardware / candidate model | Qty | Purchase links | Dependency / selection note |
|---|---:|---|---|
| Adafruit LSM6DSOX 6-DoF breakout — #4438 | 1-3 | [DigiKey Thailand](https://www.digikey.co.th/en/products/detail/adafruit-industries-llc/4438/11497501) / [Adafruit, overseas](https://www.adafruit.com/product/4438) | Matches LSM6DSOX in the infographic; buy the breakout, not the loose chip. An Adafruit page snapshot showed out of stock; check distributor stock before ordering |
| Separate NodeMCU ESP32 development board — ESP-WROOM-32 | 0-1 initially | [Cytron Thailand](https://th.cytron.io/c-esp32/p-nodemcu-esp32) | Only for independent IMU logging; one controller with wired sensors or multiple wireless nodes are different architectures and must not be conflated |
| STEMMA QT/Qwiic JST-SH cable, 100 mm — Adafruit #4210 | As wiring requires | [Adafruit, overseas](https://www.adafruit.com/product/4210) | Direct board-to-board cable; confirm length is sufficient for body placement |
| Qwiic/STEMMA QT to female header sockets, 150 mm — Adafruit #4397 | 1 if connecting Qwiic sensor to NodeMCU headers | [Adafruit, overseas](https://www.adafruit.com/product/4397) | Converts the sensor's JST-SH connector to female sockets for a controller with male headers; confirm pin mapping |
| Female-to-female 20-cm jumpers — Cytron WR-JW-FF10 | 1 pack initially | [Cytron Thailand](https://th.cytron.io/p-female-to-female-jumper-wire) | Use for header connections; unsoldered headers need assembly |
| TCA9548A multiplexer breakout — Adafruit #2717 | 0-1 | [DigiKey Thailand](https://www.digikey.co.th/en/products/detail/adafruit-industries-llc/2717/5604376) / [Adafruit, overseas](https://www.adafruit.com/product/2717) | For three same-family IMUs on one I2C bus; #2717 uses headers, so provide jumpers/assembly. A separate mux is unnecessary with suitable SPI or separate controllers |
| Regulated 5-V USB battery pack — example Adafruit #1565, 5000 mAh | 0-1 | [Adafruit, overseas](https://www.adafruit.com/product/1565) | Example for the independent ESP32 USB input only, not Pi 5 or radar. Verify current availability and low-load auto-off behavior before selecting |
| Reusable hook-and-loop straps | 1 set sized to body sites | [Thai marketplace example](https://shopee.co.th/%E0%B8%AA%E0%B8%B2%E0%B8%A2%E0%B8%A3%E0%B8%B1%E0%B8%94%E0%B8%95%E0%B8%B5%E0%B8%99%E0%B8%95%E0%B8%B8%E0%B9%8A%E0%B8%81%E0%B9%81%E0%B8%81-%E0%B8%AA%E0%B8%B2%E0%B8%A2%E0%B8%A3%E0%B8%B1%E0%B8%94%E0%B8%AA%E0%B8%B2%E0%B8%A2%E0%B9%84%E0%B8%9F-%E0%B9%80%E0%B8%97%E0%B8%9B%E0%B8%95%E0%B8%B5%E0%B8%99%E0%B8%95%E0%B8%B8%E0%B9%8A%E0%B8%81%E0%B9%81%E0%B8%81-%E0%B8%82%E0%B8%99%E0%B8%B2%E0%B8%94-2%2A20-2%2A30-2%2A40-3%2A50-%E0%B8%8B%E0%B8%A1-%E0%B8%AA%E0%B8%B5%E0%B8%94%E0%B8%B3-i.86809269.2356285906) | Commodity example, not a medically validated wearable. Select comfortable lengths and use a sensor enclosure/holder |
| Skin-contact tape — example 3M Micropore 1530-1 | 1 roll if needed | [Thai marketplace example](https://shopee.co.th/3M-Micropore-%E0%B9%80%E0%B8%97%E0%B8%9B%E0%B9%81%E0%B8%95%E0%B9%88%E0%B8%87%E0%B9%81%E0%B8%9C%E0%B8%A5-%E0%B9%80%E0%B8%97%E0%B8%9B%E0%B9%80%E0%B8%A2%E0%B8%B7%E0%B9%88%E0%B8%AD%E0%B8%81%E0%B8%A3%E0%B8%B0%E0%B8%94%E0%B8%B2%E0%B8%A9-%E0%B8%82%E0%B8%99%E0%B8%B2%E0%B8%94-1-%E0%B8%99%E0%B8%B4%E0%B9%89%E0%B8%A7-x-10-%E0%B8%AB%E0%B8%A5%E0%B8%B2-%E0%B8%AA%E0%B8%B5%E0%B8%82%E0%B8%B2%E0%B8%A7-%281-%E0%B8%A1%E0%B9%89%E0%B8%A7%E0%B8%99-%E0%B9%84%E0%B8%A1%E0%B9%88%E0%B8%A1%E0%B8%B5%E0%B8%81%E0%B8%A5%E0%B9%88%E0%B8%AD%E0%B8%87-1530-1%29-II-8313-%E0%B8%AD%E0%B9%88%E0%B8%AD%E0%B8%99%E0%B9%82%E0%B8%A2%E0%B8%99-i.97475696.23448564550) | Supplementary securing of leads/holders; does not replace EMG electrodes. Check seller/package authenticity and suitability |

The LSM6DSOX has two selectable I2C addresses (0x6A/0x6B): three identical boards cannot all share one address pair on the same direct bus. See [Adafruit pinouts](https://learn.adafruit.com/lsm6dsox-and-ism330dhc-6-dof-imu/pinouts). Wiring and timestamp synchronization remain implementation work, not automatic features of buying these boards.

## 5. Experiment and demo equipment

| Hardware / candidate model | Qty | Priority | Purchase links | Note |
|---|---:|---|---|---|
| Adjustable dumbbell set — Decathlon reference 8018574, 20-kg total kit | 1 set or reuse | Required suitable resistance | [Decathlon Thailand](https://www.decathlon.co.th/p/%E0%B8%8A%E0%B8%B8%E0%B8%94%E0%B8%94%E0%B8%B1%E0%B8%A1%E0%B9%80%E0%B8%9A%E0%B8%A5%E0%B8%AA%E0%B8%B3%E0%B8%AB%E0%B8%A3%E0%B8%B1%E0%B8%9A%E0%B8%81%E0%B8%B2%E0%B8%A3%E0%B8%9D%E0%B8%B6%E0%B8%81%E0%B9%80%E0%B8%A7%E0%B8%97%E0%B9%80%E0%B8%97%E0%B8%A3%E0%B8%99%E0%B8%99%E0%B8%B4%E0%B9%88%E0%B8%87-%E0%B8%81%E0%B8%B4%E0%B9%82%E0%B8%A5%E0%B8%81%E0%B8%A3%E0%B8%B1%E0%B8%A1-8018574.html) | Kit capacity is not the exercise load; choose actual load under the experiment protocol |
| Stable chair without wheels — candidate IKEA SANDSBERG | 1 or reuse | Recommended | [IKEA Thailand](https://www.ikea.com/th/en/p/sandsberg-chair-black-80605430/) | Existing suitable chair is adequate |
| Measuring tape — Stanley Global Tape 3 m | 1 or reuse | Recommended positioning | [HomePro Thailand](https://www.homepro.co.th/p/1029086?lang=th) | Record radar distance/height and body positions |
| Floor marking tape — example 3M T76 48 mm | 1 roll | Recommended positioning | [Thai marketplace example](https://shopee.co.th/%2A3M-%E0%B9%80%E0%B8%97%E0%B8%9B%E0%B8%95%E0%B8%B5%E0%B9%80%E0%B8%AA%E0%B9%89%E0%B8%99-%E0%B9%80%E0%B8%97%E0%B8%9B%E0%B8%9E%E0%B8%B1%E0%B8%99%E0%B8%A3%E0%B8%B1%E0%B8%94%E0%B8%AA%E0%B8%B4%E0%B9%88%E0%B8%87%E0%B8%82%E0%B8%AD%E0%B8%87-Vinyl-T76-%2848-%E0%B8%A1%E0%B8%A1.-%E0%B8%A2%E0%B8%B2%E0%B8%A7-33-%E0%B8%A1.%29-i.472243307.21039830751) | Commodity example; removable markers are also acceptable |
| Existing phone/camera | 1 | Recommended video reference | Reuse the team's phone; no new camera purchase selected | Keep it out of final radar-only deployment |
| Phone tripod — Ulanzi MT-44 B | 1 if needed | Recommended video reference | [ZoomCamera Thailand](https://www.zoomcamera.net/shop/tripods-gimbals/tripods-supports/ulanzi-mt-44-b-2-in-1-selfie-stick-tripod/) | A simultaneous video setup needs its own stand if the radar uses the other one |
| Load cell — SparkFun TAL220 10 kg, SEN-13329 | 1 if force experiment approved | Optional | [SparkFun, overseas](https://www.sparkfun.com/load-cell-10kg-straight-bar-tal220.html) | Example only: choose capacity, load direction and fixture after designing the force protocol. A bar load cell alone does not measure dynamic dumbbell force automatically |
| Load-cell amplifier — SparkFun HX711, SEN-13879 | 1 with load cell | Optional paired item | [SparkFun, overseas](https://www.sparkfun.com/sparkfun-load-cell-amplifier-hx711.html) | Requires wiring, calibration and a mechanically suitable fixture |
| Load-cell frame / mounting hardware | 1 if using force rig | Optional mechanical work | Custom fixture; no verified plug-and-play retail kit selected | Do not confuse a bare load cell with a complete force measurement instrument |

## Coverage and sourcing limitations

All hardware groups in the latest no-DCA infographic are covered: radar/development, Pi, sEMG, IMU, experiment/demo, plus the software data path. Notebook, monitor and phone are reuse items, not new purchase recommendations. Radar mounting adapters, wearable holders and the force rig need fit/design decisions; unverified product compatibility is not claimed. Marketplace links are examples for commodity supplies, not endorsements of authenticity. Manufacturer information links are labelled separately from retailer links.

The prior ฿34,763.37 / ฿35,463.73 totals cover only the radar/adapter/MyoWare subset (with/without quoted USB-C cables). They exclude Pi, mains cord, IMU, mounting, SSD and other accessories; do not present them as a full system budget.

The submitted poster and proposal are unchanged. No orders, firmware flashing, package installs, Git commit or push were performed.
