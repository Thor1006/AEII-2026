"""
A provider produces data for the bridge. To add a data source (radar capture,
a model, a sensor), subclass Provider, then register it in providers/__init__.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from ..protocol import DeviceHealth, ManifestPart, Message, Session

Emit = Callable[[Message], None]


class Provider(ABC):
    #: Short id used in config ([providers.<name>]) and logs.
    name: str = "provider"
    #: True if the data is made up. The dashboard then shows a "Demo data" banner.
    synthetic: bool = False

    def __init__(self, **options: Any) -> None:
        self.options = options

    @abstractmethod
    def manifest(self) -> ManifestPart:
        """Every stream this provider will send. The dashboard labels itself from this,
        and check_bridge.py fails if an announced stream never arrives."""

    @abstractmethod
    def health(self) -> dict[str, DeviceHealth]:
        """Device states for the status heartbeat, keyed by device id (radar, arduino, model...).
        Use plain language in `message`: it is shown to users ("Not plugged in")."""

    @abstractmethod
    async def run(self, emit: Emit) -> None:
        """Produce messages forever by calling emit(msg). Runs in the bridge's event loop.
        Blocking I/O (serial, UDP capture) belongs in a thread; hand messages back with
        loop.call_soon_threadsafe(emit, msg). If this raises, the bridge marks the
        provider's devices as errors and restarts it after a few seconds."""

    def on_session_start(self, session: Session) -> None:
        """A session started (reset rep counters, open files, ...)."""

    def on_session_end(self, session: Session) -> None:
        """A session ended."""
