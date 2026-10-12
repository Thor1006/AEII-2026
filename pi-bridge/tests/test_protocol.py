"""Unit tests: python -m unittest discover -s tests (from pi-bridge/)."""
from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from truerehab_bridge.config import BridgeConfig  # noqa: E402
from truerehab_bridge.protocol import Aux, Event, Frame, Scores, decode_frame, encode, parse_serial_line  # noqa: E402
from truerehab_bridge.providers import SyntheticProvider  # noqa: E402
from truerehab_bridge.server import Bridge  # noqa: E402

ENV = {"v": 1, "seq": 7, "t": 1000.0, "src": "test", "kitId": "KIT-T"}


class FrameEncoding(unittest.TestCase):
    def test_round_trip_all_dtypes(self) -> None:
        data = (np.random.default_rng(0).random((8, 5)) * 40 - 40).astype(np.float32)
        for dtype, tol in (("f32", 0), ("u16", 1e-3), ("u8", 0.2)):
            buf = encode(Frame("range_doppler", data, frame_index=3), ENV, dtype)
            self.assertIsInstance(buf, bytes)
            assert isinstance(buf, bytes)
            self.assertEqual(buf[:4], b"TRF1")
            header, back = decode_frame(buf)
            self.assertEqual(header["shape"], [8, 5])
            self.assertEqual(header["seq"], 7)
            self.assertEqual(header["frameIndex"], 3)
            self.assertLessEqual(float(np.max(np.abs(back - data))), tol, dtype)

    def test_payload_is_4_byte_aligned(self) -> None:
        for view in ("a", "ab", "abc", "abcd"):
            buf = encode(Frame(view, np.zeros((2, 2), np.float32)), ENV)
            n = int.from_bytes(buf[4:8], "little")
            self.assertEqual((len(buf) - 16) % 4, 0)
            self.assertEqual(len(buf) - ((8 + n + 3) & ~3), 16)

    def test_rejects_1d(self) -> None:
        with self.assertRaises(ValueError):
            encode(Frame("x", np.zeros(4, np.float32)), ENV)


class JsonMessages(unittest.TestCase):
    def test_scores_with_and_without_confidence(self) -> None:
        m = json.loads(encode(Scores({"fatigue": (0.4, 0.8), "quality": 0.9}), ENV))
        self.assertEqual(m["scores"], {"fatigue": {"value": 0.4, "confidence": 0.8}, "quality": {"value": 0.9}})
        self.assertEqual(m["type"], "scores")

    def test_event_drops_empty_fields(self) -> None:
        m = json.loads(encode(Event("marker", {"label": "x"}), ENV))
        self.assertNotIn("label", m)
        self.assertEqual(m["data"], {"label": "x"})

    def test_message_time_overrides_envelope(self) -> None:
        m = json.loads(encode(Aux({"emg": 1}, t=5.0), ENV))
        self.assertEqual(m["t"], 5.0)


class SerialLines(unittest.TestCase):
    def test_formats(self) -> None:
        self.assertEqual(parse_serial_line("emg:512,force:20.3"), {"emg": 512.0, "force": 20.3})
        self.assertEqual(parse_serial_line("512,20.3", ["emg", "force"]), {"emg": 512.0, "force": 20.3})
        self.assertEqual(parse_serial_line('{"emg":5,"ok":true}'), {"emg": 5.0})
        self.assertEqual(parse_serial_line('{"type":"aux","channels":{"emg":2}}'), {"emg": 2.0})
        self.assertEqual(parse_serial_line("512\t3"), {"ch0": 512.0, "ch1": 3.0})
        self.assertIsNone(parse_serial_line("hello"))
        self.assertIsNone(parse_serial_line(""))
        self.assertIsNone(parse_serial_line("nan"))


class BridgeLogic(unittest.TestCase):
    def setUp(self) -> None:
        self.bridge = Bridge(BridgeConfig(), [SyntheticProvider()])

    def test_hello_has_full_manifest(self) -> None:
        h = self.bridge.hello()
        self.assertEqual(h["type"], "hello")
        self.assertEqual(h["seq"], -1)
        self.assertEqual(h["protocol"], "1.1")
        self.assertTrue(h["synthetic"])
        m = h["manifest"]
        self.assertEqual([f["view"] for f in m["frames"]], ["range_doppler"])
        self.assertEqual({s["key"] for s in m["scores"]}, {"fatigue", "quality", "compensation"})
        self.assertIn("marker", m["events"])
        self.assertIn("session.start", m["commands"])
        self.assertIs(m["scores"][1]["higherIsWorse"], False)

    def test_session_commands(self) -> None:
        ok, err, res = self.bridge.handle_command("session.start", {"exercise": "elbow_flexion", "targetReps": 10})
        self.assertTrue(ok, err)
        assert res is not None
        self.assertEqual(res["session"]["targetReps"], 10)
        self.assertEqual(self.bridge.handle_command("session.start", {})[:2], (False, "A session is already running"))
        self.assertEqual(self.bridge._envelope()["sessionId"], res["session"]["id"])
        self.assertTrue(self.bridge.handle_command("session.stop", {})[0])
        self.assertFalse(self.bridge.handle_command("session.stop", {})[0])
        self.assertNotIn("sessionId", self.bridge._envelope())

    def test_bad_args_and_unknown_command(self) -> None:
        self.assertFalse(self.bridge.handle_command("session.start", {"targetReps": "ten"})[0])
        self.assertFalse(self.bridge.handle_command("session.start", {"targetReps": True})[0])
        ok, err, _ = self.bridge.handle_command("reboot", {})
        self.assertFalse(ok)
        self.assertIn("Unknown command", err or "")

    def test_status_lists_devices(self) -> None:
        st = self.bridge.status()
        self.assertEqual(st["devices"]["radar"]["state"], "ok")
        self.assertTrue(st["synthetic"])


class SyntheticData(unittest.TestCase):
    def test_produces_every_announced_stream(self) -> None:
        p = SyntheticProvider(fps=20)
        man = p.manifest()
        seen: set[str] = set()
        t = time.time()
        for i in range(200):  # 10 s of ticks
            for msg in p._tick(t + i / 20):
                if isinstance(msg, Frame):
                    seen.add(f"frame:{msg.view}")
                    self.assertEqual(msg.data.shape, (64, 64))
                    self.assertTrue(np.isfinite(msg.data).all())
                elif isinstance(msg, Scores):
                    seen.update(f"score:{k}" for k in msg.values)
                elif isinstance(msg, Aux):
                    seen.update(f"aux:{k}" for k in msg.channels)
                elif isinstance(msg, Event):
                    seen.add(f"event:{msg.kind}")
        expected = {f"frame:{f.view}" for f in man.frames} | {f"score:{s.key}" for s in man.scores} | {f"aux:{a.key}" for a in man.aux}
        self.assertLessEqual(expected, seen)
        self.assertIn("event:rep_end", seen)


if __name__ == "__main__":
    unittest.main()
