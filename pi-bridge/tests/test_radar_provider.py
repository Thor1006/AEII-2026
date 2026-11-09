"""The radar provider: port detection, maps the way the network sees them (from a replayed recording), recording
into the bridge's shared session folder in the recorder's format, and the live radar's restart at its frame limit
(fake ports). Needs numpy only (pyserial for the 'not plugged in' case); no radar, no websockets."""
from __future__ import annotations

import contextlib
import shutil
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from truerehab_bridge.protocol import Frame, Session  # noqa: E402
from truerehab_bridge.providers import radar as radar_mod  # noqa: E402
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
        self.assertEqual([f.view for f in m.frames], ["range_azimuth", "phase_change", "point_height", "range_doppler"])
        self.assertEqual({f.shape for f in m.frames}, {(40, 32), (40, 16)})       # 32 angle bins, 16 speed bins
        self.assertEqual([f.shape[1] for f in m.frames], [32, 32, 32, 16])
        wire = {f.view: f.wire() for f in m.frames}
        self.assertEqual(wire["point_height"]["range"], [-0.6, 0.6])        # its own colour scale, in metres
        self.assertNotIn("range", wire["range_azimuth"])
        self.assertEqual({f.fps for f in m.frames}, {15.0})
        self.assertIn("marker", m.events)

    def test_maps_from_a_replayed_recording(self):
        p = self.provider()
        out: list[Frame] = []
        p._read(FakeLoop(), out.append)
        self.assertEqual(len(out), 4 * len([n for n in range(1, self.n_frames + 1) if n % 4 == 0]))
        by_view = {}
        for f in out:
            by_view.setdefault(f.view, []).append(f)
            self.assertEqual(f.data.shape, (40, 16 if f.view == "range_doppler" else 32))
            self.assertEqual(f.data.dtype, np.float32)
            self.assertTrue(np.isfinite(f.data).all())
        heights = np.stack([f.data for f in by_view["point_height"]])
        self.assertTrue(np.abs(heights).max() > 0 and np.abs(heights).max() <= 1.0)   # metres, within the 1-m scale
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

    def test_a_looping_replay_keeps_counting(self):
        """Frame numbers go on across the replay's loops, in the packet header too: a recording of a replay longer than
        its source then has no backwards jump (the model read one as a broken clock and 1667 missing frames)."""
        from radarlab.tlv import FrameReader
        p = RadarProvider(replay=str(self.session), replay_speed=1000, replay_loop=True)
        nos, in_header = [], []
        for raw, f in p._replay_frames():
            nos.append(f.number)
            in_header.append(FrameReader().feed(raw)[0].number)
            if len(nos) == self.n_frames + 50:
                break
        self.assertEqual(nos, list(range(nos[0], nos[0] + len(nos))))
        self.assertEqual(in_header, nos)

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


class FakeRadar:
    """The radar's two USB ports, faked (no pyserial needed). The data port hands out packets run by run. Sending the
    profile (send_cfg, which ends with sensorStart) begins the next run, the way the radar starts again from frame 1.
    `done` (an Event) is set once the last run is used up."""

    def __init__(self, *runs, running=False, done=None):
        self.runs = [list(r) for r in runs]
        self.run = 0 if running else -1          # running: someone else started it before the bridge came
        self.starts = 0
        self.done = done

    def module(self):
        m = types.ModuleType("serial")
        m.Serial = lambda port, baud, timeout=0.05: FakePort(self)
        m.SerialException = OSError
        return m

    def send_cfg(self, cli, lines):
        self.starts += 1
        self.run += 1
        return True


class FakePort:
    def __init__(self, radar):
        self.radar = radar

    def read(self, n):
        r = self.radar
        if 0 <= r.run < len(r.runs) and r.runs[r.run]:
            return r.runs[r.run].pop(0)
        if r.done is not None and r.run == len(r.runs) - 1:
            r.done.set()
        time.sleep(0.005)
        return b""

    def reset_input_buffer(self):
        pass

    def close(self):
        pass


@contextlib.contextmanager
def faked(radar):
    import view                                   # radar-lab/view.py: where the bridge's start sequence comes from
    with mock.patch.dict(sys.modules, {"serial": radar.module()}), \
            mock.patch.object(view, "send_cfg", radar.send_cfg), \
            mock.patch.object(view, "cli_send", lambda *a, **k: ""):
        yield


def take(frames, n):
    """The first n (raw, frame) pairs of a live source, then close it (as the bridge does when it stops)."""
    out = []
    for item in frames:
        out.append(item)
        if len(out) == n:
            break
    frames.close()
    return out


def packets(numbers):
    from radarlab.tlv import encode_frame
    return [encode_frame(n, {}) for n in numbers]


