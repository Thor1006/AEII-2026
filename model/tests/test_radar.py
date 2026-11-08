import json
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

from _util import REAL_RADAR_SESSION, have_real_sessions, small_contract
from trnet import radar as R

from radarlab import maps  # noqa: E402  (radar-lab, read-only)
from radarlab.tlv import encode_frame  # noqa: E402
from rec import session as S  # noqa: E402  (recorder, read-only)


def payload(iq):
    """complex [64, 8] -> static heatmap payload (imaginary first, int16)."""
    return np.stack([iq.imag, iq.real], -1).round().clip(-32768, 32767).astype("<i2").tobytes()


def tiny_session(tmp, frame_numbers, period_s=1 / 60, seed=0):
    """A radar-only session folder in recorder format with chosen frame numbers (gaps allowed)."""
    rng = np.random.default_rng(seed)
    d = Path(tmp) / "2026-01-01_000000_TEST_tiny"
    d.mkdir()
    rows, off = [], 0
    with open(d / "radar.bin", "wb") as f:
        for no in frame_numbers:
            iq = 200 * (rng.standard_normal((64, 8)) + 1j * rng.standard_normal((64, 8)))
            rd = np.full((64, 16), 256 * 7.0).astype("<u2")
            b = encode_frame(int(no), {4: payload(iq), 5: rd.tobytes()})
            f.write(b)
            t_ns = int(1e9 + no * period_s * 1e9 + rng.uniform(0, 3e6))
            rows.append(f"{no},{t_ns},{off},{len(b)}")
            off += len(b)
    (d / "radar_index.csv").write_text("frame_no,t_ns,offset,length\n" + "\n".join(rows) + "\n")
    (d / "markers.csv").write_text("t_ns,key,label\n")
    (d / "meta.json").write_text(json.dumps({"format": S.FORMAT, "subject": "TEST", "sources": {"radar": {}}}))
    return S.load(d)


class RadarTest(unittest.TestCase):
    def setUp(self):
        self.c = small_contract()

    def test_angle_fft_matches_radar_lab(self):
        rng = np.random.default_rng(1)
        iq = (300 * (rng.standard_normal((64, 8)) + 1j * rng.standard_normal((64, 8)))).round()
        p = payload(iq)
        ours = np.abs(R.angle_fft(R.static_iq(p), self.c))
        for a in (16, self.c.angle_bins):              # radar-lab's own range-azimuth map, at both grids
            c = small_contract(angle_bins=a)
            ours = np.abs(R.angle_fft(R.static_iq(p), c))
            theirs = maps.range_azimuth(p, 8, angle_bins=a, az_index=list(c.az_index), az_cols=list(c.az_cols))
            np.testing.assert_allclose(ours, theirs, rtol=1e-4, atol=1e-2)

    def test_range_doppler_units(self):
        rd = np.zeros((64, 16), "<u2")
        rd[:, 0] = 256 * 10       # zero speed, magnitude 2**10
        out = R.rd_db(rd.tobytes(), 64)
        self.assertAlmostEqual(out[0, 8], 20 * np.log10(2 ** 10), places=3)   # moved to the middle column
        self.assertEqual(out[0, 0], 0)

    def test_phase_change_measures_tiny_motion_and_stops_at_gaps(self):
        n, d_m = 6, 0.1e-3            # a reflector creeping 0.1 mm away per frame
        k = 4 * np.pi * d_m / R.WAVELENGTH_M
        A = self.c.angle_bins
        Z = np.full((n, 64, A), 1000 + 0j, np.complex64) * np.exp(-1j * k * np.arange(n))[:, None, None]
        valid = np.array([1, 1, 1, 0, 1, 1], bool)
        rec = R.RadarRecording(np.arange(n), np.arange(n) / 60, valid, Z.astype(np.complex64),
                               np.full((n, 64, 16), 40, np.float32), np.full(n, 40.0), np.zeros(n, int),
                               np.arange(n) / 60, self.c)
        H, D, mask = R.to_inputs(rec)
        self.assertEqual(H.shape, (n, 4, 64, A))
        self.assertEqual(float(np.abs(H[:, 2:]).max()), 0.0)                  # no points: empty point layers
        self.assertAlmostEqual(float(-H[1, 1, 0, 0]) * np.pi, k, places=4)    # 0.32 rad for 0.1 mm
        self.assertEqual(float(np.abs(H[4, 1]).max()), 0.0)    # first frame after the gap: no phase
        self.assertEqual(float(np.abs(H[3]).max()), 0.0)       # the missing frame itself is empty
        self.assertFalse(mask[3])
        self.assertTrue(np.all((H[:, 0] >= 0) & (H[:, 0] <= 1)))

    def test_missing_frames_become_masked_grid_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = tiny_session(tmp, [1, 2, 3, 4, 7, 8, 9, 10, 11, 12])
            rec = R.load_radar(s, self.c)
            self.assertEqual(list(rec.frame_no), list(range(1, 13)))
            self.assertEqual(list(np.flatnonzero(~rec.valid)), [4, 5])
            self.assertLess(np.ptp(np.diff(rec.t_s)), 1e-9)                  # a regular grid, bunching removed
            self.assertAlmostEqual(np.diff(rec.t_s).mean(), 1 / 60, delta=1e-4)  # 0.2 s of jittery data: ~0.1 %
            H, D, mask = R.to_inputs(rec)
            self.assertEqual(int(mask.sum()), 10)
            self.assertEqual(float(np.abs(H[6, 1]).max()), 0.0)

    @unittest.skipUnless(have_real_sessions(), "real recordings not on this computer")
    def test_real_recording(self):
        s = S.load(REAL_RADAR_SESSION)
        rec = R.load_radar(s)
        self.assertEqual(len(rec.frame_no), 919)
        self.assertTrue(rec.valid.all())
        self.assertAlmostEqual(rec.fps, 60.0, delta=0.05)
        self.assertEqual(rec.contract.az_cols, (0, 2, 7, 9, 3, 5, 10, 12))
        H, D, mask = R.to_inputs(rec)
        self.assertEqual(H.shape, (919, 4, 64, 32))
        self.assertEqual(D.shape, (919, 1, 64, 16))
        self.assertTrue(H[:, 3].max() > 0 and np.abs(H[:, 2]).max() <= 1)   # the real points fill their layers
        self.assertTrue(np.isfinite(H).all() and np.isfinite(D).all())
        self.assertTrue(0 <= H[:, 0].min() and H[:, 0].max() <= 1 and np.abs(H[:, 1]).max() <= 1)
        self.assertEqual(np.nanmax(rec.temp_c), 45.0)
        frame = next(iter(s.radar_frames()))[1]
        theirs = maps.range_azimuth(frame.tlvs[4], 8, angle_bins=32, az_index=list(rec.contract.az_index),
                                    az_cols=list(rec.contract.az_cols))
        np.testing.assert_allclose(np.abs(rec.Z[0]), theirs, rtol=1e-4, atol=1e-2)

    @unittest.skipUnless(have_real_sessions(), "real recordings not on this computer")
    def test_real_points_sit_on_bright_heatmap_cells(self):
        """The radar's still points and its static heatmap, same frame: with the contract's sign the points sit on
        cells far brighter than the rest of their range row; with the other sign they don't (measured 2026-11-08)."""
        rec = R.load_radar(S.load(REAL_RADAR_SESSION.parent / "2026-11-05_191441_TEST_radar_curls"))
        right, n = R.points_on_heatmap(rec)
        wrong, _ = R.points_on_heatmap(rec, sign=-rec.contract.points_az_sign)
        self.assertGreater(n, 10_000)
        self.assertGreater(right, 8.0)
        self.assertLess(wrong, right - 6.0)


