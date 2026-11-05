"""What the network's radar input looks like. Saved with the weights; loading refuses a mismatch.

v0-draft, measured 2026-11-05 from the recorder's radar sessions (radar-lab profile fullmap_awr2x44p.cfg):
  - 60.00 fps; 64 range bins x 5.94 cm (3.80 m); 16 Doppler bins x 0.137 m/s
  - static heatmap = 64 range bins x 8 AZIMUTH ANTENNAS (complex int16), not angles. The antennas sit at
    columns 0,2,7,9,3,5,10,12 of a 13-wide row, so angles need a host angle FFT (16 bins ~ the real ~9 deg).
Network input per frame:
  H [C, 64, 16]  angle-FFT magnitude (0..1, 40 dB span) and, if use_phase, the phase change since the
                 previous frame (-1..1 = -pi..pi, 0 where the cell is near the noise floor or after a gap)
  D [1, 64, 16]  range-Doppler magnitude (0..1, 40 dB span), zero speed in the middle column
  mask           1 = real frame, 0 = missing/padded
It becomes v1 only when the real recording profile and protocol are frozen.
"""
import hashlib
import json
import math
import tempfile
import warnings
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from . import paths  # noqa: F401


def _quiet(fn, *args, **kw):
    """Call radar-lab's cfg helpers without their harmless 'unclosed file' ResourceWarning."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        return fn(*args, **kw)


@dataclass(frozen=True)
class InputContract:
    version: str = "v0-draft"
    fps: float = 60.0
    frames_per_rep: int = 128          # T: 2.13 s at 60 fps; longer reps are cropped around their peak
    range_bins: int = 64
    angle_bins: int = 16
    doppler_bins: int = 16
    use_phase: bool = True
    db_span: float = 40.0              # 0..1 covers the top 40 dB below the session's reference level
    baseline_s: float = 5.0            # reference level from the first 5 s (standing still)
    range_res_m: float = 0.0594140625
    vel_res_ms: float = 0.13664786392059117
    az_index: tuple = (0, 1, 2, 3, 4, 5, 6, 7)
    az_cols: tuple = (0, 2, 7, 9, 3, 5, 10, 12)
    cfg_lines: tuple = ()
    notes: str = "v0-draft from radar-lab fullmap_awr2x44p.cfg recordings (2026-11-04); not frozen"

    @property
    def heatmap_channels(self):
        return 2 if self.use_phase else 1

    def shapes(self):
        T = self.frames_per_rep
        return {"H": (T, self.heatmap_channels, self.range_bins, self.angle_bins),
                "D": (T, 1, self.range_bins, self.doppler_bins), "mask": (T,)}

    def to_dict(self):
        d = asdict(self)
        return {k: list(v) if isinstance(v, tuple) else v for k, v in d.items()}

    @classmethod
    def from_dict(cls, d):
        known = {f.name for f in fields(cls)}
        extra = set(d) - known
        if extra:
            raise ValueError(f"unknown contract fields {sorted(extra)} (made by a newer version?)")
        return cls(**{k: tuple(v) if isinstance(v, list) else v for k, v in d.items()})

    INFO_ONLY = ("notes", "cfg_lines")  # kept for the record; the fields derived from them are compared

    def differences(self, other):
        """Fields that change the data, as readable strings (empty list = compatible)."""
        a, b = self.to_dict(), other.to_dict()
        return [f"{k}: {a[k]!r} != {b[k]!r}" for k in a if k not in self.INFO_ONLY and a[k] != b[k]]

    def key(self):
        """Short hash for caches: changes whenever the data would change."""
        d = {k: v for k, v in self.to_dict().items() if k not in self.INFO_ONLY}
        return hashlib.sha1(json.dumps(d, sort_keys=True).encode()).hexdigest()[:10]

    @classmethod
    def from_radar_cfg(cls, cfg_lines, **overrides):
        """Contract for a recorded profile: resolutions, antenna columns and fps from its cfg lines."""
        from radarlab import cfg as radar_cfg
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "profile.cfg"
            p.write_text("\n".join(cfg_lines) + "\n")
            layout = _quiet(radar_cfg.load, p)
        fps = 60.0
        for line in cfg_lines:
            parts = line.split()
            if parts and parts[0] == "frameCfg":
                period_at = 6 if len(parts) == 9 else 5  # same rule as radar-lab's cfg.read_lines
                fps = round(1000.0 / float(parts[period_at]), 2)
        kw = dict(fps=fps, range_res_m=layout.range_res, vel_res_ms=layout.vel_res,
                  doppler_bins=layout.doppler_bins, az_index=tuple(layout.az_index),
                  az_cols=tuple(layout.az_cols), cfg_lines=tuple(cfg_lines))
        kw.update(overrides)
        return cls(**kw)


def default_contract(**overrides):
    """The v0-draft contract for the profile the recorder uses (radar-lab fullmap_awr2x44p.cfg)."""
    from radarlab import cfg as radar_cfg
    lines = _quiet(radar_cfg.read_lines, paths.RADAR_CFG, period_ms=1000 / 60)
    c = InputContract.from_radar_cfg(lines, **overrides)
    if not math.isclose(c.fps, 60.0, rel_tol=1e-3):
        raise ValueError(f"default profile gives {c.fps} fps, expected 60")
    return c