class LiveRestartTest(unittest.TestCase):
    """The radar stops by itself after its 65,535 frames (about 18 min at 60 fps). The bridge starts it again on the
    open command port and goes on counting frames, so a recording never jumps back: the model sorts frames by number,
    and two runs that both begin at frame 1 would be mixed. Fake ports: no radar, no pyserial."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(HERE.parents[1] / "model"))
        from radarlab.tlv import FrameReader
        from rec import session as S
        from trnet import synth
        cls.tmp = Path(tempfile.mkdtemp())
        person = synth.make_person("F01", 1)
        plan = synth.Plan(sets=1, reps_per_set=2, set_rest_s=5, problems=("no_emg", "no_imu", "no_pose"))
        s = S.load(synth.make_session(cls.tmp / "src", person, plan))
        idx, raw = s.radar_index(), (s.dir / "radar.bin").read_bytes()
        cls.frames = [FrameReader().feed(raw[o:o + n])[0] for o, n in zip(idx["offset"][:120], idx["length"][:120])]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_starts_it_again_at_its_frame_limit_and_counts_on(self):
        radar = FakeRadar(packets(range(65530, 65536)), packets(range(1, 6)))
        p = RadarProvider(data_port="data", cli_port="cli")
        with faked(radar):
            got = take(p._live_frames(), 11)
        numbers = [f.number for _, f in got]
        self.assertEqual(radar.starts, 2)                               # the start, then once more at the limit
        self.assertEqual(numbers[:6], list(range(65530, 65536)))
        pause = numbers[6] - numbers[5]                                  # the quiet before the restart, in frames
        self.assertGreaterEqual(pause, round(radar_mod.END_SILENCE_S * 1000 / radar_mod.FRAME_PERIOD_MS) - 1)
        self.assertEqual(numbers[6:], list(range(numbers[6], numbers[6] + 5)))
        from radarlab.tlv import FrameReader
        self.assertEqual([FrameReader().feed(raw)[0].number for raw, _ in got], numbers)   # in the packet too
        h = p.health()["radar"]
        self.assertEqual(h.state, "ok")
        self.assertIn("restarted 1× at its 18-min frame limit", h.message)

    def test_counts_on_when_the_bridge_starts_the_radar_again(self):
        """After an error the bridge's supervisor runs the reader again, which starts the radar from frame 1."""
        radar = FakeRadar(packets(range(1, 4)), packets(range(1, 4)))
        p = RadarProvider(data_port="data", cli_port="cli")
        with faked(radar):
            first = [f.number for _, f in take(p._live_frames(), 3)]
            p._cli = None                                                # what _shutdown_radar leaves behind
            second = [f.number for _, f in take(p._live_frames(), 3)]
        self.assertEqual(first, [1, 2, 3])
        self.assertGreater(second[0], 3)
        self.assertEqual(second, list(range(second[0], second[0] + 3)))
        self.assertNotIn("restarted", p.health()["radar"].message)        # that was not the frame limit

    def test_says_why_when_someone_else_started_it(self):
        radar = FakeRadar(packets(range(65530, 65536)), running=True)
        p = RadarProvider(data_port="data", cli_port="cli", start_radar=False)
        with faked(radar), mock.patch.object(radar_mod, "NO_FRAMES_S", 0.3):
            with self.assertRaises(RuntimeError):
                take(p._live_frames(), 99)
        h = p.health()["radar"]
        self.assertEqual((h.state, radar.starts), ("error", 0))
        self.assertIn("sent all its 65,535 frames", h.message)

    def test_quiet_in_the_middle_is_still_the_cables(self):
        radar = FakeRadar(packets(range(100, 106)))
        p = RadarProvider(data_port="data", cli_port="cli")
        with faked(radar), mock.patch.object(radar_mod, "NO_FRAMES_S", 0.3):
            with self.assertRaises(RuntimeError):
                take(p._live_frames(), 99)
        self.assertEqual(radar.starts, 1)                                # no restart in the middle of a run
        self.assertIn("Check the cables", p.health()["radar"].message)

    def test_a_recording_across_the_restart_reads_as_one_clock(self):
        from rec import session as S
        from trnet import radar as R
        before = [radar_mod.renumber(f, n)[0] for f, n in zip(self.frames[:60], range(65476, 65536))]
        after = [radar_mod.renumber(f, n)[0] for f, n in zip(self.frames[60:], range(1, 61))]
        p = RadarProvider(data_port="data", cli_port="cli")
        radar = FakeRadar(before, after, done=p._stop)
        rec = Recording(self.tmp / "rec", Session("S-restart", "running", exercise="elbow flexion", user_id="S01"))
        p.on_recording_start(rec)
        with faked(radar):
            p._read(FakeLoop(), lambda m: None)
        rec.close(p.on_recording_end())
        s = S.load(rec.dir)
        nos = s.radar_index()["frame_no"]
        self.assertEqual(radar.starts, 2)
        self.assertEqual(len(nos), 120)
        self.assertTrue(np.all(np.diff(nos) > 0))                        # never back
        pause = int(nos[60] - nos[59])
        self.assertGreater(pause, 1)
        self.assertEqual(s.meta["summary"]["radar"]["missing_frames"], pause - 1)   # the pause, as missing frames
        r = R.load_radar(s)                     # the model's reader: every frame kept, none mixed or dropped
        self.assertEqual(int(r.valid.sum()), 120)
        self.assertEqual(len(r.valid), int(nos[-1] - nos[0] + 1))


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
