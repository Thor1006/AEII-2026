"""End to end over a real WebSocket: the bridge on a free port, a viewer connects, gets hello, data and the status
heartbeat, pings, starts a session, sets a marker and stops it; then the bridge is stopped the way SIGTERM stops it
(its task is cancelled) and every provider must get to clean up. The unhashable-viewer bug (2026-11-05: every
connection failed with 1011) went unnoticed because no test connected for real."""
from __future__ import annotations

import asyncio
import json
import socket
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from truerehab_bridge.config import BridgeConfig  # noqa: E402
from truerehab_bridge.protocol import DeviceHealth, ManifestPart  # noqa: E402
from truerehab_bridge.providers import SyntheticProvider  # noqa: E402
from truerehab_bridge.providers.base import Provider  # noqa: E402

try:
    import websockets  # noqa: F401
    HAVE_WS = True
except ImportError:
    HAVE_WS = False


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class CleanupProbe(Provider):
    """Sends nothing; records which hooks ran and whether its run() got to clean up."""
    name = "probe"

    def __init__(self) -> None:
        super().__init__()
        self.events: list[str] = []

    def manifest(self) -> ManifestPart:
        return ManifestPart()

    def health(self) -> dict[str, DeviceHealth]:
        return {"probe": DeviceHealth("ok", "Probe")}

    async def run(self, emit: Any) -> None:
        try:
            await asyncio.sleep(3600)
        finally:
            await asyncio.sleep(0.05)          # cleanup that itself awaits (like stopping the radar)
            self.events.append("cleaned up")

    def on_session_start(self, session: Any) -> None:
        self.events.append("start")

    def on_marker(self, label: str) -> None:
        self.events.append(f"marker {label}")

    def on_session_end(self, session: Any) -> None:
        self.events.append("end")


@unittest.skipUnless(HAVE_WS, "websockets not installed")
class LiveConnection(unittest.TestCase):
    def test_viewer_session_and_clean_stop(self) -> None:
        probe = CleanupProbe()
        asyncio.run(self._run(probe))
        self.assertEqual(probe.events, ["start", "marker halfway", "end", "cleaned up"])

    async def _run(self, probe: CleanupProbe) -> None:
        from truerehab_bridge.server import Bridge
        from websockets.asyncio.client import connect
        port = free_port()
        cfg = BridgeConfig(host="127.0.0.1", ws_port=port, http_port=0, status_interval_ms=200,
                           providers={"synthetic": {"enabled": True}})
        bridge = Bridge(cfg, [SyntheticProvider(fps=20), probe])
        task = asyncio.create_task(bridge.serve_forever())
        for _ in range(50):
            try:
                ws = await connect(f"ws://127.0.0.1:{port}")
                break
            except OSError:
                await asyncio.sleep(0.05)
        else:
            self.fail("bridge never listened")

        async def until(pred, timeout: float = 5.0) -> Any:
            async def loop() -> Any:
                while True:
                    raw = await ws.recv()
                    msg = raw if isinstance(raw, bytes) else json.loads(raw)
                    if pred(msg):
                        return msg
            return await asyncio.wait_for(loop(), timeout)

        async with ws:
            hello = json.loads(await ws.recv())
            self.assertEqual(hello["type"], "hello")
            self.assertEqual(hello["manifest"]["commands"], ["session.start", "session.stop", "marker"])
            await until(lambda m: isinstance(m, bytes))                              # a binary radar frame
            await until(lambda m: isinstance(m, dict) and m.get("type") == "status")
            await ws.send(json.dumps({"type": "ping", "id": 5, "clientT": 1}))
            self.assertEqual((await until(lambda m: isinstance(m, dict) and m.get("type") == "pong"))["id"], 5)
            for cid, name, args in ((1, "session.start", {"exercise": "elbow_flexion", "userId": "S01"}),
                                    (2, "marker", {"label": "halfway"}), (3, "session.stop", {})):
                await ws.send(json.dumps({"type": "command", "id": cid, "name": name, "args": args}))
                ack = await until(lambda m, cid=cid: isinstance(m, dict) and m.get("type") == "ack" and m.get("id") == cid)
                self.assertTrue(ack["ok"], ack)
        task.cancel()                                   # what SIGTERM does now
        await asyncio.gather(task, return_exceptions=True)


if __name__ == "__main__":
    unittest.main()
