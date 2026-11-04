#!/usr/bin/env python3
"""TrueRehab-RF (AEII 2026) - IMU serial logger.

Reads the LIVE-mode CSV stream (RECORD_MODE 0) from imu_mpu6050_oled/ and
writes it to a file, stamping every line with the HOST clock on arrival.
Standalone use only: for data that must line up with the radar, use RECORD
mode with recorder/record.py --imu (device timestamps, aligned afterwards).

Usage:
    python log_imu.py --port /dev/cu.usbserial-0001      # macOS (CP2102 board)
    python log_imu.py --port COM7 --out my_session.csv    # Windows

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
    # macOS replays stale bytes for a few ms after a port opens (one old line
    # ~50 times, the last copy spliced onto a new one): drop them.
    time.sleep(0.05)
    ser.reset_input_buffer()

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
