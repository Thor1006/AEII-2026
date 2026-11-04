# IMU ground-truth firmware (ESP32 + MPU-6050/6500 + OLED)

ESP32 sketch that reads an **MPU-6050-type IMU**, shows live values on a **128×64 SSD1306 OLED**, and
streams the data over USB serial, either as a CSV for people (**LIVE**) or as the session recorder's line
(**RECORD**, for `recorder/record.py --imu`). With `WIFI_LINK 1` the same lines also go over Wi-Fi.

This is a **development / validation tool**: the IMU is ground truth for the radar work, not part of the
final radar-only product (see `CLAUDE/PROJECT.md` non-goals).

| Folder / file | What it is |
|---|---|
| `imu_mpu6050_oled/` | the firmware; open **this folder** in the Arduino IDE |
| `imu_mpu6050_oled/wifi_secrets.example.h` | template for your Wi-Fi name/password (copy to `wifi_secrets.h`, git-ignored) |
| `i2c_scanner/` | wiring check for both I2C buses (pull-ups, stuck lines, addresses, chip ID) |
| `log_imu.py` | saves LIVE-mode data to a CSV with host timestamps |

> **Our board's chip is not a genuine MPU-6050.** It answers WHO_AM_I **0x74** (MPU-6500 family, the
> MPU-6515 ID). The Adafruit MPU6050 library refuses it, so the sketch talks to the registers directly
> and accepts any chip whose settings read back correctly (0x68, 0x70, 0x71, 0x72, 0x73, 0x74, 0x98, …).

## Wiring: two I2C buses
| Signal | MPU-6050 (bus `Wire`) | OLED (bus `Wire1`) |
|--------|-----------------------|--------------------|
| Power  | VCC → 3V3             | VCC → 3V3          |
| Ground | GND → GND             | GND → GND          |
| SDA    | SDA → GPIO 27         | SDA → GPIO 32      |
| SCL    | SCL → GPIO 26         | SCL → GPIO 33      |

Tie the IMU's **AD0 to GND** (address 0x68; 0x69 also works). The OLED is 0x3C (0x3D also works).
Power both from **3V3**, not 5V.

Why two buses: one OLED refresh takes ~25 ms. The old single-loop sketch stalled for it, so 50 Hz became
~46 Hz with uneven 20/29 ms steps, and 200 Hz recording would have lost about a quarter of the samples.
Now the OLED is drawn by its own task on the ESP32's other core, on its own bus, so it never delays a
sample.

## Upload
- Arduino IDE: install the **esp32 by Espressif Systems** boards package, board **ESP32 Dev Module**,
  port `/dev/cu.usbserial-0001` on this Mac (CP2102 chip) or `COMx` on Windows.
- Libraries (Library Manager): **Adafruit SSD1306** and **Adafruit GFX Library** (they bring Adafruit
  BusIO). No MPU library is needed.
- Choose the mode at the top of `imu_mpu6050_oled.ino`: `#define RECORD_MODE 0` (LIVE) or `1` (RECORD).
- Close the Serial Monitor before uploading or recording: only one program can hold the port.

Command line (the IDE's bundled `arduino-cli`), RECORD mode without editing the file:
```bash
"/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli" compile --upload -p /dev/cu.usbserial-0001 --fqbn esp32:esp32:esp32 --build-property "compiler.cpp.extra_flags=-DRECORD_MODE=1" sandbox/imu-mpu6050-oled/imu_mpu6050_oled
```

## The two modes
**LIVE** (`RECORD_MODE 0`, default): 115200 baud, 50 Hz.
```
t_ms,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps,temp_c,pitch_deg,roll_deg
```
`t_ms` is the ESP32's `millis()` at the moment of the reading. Accel in g (accel calibration applied if
there is one), gyro in °/s with the resting bias removed, pitch/roll in degrees. Data starts once the
start-up gyro calibration is done (at most 5 s).

