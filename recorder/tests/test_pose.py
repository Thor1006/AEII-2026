import csv
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rec import pose as P  # noqa: E402
from rec import session as S  # noqa: E402


def skeleton(lean_deg=0.0, shrug_m=0.0):
    """World landmarks (m, y down): left elbow bent 90 deg, right arm straight, trunk leaning sideways."""
    w = np.zeros((33, 3))
    dx = 0.5 * np.tan(np.radians(lean_deg))
    w[P.LM["l_hip"]], w[P.LM["r_hip"]] = (0.1, 0, 0), (-0.1, 0, 0)
    w[P.LM["l_shoulder"]] = (0.18 + dx, -0.5 - shrug_m, 0)
    w[P.LM["r_shoulder"]] = (-0.18 + dx, -0.5, 0)
    w[P.LM["l_ear"]], w[P.LM["r_ear"]] = (0.08 + dx, -0.65, 0), (-0.08 + dx, -0.65, 0)
    w[P.LM["l_elbow"]] = (0.18 + dx, -0.2 - shrug_m, 0)
    w[P.LM["l_wrist"]] = (0.18 + dx, -0.2 - shrug_m, -0.3)
    w[P.LM["r_elbow"]], w[P.LM["r_wrist"]] = (-0.18 + dx, -0.2, 0), (-0.18 + dx, 0.1, 0)
    return w


class AngleTest(unittest.TestCase):
    def test_upright(self):
        a = P.angles(skeleton())
        self.assertAlmostEqual(float(a["elbow_l"][0]), 90, places=3)
        self.assertAlmostEqual(float(a["elbow_r"][0]), 180, places=3)
        self.assertAlmostEqual(float(a["trunk_lean"][0]), 0, places=3)
        self.assertAlmostEqual(float(a["ear_shoulder_r"][0]), 0.15, places=6)

    def test_lean_and_shrug(self):
        a = P.angles(np.stack([skeleton(lean_deg=10), skeleton(shrug_m=0.04)]))
        self.assertAlmostEqual(float(a["trunk_lean_side"][0]), 10, delta=0.5)
        self.assertLess(float(a["ear_shoulder_l"][1]), float(a["ear_shoulder_r"][1]))  # left shrugged
        self.assertAlmostEqual(float(a["ear_shoulder_l"][1]), 0.11, places=6)


class EstimatorTest(unittest.TestCase):
    def test_empty_frame_has_no_person(self):
        est = P.PoseEstimator()
        try:
            img, world = est(np.zeros((480, 640, 3), np.uint8), 0)
            self.assertIsNone(img)
            self.assertIsNone(world)
            est(np.zeros((480, 640, 3), np.uint8), 0)  # same timestamp again must not crash
        finally:
            est.close()


class ReaderTest(unittest.TestCase):
    def test_pose_csv_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            sess = S.SessionWriter(d, "TEST", "pose")
            img = np.random.default_rng(0).random((33, 4))
            world = skeleton(lean_deg=5)
            with open(sess.dir / "pose.csv", "w", newline="") as f:
                out = csv.writer(f)
                out.writerow(P.HEADER)
                out.writerow([1_000_000, 0, 1] + [f"{v:.5f}" for v in img.ravel()] + [f"{v:.5f}" for v in world.ravel()])
                out.writerow([34_000_000, 1, 0])
            sess.close({})
            p = S.load(sess.dir).pose()
            self.assertEqual(p["person"].tolist(), [True, False])
            self.assertTrue(np.allclose(p["world"][0], world, atol=1e-5))
            self.assertTrue(np.isnan(p["world"][1]).all())
            self.assertAlmostEqual(float(P.angles(p["world"])["trunk_lean_side"][0]), 5, delta=0.5)


if __name__ == "__main__":
    unittest.main()
