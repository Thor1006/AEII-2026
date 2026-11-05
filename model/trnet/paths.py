"""Where things live, and access to recorder/ and radar-lab/ code without copying it (read-only reuse)."""
import sys
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[1]
REPO = MODEL_DIR.parent
RECORDER = REPO / "recorder"
RADAR_LAB = REPO / "radar-lab"
SESSIONS = RECORDER / "data" / "sessions"      # real recordings (git-ignored)
RADAR_CFG = RADAR_LAB / "configs" / "fullmap_awr2x44p.cfg"
CALIB = MODEL_DIR / "calib" / "real_stats.json"
DATA = MODEL_DIR / "data"                      # fake sessions, caches (git-ignored)
RUNS = MODEL_DIR / "runs"                      # training runs, session checks (git-ignored)

for _p in (RECORDER, RADAR_LAB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
