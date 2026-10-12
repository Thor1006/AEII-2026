"""Bridge settings from a TOML file (see config.example.toml). Every value has a default."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_WEB_ROOT = PACKAGE_DIR.parents[1] / "frontend" / "dist"


@dataclass
class BridgeConfig:
    name: str = "TrueRehab kit"
    kit_id: str = "KIT-00"
    src: str = "pi5-bridge"
    host: str = "0.0.0.0"
    ws_port: int = 8765
    #: Serves the built dashboard so people only open http://<pi>:8080. 0 disables.
    http_port: int = 8080
    web_root: Path = DEFAULT_WEB_ROOT
    status_interval_ms: int = 1000
    #: Messages buffered per viewer before dropping (a slow phone shouldn't slow the Pi).
    client_queue: int = 120
    frame_dtype: str = "f32"
    #: [providers.<name>] tables, only those with enabled = true are started.
    providers: dict[str, dict[str, Any]] = field(default_factory=lambda: {"synthetic": {"enabled": True}})


def load_config(path: str | Path | None) -> BridgeConfig:
    if path is None:
        return BridgeConfig()
    path = Path(path)
    with path.open("rb") as f:
        raw = tomllib.load(f)
    b = raw.get("bridge", {})
    cfg = BridgeConfig()
    for key in ("name", "kit_id", "src", "host", "ws_port", "http_port", "status_interval_ms", "client_queue", "frame_dtype"):
        if key in b:
            setattr(cfg, key, type(getattr(cfg, key))(b[key]))
    if "web_root" in b:
        root = Path(b["web_root"])
        cfg.web_root = root if root.is_absolute() else (path.parent / root).resolve()
    if "providers" in raw:
        cfg.providers = raw["providers"]
    if cfg.frame_dtype not in ("f32", "u16", "u8"):
        raise ValueError(f"frame_dtype must be f32, u16 or u8, not {cfg.frame_dtype!r}")
    return cfg
