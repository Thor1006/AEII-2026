import unittest

import numpy as np

from _util import have_real_sessions
from trnet import labels as L
from trnet import reps as RP
from trnet import sync as SY
from trnet import truth as TR

from rec import session as S  # noqa: E402

rng = np.random.default_rng(0)


def fake_emg(freqs_by_segment, seconds_each=4.0, fs=1000.0, mains=0.0):
    """Sines at chosen frequencies, one segment after another, on a clean 1-kHz clock."""
    parts = []
    for f in freqs_by_segment:
        t = np.arange(int(seconds_each * fs)) / fs
        parts.append(300 * np.sin(2 * np.pi * f * t) + mains * np.sin(2 * np.pi * 50 * t) + rng.normal(0, 5, t.size))
    raw = 2048 + np.concatenate(parts)
    t_s = np.arange(raw.size) / fs
    return TR.Emg(t_s, raw, np.abs(raw - 2048), t_s, (t_s * 1e6).astype(np.int64))


def flexion_curve(rep_s=2.5, pause_s=1.0, reps_per_set=5, sets=2, set_break_s=12.0, rom=120.0, fs=100.0):
    t, x, now = [], [], 0.0
    for s in range(sets):
        for r in range(reps_per_set):
            tt = np.arange(0, rep_s, 1 / fs)
            t.append(now + tt)
            x.append(rom / 2 * (1 - np.cos(2 * np.pi * tt / rep_s)))
            now += rep_s
            tt = np.arange(0, set_break_s if r == reps_per_set - 1 else pause_s, 1 / fs)
            t.append(now + tt)
            x.append(np.zeros(tt.size))
            now += tt[-1] + 1 / fs if tt.size else 0
    return np.concatenate(t), np.concatenate(x) + rng.normal(0, 0.5, sum(len(a) for a in x))


class EmgTest(unittest.TestCase):
    def test_median_frequency_of_a_known_signal(self):
        t, mdf, _ = TR.emg_mdf(fake_emg([110.0]))   # not a multiple of 50 Hz: those bands are mains, removed
        self.assertTrue(np.all(np.abs(mdf - 110) <= 2), mdf)

    def test_mains_hum_is_removed(self):
        t, mdf, _ = TR.emg_mdf(fake_emg([120.0], mains=2000.0))
        self.assertTrue(np.all(np.abs(mdf - 120) <= 2), mdf)

    def test_twenty_percent_mdf_drop_is_full_fatigue(self):
        reps = [RP.Rep(i, i + 0.5, i + 1, 100, 100, -1.6) for i in range(6)]
        meas = [{"rom_deg": 100, "peak_speed_dps": 100, "sparc": -1.6, "mdf_hz": f, "rise_cm": 0, "lean_deg": 0}
                for f in (100, 100, 100, 90, 80, 70)]
        raw_rule = {**L.PLACEHOLDER_THRESHOLDS, "mdf_smooth_reps": 1}
        tgt, msk, aux, aux_m = L.make_labels(reps, meas, raw_rule)
        np.testing.assert_allclose(tgt["fatigue"], [0, 0, 0, 0.5, 1.0, 1.0], atol=1e-6)
        self.assertTrue(msk["fatigue"].all())
        np.testing.assert_allclose(aux[:, 3], [1, 1, 1, 0.9, 0.8, 0.7], atol=1e-6)

    def test_mdf_label_is_smoothed_over_three_reps(self):
        self.assertEqual(L.smooth_over_reps([100, 100, 100, 70, 100, 100]).tolist(), [100, 100, 90, 90, 90, 100])
        out = L.smooth_over_reps([100, np.nan, 90])
        self.assertTrue(np.isnan(out[1]) and out[0] == 100 and out[2] == 90)


class RepsTest(unittest.TestCase):
    def test_reps_and_sets_are_found(self):
        t, x = flexion_curve()
        reps = RP.find_reps(t, x)
        self.assertEqual(len(reps), 10)
        self.assertEqual([r.set_id for r in reps], [0] * 5 + [1] * 5)
        for r in reps:
            self.assertAlmostEqual(r.rom_deg, 120, delta=4)
            self.assertTrue(1.8 <= r.duration_s <= 2.6, r.duration_s)   # 10 % onset/offset trims the ends
            self.assertLess(r.sparc, 0)

    def test_small_wiggles_are_not_reps(self):
        t = np.arange(0, 20, 0.01)
        self.assertEqual(RP.find_reps(t, 10 * np.sin(2 * np.pi * t / 2)), [])

    def test_zigzag(self):
        x = np.array([0, 5, 1, 40, 38, 2, 3, 45, 0], float)
        self.assertEqual(RP.zigzag(x, 30), [(0, -1), (3, +1), (5, -1), (7, +1), (8, -1)])

    def test_rep_frames_crop_and_pad(self):
        ft = np.arange(0, 10, 1 / 60)
        valid = np.ones(ft.size, bool)
        valid[130] = False
        rep = RP.Rep(2.0, 3.0, 4.5, 90, 100, -1.6)
        idx, mask, cropped = RP.rep_frames(rep, ft, valid, 64)
        self.assertTrue(cropped)
        self.assertTrue(abs(ft[idx[32]] - 3.0) < 0.05)   # centred on the peak
        short = RP.Rep(2.0, 2.4, 2.8, 90, 100, -1.6)
        idx, mask, cropped = RP.rep_frames(short, ft, valid, 64)
        self.assertFalse(cropped)
        self.assertEqual(int((idx >= 0).sum()), 49)
        self.assertFalse(mask[49:].any())
        self.assertFalse(mask[list(idx).index(130)])     # the missing frame stays masked


