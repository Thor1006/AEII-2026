"""The radar provider: port detection, maps the way the network sees them (from a replayed recording), and recording
into the bridge's shared session folder in the recorder's format. Needs numpy only (pyserial for the 'not plugged in'
case); no radar, no websockets."""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from truerehab_bridge.protocol import Frame, Session  # noqa: E402
from truerehab_bridge.providers.radar import RadarProvider, find_xds110_ports  # noqa: E402
from truerehab_bridge.recording import Recording  # noqa: E402

try:
    import serial  # noqa: F401
    HAVE_SERIAL = True
except ImportError:
    HAVE_SERIAL = False


def port(device, vid=0x0451, pid=0xBEF3, sn="RA29P055", location=None, description="XDS110 (03.00.00.32) Embed with CMSIS-DAP"):
    return SimpleNamespace(device=device, vid=vid, pid=pid, serial_number=sn, location=location, description=description)


class FakeLoop:
    """Runs what the reader thread hands to the event loop, at once."""

    def call_soon_threadsafe(self, fn, *args):
        fn(*args)


class PortTest(unittest.TestCase):
    def test_linux_names_by_interface(self):
        ports = [port("/dev/ttyACM1", location="1-1:1.3"), port("/dev/ttyACM0", location="1-1:1.0"),
                 port("/dev/ttyUSB0", vid=0x10C4, pid=0xEA60, sn="0001")]          # the IMU's CP2102: ignored
        self.assertEqual(find_xds110_ports(ports), ("/dev/ttyACM0", "/dev/ttyACM1"))

    def test_mac_names(self):
        ports = [port("/dev/cu.usbmodemRA29P0554"), port("/dev/cu.usbmodemRA29P0551")]
        self.assertEqual(find_xds110_ports(ports), ("/dev/cu.usbmodemRA29P0551", "/dev/cu.usbmodemRA29P0554"))

    def test_descriptions_win(self):
        ports = [port("/dev/ttyACM0", description="XDS110 Class Auxiliary Data Port"),
                 port("/dev/ttyACM1", description="XDS110 Class Application/User UART")]
        self.assertEqual(find_xds110_ports(ports), ("/dev/ttyACM1", "/dev/ttyACM0"))

    def test_no_board(self):
        self.assertEqual(find_xds110_ports([port("/dev/ttyUSB0", vid=0x10C4, pid=0xEA60)]), (None, None))
        self.assertEqual(find_xds110_ports([]), (None, None))


class ReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(HERE.parents[1] / "model"))
        from trnet import synth
        cls.tmp = Path(tempfile.mkdtemp())
        person = synth.make_person("F01", 1)
        plan = synth.Plan(sets=1, reps_per_set=2, set_rest_s=5, problems=("no_emg", "no_imu", "no_pose"))
        cls.session = synth.make_session(cls.tmp / "src", person, plan)
        from rec import session as S
        cls.n_frames = len(S.load(cls.session).radar_index()["frame_no"])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def provider(self, **kw):
        return RadarProvider(replay=str(self.session), replay_speed=200, replay_loop=False, **kw)

    def test_manifest(self):
        m = self.provider().manifest()
        self.assertEqual([f.view for f in m.frames], ["range_azimuth", "phase_change", "range_doppler"])
        self.assertEqual({f.shape for f in m.frames}, {(40, 16)})
        self.assertEqual({f.fps for f in m.frames}, {15.0})
        self.assertIn("marker", m.events)

    def test_maps_from_a_replayed_recording(self):
        p = self.provider()
        out: list[Frame] = []
        p._read(FakeLoop(), out.append)
        self.assertEqual(len(out), 3 * len([n for n in range(1, self.n_frames + 1) if n % 4 == 0]))
        by_view = {}
        for f in out:
            by_view.setdefault(f.view, []).append(f)
            self.assertEqual(f.data.shape, (40, 16))
            self.assertEqual(f.data.dtype, np.float32)
            self.assertTrue(np.isfinite(f.data).all())
        mag, ph, rd = (np.stack([f.data for f in by_view[v]]) for v in ("range_azimuth", "phase_change", "range_doppler"))
        self.assertTrue(0 <= mag.min() and mag.max() <= 1 and mag.max() > 0.9)
        self.assertTrue(np.abs(ph).max() <= 1 and np.abs(ph).max() > 0.05)     # the fake arm moves the phase
        self.assertTrue(0 <= rd.min() and rd.max() <= 1)
        self.assertTrue(all(f.frame_index % 4 == 0 for f in out))
        h = p.health()["radar"]
        self.assertEqual(h.state, "ok")
        self.assertIn("replay", h.message)

    def test_records_in_the_recorders_format(self):
        p = self.provider()
        self.assertTrue(p.records)
        rec = Recording(self.tmp / "rec", Session("S-test", "running", exercise="elbow flexion", user_id="S01"))
        p.on_recording_start(rec)
        rec.marker("halfway")
        p._read(FakeLoop(), lambda m: None)
        rec.close(p.on_recording_end())
        from rec import session as S
        from trnet import radar as R
        folders = list((self.tmp / "rec").iterdir())
        self.assertEqual(len(folders), 1)
        s = S.load(folders[0])
        self.assertEqual(s.meta["subject"], "S01")
        self.assertEqual(s.meta["exercise"], "elbow_flexion")
        self.assertEqual(s.meta["summary"]["radar"]["frames"], self.n_frames)
        self.assertEqual(s.meta["summary"]["radar"]["missing_frames"], 0)
        self.assertEqual(s.meta["summary"]["bridge_session"], "S-test")
        self.assertEqual(s.meta["sources"]["radar"]["cfg_lines"][0], "sensorStop")
        self.assertIn(("x", "halfway"), [(k, lbl) for _, k, lbl in s.markers])
        rec = R.load_radar(s)                     # the model's own reader takes it as it is
        self.assertEqual(int(rec.valid.sum()), self.n_frames)
        self.assertEqual(rec.contract.az_cols, (0, 2, 7, 9, 3, 5, 10, 12))

    def test_a_recording_without_frames_and_a_second_end(self):
        from rec import session as S
        p = self.provider()
        rec = Recording(self.tmp / "rec2", Session("B", "running"))      # no user code: subject KIT, no exercise
        p.on_recording_start(rec)
        summary = p.on_recording_end()
        self.assertEqual(p.on_recording_end(), {})                         # a second end is harmless
        rec.close(summary)
        s = S.load(rec.dir)
        self.assertEqual((s.meta["subject"], s.meta["exercise"]), ("KIT", "session"))
        self.assertEqual(s.meta["summary"]["radar"]["frames"], 0)
        self.assertEqual(len(s.radar_index()["frame_no"]), 0)


@unittest.skipUnless(HAVE_SERIAL, "pyserial not installed")
class NotPluggedInTest(unittest.TestCase):
    def test_says_so_in_plain_words(self):
        from serial.tools import list_ports
        p = RadarProvider()
        real = list_ports.comports
        list_ports.comports = lambda: []
        try:
            with self.assertRaises(RuntimeError):
                list(p._live_frames())
        finally:
            list_ports.comports = real
        h = p.health()["radar"]
        self.assertEqual(h.state, "missing")
        self.assertIn("Not plugged in", h.message)


if __name__ == "__main__":
    unittest.main()
