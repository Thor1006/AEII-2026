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
        cls.emg_only = synth.make_session(cls.tmp, synth.make_person("F05", 5), dataclasses.replace(
            plan, problems=("no_imu", "no_pose")), stats=STATS)
        cls.rg, cls.rb, cls.rn, cls.re = (check_session(d) for d in (cls.good, cls.bad, cls.no_emg, cls.emg_only))

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

    def test_semg_without_pose_or_imu_still_trains_fatigue(self):
        r = self.re
        self.assertTrue(has(r, "8 reps in 1 set(s) from the sEMG envelope (fallback); 8 space markers", "ok"))
        self.assertTrue(has(r, "quality and compensation can't be labelled", "info"))
        self.assertTrue(r["can_train"]["fatigue"]["ok"], r["can_train"])
        self.assertEqual(r["can_train"]["quality"]["why"], "needs pose or IMU")
        self.assertEqual(r["can_train"]["compensation"]["why"], "needs pose")
        self.assertTrue(r["usable"])

    def test_radar_without_frames_is_reported_not_a_crash(self):
        from rec import session as S
        w = S.SessionWriter(self.tmp / "empty", "TEST", "no_frames")
        w.add_source("radar", {"kind": "AWR2944PEVM mmWave demo (UART)"})
        (w.dir / "radar.bin").write_bytes(b"")
        (w.dir / "radar_index.csv").write_text("frame_no,t_ns,offset,length\n")
        w.close({})
        r = check_session(w.dir)
        self.assertFalse(r["usable"])
        self.assertTrue(has(r, "no frames could be read", "fail"))

    def test_a_board_restart_is_found_and_lined_up(self):
        """A MyoWare that restarts halfway starts its clock again near 0: the check names the restart, and the sEMG
        times stay where they were (one line through both runs put them 23-37 s off, 2026-11-09)."""
        import csv
        from rec import session as S
        from trnet import truth as TR
        d = self.tmp / "restart" / self.good.name
        shutil.copytree(self.good, d)
        with open(d / "emg.csv", newline="") as f:
            rows = list(csv.reader(f))
        data = [i for i, r in enumerate(rows) if i > 0 and len(r) == 2 and r[1].startswith("E,")]
        mid = data[len(data) // 2]
        dev_mid = int(rows[mid][1].split(",")[1])
        kept = []
        for i, r in enumerate(rows):
            if i >= mid and len(r) == 2 and r[1].startswith("E,"):
                p = r[1].split(",")
                dev = (int(p[1]) - dev_mid) & 0xFFFFFFFF
                if dev < 2_000_000:                                   # rebooting for 2 s: nothing sent
                    continue
                p[1] = str(dev - 2_000_000 + 300_000)                 # its clock starts again at 0.3 s
                r = [r[0], ",".join(p)]
            kept.append(r)
        with open(d / "emg.csv", "w", newline="") as f:
            csv.writer(f).writerows(kept)
        before, after = TR.load_emg(S.load(self.good)), TR.load_emg(S.load(d))
        n1 = len(data) // 2
        n2 = len(after.t_s) - n1
        self.assertLess(abs(after.t_s[:n1] - before.t_s[:n1]).max(), 0.002)
        self.assertLess(abs(after.t_s[n1:] - before.t_s[-n2:]).max(), 0.002)
        r = check_session(d)
        self.assertTrue(has(r, "the board restarted 1 time(s)", "warn"), texts(r))
        self.assertFalse(has(r, "times don't line up"))

    def test_another_program_on_the_myoware_is_named(self):
        import csv
        import json
        d = self.tmp / "other" / self.emg_only.name
        shutil.copytree(self.emg_only, d)
        meta = json.loads((d / "meta.json").read_text())
        meta["sources"]["emg"]["port"] = "tcp://truerehab-myoware.local:3334"
        (d / "meta.json").write_text(json.dumps(meta))
        with open(d / "emg.csv", newline="") as f:
            last_t = int(list(csv.reader(f))[-1][0])
        with open(d / "emg.csv", "a", newline="") as f:                 # 2 more clients, none of them ours
            w = csv.writer(f)
            for k, clients in ((1, 1), (2, 3)):
                w.writerow([last_t + k, f"# status up_s={100 + k} emg_hz=1000.0 skipped=0 link_clients={clients} "
                                        "link_dropped=0 link_send_fails=0"])
        r = check_session(d)
        self.assertTrue(has(r, "another program connected to the MyoWare 2 time(s)", "warn"), texts(r))
        self.assertTrue(has(r, "board counters: skipped=0, link_dropped=0, link_send_fails=0", "ok"), texts(r))

    def test_board_counters_count_only_the_recording(self):
        from trnet import check as CK
        lines = [(0.0, "# status up_s=100 skipped=3 link_clients=4 link_dropped=10"),
                 (5.0, "# recorder: link back"),
                 (9.0, "# status up_s=109 skipped=3 link_clients=6 link_dropped=12")]
        self.assertEqual(CK._board_counters(lines, ("skipped", "link_dropped", "link_clients")),
                         ({"skipped": 0, "link_dropped": 2, "link_clients": 2}, 2))
        restarted = [(0.0, "# status up_s=900 skipped=7"), (9.0, "# status up_s=4 skipped=1")]
        self.assertEqual(CK._board_counters(restarted, ("skipped",))[0], {"skipped": 1})

    def test_subject_code_rule_is_the_recorders(self):
        from rec import session as S
        from trnet import check as CK
        self.assertEqual(CK.CODE_RE.pattern, S.CODE_RE.pattern)

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
