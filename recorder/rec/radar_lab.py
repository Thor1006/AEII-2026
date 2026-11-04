"""Use radar-lab's frame reader and radar control from here, without copying them."""
import sys
from pathlib import Path

RADAR_LAB = Path(__file__).resolve().parents[2] / "radar-lab"
if str(RADAR_LAB) not in sys.path:
    sys.path.insert(0, str(RADAR_LAB))

from radarlab import cfg, sim  # noqa: E402,F401
from radarlab.tlv import FrameReader  # noqa: E402,F401
from view import cli_send, open_serial, send_cfg, stop_radar  # noqa: E402,F401

DEFAULT_CFG = RADAR_LAB / "configs" / "fullmap_awr2x44p.cfg"
