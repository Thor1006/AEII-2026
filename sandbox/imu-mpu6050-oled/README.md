# IMU ground-truth firmware (MPU-6050 + OLED)

ESP32 sketch that reads an **MPU-6050** 6-axis IMU, shows live values on a
**128×64 SSD1306 OLED**, and streams the same data over Serial as CSV for
logging on the notebook.

This is a **development / validation tool** — IMU is ground truth for the
radar work, not part of the final radar-only product (see
`CLAUDE/PROJECT.md` non-goals).

## What it does
- Reads accelerometer (g), gyroscope (°/s) and die temperature (°C).
- **Calibrates the gyro resting bias at startup** — hold the board still for
  ~2 s while the OLED shows "keep it STILL". This cuts pitch/roll drift. The
  measured bias is printed over Serial as a `# gyro bias ...` comment.
- Fuses accel + gyro into **pitch/roll** angles with a complementary filter
  (α = 0.98) — the angle is the useful rehab number (joint ROM).
- OLED shows temp, accel, gyro and large pitch/roll.
- Serial prints one CSV line per sample at 115200 baud.

> **Yaw is not available.** The MPU-6050 has no magnetometer, so rotation
> about the vertical axis has nothing to correct its drift. Trust **pitch and
> roll** only; don't build on yaw.

## Wiring (ESP32, shared I2C bus)
| Signal | ESP32 pin | MPU-6050 | OLED |
|--------|-----------|----------|------|
| Power  | 3V3       | VCC      | VCC  |
| Ground | GND       | GND      | GND  |
| SDA    | GPIO 21   | SDA      | SDA  |
| SCL    | GPIO 22   | SCL      | SCL  |

Tie the MPU-6050 **AD0 pin to GND** so its I2C address stays `0x68`.
The OLED is at `0x3C`. Both share the one I2C bus — no conflict.

> Power both from **3V3**, not 5V. The ESP32 is a 3.3 V part and most
> MPU-6050 / OLED breakout boards are happy at 3.3 V.

## Libraries (Arduino IDE → Library Manager)
Install these, then upload:
- `Adafruit MPU6050`
- `Adafruit SSD1306`
- `Adafruit GFX Library`
- `Adafruit Unified Sensor` (usually pulled in automatically)

Board support: install the **esp32 by Espressif Systems** boards package,
select your ESP32 board, set baud to 115200.

## Confirm addresses first (optional)
`i2c_scanner/i2c_scanner.ino` is a throwaway diagnostic. Upload it, open the
Serial Monitor at 115200, and it prints every I2C address it finds (annotated
with which is the MPU-6050 and which is the OLED). Use it if the main sketch
can't find a device, then update `OLED_ADDR` / the MPU address if yours differ.

> **Arduino quirk:** the IDE compiles *every* `.ino` in one folder together,
> so the scanner lives in its own `i2c_scanner/` subfolder — open it as a
> separate sketch. If the IDE offers to move a `.ino` into a matching folder,
> let it; it's just enforcing "one sketch = one folder".

## Serial CSV format
```
# t_ms,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps,temp_c,pitch_deg,roll_deg
```
`t_ms` is `millis()` on the ESP32 (relative to boot). Accel is in g,
gyro in °/s, pitch/roll in degrees. To use this as radar ground truth you
still need a **shared time reference** between the ESP32 clock and the radar
collector — that sync protocol is an open question in `CLAUDE/CONTEXT.md`.

## Logging on the notebook
`log_imu.py` reads the serial stream and writes it to a timestamped CSV,
stamping each line with the **host clock on arrival** (`host_epoch_ms`,
`host_iso`). That host timestamp is the common clock you can later align
against the radar collector — a first step toward sync, not a full solution.

```bash
pip install pyserial
python log_imu.py --port COM7          # Windows; use /dev/ttyUSB0 on Linux/macOS
python log_imu.py --port COM7 --out session1.csv
```

Close the Arduino Serial Monitor first — only one program can hold the port.
Device `#` comment lines (boot banner, gyro bias) are echoed to the console;
only data rows are written to the file. Ctrl+C stops and reports the count.

> `log_imu.py` is for **standalone** use only. For recordings that line up
> with the radar, use **record mode** below instead — it's time-aligned to the
> radar and sEMG; the standalone logger is not.

## Record mode — feed the session recorder (`recorder/`)
This sketch can instead emit the exact line the project's session recorder
expects, so a **dedicated IMU+OLED ESP32** plugs straight into
`recorder/record.py`. Set the switch near the top of the sketch:

```c
#define RECORD_MODE 1
```

Then it streams, at 200 Hz on **921600 baud**:
```
I,<micros>,ax,ay,az,gx,gy,gz
```
raw int16 register counts at **±2 g (16384/g)** and **±250 °/s (131/°·s⁻¹)** —
the same format and scale as `firmware/myoware_record`. The OLED still shows
pitch/roll as a live check; the raw line carries **no** bias removal (offline
tools handle that) and **no** temperature or fusion.

Record a session with it on its own USB port:
```bash
cd recorder
.venv/bin/python record.py --subject S01 --exercise elbow_flexion \
    --radar-data <radar_data_port> --radar-cli <radar_cmd_port> \
    --imu <this_esp32_port>
```
Read the IMU back on the radar's timeline:
```python
from rec import session
s = session.load("data/sessions/<...>")
imu = s.record_mode("imu", "I")   # t_s aligned to radar, values[:, 0:6] = ax..gz counts
```

**Notes**
- `RECORD_MODE 0` (default) keeps the human CSV + `log_imu.py` behaviour.
- Counts are converted from the Adafruit library's SI values, so they match
  the ±2 g/±250 °/s scale to <1 LSB. Don't mix with the standalone ±4 g/±500 °/s
  data — different scale factors.
- Start each session with 3 quick shoulder shrugs (press `s` in the recorder)
  so the IMU, radar and sEMG offsets can be measured and corrected.

## Quick checks if it doesn't work
- **Blank OLED / "SSD1306 not found"**: some 128×64 modules are at `0x3D` —
  change `OLED_ADDR`. Run an I2C scanner sketch to confirm addresses.
- **"MPU6050 0x68?" on screen**: check AD0 → GND and the SDA/SCL wiring.
- **Garbled Serial**: set the Serial Monitor to 115200 baud.
- **SH1106 panel** (1.3" that looks like SSD1306): needs a different driver
  (`Adafruit_SH110X`); this sketch targets SSD1306.

## Tuning
- `SAMPLE_HZ` (default 50) — IMU read + filter rate.
- `DISPLAY_HZ` (default 10) — OLED refresh (OLED I2C writes are slow; keep low).
- `ALPHA` (default 0.98) — higher trusts the gyro more (smoother, more drift).
- Accel/gyro ranges in `setup()` — widen for faster/larger motion.
