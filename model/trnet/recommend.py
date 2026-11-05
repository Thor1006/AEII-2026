"""Recommendation rules: plain if-then rules a physiotherapist can read and change.

ALL NUMBERS ARE PLACEHOLDERS, to be agreed with a physiotherapist. Checked in this order (first match wins):
  1. fatigue >= 0.85                                                 -> rest
  2. compensation still there 3 reps after a "correct posture"      -> rest
  3. fatigue >= 0.70                                                 -> reduce load or ROM
  4. next-rep risk >= 0.60 in 2 reps in a row                        -> correct posture
  5. quality fell over the last 3 sessions                           -> see physio
  6. otherwise                                                       -> continue
"""
from dataclasses import dataclass, field

RULES = {"fatigue_rest": 0.85, "fatigue_reduce": 0.70, "risk_correct": 0.60, "risk_reps": 2,
         "comp_flag": 0.50, "persist_reps": 3, "quality_sessions": 3, "quality_drop": 0.05}
ACTIONS = ("continue", "correct posture", "reduce load or ROM", "rest", "see physio")
COMP = ("comp_shrug", "comp_lean", "comp_rom")


def recommend(reps, session_quality=(), since_correction=None, rules=RULES):
    """reps: per-rep scores so far this set ({fatigue, quality, comp_shrug, comp_lean, comp_rom, risk}), the last
    one is the rep just done. session_quality: mean quality of previous sessions, oldest first, then this one.
    since_correction: reps done since the last "correct posture" (None = never). -> (action, reason)."""
    if not reps:
        return "continue", "no reps yet"
    cur = reps[-1]
    if cur["fatigue"] >= rules["fatigue_rest"]:
        return "rest", f"fatigue {cur['fatigue']:.2f} >= {rules['fatigue_rest']}"
    comp_now = any(cur[c] >= rules["comp_flag"] for c in COMP)
    if since_correction is not None and since_correction >= rules["persist_reps"] and comp_now:
        return "rest", f"compensation still there {since_correction} reps after a correction"
    if cur["fatigue"] >= rules["fatigue_reduce"]:
        return "reduce load or ROM", f"fatigue {cur['fatigue']:.2f} >= {rules['fatigue_reduce']}"
    n = rules["risk_reps"]
    if len(reps) >= n and all(r["risk"] >= rules["risk_correct"] for r in reps[-n:]):
        return "correct posture", f"compensation likely in the next reps ({n} reps >= {rules['risk_correct']})"
    q = list(session_quality)[-rules["quality_sessions"]:]
    if len(q) == rules["quality_sessions"] and all(b < a for a, b in zip(q, q[1:])) and q[0] - q[-1] >= rules["quality_drop"]:
        return "see physio", f"quality fell over {len(q)} sessions ({q[0]:.2f} -> {q[-1]:.2f})"
    return "continue", "nothing to flag"


@dataclass
class Advisor:
    """Live use: feed the scores of each finished rep, get the advice; remembers corrections within a set."""
    session_quality: list = field(default_factory=list)
    rules: dict = field(default_factory=lambda: dict(RULES))
    reps: list = field(default_factory=list)
    since_correction: int = None

    def new_set(self):
        self.reps, self.since_correction = [], None

    def feed(self, scores):
        self.reps.append(dict(scores))
        if self.since_correction is not None:
            self.since_correction += 1
        action, why = recommend(self.reps, self.session_quality, self.since_correction, self.rules)
        if action == "correct posture" and self.since_correction is None:
            self.since_correction = 0
        if action != "correct posture" and not any(scores[c] >= self.rules["comp_flag"] for c in COMP):
            self.since_correction = None        # compensation gone: the correction worked
        return action, why
