"""link_report.py: pauses held by the network vs not sent by the board, the resend-timer signature, other readers."""
import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import link_report as L  # noqa: E402


def write_session(folder: Path) -> None:
    """60 s of 1-kHz sEMG over Wi-Fi in 20-ms chunks, with:
    - at 10 s: a 1.1-s pause held by the network, ended by a 1-sample chunk, then the catch-up (resend timer);
    - at 30 s: 0.5 s the board never sent (its clock jumps);
    - another program connecting once (link_clients 3 -> 5 with one reconnect of our own)."""
    rows = [["t_ns", "line"]]
    us = 4_294_000_000                                   # micros() wraps during the session
    t = 1.0
    sample = 0
    rows.append([int(t * 1e9), "# status up_s=1 emg_hz=1000.0 rssi_dbm=-48 link_clients=3 link_dropped=0"])
    while sample < 60_000:
        if sample == 10_000:                             # held: no chunk for 1.1 s, then 1 sample, then the rest
            t += 1.1
            rows.append([int(t * 1e9), f"E,{us & 0xFFFFFFFF},2000,100"])
            us += 1000
            sample += 1
            t += 0.02
            rows += [[int(t * 1e9), f"E,{(us + i * 1000) & 0xFFFFFFFF},2000,100"] for i in range(1119)]
            us += 1119 * 1000
            sample += 1119
            continue
        if sample == 30_000:                             # not sent: the board's clock jumps 500 ms
            us += 500_000
            t += 0.5
            rows.append([int(t * 1e9), "# bridge: link lost (closed by the board)"])
            rows.append([int(t * 1e9), "# bridge: link back"])
        t += 0.02
        rows += [[int(t * 1e9), f"E,{(us + i * 1000) & 0xFFFFFFFF},2000,100"] for i in range(20)]
        us += 20 * 1000
        sample += 20
    rows.append([int(t * 1e9), "# status up_s=61 emg_hz=1000.0 rssi_dbm=-72 link_clients=5 link_dropped=0 "
                                "link_stall_ms=870 link_buf_max=23000"])
    with (folder / "emg.csv").open("w", newline="") as f:
        csv.writer(f).writerows(rows)
    (folder / "meta.json").write_text(json.dumps({"sources": {"emg": {"port": "tcp://127.0.0.1:3334"}}}))


class LinkReport(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        write_session(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_kinds_of_pause(self):
        (r,) = L.report(self.tmp)
        self.assertEqual(r["link"], "Wi-Fi")
        self.assertEqual(len(r["pauses"]), 2)
        held, not_sent = r["pauses"]
        self.assertTrue(held["held"])
        self.assertAlmostEqual(held["s"], 1.10, places=2)
        self.assertEqual(held["first_chunk"], 1)
        self.assertEqual(r["tiny_first"], 1)                 # the resend-timer signature
        self.assertFalse(not_sent["held"])
        self.assertEqual(not_sent["not_sent"], 500)
        self.assertEqual(r["link_drops"], 1)
        self.assertEqual(r["other_clients"], 1)              # 3 -> 5 with one reconnect of our own
        self.assertEqual(r["rssi"][0], -72)
        self.assertEqual((r["stall_ms"], r["buf_max"]), (870, 23000))
        self.assertAlmostEqual(r["rate_hz"], 1000, delta=30)

    def test_plain_words(self):
        text = L.describe(self.tmp, L.report(self.tmp))
        self.assertIn("held by the network (nothing lost): 1; of these 1 ended with a tiny chunk", text)
        self.assertIn("not sent by the board", text)
        self.assertIn("ANOTHER PROGRAM read the board too (1x)", text)
        self.assertIn("longest send stall 870 ms", text)
        self.assertEqual(L.main([str(self.tmp), str(self.tmp)]), 0)   # two sessions: a comparison table


if __name__ == "__main__":
    unittest.main()
