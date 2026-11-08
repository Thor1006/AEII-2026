import csv
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rec import session as S  # noqa: E402
from rec.sources import RadarSource, SerialLineSource, tcp_address  # noqa: E402


class FakeMyoWare(threading.Thread):
    """Plays the record-mode sketch on a pseudo-terminal: 1 kHz samples, sent in 20 ms batches."""

    def __init__(self, seconds):
        super().__init__(daemon=True)
        self.master, self.slave = os.openpty()
        self.path = os.ttyname(self.slave)
        self.seconds = seconds
        self.sent = 0

    def run(self):
        os.write(self.master, b"# truerehab-record v1 emg_hz=1000\n")
        dev0 = 4_294_000_000  # close to the 32-bit wrap, so the reader must unwrap it
        start = time.perf_counter()
        next_us = 0
        while time.perf_counter() - start < self.seconds:
            now_us = (time.perf_counter() - start) * 1e6  # a real ESP32 clock runs at real time
            lines = []
            while next_us <= now_us:  # every 1 ms sample that is due, sent as one batch
                lines.append(f"E,{(dev0 + next_us) % (1 << 32)},{2048 + self.sent % 50},{300}")
                next_us += 1000
                self.sent += 1
            if lines:
                os.write(self.master, ("\n".join(lines) + "\n").encode())
            time.sleep(0.02)


class FakeWifiImu(threading.Thread):
    """The IMU board's Wi-Fi link (RECORD mode, 200 Hz, device clock = real time) on localhost.

    Three connections: the board closes the first; the second goes silent with the socket still open
    (Wi-Fi gone); the third stays open until the test ends. Each ends with half a line. While nobody is
    connected the board keeps sampling and drops those lines, so its clock jumps ahead.
    """

    def __init__(self, seconds_each=0.6):
        super().__init__(daemon=True)
        self.server = socket.create_server(("127.0.0.1", 0))
        self.server.settimeout(10)
        self.url = f"tcp://127.0.0.1:{self.server.getsockname()[1]}"
        self.seconds_each = seconds_each
        self.sent = []  # device time of every whole I line sent
        self.kept_open = []

    def run(self):
        dev0, start = 4_294_000_000, time.perf_counter()  # close to the 32-bit wrap
        for episode in range(3):
            conn, _ = self.server.accept()
            next_us = (time.perf_counter() - start) * 1e6 // 5000 * 5000  # resume at "now" on the device clock
            conn.sendall(b"# truerehab-imu-record v2 fw=2.1 rate_hz=200\n")
            t_end = time.perf_counter() + self.seconds_each
            while time.perf_counter() < t_end:
                now_us = (time.perf_counter() - start) * 1e6
                lines = []
                while next_us <= now_us:
                    us = int(dev0 + next_us) % (1 << 32)
                    lines.append(f"I,{us},0,0,16384,{len(self.sent)},0,0")
                    self.sent.append(us)
                    next_us += 5000
                if lines:
                    conn.sendall(("\n".join(lines) + "\n").encode())
                time.sleep(0.02)
            conn.sendall(b"I,1,2,3")  # cut mid-line
            if episode == 0:
                conn.close()
            else:
                self.kept_open.append(conn)

    def close(self):
        """Close what the board would close when switched off (the test's sockets, so none are left open)."""
        for conn in self.kept_open:
            conn.close()
        self.server.close()


