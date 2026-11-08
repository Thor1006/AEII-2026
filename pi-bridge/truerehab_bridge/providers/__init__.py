"""Provider registry: config section [providers.<name>] → class."""
from __future__ import annotations

from .base import Provider
from .emg import EmgProvider
from .radar import RadarProvider
from .serial_aux import SerialAuxProvider
from .synthetic import SyntheticProvider

REGISTRY: dict[str, type[Provider]] = {
    "synthetic": SyntheticProvider,
    "serial_aux": SerialAuxProvider,
    "radar": RadarProvider,
    "emg": EmgProvider,
}

__all__ = ["EmgProvider", "Provider", "REGISTRY", "RadarProvider", "SerialAuxProvider", "SyntheticProvider"]
