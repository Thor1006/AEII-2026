"""The sEMG provider (MyoWare 2.0 over Wi-Fi): the live envelope and median frequency (with the model's own code),
health in plain words, recording in the recorder's format, reconnecting after a drop. Against fake_myoware.py on
this computer: numpy only (no board, no websockets)."""
from __future__ import annotations

import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from fake_myoware import FakeMyoWare, fake_signal  # noqa: E402
from truerehab_bridge.protocol import Aux, Session  # noqa: E402
from truerehab_bridge.providers.emg import EmgProvider, tcp_address  # noqa: E402
from truerehab_bridge.recording import Recording  # noqa: E402

BOOT_US = 4_294_000_000          # 0.97 s before micros() wraps: every fed signal crosses the wrap
BASE_MS = 1.7e12                 # a wall-clock time for the fed chunks' arrival


def board_lines(raw, env, start=0, boot_us=BOOT_US):
    return [f"E,{(boot_us + (start + i) * 1000) & 0xFFFFFFFF},{r},{e}".encode() for i, (r, e) in enumerate(zip(raw, env))]


def feed(p: EmgProvider, lines, chunk=20, boot_us=BOOT_US) -> list[Aux]:
    """Hand the provider the board's lines, 20 per chunk, each chunk arriving the moment its last sample was made:
    a message's t is then BASE_MS + the sample's device time in ms."""
    out: list[Aux] = []
    for s in range(0, len(lines), chunk):
        part = lines[s:s + chunk]
        made_ms = ((int(part[-1].split(b",")[1]) - boot_us) & 0xFFFFFFFF) / 1000
        p._handle_lines(part, BASE_MS + made_ms, out.append)
    return out


