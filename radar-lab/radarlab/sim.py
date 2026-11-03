"""Fake radar room that sends the same bytes as the TI demo.

Scene (top view, radar at the origin looking along +y):
back wall at 3.6 m, side wall on the left, a chair, a person sitting still,
and the person's arm doing elbow flexion (the only thing that moves).
"""
import struct

import numpy as np

from .tlv import (AZIMUTH_STATIC_HEATMAP, DETECTED_POINTS, RANGE_DOPPLER_HEATMAP,
                  encode_frame)

RANGE_BINS = 128
RANGE_RES_M = 0.04
VIRT_ANT = 8
DOPPLER_BINS = 32
VEL_RES_MS = 0.0625
FPS = 10


def _static_objects():
    """(x, y, strength, z) for everything that never moves. z: height vs the radar (mounted ~1 m up)."""
    objs = [(x, 3.6, 300.0, 0.0) for x in np.arange(-2.4, 2.41, 0.08)]   # back wall
    objs += [(-2.0, y, 250.0, 0.0) for y in np.arange(0.6, 3.6, 0.08)]   # side wall
    objs += [(0.8, 1.9, 1200.0, -0.55), (0.95, 1.95, 900.0, -0.1)]       # chair: seat, back
    objs += [(-0.6, 1.3, 2200.0, -0.3), (-0.55, 1.35, 1500.0, 0.2)]      # person sitting still: body, head
    return objs


class Room:
    def __init__(self, clutter_removal=False, seed=0, fps=FPS):
        self.clutter_removal = clutter_removal
        self.rng = np.random.default_rng(seed)
        self.static = _static_objects()
        self.fps = fps
        self.n = 0

    def _arm(self):
        """Forearm near the person: radial speed swings with each curl (~0.5 Hz)."""
        t = self.n / self.fps
        return -0.35, 1.2, 0.6 * np.sin(2 * np.pi * 0.5 * t), 900.0

    def frame(self):
        r_axis = np.arange(RANGE_BINS)
        ant = np.arange(VIRT_ANT)
        noise = 20.0
        x = noise * (self.rng.standard_normal((RANGE_BINS, VIRT_ANT))
                     + 1j * self.rng.standard_normal((RANGE_BINS, VIRT_ANT)))
        rd = np.full((RANGE_BINS, DOPPLER_BINS), noise * 4.0)
        rd *= 1 + 0.3 * self.rng.random(rd.shape)
        points = []

        if not self.clutter_removal:
            for ox, oy, amp, _ in self.static:
                r = np.hypot(ox, oy)
                theta = np.arctan2(ox, oy)
                spread = amp * np.sinc(r_axis - r / RANGE_RES_M)
                x += spread[:, None] * np.exp(1j * np.pi * ant * np.sin(theta))[None, :]
                rd[:, 0] += np.abs(spread) * VIRT_ANT
            # the demo's CFAR would also report the strongest static peaks
            points += [(ox, oy, oz, 0.0) for ox, oy, amp, oz in self.static if amp >= 900]

        ax, ay, v, amp = self._arm()
        r_bin = np.hypot(ax, ay) / RANGE_RES_M
        d_bin = int(round(v / VEL_RES_MS)) % DOPPLER_BINS
        rd[:, d_bin] += np.abs(amp * np.sinc(r_axis - r_bin)) * VIRT_ANT
        if abs(v) > VEL_RES_MS:
            points.append((ax, ay, -0.25 + 0.15 * v, v))

        self.n += 1
        static_payload = np.stack([x.imag, x.real], axis=-1)
        static_payload = np.clip(static_payload, -32768, 32767).astype("<i2").tobytes()
        # like the demo: log2 magnitude in Q8, zero speed in Doppler bin 0
        rd_payload = np.clip(256 * np.log2(rd), 0, 65535).astype("<u2").tobytes()
        pts_payload = b"".join(struct.pack("<ffff", px, py, pz, pv) for px, py, pz, pv in points)
        return encode_frame(self.n, {
            DETECTED_POINTS: pts_payload,
            AZIMUTH_STATIC_HEATMAP: static_payload,
            RANGE_DOPPLER_HEATMAP: rd_payload,
        })
