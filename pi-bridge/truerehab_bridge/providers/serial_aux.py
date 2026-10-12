"""
Arduino (sEMG / force) plugged into the Pi over USB → `aux` messages.

The Arduino prints one sample per line, in any of the formats parse_serial_line
accepts (see frontend/samples/arduino_aux.ino). Reading happens in a thread;
unplugging and replugging is handled (the device shows "Not plugged in" meanwhile).

Note: cheap Arduino clones have no unique USB serial number, so with several
serial devices on one Pi, "auto" may pick the wrong one. Set `port` explicitly
(see the multi-kit plan for the ID-handshake fix).
"""
from __future__ import annotations

import asyncio
import glob
import threading
import time
from typing import Any

from ..protocol import Aux, AuxChannel, DeviceHealth, ManifestPart, now_ms, parse_serial_line
from .base import Emit, Provider

DEVICE = "arduino"


class SerialAuxProvider(Provider):
    name = "serial_aux"

    def __init__(
        self,
        port: str = "auto",
        baud: int = 115200,
        columns: list[str] | None = None,
        channels: list[dict[str, Any]] | None = None,
        rate_hz: float | None = None,
        **options: Any,
    ) -> None:
        super().__init__(**options)
        self.port = port
        self.baud = int(baud)
        self.columns = columns or []
        self.channels = channels or [{"key": c, "label": c} for c in self.columns]
        self.rate_hz = rate_hz
        self._state = DeviceHealth("missing", "Arduino (sEMG / force)", "Not plugged in")
        self._last_line = 0.0
        self._stop = threading.Event()

    def manifest(self) -> ManifestPart:
        return ManifestPart(
            aux=[AuxChannel(c["key"], c.get("label", c["key"]), c.get("unit"), c.get("rate_hz", self.rate_hz), DEVICE) for c in self.channels]
        )

    def health(self) -> dict[str, DeviceHealth]:
        if self._state.state == "ok" and time.monotonic() - self._last_line > 3:
            return {DEVICE: DeviceHealth("error", self._state.label, "Plugged in, but sending nothing")}
        return {DEVICE: self._state}

    async def run(self, emit: Emit) -> None:
        loop = asyncio.get_running_loop()
        self._stop.clear()
        try:
            await asyncio.to_thread(self._read_forever, lambda m: loop.call_soon_threadsafe(emit, m))
        finally:
            self._stop.set()

    def _find_port(self) -> str | None:
        if self.port != "auto":
            return self.port
        ports = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*") + glob.glob("/dev/tty.usbmodem*") + glob.glob("/dev/tty.usbserial*"))
        return ports[0] if ports else None

    def _read_forever(self, emit: Emit) -> None:
        import serial  # pyserial; imported here so the bridge runs without it when this provider is off

        label = self._state.label
        while not self._stop.is_set():
            path = self._find_port()
            if not path:
                self._state = DeviceHealth("missing", label, "Not plugged in")
                time.sleep(2)
                continue
            try:
                with serial.Serial(path, self.baud, timeout=1) as ser:
                    self._state = DeviceHealth("ok", label, path)
                    self._last_line = time.monotonic()
                    while not self._stop.is_set():
                        raw = ser.readline()
                        if not raw:
                            continue
                        channels = parse_serial_line(raw.decode("utf-8", "replace"), self.columns)
                        if channels:
                            self._last_line = time.monotonic()
                            emit(Aux(channels, t=now_ms()))
            except (OSError, serial.SerialException) as exc:
                self._state = DeviceHealth("missing" if "No such file" in str(exc) else "error", label, f"Lost the port: {exc}")
                time.sleep(2)