def values(out, key) -> list[tuple[float, float]]:
    """(seconds since the first sample, value) of one channel."""
    return [((m.t - BASE_MS) / 1000, m.channels[key]) for m in out if key in m.channels]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Signal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw, cls.env, cls.curls = fake_signal(seed=3, sets=1, reps=8)

    def test_median_frequency_is_the_models_own(self):
        """With the activity gate off, every 0.5-s window equals model/trnet/truth.py emg_mdf's (the fatigue labels)."""
        from trnet.truth import Emg, emg_mdf
        p = EmgProvider(port="tcp://127.0.0.1:9", active_ratio=0)
        live = values(feed(p, board_lines(self.raw, self.env)), "emg_mdf")
        n = len(self.raw)
        t = np.arange(n) / 1000
        t_off, mdf_off, _ = emg_mdf(Emg(t, self.raw.astype(float), self.env.astype(float), t, np.arange(n) * 1000))
        self.assertEqual(len(live), len(mdf_off))
        np.testing.assert_allclose([v for _, v in live], mdf_off, atol=0.051)       # sent rounded to 0.1 Hz
        np.testing.assert_allclose([s for s, _ in live], t_off, atol=0.0015)       # stamped at the window centre

    def test_median_frequency_only_while_working_and_it_falls(self):
        out = feed(EmgProvider(port="tcp://127.0.0.1:9"), board_lines(self.raw, self.env))
        mdf = values(out, "emg_mdf")
        in_curl = [any(a - 0.3 <= s <= b + 0.3 for a, b in self.curls) for s, _ in mdf]
        self.assertGreater(len(mdf), 40)
        self.assertGreaterEqual(np.mean(in_curl), 0.95)                       # not at rest: noise isn't muscle
        self.assertFalse(any(s < self.curls[0][0] - 0.3 for s, _ in mdf))     # nothing in the still part
        per_curl = [[v for s, v in mdf if a <= s <= b] for a, b in self.curls]
        self.assertGreaterEqual(sum(len(v) >= 2 for v in per_curl), 7)        # nearly every curl gets values
        first, last = np.mean(per_curl[0] + per_curl[1]), np.mean(per_curl[-2] + per_curl[-1])
        self.assertLess(last, first - 3)                                       # the fake muscle tires

    def test_envelope_50_per_second_and_higher_in_curls(self):
        env = values(feed(EmgProvider(port="tcp://127.0.0.1:9"), board_lines(self.raw, self.env)), "emg_env")
        self.assertEqual(len(env), len(self.raw) // 20)
        times = np.array([s for s, _ in env])
        self.assertTrue(np.all(np.diff(times) > 0))
        np.testing.assert_allclose(np.diff(times), 0.02, atol=1e-6)
        v = np.array([x for _, x in env])
        working = np.array([any(a + 0.5 <= s <= b - 0.5 for a, b in self.curls) for s in times])
        still = times < self.curls[0][0] - 1
        self.assertGreater(v[working].mean(), 3 * v[still].mean())

    def test_gaps_repeats_wrap_and_restart(self):
        p = EmgProvider(port="tcp://127.0.0.1:9")
        lines = board_lines(self.raw[:3000], self.env[:3000])                 # crosses the 32-bit wrap at ~970
        lines = lines[:1000] + [lines[999]] + lines[1100:]                    # a repeat, then 100 samples lost
        out = feed(p, lines)
        self.assertEqual(p._lost, 100)
        env = values(out, "emg_env")
        self.assertEqual(len(env), 2900 // 20)
        self.assertGreater(env[-1][0], 2.9)                                   # the device clock went on over the gap
        restart = board_lines(self.raw[:500], self.env[:500], boot_us=1_000_000)  # the board rebooted: clock back
        p._handle_lines(restart, BASE_MS + 4000, lambda m: None)
        self.assertEqual(p._lost, 100)                                        # a restart isn't counted as lost

    def test_wifi_pauses_are_held_data_only(self):
        """A chunk 1.1 s after the last one with nothing missing is a Wi-Fi pause (the board kept sampling, the network
        held the data back); a gap in the board's own clock is lost samples, not a pause."""
        p = EmgProvider(port="tcp://127.0.0.1:9")
        p._link, p._connected_at = "up", time.monotonic() - 5
        lines = board_lines(self.raw[:3000], self.env[:3000])
        p._handle_lines(lines[:1000], BASE_MS + 1000, lambda m: None)
        p._handle_lines(lines[1000:2000], BASE_MS + 2100, lambda m: None)    # held back 1.1 s, then all of it
        p._handle_lines(lines[2500:3000], BASE_MS + 2700, lambda m: None)    # 500 samples never came
        self.assertEqual([round(s, 2) for _, s in p._pauses], [1.1])
        self.assertEqual(p._lost, 500)
        self.assertIn("1 Wi-Fi pause(s) in 5 min, longest 1.1 s", p.health()["emg"].message)

    def test_flat_signal_and_clipping_in_plain_words(self):
        p = EmgProvider(port="tcp://127.0.0.1:9")
        p._link, p._connected_at = "up", time.monotonic() - 5
        feed(p, board_lines(np.full(1000, 1900), np.full(1000, 30)))
        h = p.health()["emg"]
        self.assertEqual(h.state, "error")
        self.assertIn("Flat signal", h.message)
        clipped = np.where(np.arange(2000) % 10 == 0, 4095, self.raw[5000:7000])
        feed(p, board_lines(clipped, self.env[5000:7000], start=5000))
        h = p.health()["emg"]
        self.assertEqual(h.state, "ok", h.message)
        self.assertIn("clipping in 10% of samples", h.message)

    def test_median_frequency_is_announced_as_intermittent(self):
        aux = {a.key: a.wire() for a in EmgProvider(port="tcp://127.0.0.1:9").manifest().aux}
        self.assertEqual(aux["emg_mdf"]["intermittent"], True)          # only during movement: silence isn't a fault
        self.assertNotIn("intermittent", aux["emg_env"])
        self.assertEqual((aux["emg_env"]["rateHz"], aux["emg_mdf"]["rateHz"]), (50.0, 4.0))

    def test_addresses(self):
        self.assertEqual(tcp_address("tcp://truerehab-myoware.local:3334"), ("truerehab-myoware.local", 3334))
        self.assertIsNone(tcp_address("/dev/ttyUSB0"))
        with self.assertRaises(ValueError):
            tcp_address("tcp://no-port")


class Live(unittest.TestCase):
    """Over a real TCP connection to the fake board (its clock runs 5x fast to keep the tests short)."""

    def setUp(self):
        self.fake = FakeMyoWare(port=0, seed=2, speed=5).start()
        self.tmp = Path(tempfile.mkdtemp())
        self.p = EmgProvider(port=self.fake.url)
        self.out: list[Aux] = []
        self.reader = threading.Thread(target=self.p._read_forever, args=(self.out.append,), daemon=True)
        self.reader.start()

    def tearDown(self):
        self.p._stop.set()
        self.reader.join(3)
        self.fake.stop()
        shutil.rmtree(self.tmp)

    def wait_for(self, pred, timeout=5.0, what="it"):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if pred():
                return
            time.sleep(0.05)
        self.fail(f"waited {timeout:.0f} s for {what}; health: {self.p.health()['emg']}")

    def test_streams_and_says_so(self):
        self.wait_for(lambda: len(values(self.out, "emg_env")) >= 200, what="the envelope")
        h = self.p.health()["emg"]
        self.assertEqual(h.state, "ok", h.message)
        self.assertRegex(h.message, r"^\d+ samples/s · Wi-Fi -52 dBm$")

    def test_records_like_the_recorder_and_reconnects(self):
        from rec import session as S
        from trnet.truth import load_emg
        self.wait_for(lambda: self.p.health()["emg"].state == "ok", what="the link")
        rec = Recording(self.tmp, Session("S-emg", "running", exercise="elbow flexion", user_id="S02"))
        self.p.on_recording_start(rec)
        time.sleep(0.6)
        self.assertIn("recording", self.p.health()["emg"].message)
        self.fake.drop_client()                                               # the Wi-Fi drops
        self.wait_for(lambda: self.fake.clients >= 2, what="the reconnect")
        self.wait_for(lambda: self.p.health()["emg"].state == "ok", what="data after the reconnect")
        time.sleep(0.6)
        rec.close(self.p.on_recording_end())
        s = S.load(rec.dir)
        self.assertEqual(s.meta["sources"]["emg"]["port"], self.fake.url)
        summary = s.meta["summary"]
        self.assertEqual(summary["emg"]["link_drops"], 1)
        self.assertEqual(summary["bridge_session"], "S-emg")
        rows = (rec.dir / "emg.csv").read_text().splitlines()
        self.assertEqual(rows[0], "t_ns,line")
        self.assertTrue(rows[1].split(",", 1)[1].startswith("# truerehab-record v2"))   # the board's header first
        notes = [r.split(",", 1)[1] for r in rows if ",# bridge: " in r]
        self.assertEqual([n.split(" (")[0] for n in notes], ["# bridge: link lost", "# bridge: link back"])
        data = s.record_mode("emg", "E")                                       # the recorder's own reader
        self.assertGreater(len(data["values"]), 4000)
        self.assertEqual(summary["emg"]["samples"], len(data["values"]))
        self.assertTrue(np.all(np.diff(data["t_host_s"]) >= 0))
        self.assertIsNotNone(load_emg(s))                                      # and the model's

    def test_another_reader_is_named_and_not_fought(self):
        """The board serves one client and drops the old one for a new one. When another program keeps taking it, the
        bridge says so and waits longer before taking it back, instead of both reconnecting every second."""
        self.wait_for(lambda: self.p.health()["emg"].state == "ok", what="the link")
        other = socket.create_connection((self.fake.host, self.fake.port))     # another program connects
        try:
            self.wait_for(lambda: self.fake.clients >= 3, what="the bridge taking the board back")
            other.close()
            other = socket.create_connection((self.fake.host, self.fake.port))  # ... and takes it again
            self.wait_for(lambda: self.p.health()["emg"].state == "error", what="the warning")
            msg = self.p.health()["emg"].message
            self.assertIn("Another program is reading the MyoWare", msg)
            self.assertIn("trying again in 5 s", msg)
            clients = self.fake.clients
            time.sleep(2)
            self.assertEqual(self.fake.clients, clients)                         # it waits instead of fighting
        finally:
            other.close()

    def test_wifi_pause_on_a_live_link(self):
        """The fake board holds its data back for 1.1 s (as the real one does now and then): one pause, nothing lost."""
        self.wait_for(lambda: self.p.health()["emg"].state == "ok", what="the link")
        self.fake.pause_every = 60.0                                         # one pause now, the next in a minute
        self.wait_for(lambda: len(self.p._pauses) >= 1, what="the pause to be seen")
        self.assertEqual(self.fake.pauses, 1)
        self.assertGreater(self.p._pauses[0][1], 0.9)
        self.assertEqual(self.p._lost, 0)

    def test_not_reachable_in_plain_words(self):
        p = EmgProvider(port=f"tcp://127.0.0.1:{free_port()}")
        t = threading.Thread(target=p._read_forever, args=(lambda m: None,), daemon=True)
        t.start()
        try:
            end = time.monotonic() + 5
            while p.health()["emg"].message.startswith("Connecting") and time.monotonic() < end:
                time.sleep(0.05)
            h = p.health()["emg"]
            self.assertEqual(h.state, "missing")
            self.assertIn("Not reachable at 127.0.0.1:", h.message)
            self.assertIn("refused", h.message)
            self.assertIn("same Wi-Fi", h.message)
        finally:
            p._stop.set()
            t.join(3)


if __name__ == "__main__":
    unittest.main()
