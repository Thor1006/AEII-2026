import unittest

from _util import MODEL_DIR  # noqa: F401
from trnet.recommend import Advisor, recommend


def s(fatigue=0.1, quality=0.95, shrug=0.0, lean=0.0, rom=0.0, risk=0.1):
    return {"fatigue": fatigue, "quality": quality, "comp_shrug": shrug, "comp_lean": lean, "comp_rom": rom,
            "risk": risk}


class RecommendTest(unittest.TestCase):
    def test_each_rule(self):
        self.assertEqual(recommend([s()])[0], "continue")
        self.assertEqual(recommend([s(fatigue=0.9)])[0], "rest")
        self.assertEqual(recommend([s(fatigue=0.75)])[0], "reduce load or ROM")
        self.assertEqual(recommend([s(risk=0.7), s(risk=0.65)])[0], "correct posture")
        self.assertEqual(recommend([s(risk=0.3), s(risk=0.65)])[0], "continue")          # only one rep so far
        self.assertEqual(recommend([s()], session_quality=[0.95, 0.9, 0.85])[0], "see physio")
        self.assertEqual(recommend([s()], session_quality=[0.95, 0.96, 0.85])[0], "continue")  # not falling each time
        self.assertEqual(recommend([s(shrug=0.8)], since_correction=3)[0], "rest")
        self.assertEqual(recommend([])[0], "continue")

    def test_priority(self):
        self.assertEqual(recommend([s(fatigue=0.9, risk=0.9), s(fatigue=0.9, risk=0.9)])[0], "rest")
        self.assertEqual(recommend([s(fatigue=0.75, risk=0.9), s(fatigue=0.75, risk=0.9)])[0], "reduce load or ROM")

    def test_live_advisor_remembers_a_correction(self):
        a = Advisor()
        self.assertEqual(a.feed(s(risk=0.7, shrug=0.6))[0], "continue")
        self.assertEqual(a.feed(s(risk=0.7, shrug=0.6))[0], "correct posture")
        self.assertEqual(a.feed(s(risk=0.7, shrug=0.6))[0], "correct posture")
        self.assertEqual(a.feed(s(risk=0.7, shrug=0.6))[0], "correct posture")
        self.assertEqual(a.feed(s(risk=0.7, shrug=0.6))[0], "rest")       # still compensating 3 reps later
        b = Advisor()
        b.feed(s(risk=0.7, shrug=0.6))
        b.feed(s(risk=0.7, shrug=0.6))
        self.assertEqual(b.feed(s())[0], "continue")                        # corrected: compensation gone
        self.assertIsNone(b.since_correction)


if __name__ == "__main__":
    unittest.main()
