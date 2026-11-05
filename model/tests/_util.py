"""Shared test helpers: makes `trnet` importable and gives small, fast contracts."""
import sys
import warnings
from pathlib import Path

# radar-lab's cfg.read_lines leaves a file to the garbage collector; harmless, but noisy in test output
warnings.filterwarnings("ignore", category=ResourceWarning)

MODEL_DIR = Path(__file__).resolve().parents[1]
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

from trnet import paths  # noqa: E402
from trnet.contract import InputContract, default_contract  # noqa: E402

REAL_RADAR_SESSION = paths.SESSIONS / "2026-11-04_183625_TEST_radar_check"


def small_contract(**kw):
    """The real profile, but 32 frames per rep so tests run quickly."""
    kw.setdefault("frames_per_rep", 32)
    return default_contract(**kw)


def have_real_sessions():
    return REAL_RADAR_SESSION.exists()
