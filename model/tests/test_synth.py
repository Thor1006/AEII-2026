"""Fake data vs the real recordings, and the fake sessions' format. (Fake data tests the code only.)"""
import dataclasses
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from _util import have_real_sessions
from trnet import calibrate as CB
from trnet import paths
from trnet import pipeline as PL
from trnet import radar as R
from trnet import synth
from trnet import truth as TR

from rec import session as S  # noqa: E402

STATS = CB.load_stats()
SHORT = synth.Plan(sets=1, reps_per_set=6, set_rest_s=10)


def empty_room(root, background, seed=5):
    person = dataclasses.replace(synth.make_person("F90", seed), reflect=0.0)
    plan = synth.Plan(sets=1, reps_per_set=2, background=background, problems=("no_emg", "no_imu", "no_pose"))
    return S.load(synth.make_session(root, person, plan, stats=STATS))


def per_range_db(rec):
    mag = 20 * np.log10(np.abs(rec.Z[rec.valid]) + 1e-3)
    return np.median(mag, axis=(0, 2))


class FakeVsRealTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.sessions = [synth.make_session(cls.tmp, synth.make_person(f"F{i:02d}", i), SHORT, stats=STATS)
                        for i in range(1, 4)]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_empty_room_noise_floor_matches(self):
        """Noise floor per range bin (median level, and mean power). The real empty-room recording isn't steady:
        its first and second halves differ by up to 4.8 dB in some bins (mean 0.55 dB). So the fake must match
        on average (< 0.5 dB over the 64 bins) and never differ more than the real recording does from itself."""
        real_median = np.median(np.array(STATS["radar"]["static_db_median"]), axis=1)
        real_power = np.array(STATS["radar"]["static_power_db"])
        worst_allowed = 2.5
        if have_real_sessions():
            real = R.load_radar(S.load(paths.SESSIONS / STATS["radar"]["room_from"]))
            m = 20 * np.log10(np.abs(real.Z) + 1e-3)
            h = len(m) // 2
            worst_allowed = np.abs(np.median(m[:h], axis=(0, 2)) - np.median(m[h:], axis=(0, 2))).max()
        modes = ("stats",) + (("real",) if have_real_sessions() else ())
        for bg in modes:
            rec = R.load_radar(empty_room(self.tmp / bg, bg))
            d_med = np.abs(per_range_db(rec) - real_median)
            d_pow = np.abs(10 * np.log10((np.abs(rec.Z[rec.valid]) ** 2).mean(axis=(0, 2))) - real_power)
            self.assertLess(d_med.mean(), 0.5, bg)
            self.assertLess(d_pow.mean(), 0.5, bg)
            self.assertLess(d_med.max(), worst_allowed, f"{bg}: bin {d_med.argmax()} off by {d_med.max():.2f} dB")

    def test_frame_timing_matches_the_real_radar(self):
        rec = R.load_radar(S.load(self.sessions[0]))
        self.assertAlmostEqual(rec.fps, 1 / STATS["radar"]["frame_period_s"], delta=0.01)
        jit = (rec.arrival_s - rec.t_s)[rec.valid] * 1000
        q = STATS["radar"]["delivery_jitter_ms"]["quantiles_0_100_by_5"]
        self.assertAlmostEqual(np.percentile(jit, 50) - np.percentile(jit, 5), q[10] - q[1], delta=0.5)
        self.assertAlmostEqual(np.percentile(jit, 95) - np.percentile(jit, 5), q[19] - q[1], delta=0.5)
        if have_real_sessions():
            real = R.load_radar(S.load(paths.SESSIONS / STATS["radar"]["sessions"][0]))
            for p in (50, 99):
                self.assertAlmostEqual(np.percentile(np.diff(rec.arrival_s[rec.valid]), p),
                                       np.percentile(np.diff(real.arrival_s), p), delta=0.001)

    def test_imu_still_noise_within_20_percent(self):
        imu = TR.load_imu(S.load(self.sessions[0]))
        still = imu.t_s - imu.t_s[0] < 4.5
        wins = [slice(k, k + 200) for k in range(0, int(still.sum()) - 200, 200)]
        acc = np.median([imu.acc_g[w].std(0) for w in wins], 0)
        gyro = np.median([imu.gyro_dps[w].std(0) for w in wins], 0)
        np.testing.assert_allclose(acc, STATS["imu"]["acc_noise_std_g"], rtol=0.2)
        np.testing.assert_allclose(gyro, STATS["imu"]["gyro_noise_std_dps"], rtol=0.2)
        self.assertAlmostEqual(np.median(np.linalg.norm(imu.acc_g[still], axis=1)), STATS["imu"]["acc_norm_g"],
                               delta=0.01)

    def test_wifi_delay_median_within_5_ms(self):
        imu = TR.load_imu(S.load(self.sessions[1]))
        fake = np.median(imu.t_host_s - imu.t_s) * 1000
        if have_real_sessions():
            real_imu = TR.load_imu(S.load(paths.SESSIONS / STATS["wifi"]["session"]))
            real = np.median(real_imu.t_host_s - real_imu.t_s) * 1000
        else:
            q = STATS["wifi"]["extra_delay_ms_quantiles_0_100_by_5"]
            real = q[10] - q[0]
        self.assertAlmostEqual(fake, real, delta=5.0)

    def test_session_format_and_truth(self):
        for d in self.sessions:
            s = S.load(d)
            self.assertEqual(s.meta["format"], "truerehab-session/1")
            self.assertIn("FAKE", s.meta["fake"]["warning"])
            truth = s.meta["fake"]["truth"]["reps"]
            self.assertEqual(sum(1 for _, k, _ in s.markers if k == "space"), len(truth))
            self.assertEqual(sum(1 for _, k, _ in s.markers if k == "s"), 1)
            self.assertEqual(s.record_mode("emg", "E")["values"].shape[1], 2)
            self.assertEqual(s.record_mode("imu", "I")["values"].shape[1], 6)
            self.assertEqual(s.pose()["world"].shape[1:], (33, 3))

    def test_pipeline_finds_the_planned_reps_and_delays(self):
        for d in self.sessions:
            p = PL.process(d)
            truth = p.session.meta["fake"]["truth"]
            self.assertEqual(len(p.reps), len(truth["reps"]))
            for rep, tr in zip(p.reps, truth["reps"]):
                self.assertAlmostEqual(rep.rom_deg, tr["rom"], delta=6)
                self.assertTrue(tr["start"] <= rep.peak_s <= tr["end"] + 0.1)
            self.assertEqual(p.sync["radar"]["shrugs_found"] in (3, 4), True)
            radar_late = 4.0 + 0.3                       # synth: 4 ms + the jitter's low edge
            imu_late = 1.5 + STATS["wifi"]["extra_delay_ms_quantiles_0_100_by_5"][0]
            self.assertTrue(p.sync["imu"]["applied"])
            self.assertAlmostEqual(p.sync["imu"]["offset_ms"], radar_late - imu_late, delta=6.0)
            self.assertTrue(p.sync["pose"]["applied"])
            self.assertAlmostEqual(p.sync["pose"]["offset_ms"], radar_late - STATS["pose"]["latency_ms"], delta=15.0)
            self.assertEqual(p.pose.side, truth["reps"] and p.session.meta["fake"]["person"]["side"])

    def test_injected_problems_show_up(self):
        person = synth.make_person("F50", 50)
        d = synth.make_session(self.tmp / "p", person, dataclasses.replace(SHORT, problems=("radar_gap", "wifi_drop")),
                               stats=STATS)
        s = S.load(d)
        self.assertEqual(s.meta["summary"]["radar"]["missing_frames"], 18)
        self.assertEqual(s.meta["summary"]["imu"]["link_drops"], 1)
        rec = R.load_radar(s)
        self.assertEqual(int((~rec.valid).sum()), 18)
        self.assertTrue(any("link lost" in txt for _, txt in TR.comment_lines(s, "imu")))


if __name__ == "__main__":
    unittest.main()