class AlignTest(unittest.TestCase):
    def test_unwrap(self):
        v = [4294967000, 4294967290, 5, 300]
        self.assertTrue(np.all(np.diff(S.unwrap_u32(v)) > 0))

    def test_jitter_and_drift_removed(self):
        rng = np.random.default_rng(1)
        dev_us = np.arange(0, 60_000_000, 1000)  # 60 s at 1 kHz
        true_host = dev_us * 1e3 * 1.00003 + 5e9  # 30 ppm drift, 5 s offset
        burst = (dev_us // 20000) * 20000  # delivered in 20 ms batches
        host = burst * 1e3 * 1.00003 + 5e9 + 20e6 + rng.exponential(8e6, len(dev_us))  # + Bluetooth delay
        err_ms = np.abs(S.align_device_time(dev_us, host) - true_host) / 1e6
        self.assertLess(np.median(err_ms), 25)  # constant delay remains; jitter and drift are gone
        self.assertLess(np.std(err_ms), 1.0)

    def test_delay_bursts_dont_tilt_the_clock(self):
        # Wi-Fi as measured 2026-11-05: ms of jitter, plus two ~1 s pauses whose samples then arrive at once
        rng = np.random.default_rng(2)
        dev_us = np.arange(0, 120_000_000, 5000)  # 2 min at 200 Hz
        true_host = dev_us * 1e3 * 1.00002 + 3e9  # 20 ppm drift, 3 s offset
        delay = 4e6 + rng.exponential(6e6, len(dev_us))
        for start in (10e6, 56e6):  # device us
            held = (dev_us >= start) & (dev_us < start + 1.1e6)
            delay[held] += (start + 1.1e6 - dev_us[held]) * 1e3  # waits until the pause ends
        err_ms = (S.align_device_time(dev_us, true_host + delay) - true_host) / 1e6
        self.assertLess(np.percentile(err_ms, 99) - np.percentile(err_ms, 1), 1.0)  # no tilt: a constant offset
        self.assertAlmostEqual(float(np.median(err_ms)), 4.0, delta=1.0)  # = the least delay


class SessionTest(unittest.TestCase):
    def test_repeated_lines_dropped(self):
        # macOS replays one stale line ~50 times when a port opens; the last copy is spliced onto a new line
        with tempfile.TemporaryDirectory() as d:
            sess = S.SessionWriter(d, "TEST", "dup")
            rows = ["I,1000,0,0,16384,0,0,0"] * 5 + ["I,1000,0,0,16384,9,9,9", "I,6000,1,1,16384,1,1,1",
                                                     "I,11000,2,2,16384,2,2,2"]
            with open(sess.dir / "imu.csv", "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["t_ns", "line"])
                for i, ln in enumerate(rows):
                    w.writerow([i * 1_000_000, ln])
            sess.close({})
            imu = S.load(sess.dir).record_mode("imu", "I")
            self.assertEqual(len(imu["t_s"]), 3)
            self.assertEqual(imu["values"][:, 3].tolist(), [0, 1, 2])

    def test_two_sessions_in_the_same_second(self):
        with tempfile.TemporaryDirectory() as d:
            a = S.SessionWriter(d, "TEST", "same")
            b = S.SessionWriter(d, "TEST", "same")
            a.close({})
            b.close({})
            self.assertNotEqual(a.dir, b.dir)
            self.assertTrue(b.dir.name.startswith(a.dir.name[:17]))

    def test_tcp_address(self):
        self.assertEqual(tcp_address("tcp://truerehab-imu.local:3333"), ("truerehab-imu.local", 3333))
        self.assertIsNone(tcp_address("/dev/cu.usbserial-0001"))
        with self.assertRaises(ValueError):
            tcp_address("tcp://truerehab-imu.local")

    def test_wifi_link_unreachable_fails_early(self):
        free = socket.create_server(("127.0.0.1", 0))
        port = free.getsockname()[1]
        free.close()  # nothing listens there now
        with tempfile.TemporaryDirectory() as d:
            sess = S.SessionWriter(d, "TEST", "wifi")
            with self.assertRaisesRegex(OSError, "can't reach"):
                SerialLineSource(sess, "imu", f"tcp://127.0.0.1:{port}")
            sess.close({})  # record.py also closes the session when a source can't start

    def test_wifi_link_reconnects(self):
        with tempfile.TemporaryDirectory() as d:
            sess = S.SessionWriter(d, "TEST", "wifi")
            imu = FakeWifiImu()
            self.addCleanup(imu.close)
            src = SerialLineSource(sess, "imu", imu.url)
            src.TCP_IDLE_S, src.TCP_RETRY_S = 0.5, 0.2  # faster than real life, same logic
            imu.start()
            src.start()
            imu.join(timeout=15)
            time.sleep(0.2)  # the last connection is still open and quiet: stop before it times out
            src.stop()
            sess.close({"imu": src.summary()})

            s = S.load(sess.dir)
            with open(sess.dir / "imu.csv", newline="") as f:
                lines = [row[1] for row in csv.reader(f)][1:]  # every row, comments included
            notes = [ln for ln in lines if ln.startswith("# recorder:")]
            self.assertEqual(notes, ["# recorder: link lost (closed by the board)", "# recorder: link back",
                                     "# recorder: link lost (no data for 0 s)", "# recorder: link back"])
            self.assertFalse(any("I,1,2,3I" in ln for ln in lines))  # half lines never glued to the next one
            self.assertEqual(src.summary()["link_drops"], 2)

            imu_rows = s.record_mode("imu", "I")
            self.assertEqual(len(imu_rows["t_s"]), len(imu.sent))  # every whole line, none twice
            self.assertEqual(imu_rows["values"][:, 3].tolist(), list(range(len(imu.sent))))
            steps = np.diff(imu_rows["t_s"])
            self.assertTrue(np.all(steps > 0))
            self.assertAlmostEqual(float(np.median(steps)), 0.005, delta=0.0005)  # device clock, 200 Hz
            self.assertEqual(int(np.sum(steps > 0.1)), 2)  # the two outages show up as gaps

    def test_subject_must_be_a_code(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                S.SessionWriter(d, "Jane Doe", "elbow_flexion")

    def test_record_and_read_back(self):
        with tempfile.TemporaryDirectory() as d:
            sess = S.SessionWriter(d, "TEST", "elbow flexion", notes="unit test")
            myo = FakeMyoWare(seconds=1.6)
            radar = RadarSource(sess, sim_fps=60)
            emg = SerialLineSource(sess, "emg", myo.path)
            radar.start()
            emg.start()
            myo.start()
            time.sleep(0.3)
            sess.marker("s")
            sess.marker(" ")
            myo.join()
            time.sleep(0.3)
            radar.stop()
            emg.stop()
            sess.close({"radar": radar.summary(), "emg": emg.summary()})

            s = S.load(sess.dir)
            self.assertEqual(s.meta["exercise"], "elbow_flexion")
            self.assertEqual([m[2] for m in s.markers], ["sync shrugs", "rep start"])

            idx = s.radar_index()
            self.assertGreater(len(idx["frame_no"]), 80)  # ~2 s at 60 fps
            self.assertTrue(np.all(np.diff(idx["t_s"]) >= 0))
            self.assertTrue(np.all(np.diff(idx["frame_no"]) == 1))
            frames = list(s.radar_frames())
            self.assertEqual(len(frames), len(idx["frame_no"]))
            self.assertIn(4, frames[0][1].tlvs)  # static heatmap survived the round trip

            e = s.record_mode("emg", "E")
            self.assertEqual(len(e["t_s"]), myo.sent)  # every sample, none lost
            self.assertTrue(np.all(np.diff(e["t_s"]) > 0))  # unwrapped and in order
            gaps_ms = np.diff(e["t_s"]) * 1e3
            self.assertAlmostEqual(float(np.median(gaps_ms)), 1.0, delta=0.05)  # device clock, not batches
            self.assertEqual(e["values"].shape[1], 2)  # raw, env


if __name__ == "__main__":
    unittest.main()