class LabelsTest(unittest.TestCase):
    def setUp(self):
        self.reps = [RP.Rep(i * 3, i * 3 + 1, i * 3 + 2, 100, 100, -1.6, set_id=0 if i < 8 else 1)
                     for i in range(10)]

    def meas(self, over=None):
        over = over or {}
        rows = [{"rom_deg": 100.0, "peak_speed_dps": 100.0, "sparc": -1.6, "mdf_hz": 100.0, "rise_cm": 0.5,
                 "lean_deg": 3.0} for _ in self.reps]
        for (i, k), v in over.items():
            rows[i][k] = v
        return rows

    def test_flags_and_next_rep_risk(self):
        tgt, msk, _, _ = L.make_labels(self.reps, self.meas({(6, "rise_cm"): 3.0, (9, "rom_deg"): 70.0}))
        self.assertEqual(list(np.flatnonzero(tgt["comp_shrug"])), [6])
        self.assertEqual(list(np.flatnonzero(tgt["comp_rom"])), [9])
        self.assertEqual(list(np.flatnonzero(tgt["risk"])), [3, 4, 5, 8])  # rep 9 is in set 1 only
        self.assertFalse(msk["risk"][7])          # last rep of set 0: no next rep in the set
        self.assertFalse(msk["risk"][9])
        self.assertTrue(msk["risk"][8])

    def test_quality_drops_with_rom_speed_and_smoothness(self):
        tgt, _, _, _ = L.make_labels(self.reps, self.meas({(5, "rom_deg"): 50.0, (5, "peak_speed_dps"): 50.0,
                                                          (5, "sparc"): -3.2}))
        self.assertAlmostEqual(float(tgt["quality"][5]), 0.5, places=5)
        self.assertAlmostEqual(float(tgt["quality"][4]), 1.0, places=5)

    def test_missing_sensors_mask_their_labels(self):
        m = self.meas()
        for row in m:
            row["mdf_hz"] = np.nan
            row["rise_cm"] = row["lean_deg"] = np.nan
        tgt, msk, aux, aux_m = L.make_labels(self.reps, m)
        for h in ("fatigue", "comp_shrug", "comp_lean", "risk"):
            self.assertFalse(msk[h].any(), h)
        self.assertTrue(msk["quality"].all() and msk["comp_rom"].all())
        self.assertFalse(aux_m[:, 1:].any())

    def test_too_few_reps_label_nothing(self):
        tgt, msk, _, _ = L.make_labels(self.reps[:3], self.meas()[:3])
        self.assertFalse(any(m.any() for m in msk.values()))


class SyncTest(unittest.TestCase):
    def test_known_delay_is_recovered(self):
        t = np.arange(0, 12, 1 / 60)
        bumps = sum(np.exp(-0.5 * ((t - c) / 0.15) ** 2) for c in (3, 5, 7))
        t_x = np.arange(0, 12, 1 / 30) + 0.060              # this sensor stamps everything 60 ms late
        bx = sum(np.exp(-0.5 * ((t_x - 0.060 - c) / 0.15) ** 2) for c in (3, 5, 7))
        off, corr = SY.estimate_offset(t, bumps, t_x, bx, (1, 10))
        self.assertAlmostEqual(off, -0.060, delta=0.003)
        self.assertGreater(corr, 0.9)
        self.assertEqual(SY.count_peaks(t_x, bx, (1, 10)), 3)

    def test_marker_sets_the_window(self):
        self.assertEqual(SY.shrug_window([(8.0, "s", "sync shrugs")], 0, 100), (7.0, 18.0))
        self.assertEqual(SY.shrug_window([(8.0, "s", "sync shrugs"), (14.0, "space", "rep start")], 0, 100),
                         (7.0, 13.7))      # ends just before the first rep
        self.assertEqual(SY.shrug_window([], 0, 100), (0, 30.0))


class ImuTest(unittest.TestCase):
    def test_forearm_angle_from_a_turning_imu(self):
        fs = 200.0
        t = np.arange(0, 12, 1 / fs)
        phi = np.where(t < 2, 0, 60 * (1 - np.cos(2 * np.pi * (t - 2) / 2.5)))       # deg
        acc = np.stack([np.zeros_like(t), np.sin(np.radians(phi)), np.cos(np.radians(phi))], 1)
        gyro = np.stack([np.gradient(phi, t), np.zeros_like(t), np.zeros_like(t)], 1)
        imu = TR.Imu(t, acc + rng.normal(0, 0.003, acc.shape), gyro + rng.normal(0, 0.3, gyro.shape), t,
                     (t * 1e6).astype(np.int64))
        flex, w = TR.forearm_flexion(imu)
        self.assertLess(np.max(np.abs(flex - phi)), 3.0)

    @unittest.skipUnless(have_real_sessions(), "real recordings not on this computer")
    def test_rows_match_the_recorder(self):
        s = S.load(S.Path(__file__).resolve().parents[2] / "recorder/data/sessions/2026-11-05_001132_TEST_wifi_final")
        ours = TR.record_rows(s, "imu", "I")
        theirs = s.record_mode("imu", "I")
        np.testing.assert_array_equal(ours["values"], theirs["values"])
        np.testing.assert_allclose(ours["t_s"], theirs["t_s"])
        steps = np.diff(ours["dev_us"])
        self.assertEqual(int(np.median(steps)), 5000)   # 200 Hz device clock


if __name__ == "__main__":
    unittest.main()
