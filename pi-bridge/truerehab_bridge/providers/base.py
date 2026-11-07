"""
A provider produces data for the bridge. To add a data source (radar capture,
a model, a sensor), subclass Provider, then register it in providers/__init__.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

from ..protocol import DeviceHealth, ManifestPart, Message, Session

if TYPE_CHECKING:
    from ..recording import Recording

Emit = Callable[[Message], None]


class Provider(ABC):
    #: Short id used in config ([providers.<name>]) and logs.
    name: str = "provider"
    #: True if the data is made up. The dashboard then shows a "Demo data" banner.
    synthetic: bool = False
    #: True if this provider saves its data when the dashboard records (Start/Stop): see on_recording_start.
    records: bool = False

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

    def on_marker(self, label: str) -> None:
        """Someone set a marker in the dashboard (the bridge already saves it in an open recording)."""

    def on_recording_start(self, rec: Recording) -> None:
        """Start in the dashboard opened a recording (only called when `records` is True): one session folder for
        every provider, in the recorder's format. Write your files into rec.dir, stamp rows with rec.t()
        (nanoseconds on the shared clock; safe from any thread) and describe your source once with
        rec.add_source(name, info)."""

    def on_recording_end(self) -> dict[str, Any]:
        """Stop in the dashboard, or the bridge stopping: stop writing and close your files. Return
        {source name: summary} for meta.json, e.g. {"radar": {"frames": 1234, ...}}."""
        return {}