**RECORD** (`RECORD_MODE 1`): 921600 baud, 200 Hz, the recorder's line:
```
I,<micros>,ax,ay,az,gx,gy,gz
```
`micros` is the ESP32's microsecond clock when the sample was read, so the recorder can line it up with
the radar. Values are **counts at 16384 per g and 131 per °/s**, the same scale as `firmware/myoware_record`.
They are **raw**: no gyro bias and no accel calibration (both are in the `#` lines, for offline use).
- `RECORD_WIDE_RANGE 1` (default): the sensor runs at ±4 g / ±500 °/s and the counts are 2 × the
  register value. Quick reps don't clip at ±2 g / ±250 °/s, but values can then exceed ±32767
  (don't store them as int16).
- `RECORD_WIDE_RANGE 0`: ±2 g / ±250 °/s, plain int16 register values.

Sensor low-pass: ~44 Hz in RECORD (≈5–6 ms delay), ~20 Hz in LIVE (≈9–10 ms delay). The timestamp is
when the sample was read; the motion it shows is that much older.

## Comment lines (`#`)
Both modes print comments; `log_imu.py` and the recorder's `record_mode()` skip them.
- **Header**: mode, rate, scale, range, chip address/ID, I2C speed, pull-ups, accel calibration. RECORD
  repeats it every 10 s, because the recorder opening the port does **not** reset the board.
- **`# status` every 5 s**: `samples`, `rate_hz`, `skipped` (missed sample slots), `i2c_err`,
  `recoveries` (reconnects), `frozen`, `saturated` (samples at full scale), `i2c_hz`, `gyro_cal`,
  `gyro_bias_dps` (RECORD also `gyro_bias_counts`), `a_rest_g` (|a| when still), `accel_cal`, `temp_c`,
  `oled`.
- Events: calibration results, `imu lost`, `imu reconnected`, OLED found/missing.

Keys in the Serial Monitor (type, then Enter): `c` gyro calibration · `a` accel calibration · `x` cancel
it · `X` erase the saved accel calibration · `?` header, status, help.

## Calibration
**Gyro bias**: automatic at start-up. Keep the board **still** for ~1.5 s; the OLED shows *hold STILL*
with a bar. A moving board is refused (it retries for 30 s, then keeps the old bias and shows *gyro
uncal*). Redo it any time with a **short press of BOOT** or `c`; data keeps streaming meanwhile.

**Accelerometer (once per IMU board, recommended)**: at rest our clone reads |a| = **0.88 g** instead of
1.00 g, which skews the angles by several degrees. Six-face calibration fixes offset and gain per axis:
1. Send `a`, or **hold BOOT for 3 s** and release.
2. Put each face up in turn (+X, −X, +Y, −Y, +Z, −Z), flat and still for ~1 s each. The OLED marks
   each captured face; order doesn't matter.
3. After the sixth face it's saved in flash (survives power-off) and applied to LIVE data, the OLED and
   the angles. `X` erases it; a different chip ID ignores it.

RECORD lines stay raw. Their header prints `off_g` and `scale`; correct offline with
`a_g = (counts / 16384 - off_g) / scale`.

## Recording with the session recorder (`recorder/`)
Upload with `RECORD_MODE 1`, then:
```bash
cd recorder
.venv/bin/python record.py --subject S01 --exercise elbow_flexion --radar-data <radar_data_port> --radar-cli <radar_cmd_port> --imu /dev/cu.usbserial-0001
```
Read it back on the radar's timeline:
```python
from rec import session
s = session.load("data/sessions/<...>")
imu = s.record_mode("imu", "I")   # t_s aligned to radar, values[:, 0:6] = ax..gz counts
```
Start each session with 3 quick shoulder shrugs (press `s` in the recorder) so the IMU, radar and sEMG
offsets can be measured. Without a USB cable, use the Wi-Fi link below.

## Wi-Fi link (`WIFI_LINK 1`)
The same lines also go out over Wi-Fi, so the board can sit on a moving arm with just a USB power bank.
USB keeps working at the same time.

1. Copy `imu_mpu6050_oled/wifi_secrets.example.h` to `imu_mpu6050_oled/wifi_secrets.h` and put your
   network name and password in the copy. That file is git-ignored.
   - The ESP32 only joins **2.4 GHz** networks, and the network must let devices talk to each other. A
     home network works, and so does an iPhone hotspot with "Maximize Compatibility" on. School/enterprise
     and guest networks usually block it.
   - The Mac must be on the same network.
2. Upload with `WIFI_LINK 1` (plus `RECORD_MODE 1` for the recorder):
   ```bash
   "/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli" compile --upload -p /dev/cu.usbserial-0001 --fqbn esp32:esp32:esp32 --build-property "compiler.cpp.extra_flags=-DRECORD_MODE=1 -DWIFI_LINK=1" sandbox/imu-mpu6050-oled/imu_mpu6050_oled
   ```
3. Watch the OLED:
   - `wifi: joining...` while it connects;
   - `wifi <IP address>` once it's on the network;
   - `W` on the top line and `ok, wifi streaming` while a client receives data.
4. Record from `recorder/` with `--imu tcp://truerehab-imu.local:3333`. If the `.local` name isn't found,
   use the IP from the OLED, e.g. `tcp://192.168.1.42:3333`. To watch the stream by hand, run
   `nc -4 truerehab-imu.local 3333`; keys such as `?` work there too. Without `-4`, macOS spends 5 s
   waiting for an IPv6 address the board doesn't have.

How it behaves:
- **Clients:** one at a time; a new client replaces the old one, so the recorder can always reconnect. On
  connect the board sends its header and status at once.
- **Buffering:** sampling never waits for Wi-Fi. Lines wait in a 32 KB buffer, about 4 s of RECORD data.
  If Wi-Fi stalls longer, whole lines are dropped and counted (`link_dropped`), and the device clock in
  the `I` lines shows the gap. When a send fails, because the client closed or took nothing for ~10 s,
  the board drops that client (`link_send_fails`; a normal disconnect counts too).
- **Reconnects:** the recorder reconnects once a second when the link closes or goes quiet for 6 s. It
  marks this with `# recorder: link lost (...)` and `# recorder: link back` rows, which the readers skip.
- **Status line:** adds `wifi=joining|up|streaming ip=… rssi_dbm=… link_clients=… link_dropped=… link_send_fails=…`.
- **Power:** Wi-Fi power save is off to keep the delay low, so run the board from a USB power bank.
- **Security:** anyone on the same network can read the stream or send the keys. That's fine at home; don't
  use it on public Wi-Fi.

## Logging LIVE data (`log_imu.py`)
Saves each line with the **host clock on arrival** (`host_epoch_ms`, `host_iso`). This is for standalone
use; for anything that has to line up with the radar, use RECORD mode.
```bash
recorder/.venv/bin/python sandbox/imu-mpu6050-oled/log_imu.py --port /dev/cu.usbserial-0001
```

## Built-in robustness
- Never halts. No OLED: data continues, and the OLED is picked up when plugged in.
- IMU missing or lost: the OLED and `#` lines say why (nothing answers, missing pull-up, stuck line,
  wrong device), and it retries every second. Reads are never repeated with a new timestamp; a gap stays
  a gap.
- A stuck bus is freed (9 clocks + STOP); 400 kHz falls back to 100 kHz when the IMU only answers slowly
  or after repeated errors.
- The sensor's settings are read back every second (a power glitch resets them) and identical data for
  0.2 s counts as frozen; both trigger a reconnect.

## Troubleshooting
- **OLED: "no pull-up on SDA27 / SCL26" or "nothing answers"**: check the IMU's **VCC and GND first**
  (a half-powered module looks like a missing pull-up, and the side that's missing can change between
  tries), then SDA/SCL. Run `i2c_scanner/` for the detail.
- **2026-11-04 bench test: the IMU connection was intermittent, and it dropped while the board was
  being moved.** The scanner saw SCL without its pull-up, then everything fine, then SDA without its
  pull-up. The old sketch also failed with "nothing found". Before recording on an arm, solder (or at
  least re-seat) the four IMU wires, keep them short, and add strain relief.
- **"SATURATED: too fast"**: motion beyond ±4 g / ±500 °/s (or ±2 g / ±250 °/s with
  `RECORD_WIDE_RANGE 0`).
- **Wi-Fi: the OLED stays on `wifi: joining...`**: check the name and password in `wifi_secrets.h`. A
  5 GHz-only, enterprise or guest network won't work; try the phone hotspot with "Maximize Compatibility" on.
- **Recorder: "can't reach tcp://truerehab-imu.local:3333"**: the Mac isn't on the board's network, or
  the network blocks devices from reaching each other. Try the IP address from the OLED.
- **SH1106 panel** (1.3" that looks like SSD1306): needs `Adafruit_SH110X`; this sketch targets SSD1306.
- **Garbage at the start of the serial output**: the ESP32's boot messages are at 115200 baud; in RECORD
  mode they show as junk once. On this Mac the serial driver also replays old bytes for a few ms when a
  port opens; the recorder now discards them.

## Tuning (top of the sketch)
Pins, I2C speeds, `SAMPLE_HZ`, low-pass (`DLPF_CFG`), stillness limits, `FILTER_KP` (how strongly the
accelerometer corrects the angle, ~1 s time constant), `ACCEL_GATE` (the accelerometer is ignored while
|a| is more than 15 % off its resting value, i.e. while the arm accelerates).

## Verified (2026-11-04)
- Compiles without warnings (`-Wall -Wextra`, ESP32 core 3.3.12) in five variants: LIVE, RECORD wide,
  RECORD narrow, and two simulated-sensor test builds (`-DIMU_SIMULATE=1`, synthetic ±60° swing).
- **Real sensor** (CP2102 DevKit, chip 0x74, OLED connected, board lying still):
  - RECORD through `recorder/record.py --imu`, 40 s: 8032 samples, **200.00 Hz**, steps 4999–5001 µs,
    no gaps, `skipped=0`, `i2c_err=0`. Host alignment within 0.32 ms (99th percentile). Gyro noise
    0.06 °/s. Header every 10 s.
  - LIVE, 10 s: every step exactly 20 ms (the old sketch: 45.9 Hz, 20/29 ms steps). Gyro noise 0.05–0.07
    °/s after bias removal; angles steady within 0.06°.
  - Gyro bias −1.0 / 1.3 / 0.7 °/s, the same as the old sketch measured. |a| at rest is 0.88 g upside
    down and 1.05 g on its side: the clone's accel offsets, which the 6-face calibration fixes.
  - While the wiring was loose, reconnects, the 100 kHz fallback and the "no pull-up" diagnosis all
    happened on the real board. An earlier 25 s recording had one 10 ms I2C timeout; the scheduler now
    skips that slot instead of bursting, and the timeout is 5 ms.
- Simulated sensor on the same board: the filter's roll tracked the true ±60° swing within 0.9° RMS
  (2.0° max at up to 94 °/s). Keys `a`/`x`/`c`/`?` worked, and gyro calibration refused while moving.
- **Wi-Fi link (fw 2.1)**:
  - Builds: LIVE and RECORD each compile with `WIFI_LINK` 0 and 1, with no warnings from the sketch. With Wi-Fi
    the build is 75 % of flash; the USB-only builds produce the same output as before.
  - Missing `wifi_secrets.h`: the build stops with a message saying what to do.
  - Recorder side, tested against a simulated board on this Mac: a closed link and a silent link were both
    reconnected, every whole line was kept exactly once, and half lines were never glued to the next one.
  - **On the board (2026-11-05):**
    - Setup: home Wi-Fi, RSSI −31 to −46 dBm, board on the desk. A 2-min recording over Wi-Fi, with the board's
      USB output recorded alongside as a reference.
    - Board: 200.0 Hz, `skipped=0`, `i2c_err=0`, `link_dropped=0`. All 23,805 samples present in both copies
      are byte-identical.
    - Reconnect: a second client took the stream at 40 s; the recorder reconnected 1.0 s later
      (`link_drops=1`). The Wi-Fi copy has that one 1.0-s gap; the USB copy has none.
    - Delivery: median 15 ms after USB. 13 % of samples arrived > 30 ms late and 2 % > 100 ms. Two ~1-s Wi-Fi
      pauses were bridged by the board's buffer, with nothing lost.
    - Timing: with the recorder's lower-edge clock fit, Wi-Fi-aligned and USB-aligned times differ by a
      constant 4.1 ms (spread < 0.01 ms over 2 min).
    - Final build, 20 s: 200.05 Hz, no gaps, every common sample identical, 4.0 ms apart (p1–p99 3.6–4.4 ms).
  - Not tested yet: Wi-Fi switched off mid-recording (only the simulated silent link), power-bank power, a
    moving arm, a phone hotspot or school network.
- **Not yet tested**: the full 6-face accel calibration and saving it to flash (needs someone to turn the
  board), the BOOT button, the OLED picture itself (it was found and refreshed, but nobody looked at
  it), and a recording on a moving arm.

## Limits
- **No yaw**: the MPU-6050 has no magnetometer; trust pitch and roll only.
- The accel calibration corrects offset and gain per axis, not cross-axis misalignment.
- The device clock lines up with the radar through the recorder; still check with the shrug marker.
