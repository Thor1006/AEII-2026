"""Provider registry: config section [providers.<name>] → class."""
from __future__ import annotations

from .base import Provider
from .radar import RadarProvider
from .serial_aux import SerialAuxProvider
from .synthetic import SyntheticProvider

REGISTRY: dict[str, type[Provider]] = {
    "synthetic": SyntheticProvider,
    "serial_aux": SerialAuxProvider,
    "radar": RadarProvider,
}

__all__ = ["Provider", "REGISTRY", "RadarProvider", "SerialAuxProvider", "SyntheticProvider"]
