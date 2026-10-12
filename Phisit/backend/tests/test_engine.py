"""Core behavior checks for the demonstration simulator."""

import unittest

from app.adapters import SimulationRadarSource, demo_indices
from app.engine import EXPORT_FIELDS, SimulationEngine, recommendation_for


class SimulationEngineTests(unittest.TestCase):
    def test_reps_come_from_waveform_peaks(self) -> None:
        engine = SimulationEngine()
        engine.start()
        observed = []
        for _ in range(800):
            previous = engine.rep_count
            engine.advance(0.05)
            if engine.rep_count != previous:
                observed.append((engine.rep_count, engine.elapsed_s))
            if engine.rep_count == 10:
                break
        self.assertEqual([rep for rep, _ in observed], list(range(1, 11)))
        self.assertTrue(all(2.7 < b[1] - a[1] < 3.3 for a, b in zip(observed, observed[1:])))
        self.assertFalse(engine.running)

    def test_risk_rises_before_compensation(self) -> None:
        rep7 = demo_indices(7)
        rep9 = demo_indices(9)
        self.assertGreater(rep7[3], 0.70)
        self.assertLess(rep7[2], 0.30)
        self.assertGreater(rep9[2], 0.50)
        self.assertEqual(recommendation_for(7).status, "correct_form")
        self.assertEqual(recommendation_for(9).status, "rest")

    def test_stop_reset_and_csv_contract(self) -> None:
        engine = SimulationEngine()
        engine.start()
        for _ in range(50):
            engine.advance(0.05)
        paused = engine.stop()
        self.assertFalse(paused.running)
        self.assertGreater(paused.movement.rep_count, 0)
        csv_text = engine.export_csv()
        self.assertEqual(csv_text.splitlines()[0].split(","), EXPORT_FIELDS)
        self.assertGreater(len(csv_text.splitlines()), 2)
        reset = engine.reset()
        self.assertEqual(reset.movement.rep_count, 0)
        self.assertEqual(len(engine.records), 0)

    def test_synthetic_radar_motion_is_periodic(self) -> None:
        source = SimulationRadarSource()
        self.assertAlmostEqual(source.read_frame(1.5).normalized_movement, 1.0, places=2)
        self.assertAlmostEqual(source.read_frame(4.5).normalized_movement, 1.0, places=2)


if __name__ == "__main__":
    unittest.main()