class PointsTest(unittest.TestCase):
    def setUp(self):
        self.c = small_contract()

    def test_points_and_their_snr_are_read(self):
        pts = [(0.1, 1.2, 0.3, 0.0), (-0.4, 1.0, -0.2, 0.55)]
        tlvs = {1: b"".join(struct.pack("<ffff", *p) for p in pts), 7: struct.pack("<hhhh", 155, 300, 80, 300)}
        out = R.points_of(tlvs)
        np.testing.assert_allclose(out[:, :4], pts, atol=1e-6)
        np.testing.assert_allclose(out[:, 4], [15.5, 8.0])
        self.assertEqual(R.points_of({}).shape, (0, 5))
        self.assertTrue(np.isnan(R.points_of({1: tlvs[1]})[:, 4]).all())    # no side info: SNR unknown

    def test_a_point_lands_on_its_range_and_angle_cell(self):
        c = self.c
        r, u = 1.30, 0.25                       # 1.3 m away, direction cosine 0.25 along the antenna row
        x = u * r
        pts = np.array([[x, np.sqrt(r * r - x * x), 0.0, 0.0, 20.0]])
        rb, ab, ok = R.point_cells(pts, c)
        self.assertTrue(ok[0])
        self.assertEqual(rb[0], round(r / c.range_res_m))
        self.assertEqual(ab[0], round(c.angle_bins / 2 * (1 + c.points_az_sign * u)))
        # the same place in the angle FFT of a target there: the brightest bin
        iq = np.exp(1j * np.pi * np.array(c.az_cols) * c.points_az_sign * u)[None].repeat(64, 0) * 1000
        self.assertEqual(int(np.argmax(np.abs(R.angle_fft(iq, c))[rb[0]])), ab[0])
        far = np.array([[0.0, c.range_bins * c.range_res_m + 0.5, 0.0, 0.0, 20.0]])
        self.assertFalse(R.point_cells(far, c)[2][0])                             # beyond the grid: dropped

    def test_window_pools_the_last_frames_and_forgets_older_ones(self):
        c = small_contract(points_window=3)
        w = R.PointWindow(c)
        p_hi = np.array([[0.0, np.sqrt(1 - 0.4 ** 2), 0.4, 0.0, 30.0]])   # 1.0 m away, 0.4 m above the radar, 30 dB
        p_lo = np.array([[0.0, np.sqrt(1 - 0.2 ** 2), -0.2, 0.0, 10.0]])  # same cell (1.0 m), 0.2 m below, 10 dB
        rb, ab, _ = R.point_cells(p_hi, c)
        w.push(p_hi)
        w.push(p_lo)
        h, pres = w.layers()
        self.assertAlmostEqual(float(h[rb[0], ab[0]]), (30 * 0.4 + 10 * -0.2) / 40 / c.height_scale_m, places=5)
        self.assertAlmostEqual(float(pres[rb[0], ab[0]]), 2 / c.presence_full)
        w.push(None)                                            # a frame without points (or a missing one)
        w.push(None)                                            # the 0.4-m point is now 3 frames old: gone
        h, pres = w.layers()
        self.assertAlmostEqual(float(h[rb[0], ab[0]]), -0.2 / c.height_scale_m, places=5)
        w.push(None)
        h, pres = w.layers()
        self.assertEqual(float(np.abs(h).max() + pres.max()), 0.0)               # nothing left, nothing invented


if __name__ == "__main__":
    unittest.main()
