"""
One recording per Start/Stop in the dashboard, shared by every provider that saves data (radar, sEMG): one session
folder in the recorder's format (recorder/rec/session.py) with every row on one clock, so model/check_session.py and
model/export_dashboard.py read it unchanged.

  meta.json, markers.csv          written here (the bridge's markers go in as key "x")
  radar.bin, radar_index.csv      the radar provider
  emg.csv                         the sEMG provider
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .protocol import Session
from .repo import use_repo_code


class Recording:
    def __init__(self, root: str | Path, session: Session) -> None:
        use_repo_code()
        from rec import session as S
        subject = session.user_id if session.user_id and S.SUBJECT_RE.match(session.user_id) else "KIT"
        exercise = (session.exercise or "").strip().replace(" ", "_")
        exercise = exercise if S.EXERCISE_RE.match(exercise) else "session"
        self.session_id = session.id
        self._writer = S.SessionWriter(Path(root).expanduser(), subject, exercise,
                                       notes=f"recorded by the Pi bridge, session {session.id}")

    @property
    def dir(self) -> Path:
        return self._writer.dir

    def t(self) -> int:
        """Nanoseconds since the recording started, on the shared monotonic clock. Safe from any thread."""
        return self._writer.t()

    def add_source(self, name: str, info: dict[str, Any]) -> None:
        """Describe a sensor in meta.json (call from the event loop, once per recording)."""
        self._writer.add_source(name, info)

    def marker(self, label: str) -> None:
        self._writer.marker("x", label)

    def close(self, summary: dict[str, Any]) -> None:
        self._writer.close({**summary, "bridge_session": self.session_id})
