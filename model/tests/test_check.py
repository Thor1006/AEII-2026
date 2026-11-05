"""The session check on the real recordings (expected results from the plan) and on good/broken fake sessions."""
import dataclasses
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _util import MODEL_DIR, have_real_sessions
from trnet import calibrate as CB
from trnet import paths
from trnet import synth
from trnet.check import check_session

STATS = CB.load_stats()


def texts(r, level=None):
    return [i["text"] for i in r["items"] if level is None or i["level"] == level]


def has(r, fragment, level=None):
    return any(fragment in t for t in texts(r, level))


@unittest.skipUnless(have_real_sessions(), "real recordings not on this computer")
class RealSessionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = {p.name: check_session(p) for p in sorted(paths.SESSIONS.iterdir()) if (p / "meta.json").exists()}

    def pick(self, part):
        return [r for name, r in self.r.items() if part in name]

    def test_radar_only_sessions(self):
        for r in self.pick("TEST_radar_check") + self.pick("TEST_stop_check") + self.pick("TEST_no_reset_check"):
            self.assertFalse(r["usable"])
            self.assertAlmostEqual(r["numbers"]["radar"]["fps"], 60.0, delta=0.05)
            self.assertEqual(r["numbers"]["radar"]["missing"], 0)
            self.assertTrue(has(r, "no movement seen", "warn"))
            self.assertIn("no ground truth", r["can_train"]["quality"]["why"])

    def test_usb_imu_sessions(self):
        for r in self.pick("imu_fw_real"):
            self.assertTrue(has(r, "at 200.0 Hz"))
            self.assertTrue(has(r, "board counters: skipped=0, i2c_err=0, saturated=0", "ok"))
            self.assertFalse(r["usable"])
            self.assertEqual(r["can_train"]["quality"]["why"], "no radar")

    def test_firmware_simulations_are_flagged(self):
        for r in self.pick("imu_fw_sim"):
            self.assertTrue(has(r, "simulated", "warn"))

    def test_wifi_sessions(self):
        for r in self.pick("wifi_"):
            self.assertTrue(has(r, "emg.csv holds I, lines", "fail"))
        self.assertTrue(has(self.pick("wifi_check")[0], "Wi-Fi link dropped 1 time", "warn"))
        self.assertFalse(has(self.pick("wifi_final")[0], "Wi-Fi link dropped"))


class FakeSessionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        plan = synth.Plan(sets=1, reps_per_set=8, set_rest_s=10)
        cls.good = synth.make_session(cls.tmp, synth.make_person("F01", 1), plan, stats=STATS)
        cls.bad = synth.make_session(cls.tmp, synth.make_person("F02", 2), dataclasses.replace(
            plan, problems=("radar_gap", "wifi_drop", "emg_usb", "imu_saturation", "no_shrug", "long_rep",
                            "name_subject", "raw_video")), stats=STATS)
        cls.no_emg = synth.make_session(cls.tmp, synth.make_person("F03", 3), dataclasses.replace(
            plan, problems=("emg_as_imu", "no_pose")), stats=STATS)
        cls.rg, cls.rb, cls.rn = (check_session(d) for d in (cls.good, cls.bad, cls.no_emg))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_good_session_is_usable(self):
        r = self.rg
        self.assertTrue(r["usable"])
        self.assertTrue(all(v["ok"] for v in r["can_train"].values()), r["can_train"])
        self.assertEqual(texts(r, "fail"), [])
        self.assertTrue(has(r, "FAKE data", "warn"))
        self.assertTrue(has(r, "8 reps in 1 set(s) from the pose elbow angle; 8 space markers", "ok"))

    def test_every_planted_problem_is_reported(self):
        r = self.rb
        for fragment in ("18 missing", "does not look like a code", "raw video was saved", "SparkFun",
                         "at the sensor's limit", "Wi-Fi link dropped 1 time", "no 's' (sync shrugs) marker",
                         "get cropped around their peak", "1 gap (200 samples = 1.00 s lost)"):
            self.assertTrue(has(r, fragment, "warn"), fragment)

    def test_wrong_emg_lines_and_missing_pose(self):
        r = self.rn
        self.assertTrue(has(r, "emg.csv holds I, lines", "fail"))
        self.assertFalse(r["can_train"]["fatigue"]["ok"])
        self.assertFalse(r["can_train"]["compensation"]["ok"])
        self.assertEqual(r["can_train"]["compensation"]["why"], "needs pose")
        self.assertTrue(r["can_train"]["quality"]["ok"])      # reps from the IMU
        self.assertTrue(has(r, "from the imu elbow angle"))

    def test_command_line_exit_codes(self):
        cmd = [sys.executable, str(MODEL_DIR / "check_session.py"), "--no-save"]
        ok = subprocess.run(cmd + [str(self.good)], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("verdict: USABLE", ok.stdout)
        radar_only = synth.make_session(self.tmp / "ro", synth.make_person("F04", 4), synth.Plan(
            sets=1, reps_per_set=4, problems=("no_emg", "no_imu", "no_pose")), stats=STATS)
        bad = subprocess.run(cmd + [str(radar_only)], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn("NOT USABLE", bad.stdout)


if __name__ == "__main__":
    unittest.main()
