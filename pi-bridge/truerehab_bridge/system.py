"""Small facts about the machine for the status heartbeat and the startup banner."""
from __future__ import annotations

import socket
from pathlib import Path


def cpu_temp_c() -> float | None:
    """Raspberry Pi / Linux CPU temperature, None elsewhere."""
    try:
        return int(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()) / 1000.0
    except (OSError, ValueError):
        return None


def lan_ip() -> str | None:
    """The address other devices on the Wi-Fi use to reach this one. Sends no traffic."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return None


def mdns_name() -> str:
    host = socket.gethostname()
    return host if host.endswith(".local") else f"{host}.local"
