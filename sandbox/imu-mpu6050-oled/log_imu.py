#!/usr/bin/env python3
"""TrueRehab-RF (AEII 2026) - IMU serial logger.

Reads the CSV stream from imu_mpu6050_oled.ino and writes it to a file,
stamping every line with the HOST clock on arrival. That host timestamp is
the shared reference you can later align against the radar collector's
timestamps (the full radar/IMU sync protocol is still an open question in
CLAUDE/CONTEXT.md - this just gives both sides one common clock).

Usage:
    python log_imu.py --port COM7
    python log_imu.py --port /dev/ttyUSB0 --out my_session.csv

Dependency: pyserial  (pip install pyserial)
"""

import argparse
import csv
import sys
import time
from datetime import datetime, timezone

try:
    import serial  # pyserial
except ImportError:
    sys.exit("pyserial not installed - run: pip install pyserial")


def main() -> None:
    ap = argparse.ArgumentParser(description="Log the ESP32 IMU CSV stream.")
    ap.add_argument("--port", required=True,
                    help="serial port, e.g. COM7 or /dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=115200,
                    help="baud rate (must match the sketch, default 115200)")
    ap.add_argument("--out", default=None,
                    help="output CSV path (default: imu_log_<timestamp>.csv)")
    args = ap.parse_args()

    out_path = args.out or (
        "imu_log_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv")

    # The device header (without its leading '#'); we prepend host columns.
    device_cols = ["t_ms", "ax_g", "ay_g", "az_g",
                   "gx_dps", "gy_dps", "gz_dps", "temp_c",
                   "pitch_deg", "roll_deg"]
    header = ["host_epoch_ms", "host_iso"] + device_cols

    print(f"Opening {args.port} @ {args.baud} ...")
    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
    except serial.SerialException as exc:
        sys.exit(f"could not open {args.port}: {exc}")

    n = 0
    print(f"Logging to {out_path}  (Ctrl+C to stop)")
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        try:
            while True:
                raw = ser.readline()
                if not raw:
                    continue
                # Host timestamp captured the instant the line arrived.
                now = time.time()
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                if line.startswith("#"):
                    # Device comment (boot banner, gyro bias) - echo only.
                    print("  " + line)
                    continue

                fields = line.split(",")
                if len(fields) != len(device_cols):
                    # Partial line on startup, or garbled - skip it.
                    continue

                iso = datetime.fromtimestamp(
                    now, tz=timezone.utc).isoformat(timespec="milliseconds")
                writer.writerow([int(now * 1000), iso] + fields)
                n += 1
                if n % 50 == 0:
                    f.flush()
                    print(f"  {n} samples...", end="\r", flush=True)
        except KeyboardInterrupt:
            print(f"\nStopped. Wrote {n} samples to {out_path}")
        finally:
            ser.close()


if __name__ == "__main__":
    main()
