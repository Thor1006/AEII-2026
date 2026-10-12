"""
The bridge: runs providers, stamps every message with the envelope, and broadcasts
to every connected dashboard. Each viewer gets `hello` first, then the live stream.
Viewers can send commands (session.start / session.stop / marker) and pings.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from . import __version__
from .auth import Handshake, RateLimiter
from .config import BridgeConfig
from .protocol import (
    PROTOCOL_VERSION,
    PROTOCOL_VERSION_STRING,
    DeviceHealth,
    Event,
    Frame,
    Message,
    Session,
    dumps,
    encode,
    manifest_wire,
    now_ms,
)
from .providers import REGISTRY, Provider
from .system import cpu_temp_c

log = logging.getLogger("truerehab.bridge")

COMMANDS = ["session.start", "session.stop", "marker"]
#: A viewer must answer the key challenge within this many seconds.
AUTH_TIMEOUT_S = 10.0
SESSION_EVENTS = ["session_start", "session_end", "marker"]


@dataclass
class Viewer:
    ws: ServerConnection
    queue: asyncio.Queue[str | bytes]
    dropped: int = 0


@dataclass
class ProviderRun:
    provider: Provider
    error: str | None = None
    task: asyncio.Task[None] | None = None


class Bridge:
    def __init__(self, cfg: BridgeConfig, providers: list[Provider]) -> None:
        self.cfg = cfg
        self.runs = [ProviderRun(p) for p in providers]
        self.viewers: set[Viewer] = set()
        self.session: Session | None = None
        self._seq = 0
        self._frame_times: list[float] = []
        self._parts = [p.manifest() for p in providers]
        self._manifest = manifest_wire(self._parts, COMMANDS, cfg.status_interval_ms)
        self._manifest["events"] = sorted(set(self._manifest["events"]) | set(SESSION_EVENTS))
        key_hex = cfg.resolved_key()
        #: Kit key as bytes, or None for an open kit (anyone on the Wi-Fi can connect).
        self.key: bytes | None = bytes.fromhex(key_hex) if key_hex else None
        self.limiter = RateLimiter()

    @property
    def synthetic(self) -> bool:
        return any(r.provider.synthetic for r in self.runs)

    # ---------- envelope & broadcast ----------

    def _envelope(self, sequenced: bool = True) -> dict[str, Any]:
        env: dict[str, Any] = {"v": PROTOCOL_VERSION, "seq": -1, "t": now_ms(), "src": self.cfg.src, "kitId": self.cfg.kit_id}
        if sequenced:
            env["seq"] = self._seq
            self._seq += 1
        if self.session and self.session.state == "running":
            env["sessionId"] = self.session.id
        return env

    def emit(self, msg: Message) -> None:
        """Called by providers (in the event loop). Encodes once, queues for every viewer."""
        if isinstance(msg, Frame):
            self._frame_times.append(time.monotonic())
        if not self.viewers:
            return  # nobody watching: don't spend sequence numbers or CPU on encoding
        try:
            data = encode(msg, self._envelope(), self.cfg.frame_dtype)
        except (ValueError, TypeError) as exc:
            log.warning("could not encode %s: %s", type(msg).__name__, exc)
            return
        self._broadcast(data)

    def _broadcast(self, data: str | bytes) -> None:
        for v in self.viewers:
            try:
                v.queue.put_nowait(data)
            except asyncio.QueueFull:
                # A slow viewer misses this message; its sequence gap shows up as "lost" on its screen.
                v.dropped += 1

    # ---------- hello & status ----------

    def hello(self) -> dict[str, Any]:
        return {
            **self._envelope(sequenced=False),
            "type": "hello",
            "protocol": PROTOCOL_VERSION_STRING,
            "device": {"name": self.cfg.name, "kitId": self.cfg.kit_id, "bridgeVersion": __version__},
            "synthetic": self.synthetic,
            "auth": "hmac-sha256" if self.key else "none",
            "manifest": self._manifest,
            "session": self.session.wire() if self.session else None,
        }

    def devices(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for r in self.runs:
            try:
                health = r.provider.health()
            except Exception as exc:  # a broken provider must not stop the heartbeat
                health = {r.provider.name: DeviceHealth("error", r.provider.name, f"health() failed: {exc}")}
            for key, h in health.items():
                if r.error:
                    h = DeviceHealth("error", h.label, f"Crashed, restarting: {r.error}")
                out[key] = h.wire()
        return out

    def status(self) -> dict[str, Any]:
        now = time.monotonic()
        self._frame_times = [t for t in self._frame_times if now - t <= 1.0]
        msg: dict[str, Any] = {
            **self._envelope(),
            "type": "status",
            "fps": len(self._frame_times),
            "synthetic": self.synthetic,
            "devices": self.devices(),
            "session": self.session.wire() if self.session else None,
            "clients": len(self.viewers),
        }
        if self.synthetic:
            msg["message"] = "Synthetic demo data, not a measurement"
        temp = cpu_temp_c()
        if temp is not None:
            msg["cpuTempC"] = temp
        return msg

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(self.cfg.status_interval_ms / 1000)
            if self.viewers:
                self._broadcast(dumps(self.status()))

    # ---------- commands ----------

    def handle_command(self, name: str, args: dict[str, Any]) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Returns (ok, error, result). Side effects are broadcast in sequence order."""
        if name == "session.start":
            if self.session and self.session.state == "running":
                return False, "A session is already running", None
            target = args.get("targetReps")
            if target is not None and (not isinstance(target, int) or isinstance(target, bool) or not 1 <= target <= 1000):
                return False, "targetReps must be a whole number from 1 to 1000", None
            self.session = Session(
                id=str(args.get("sessionId") or f"S-{uuid.uuid4().hex[:10]}"),
                state="running",
                exercise=_str_or_none(args.get("exercise")) or "unspecified",
                side=_str_or_none(args.get("side")),
                target_reps=target,
                user_id=_str_or_none(args.get("userId")),
                started_at=now_ms(),
            )
            for r in self.runs:
                r.provider.on_session_start(self.session)
            self.emit(Event("session_start", {"session": self.session.wire()}, "Session started"))
            self._broadcast(dumps(self.status()))
            log.info("session %s started (%s)", self.session.id, self.session.exercise)
            return True, None, {"session": self.session.wire()}

        if name == "session.stop":
            if not self.session or self.session.state != "running":
                return False, "No session is running", None
            ended = self.session
            ended.state = "stopped"
            ended.ended_at = now_ms()
            for r in self.runs:
                r.provider.on_session_end(ended)
            self.emit(Event("session_end", {"session": ended.wire()}, "Session ended"))
            self._broadcast(dumps(self.status()))
            log.info("session %s stopped", ended.id)
            return True, None, {"session": ended.wire()}

        if name == "marker":
            label = _str_or_none(args.get("label")) or "Marker"
            self.emit(Event("marker", {"label": label[:200]}, label[:200]))
            return True, None, None

        return False, f'Unknown command "{name}". This bridge accepts: {", ".join(COMMANDS)}', None

    # ---------- connections ----------

    async def _authenticate(self, ws: ServerConnection, peer: str) -> Handshake | None:
        """Run the key handshake. Returns the passed handshake, or None after closing the connection."""
        assert self.key is not None
        if self.limiter.locked(peer):
            await ws.send(dumps({"type": "autherr", "error": "locked"}))
            await ws.close(4401, "locked")
            log.warning("refused %s: too many wrong keys", peer)
            return None
        hs = Handshake(self.key, self.cfg.kit_id)
        await ws.send(dumps(hs.challenge()))
        try:
            raw = await asyncio.wait_for(ws.recv(), AUTH_TIMEOUT_S)
        except asyncio.TimeoutError:
            await ws.close(4401, "no key sent")
            return None
        proof = None
        if isinstance(raw, str):
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                msg = None
            if isinstance(msg, dict):
                proof = hs.check_auth(msg)
        if proof is None:
            self.limiter.fail(peer)
            log.warning("viewer %s sent a wrong key", peer)
            await ws.send(dumps({"type": "autherr", "error": "wrong-key"}))
            await ws.close(4401, "wrong key")
            return None
        await ws.send(dumps({"type": "authok", "proof": proof}))
        return hs

    async def handler(self, ws: ServerConnection) -> None:
        peer = ws.remote_address[0] if ws.remote_address else "?"
        hs: Handshake | None = None
        if self.key is not None:
            try:
                hs = await self._authenticate(ws, peer)
            except ConnectionClosed:
                return
            if hs is None:
                return
        viewer = Viewer(ws, asyncio.Queue(maxsize=self.cfg.client_queue))
        try:
            await ws.send(dumps(self.hello()))
        except ConnectionClosed:
            return
        self.viewers.add(viewer)
        log.info("viewer connected from %s (%d watching)%s", peer, len(self.viewers), "" if hs is None else ", key accepted")
        sender = asyncio.create_task(self._pump(viewer))
        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    continue
                reply = self._on_text(raw, hs)
                if reply is not None:
                    await ws.send(dumps(reply))
        except ConnectionClosed:
            pass
        finally:
            self.viewers.discard(viewer)
            sender.cancel()
            log.info("viewer %s left (%d watching, %d messages dropped for it)", peer, len(self.viewers), viewer.dropped)

    def _on_text(self, raw: str, hs: Handshake | None = None) -> dict[str, Any] | None:
        """Handle one text message. `hs` is the passed handshake on a protected kit, None on an open one."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(msg, dict):
            return None
        if msg.get("type") == "ping":
            return {"type": "pong", "id": msg.get("id"), "clientT": msg.get("clientT"), "t": now_ms()}
        if msg.get("type") == "command":
            cid = msg.get("id")
            if self.key is not None:
                # Protected kit: only commands signed with this connection's session key count.
                signed = hs.read_command(msg) if hs else None
                if signed is None:
                    return {"type": "ack", "id": cid, "ok": False, "error": "Command not signed correctly"}
                name, args = signed
            else:
                name = msg.get("name")
                args = msg.get("args") or {}
            if not isinstance(name, str) or not isinstance(args, dict):
                return {"type": "ack", "id": cid, "ok": False, "error": "Malformed command"}
            ok, error, result = self.handle_command(name, args)
            reply: dict[str, Any] = {"type": "ack", "id": cid, "ok": ok}
            if error:
                reply["error"] = error
            if result:
                reply["result"] = result
            return reply
        return None

    async def _pump(self, viewer: Viewer) -> None:
        try:
            while True:
                await viewer.ws.send(await viewer.queue.get())
        except ConnectionClosed:
            pass

    # ---------- providers ----------

    async def _supervise(self, run: ProviderRun) -> None:
        while True:
            try:
                await run.provider.run(self.emit)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                run.error = f"{type(exc).__name__}: {exc}"
                log.exception("provider %s crashed; restarting in 5 s", run.provider.name)
                await asyncio.sleep(5)
                run.error = None

    async def serve_forever(self) -> None:
        for r in self.runs:
            r.task = asyncio.create_task(self._supervise(r), name=f"provider:{r.provider.name}")
        heartbeat = asyncio.create_task(self._heartbeat())
        try:
            async with serve(self.handler, self.cfg.host, self.cfg.ws_port, max_size=2**16, ping_interval=20, ping_timeout=20) as server:
                await server.serve_forever()
        finally:
            heartbeat.cancel()
            for r in self.runs:
                if r.task:
                    r.task.cancel()


def build_providers(cfg: BridgeConfig) -> list[Provider]:
    providers: list[Provider] = []
    for name, opts in cfg.providers.items():
        opts = dict(opts)
        if not opts.pop("enabled", False):
            continue
        cls = REGISTRY.get(name)
        if cls is None:
            raise ValueError(f"Unknown provider [providers.{name}]. Known: {', '.join(REGISTRY)}")
        providers.append(cls(**opts))
    if not providers:
        raise ValueError("No providers enabled. Set enabled = true under at least one [providers.*] section.")
    return providers


def _str_or_none(x: Any) -> str | None:
    return x.strip() if isinstance(x, str) and x.strip() else None
