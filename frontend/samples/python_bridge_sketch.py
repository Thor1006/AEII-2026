"""
Sketch of the Raspberry Pi bridge side (NOT a working radar pipeline).
Shows how to send protocol v1 messages from Python. Replace `get_range_doppler()`
with the real DCA1000 capture + FFT code.

    pip install websockets numpy
    python python_bridge_sketch.py
"""
import asyncio
import json
import struct
import time

import numpy as np
import websockets

PROTOCOL_VERSION = 1
seq = 0


def envelope(msg_type: str, **fields) -> dict:
    global seq
    seq += 1
    return {"v": PROTOCOL_VERSION, "seq": seq, "t": time.time() * 1000, "src": "pi5-radar", "type": msg_type, **fields}


def encode_frame(view: str, arr: np.ndarray, **fields) -> bytes:
    """TRF1 binary frame: magic, uint32 header length, JSON header, pad to 4, float32 LE row-major."""
    header = json.dumps(envelope("frame", view=view, shape=list(arr.shape), dtype="f32", **fields)).encode()
    pad = (-(8 + len(header))) % 4
    return b"TRF1" + struct.pack("<I", len(header)) + header + b"\0" * pad + arr.astype("<f4").tobytes()


def get_range_doppler() -> np.ndarray:
    return (np.random.rand(64, 64) * -40).astype(np.float32)  # placeholder


async def handler(ws):
    async def reader():
        async for raw in ws:  # answer pings so the dashboard can show round-trip time
            msg = json.loads(raw)
            if msg.get("type") == "ping":
                await ws.send(json.dumps({"type": "pong", "id": msg["id"], "clientT": msg["clientT"]}))

    asyncio.create_task(reader())
    while True:
        await ws.send(encode_frame("range_doppler", get_range_doppler(), unit="dB"))
        await ws.send(json.dumps(envelope("scores", scores={"fatigue": 0.3, "quality": 0.8, "compensation": 0.1})))
        await asyncio.sleep(0.05)


async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
