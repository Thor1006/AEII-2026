"""Start/Stop in the dashboard records ONE session folder with every sensor on one clock: a replayed radar recording
and the fake MyoWare together, through the bridge's own command handling, then the model's readers take it as it is.
Stopping the bridge (SIGTERM) finishes a recording that is still open. The bridge tests need websockets (the bridge
module imports it); the config test doesn't."""
from __future__ import annotations

import asyncio
import shutil
import socket
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from fake_myoware import FakeMyoWare  # noqa: E402
from truerehab_bridge.config import BridgeConfig, load_config  # noqa: E402
from truerehab_bridge.providers import EmgProvider, RadarProvider, SyntheticProvider  # noqa: E402

try:
    import websockets  # noqa: F401
    HAVE_WS = True
except ImportError:
    HAVE_WS = False


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def load(self, text: str) -> BridgeConfig:
        p = self.tmp / "config.toml"
        p.write_text(text)
        return load_config(p)

    def test_record_dir(self):
        self.assertEqual(BridgeConfig().record_dir, "~/truerehab-sessions")
        self.assertEqual(self.load('[bridge]\nrecord_dir = "rec"\n').record_dir, str((self.tmp / "rec").resolve()))
        self.assertEqual(self.load('[bridge]\nrecord_dir = ""\n').record_dir, "")
        v01 = self.load('[providers.radar]\nenabled = false\nrecord_dir = "/data/sessions"\n')   # Pi set v0.1
        self.assertEqual(v01.record_dir, "/data/sessions")
        both = self.load('[bridge]\nrecord_dir = "/a"\n[providers.radar]\nrecord_dir = "/b"\n')
        self.assertEqual(both.record_dir, "/a")


@unittest.skipUnless(HAVE_WS, "websockets not installed")
class SharedRecording(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(HERE.parents[1] / "model"))
        from trnet import synth
        cls.tmp = Path(tempfile.mkdtemp())
        plan = synth.Plan(sets=1, reps_per_set=2, set_rest_s=5, problems=("no_emg", "no_imu", "no_pose"))
        cls.radar_src = synth.make_session(cls.tmp / "src", synth.make_person("F02", 2), plan)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def bridge(self, providers, record_dir):
        from truerehab_bridge.server import Bridge
        cfg = BridgeConfig(host="127.0.0.1", ws_port=free_port(), http_port=0, record_dir=str(record_dir), providers={})
        return Bridge(cfg, providers)

    def test_radar_and_semg_in_one_folder_on_one_clock(self):
        rec_dir = self.tmp / "rec"
        fake = FakeMyoWare(port=0, seed=4).start()
        try:
            acks = asyncio.run(self._session(fake, rec_dir))
        finally:
            fake.stop()
        from rec import session as S
        from trnet import radar as R
        from trnet.truth import load_emg
        first, second = sorted(rec_dir.iterdir())
        self.assertEqual([acks[0]["recording"], acks[1]["recording"]], [first.name, second.name])
        s = S.load(first)
        self.assertEqual((s.meta["subject"], s.meta["exercise"]), ("S03", "elbow_flexion"))
        self.assertEqual(set(s.meta["sources"]), {"radar", "emg"})
        summary = s.meta["summary"]
        self.assertEqual(summary["bridge_session"], acks[0]["session"]["id"])
        self.assertGreater(summary["radar"]["frames"], 100)
        self.assertGreater(summary["emg"]["samples"], 2000)
        self.assertIn(("x", "halfway"), [(k, lbl) for _, k, lbl in s.markers])
        # one clock: both sensors start within 0.5 s of the recording's start and end within 0.5 s of its end
        dur = s.meta["duration_s"]
        radar_t = s.radar_index()["t_s"]
        emg_t, _ = s.serial_lines("emg")
        for name, t in (("radar", radar_t), ("emg", emg_t)):
            self.assertLess(t[0], 0.5, name)
            self.assertGreater(t[-1], dur - 0.5, name)
            self.assertLessEqual(t[-1], dur, name)
        self.assertEqual(int(R.load_radar(s).valid.sum()), summary["radar"]["frames"])
        emg = load_emg(s)
        self.assertIsNotNone(emg)
        self.assertLess(abs(emg.t_s[0] - emg_t[0]), 0.1)            # device time put on the shared clock
        # the second one was still open when the bridge stopped (SIGTERM): finished, not half-written
        s2 = S.load(second)
        self.assertIn("ended", s2.meta)
        self.assertGreater(s2.meta["summary"]["emg"]["samples"], 0)
        self.assertGreater(s2.meta["summary"]["radar"]["frames"], 0)

    async def _session(self, fake: FakeMyoWare, rec_dir: Path) -> list[dict]:
        radar = RadarProvider(replay=str(self.radar_src), replay_loop=True)
        emg = EmgProvider(port=fake.url)
        b = self.bridge([radar, emg], rec_dir)
        task = asyncio.create_task(b.serve_forever())
        try:
            for _ in range(100):                                       # both sensors up
                devices = b.devices()
                if devices["radar"]["state"] == "ok" and devices["emg"]["state"] == "ok":
                    break
                await asyncio.sleep(0.05)
            else:
                self.fail(f"sensors not up: {b.devices()}")
            ok, err, first = b.handle_command("session.start", {"exercise": "elbow_flexion", "userId": "S03"})
            self.assertTrue(ok, err)
            await asyncio.sleep(1.2)
            self.assertTrue(b.handle_command("marker", {"label": "halfway"})[0])
            self.assertIn("recording", b.devices()["emg"]["message"])
            await asyncio.sleep(1.2)
            self.assertTrue(b.handle_command("session.stop", {})[0])
            ok, err, second = b.handle_command("session.start", {"exercise": "elbow_flexion", "userId": "S03"})
            self.assertTrue(ok, err)
            await asyncio.sleep(0.8)
        finally:
            task.cancel()                                              # what SIGTERM does
            await asyncio.gather(task, return_exceptions=True)
        return [first, second]

    def test_nothing_that_records_means_no_folder(self):
        rec_dir = self.tmp / "none"

        async def go():
            b = self.bridge([SyntheticProvider(fps=5)], rec_dir)
            ok, _, result = b.handle_command("session.start", {})
            self.assertTrue(ok)
            self.assertNotIn("recording", result)
            self.assertTrue(b.handle_command("session.stop", {})[0])

        asyncio.run(go())
        self.assertFalse(rec_dir.exists())

    def test_recording_off(self):
        async def go():
            b = self.bridge([RadarProvider(replay=str(self.radar_src))], "")
            ok, _, result = b.handle_command("session.start", {})
            self.assertTrue(ok)
            self.assertNotIn("recording", result)
            self.assertIsNone(b.recording)
            b.handle_command("session.stop", {})

        asyncio.run(go())

    def test_an_unwritable_folder_is_reported_not_fatal(self):
        blocker = self.tmp / "a-file"
        blocker.write_text("not a folder")

        async def go():
            b = self.bridge([RadarProvider(replay=str(self.radar_src))], blocker / "sessions")
            ok, _, result = b.handle_command("session.start", {})
            self.assertTrue(ok)                                        # the live view still starts
            self.assertIn("Not recording", result["recordingError"])
            b.handle_command("session.stop", {})

        asyncio.run(go())


if __name__ == "__main__":
    unittest.main()
