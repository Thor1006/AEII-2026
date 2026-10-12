"""
CNN frame encoder v0.1 (learning sandbox).

One processed radar "frame" -> one fixed-width embedding vector.

    frames:    [B, C, H, W]      -> FrameEncoder         -> [B, E]
    sequences: [B, T, C, H, W]   -> .encode_sequence()   -> [B, T, E]

H and W are whatever 2D view you feed it (range-Doppler, micro-Doppler,
range-time, ...). The encoder does NOT know or care which; that is written
down in an InputContract that travels with the saved weights.
Preprocessing (FFTs, dB, normalisation) stays OUTSIDE this module.

Defaults are guesses, not agreed specs: the real AWR1843 chirp config
will decide H, W and C.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from math import gcd
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

VERSION = "0.1"


# =========================================================================
# 1. Input contract: what the tensor going in MEANS
# =========================================================================
@dataclass
class InputContract:
    """Describes the input tensor. Saved next to the weights so a model is
    never fed data that was preprocessed differently from its training data.

    shape: (C, H, W); use None for a dimension that may vary.
    """
    view: str = "range_doppler"                      # e.g. range_doppler | micro_doppler | range_time
    axes: tuple = ("channel", "range_bin", "doppler_bin")
    shape: tuple = (1, None, None)
    units: str = "log-magnitude dB"
    scaling: str = "per-sample: x - max, clip at -40 dB, then (x + 40) / 40 -> [0, 1]"
    dtype: str = "float32"
    missing_data: str = ("lost packets/frames must be flagged upstream; tensor must be finite "
                         "(no NaN/inf). Never fill gaps with zeros silently. If mask_channel "
                         "is true, the LAST channel is 1 = valid, 0 = missing.")
    mask_channel: bool = False
    notes: str = ""

    def check(self, x: torch.Tensor) -> None:
        """Raise if a [B, C, H, W] tensor does not match this contract."""
        if x.dim() != 4:
            raise ValueError(f"expected [B, C, H, W], got shape {tuple(x.shape)}")
        for name, want, got in zip(("C", "H", "W"), self.shape, x.shape[1:]):
            if want is not None and want != got:
                raise ValueError(f"contract '{self.view}' wants {name}={want}, got {got}")
        if str(x.dtype) != f"torch.{self.dtype}":
            raise ValueError(f"contract wants {self.dtype}, got {x.dtype}")

    @classmethod
    def from_dict(cls, d: dict) -> "InputContract":
        d = dict(d)
        d["axes"], d["shape"] = tuple(d["axes"]), tuple(d["shape"])
        return cls(**d)


# =========================================================================
# 2. Encoder config: the architecture knobs
# =========================================================================
@dataclass
class FrameEncoderConfig:
    in_channels: int = 1
    widths: tuple = (16, 32, 64, 128)        # channels per stage
    blocks_per_stage: int = 1                # conv blocks inside each stage
    norm: str = "group"                      # "group" (default, small batches) | "batch"
    dropout: float = 0.1                     # before the final projection
    embed_dim: int = 128                     # E
    min_size: int = 4                        # never pool an axis below this many bins
    validate_inputs: bool = True             # shape + finite checks in forward (costs a sync on GPU)

    def __post_init__(self):
        self.widths = tuple(self.widths)
        if self.norm not in ("group", "batch"):
            raise ValueError("norm must be 'group' or 'batch'")
        if not self.widths or self.blocks_per_stage < 1 or self.embed_dim < 1:
            raise ValueError("widths, blocks_per_stage and embed_dim must be non-empty/positive")


def _norm(kind: str, ch: int) -> nn.Module:
    if kind == "batch":
        return nn.BatchNorm2d(ch)
    return nn.GroupNorm(gcd(ch, 8), ch)      # up to 8 groups that divide ch


class _ConvBlock(nn.Sequential):
    """3x3 conv -> norm -> ReLU. Padding keeps H, W unchanged."""
    def __init__(self, c_in: int, c_out: int, norm: str):
        super().__init__(
            nn.Conv2d(c_in, c_out, 3, padding=1, bias=False),
            _norm(norm, c_out),
            nn.ReLU(inplace=True),
        )


# =========================================================================
# 3. The encoder
# =========================================================================
class FrameEncoder(nn.Module):
    """Stages of conv blocks. Between stages, each axis is halved by max-pool
    ONLY while it stays >= min_size, so a short axis (e.g. 16 Doppler bins)
    is not pooled away. Then global average pool -> linear -> [B, E]."""

    def __init__(self, cfg: FrameEncoderConfig | None = None,
                 contract: InputContract | None = None):
        super().__init__()
        self.cfg = cfg or FrameEncoderConfig()
        self.contract = contract or InputContract(shape=(self.cfg.in_channels, None, None))
        if self.contract.shape[0] not in (None, self.cfg.in_channels):
            raise ValueError("contract channel count != cfg.in_channels")

        c = self.cfg
        self.stages = nn.ModuleList()
        c_in = c.in_channels
        for w in c.widths:
            blocks = [_ConvBlock(c_in if i == 0 else w, w, c.norm) for i in range(c.blocks_per_stage)]
            self.stages.append(nn.Sequential(*blocks))
            c_in = w
        self.head = nn.Sequential(nn.Dropout(c.dropout), nn.Linear(c.widths[-1], c.embed_dim))

    @property
    def embed_dim(self) -> int:
        return self.cfg.embed_dim

    def _validate(self, x: torch.Tensor) -> None:
        if x.dim() != 4:
            raise ValueError(f"expected [B, C, H, W], got {tuple(x.shape)}; "
                             "use encode_sequence() for [B, T, C, H, W]")
        if x.shape[1] != self.cfg.in_channels:
            raise ValueError(f"expected C={self.cfg.in_channels}, got C={x.shape[1]}")
        h, w = x.shape[-2:]
        if min(h, w) < self.cfg.min_size:
            raise ValueError(f"input {h}x{w} is smaller than min_size={self.cfg.min_size}")
        if not torch.isfinite(x).all():
            raise ValueError("input has NaN/inf; see InputContract.missing_data")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.cfg.validate_inputs:
            self._validate(x)
        for i, stage in enumerate(self.stages):
            if i > 0:                                        # downsample between stages
                kh = 2 if x.shape[-2] >= 2 * self.cfg.min_size else 1
                kw = 2 if x.shape[-1] >= 2 * self.cfg.min_size else 1
                if kh > 1 or kw > 1:
                    x = F.max_pool2d(x, (kh, kw))
            x = stage(x)
        x = x.mean(dim=(-2, -1))                             # global average pool -> [B, widths[-1]]
        return self.head(x)                                  # [B, E]

    def encode_sequence(self, x: torch.Tensor) -> torch.Tensor:
        """[B, T, C, H, W] -> [B, T, E]. Frames are encoded independently
        (same weights); time is handled later by the temporal block."""
        if x.dim() != 5:
            raise ValueError(f"expected [B, T, C, H, W], got {tuple(x.shape)}")
        b, t = x.shape[:2]
        return self(x.reshape(b * t, *x.shape[2:])).reshape(b, t, -1)

    # ---------------------------------------------------------------------
    # Save / load: weights + architecture + input contract together
    # ---------------------------------------------------------------------
    def save(self, directory: str | Path) -> Path:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        torch.save(self.state_dict(), d / "weights.pt")
        (d / "encoder_config.json").write_text(
            json.dumps({"version": VERSION, **asdict(self.cfg)}, indent=2))
        (d / "input_contract.json").write_text(json.dumps(asdict(self.contract), indent=2))
        return d

    @classmethod
    def load(cls, directory: str | Path, *, expected_contract: InputContract | None = None,
             map_location: str = "cpu") -> "FrameEncoder":
        """Rebuild from a saved folder. Refuses if the saved contract differs
        from expected_contract (when given) or the weights don't fit."""
        d = Path(directory)
        cfg_d = json.loads((d / "encoder_config.json").read_text())
        version = cfg_d.pop("version", None)
        if version != VERSION:
            raise ValueError(f"saved encoder is v{version}, this code is v{VERSION}")
        contract = InputContract.from_dict(json.loads((d / "input_contract.json").read_text()))
        if expected_contract is not None and contract != expected_contract:
            raise ValueError(f"input contract mismatch:\n saved:    {contract}\n expected: {expected_contract}")
        model = cls(FrameEncoderConfig(**cfg_d), contract)
        state = torch.load(d / "weights.pt", map_location=map_location, weights_only=True)
        model.load_state_dict(state, strict=True)            # raises if architecture differs
        return model


def count_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
