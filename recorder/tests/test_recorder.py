import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rec import session as S  # noqa: E402
from rec.sources import RadarSource, SerialLineSource  # noqa: E402


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


class SessionTest(unittest.TestCase):
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
