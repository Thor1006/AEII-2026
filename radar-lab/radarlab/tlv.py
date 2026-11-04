"""TI mmWave demo UART output: frames of [magic | 40-byte header | TLVs | padding].

Layout follows the xWR18xx/68xx SDK 3.x demo. The AWR2944 demo may differ;
run `view.py --dump` on the real board to check the TLV types it sends.
"""
import struct
from dataclasses import dataclass, field

MAGIC = bytes([2, 1, 4, 3, 6, 5, 8, 7])
# magic, version, totalPacketLen, platform, frameNumber, timeCpuCycles,
# numDetectedObj, numTLVs, subFrameNumber
HEADER = struct.Struct("<8sIIIIIIII")
TLV_HEAD = struct.Struct("<II")

DETECTED_POINTS = 1
RANGE_PROFILE = 2
NOISE_PROFILE = 3
AZIMUTH_STATIC_HEATMAP = 4
RANGE_DOPPLER_HEATMAP = 5
STATS = 6

TLV_NAMES = {
    1: "detected points",
    2: "range profile",
    3: "noise profile",
    4: "azimuth static heatmap",
    5: "range-Doppler heatmap",
    6: "stats",
    7: "point side info",
    8: "azimuth/elevation static heatmap",
    9: "temperature",
}

MAX_PACKET = 1 << 20  # anything bigger is a corrupt length field


@dataclass
class Frame:
    number: int
    platform: int
    num_points: int
    tlvs: dict = field(default_factory=dict)  # type -> payload bytes
    raw: bytes = b""  # the whole packet as received, so a recorder can save it unchanged


def encode_frame(number, tlvs, platform=0x2944):
    """Build one frame the way the demo does (used by the simulator and tests)."""
    body = b"".join(TLV_HEAD.pack(t, len(p)) + p for t, p in tlvs.items())
    total = HEADER.size + len(body)
    total += (-total) % 32  # the demo pads frames to 32 bytes
    head = HEADER.pack(MAGIC, 0x03060000, total, platform, number, 0, 0, len(tlvs), 0)
    return (head + body).ljust(total, b"\0")


class FrameReader:
    """Feed it raw bytes in any chunk size; it returns whole frames."""

    def __init__(self):
        self.buf = bytearray()
        self.dropped = 0  # bytes skipped while hunting for the magic word

    def feed(self, data):
        self.buf += data
        frames = []
        while True:
            start = self.buf.find(MAGIC)
            if start < 0:
                keep = len(MAGIC) - 1  # a magic word may be split across reads
                self.dropped += max(0, len(self.buf) - keep)
                del self.buf[: max(0, len(self.buf) - keep)]
                return frames
            if start:
                self.dropped += start
                del self.buf[:start]
            if len(self.buf) < HEADER.size:
                return frames
            _, _, total, platform, number, _, n_obj, n_tlv, _ = HEADER.unpack_from(self.buf)
            if total < HEADER.size or total > MAX_PACKET:
                self.dropped += 1
                del self.buf[:1]
                continue
            if len(self.buf) < total:
                return frames
            frame = self._parse(bytes(self.buf[:total]), number, platform, n_obj, n_tlv)
            del self.buf[:total]
            if frame is None:
                self.dropped += total
            else:
                frames.append(frame)

    @staticmethod
    def _parse(packet, number, platform, n_obj, n_tlv):
        frame = Frame(number, platform, n_obj, raw=packet)
        pos = HEADER.size
        for _ in range(n_tlv):
            if pos + TLV_HEAD.size > len(packet):
                return None
            kind, length = TLV_HEAD.unpack_from(packet, pos)
            pos += TLV_HEAD.size
            if pos + length > len(packet):
                return None
            frame.tlvs[kind] = packet[pos : pos + length]
            pos += length
        return frame
