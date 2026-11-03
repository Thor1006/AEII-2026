import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radarlab import cfg, maps, sim  # noqa: E402
from radarlab.tlv import (AZIMUTH_STATIC_HEATMAP, RANGE_DOPPLER_HEATMAP,  # noqa: E402
                          FrameReader, encode_frame)


class ParserTest(unittest.TestCase):
    def test_round_trip_with_garbage_and_tiny_chunks(self):
        data = b"\xff\x02\x01junk" + encode_frame(7, {4: b"abcd", 5: b"\x01\x02"}) + encode_frame(8, {})
        reader, frames = FrameReader(), []
        for i in range(len(data)):  # one byte at a time
            frames += reader.feed(data[i : i + 1])
        self.assertEqual([f.number for f in frames], [7, 8])
        self.assertEqual(frames[0].tlvs, {4: b"abcd", 5: b"\x01\x02"})

    def test_bad_length_is_skipped(self):
        bad = bytearray(encode_frame(1, {4: b"x" * 8}))
        bad[12:16] = (10**9).to_bytes(4, "little")  # absurd totalPacketLen
        frames = FrameReader().feed(bytes(bad) + encode_frame(2, {}))
        self.assertEqual([f.number for f in frames], [2])


class SimTest(unittest.TestCase):
    def static_map(self, clutter_removal):
        frame = FrameReader().feed(sim.Room(clutter_removal).frame())[0]
        return maps.range_azimuth(frame.tlvs[AZIMUTH_STATIC_HEATMAP], sim.VIRT_ANT), frame

    def test_chair_shows_up_at_the_right_place(self):
        ra, _ = self.static_map(False)
        ang = maps.angles_deg(ra.shape[1])
        r = np.hypot(0.8, 1.9)
        r_bin = int(round(r / sim.RANGE_RES_M))
        best = np.argmax(ra[r_bin])
        self.assertAlmostEqual(ang[best], np.degrees(np.arctan2(0.8, 1.9)), delta=6)

    def test_clutter_removal_hides_still_things(self):
        on, _ = self.static_map(True)
        off, frame = self.static_map(False)
        self.assertGreater(off.max() / on.max(), 20)
        rd = maps.range_doppler(frame.tlvs[RANGE_DOPPLER_HEATMAP], sim.RANGE_BINS)
        self.assertEqual(rd.shape, (sim.RANGE_BINS, sim.DOPPLER_BINS))


class BoardCfgTest(unittest.TestCase):
    CFG = Path(__file__).resolve().parents[1] / "configs" / "fullmap_awr2x44p.cfg"

    def test_layout(self):
        L = cfg.load(self.CFG)
        self.assertEqual(L.n_virt, 12)  # 3 TX x 4 RX
        self.assertEqual(sorted(L.az_cols), [0, 2, 3, 5, 7, 9, 10, 12])
        self.assertAlmostEqual(L.vel_res, 0.137, places=3)  # visualizer said 0.13

    def test_uneven_antennas_find_the_right_angle(self):
        L = cfg.load(self.CFG)
        theta = np.radians(25)
        x = np.zeros((4, L.n_virt), complex)
        for k, col in zip(L.az_index, L.az_cols):
            x[2, k] = 1000 * np.exp(1j * np.pi * col * np.sin(theta))
        payload = np.stack([x.imag, x.real], -1).astype("<i2").tobytes()
        ra = maps.range_azimuth(payload, L.n_virt, angle_bins=128,
                                az_index=L.az_index, az_cols=L.az_cols)
        self.assertAlmostEqual(maps.angles_deg(128)[np.argmax(ra[2])], 25, delta=2)


if __name__ == "__main__":
    unittest.main()
