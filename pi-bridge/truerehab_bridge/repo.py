"""The project folders the bridge borrows code from, read-only: model/ (the network's radar preprocessing and sEMG
maths), radar-lab/ (the radar's frame reader and start sequence) and recorder/ (the session folder format). They sit
next to pi-bridge/ both in a checkout and in the unpacked Pi set."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def use_repo_code() -> None:
    for sub in ("model", "radar-lab", "recorder"):
        path = str(REPO / sub)
        if path not in sys.path:
            sys.path.insert(0, path)
