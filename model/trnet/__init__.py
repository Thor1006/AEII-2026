"""TrueRehab-RF radar-only network and its data pipeline (untrained; see model/README.md).

Everything here runs without sensors. Results on fake data only show that the code works,
never that the model works on real radar.
"""
from . import paths  # noqa: F401  (makes recorder/ and radar-lab/ importable)

__version__ = "0.1.0"
