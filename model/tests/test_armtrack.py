import unittest
from types import SimpleNamespace

import numpy as np

import _util  # noqa: F401  (puts model/ on the path)

from trnet import armtrack as AT
from trnet.contract import default_contract
from trnet.reps import Rep

C = default_contract()


def curling_recording(n_reps=20, period_s=2.5, arm_bin=30, seed=0, missing=0.0):
    """A fake range-Doppler recording: noise everywhere, plus an arm at arm_bin whose radial speed swings like a
    curl (out and back once per rep, with a short rest at the bottom), and a still wall at bin 50."""
    rng = np.random.default_rng(seed)
    fps = C.fps
    n = int((n_reps * period_s + 8) * fps)
    t = np.arange(n) / fps
    phase = np.clip((t - 4) / period_s, 0, n_reps)
    speed = 0.8 * np.sin(2 * np.pi * phase) * (phase < n_reps)       # m/s: out, then back, once per rep
    nd = C.doppler_bins
    rd = rng.normal(20, 1.0, (n, C.range_bins, nd))                   # dB noise floor
    rd[:, 50, nd // 2] += 30                                          # still wall: zero speed only
    k = np.clip(np.round(speed / C.vel_res_ms).astype(int) + nd // 2, 0, nd - 1)
    rd[np.arange(n), arm_bin, k] += 25
    valid = rng.random(n) >= missing
    rd[~valid] = 0
    rec = SimpleNamespace(t_s=t, valid=valid, rd_db=rd.astype(np.float32), contract=C)
    starts = 4 + np.arange(n_reps) * period_s                         # arm down; furthest out half a period later
    return rec, starts


class ArmTrackTest(unittest.TestCase):
    def test_velocity_of_a_single_moving_cell(self):
        rd = np.full((3, C.range_bins, C.doppler_bins), -60.0)          # near silence everywhere else
        rd[:, 10, C.doppler_bins // 2 + 3] = 40
        V, power = AT.doppler_velocity(rd, np.ones(3, bool), C.vel_res_ms)
        self.assertAlmostEqual(V[0, 10], 3 * C.vel_res_ms, places=3)
        self.assertGreater(power[0, 10], power[0, 20])

    def test_finds_the_curling_arm_not_the_wall(self):
        rec, _ = curling_recording(arm_bin=30)
        tr = AT.track(rec)
        self.assertIn(tr.range_bin, (29, 30, 31))
        self.assertAlmostEqual(tr.range_m, tr.range_bin * C.range_res_m)

    def test_counts_and_times_the_curls(self):
        rec, starts = curling_recording(n_reps=20, missing=0.05)
        tr = AT.track(rec)
        self.assertLessEqual(abs(len(tr.reps) - 20), 1)
        imu = [Rep(s, s + 1.25, s + 2.5, 90, 100, -2) for s in starts]
        s = AT.score_reps(tr.reps, imu)
        self.assertGreaterEqual(s["found_share"], 0.9)
        self.assertLess(s["chance_share"], s["found_share"])
        self.assertAlmostEqual(s["median_rep_interval_s"]["radar"], 2.5, delta=0.1)

    def test_too_short_or_empty(self):
        rec, _ = curling_recording(n_reps=1, period_s=1.0)
        rec.valid[:] = False
        self.assertIsNone(AT.track(rec))
        s = AT.score_reps([], [Rep(1, 2, 3, 90, 100, -2)])
        self.assertEqual((s["radar_reps"], s["found"], s["chance_share"]), (0, 0, 0.0))

    def test_score_counts_each_imu_rep_once_and_accepts_either_turn(self):
        imu = [Rep(10 * i + 1, 10 * i + 2, 10 * i + 3, 90, 100, -2) for i in range(5)]
        both = [Rep(0, 10 * i + 2, 0, 50, 1, -2) for i in range(5)] + [Rep(0, 10 * i + 1, 0, 50, 1, -2) for i in range(5)]
        s = AT.score_reps(sorted(both, key=lambda r: r.peak_s), imu)
        self.assertEqual(s["found"], 5)                              # never more than the IMU's reps
        bottoms = [Rep(0, t, 0, 50, 1, -2) for t in (1.1, 7.1, 17.1, 27.1, 37.1)]   # start, then mid-rest gaps
        self.assertEqual(AT.score_reps(bottoms, imu)["found"], 5)     # the radar marked the bottoms: still found
        late = [Rep(0, 10 * i + 2 + 0.6, 0, 50, 1, -2) for i in range(5)]
        self.assertEqual(AT.score_reps(late, imu)["found"], 0)        # 0.6 s off: not found


if __name__ == "__main__":
    unittest.main()
