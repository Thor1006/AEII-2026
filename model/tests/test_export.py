"""The dashboard export: a valid protocol-1.2 recording of the network running on a session."""
import base64
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _util import MODEL_DIR, small_contract
from trnet import calibrate as CB
from trnet import synth
from trnet.inference import run_session
from trnet.network import TrueRehabNet

spec = importlib.util.spec_from_file_location("export_dashboard", MODEL_DIR / "export_dashboard.py")
EX = importlib.util.module_from_spec(spec)
spec.loader.exec_module(EX)


class ExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        folder = synth.make_session(cls.tmp, synth.make_person("F01", 1),
                                    synth.Plan(sets=1, reps_per_set=6, set_rest_s=10), stats=CB.load_stats())
        weights = cls.tmp / "untrained.pt"
        TrueRehabNet(small_contract()).save(weights)       # untrained is fine: this tests the format only
        cls.result = run_session(folder, weights)
        cls.out = cls.tmp / "replay.ndjson"
        EX.export(cls.result, cls.out)
        cls.msgs = [json.loads(line) for line in cls.out.read_text().splitlines()]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_hello_first_with_manifest(self):
        h = self.msgs[0]
        self.assertEqual(h["type"], "hello")
        self.assertEqual(h["protocol"], "1.2")
        self.assertTrue(h["synthetic"])                      # fake session -> the dashboard's demo banner
        m = h["manifest"]
        self.assertEqual([f["view"] for f in m["frames"]], ["range_azimuth", "phase_change", "range_doppler"])
        self.assertEqual([s["key"] for s in m["scores"]],
                         ["fatigue", "quality", "comp_shrug", "comp_lean", "comp_rom", "risk"])

    def test_order_and_numbering(self):
        rest = self.msgs[1:]
        self.assertEqual([m["seq"] for m in rest], list(range(len(rest))))      # no gaps: no "lost messages"
        self.assertEqual([m["t"] for m in rest], sorted(m["t"] for m in rest))

    def test_frames_scores_and_events(self):
        frames = [m for m in self.msgs if m["type"] == "frame"]
        self.assertTrue(frames)
        for f in frames[:30]:
            self.assertEqual(f["encoding"], "base64-f32")
            self.assertEqual(len(base64.b64decode(f["data"])), 40 * 16 * 4)
        keys = {k for m in self.msgs if m["type"] == "scores" for k in m["scores"]}
        self.assertEqual(keys, {"fatigue", "quality", "comp_shrug", "comp_lean", "comp_rom", "risk"})
        reps = [m for m in self.msgs if m["type"] == "event" and m["kind"] == "rep_end"]
        self.assertEqual(len(reps), len(self.result.reps))
        actions = {m["data"]["action"] for m in self.msgs if m["type"] == "event" and m["kind"] == "recommendation"}
        self.assertTrue(actions <= {"continue", "correct_posture", "reduce_load", "rest", "see_physio"})
        kinds = [m["kind"] for m in self.msgs if m["type"] == "event"]
        self.assertEqual((kinds[0], kinds[-1]), ("session_start", "session_end"))

    def test_reps_from_semg_export_without_an_angle(self):
        """Radar + sEMG only: reps come from the sEMG envelope and have no range of motion. The export leaves romDeg
        out instead of writing NaN, which the browser's JSON reader refuses."""
        folder = synth.make_session(self.tmp / "emg", synth.make_person("F05", 5),
                                    synth.Plan(sets=1, reps_per_set=6, set_rest_s=10, problems=("no_imu", "no_pose")),
                                    stats=CB.load_stats())
        weights = self.tmp / "untrained.pt"
        result = run_session(folder, weights)
        self.assertEqual(result.processed.rep_source, "emg")
        out = self.tmp / "replay_emg.ndjson"
        EX.export(result, out)
        msgs = [json.loads(line, parse_constant=lambda c: self.fail(f"{c} in the export")) for line in out.read_text().splitlines()]
        ends = [m["data"] for m in msgs if m["type"] == "event" and m["kind"] == "rep_end"]
        self.assertEqual(len(ends), 6)
        self.assertTrue(all("romDeg" not in e for e in ends))


if __name__ == "__main__":
    unittest.main()
