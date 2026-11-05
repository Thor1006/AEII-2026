"""Radar-only network (untrained, ~239k parameters). Shapes for one batch of B sets with R reps of T frames:

  H [B,R,T,C,64,16]  -> Stem A (conv, pool 2x2, conv) ----\
  D [B,R,T,1,64,16]  -> Stem B (conv, pool 2x2, conv) ----+-> concat [32,32,8] -> CNN trunk -> 128 per frame
  per rep:  128 x T  -> 3 dilated Conv1d (sees ~0.9 s) -> masked attention pooling -> + (duration, rest before)
            -> rep vector v_r [64]
  baseline: v_base = mean of the session's first 3 reps (passed in as `base_*`, encoded by the same layers)
  per set:  [v_r, v_r - v_base] -> causal GRU over reps -> heads: fatigue, quality, 3 compensation flags,
            next-rep risk (logits) + training-only extra head from v_r (ROM, shoulder rise, trunk lean, MDF ratio)

Nothing mixes information across the batch (GroupNorm/LayerNorm only), across time inside a frame,
or from later reps into earlier ones (the GRU runs forward only), so the same model can run live.
"""
from math import gcd

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.utils.checkpoint

from .contract import InputContract

HEADS = ("fatigue", "quality", "comp_shrug", "comp_lean", "comp_rom", "risk")
AUX = ("rom", "shoulder_rise", "trunk_lean", "mdf_ratio")
REP_FEATURES = ("duration_s", "rest_before_s")


def _gn(ch):
    return nn.GroupNorm(gcd(ch, 8), ch)


class ConvBlock(nn.Sequential):
    """3x3 conv -> GroupNorm -> ReLU; keeps the size (same blocks as sandbox/Encoder_0.1)."""

    def __init__(self, c_in, c_out):
        super().__init__(nn.Conv2d(c_in, c_out, 3, padding=1, bias=False), _gn(c_out), nn.ReLU(inplace=True))


class Stem(nn.Module):
    """[C, 64, 16] -> [16, 32, 8]."""

    def __init__(self, c_in, width=16):
        super().__init__()
        self.c1 = ConvBlock(c_in, width)
        self.c2 = ConvBlock(width, width)

    def forward(self, x):
        return self.c2(F.max_pool2d(self.c1(x), 2))


class ChannelNorm(nn.Module):
    """LayerNorm over channels at each time step of [N, C, T]; never mixes time steps (padding can't leak)."""

    def __init__(self, ch):
        super().__init__()
        self.ln = nn.LayerNorm(ch)

    def forward(self, x):
        return self.ln(x.transpose(1, 2)).transpose(1, 2)


class TrueRehabNet(nn.Module):
    def __init__(self, contract: InputContract | None = None, embed=128, rep_dim=64, hidden=64,
                 dilations=(1, 3, 9), dropout=0.1):
        super().__init__()
        self.contract = contract or InputContract()
        c = self.contract
        if (c.range_bins, c.angle_bins, c.doppler_bins) != (64, 16, 16):
            raise ValueError("this layout expects 64 range x 16 angle/Doppler bins (see InputContract)")
        self.stem_a = Stem(c.heatmap_channels)
        self.stem_b = Stem(1)
        self.t1 = ConvBlock(32, 48)   # [48,32,8] -> pool 2x2
        self.t2 = ConvBlock(48, 64)   # [64,16,4] -> pool (2,1)
        self.t3 = ConvBlock(64, 96)   # [96,8,4]  -> global average pool
        self.drop = nn.Dropout(dropout)
        self.proj = nn.Linear(96, embed)
        d1, d2, d3 = dilations
        self.r1 = nn.Conv1d(embed, rep_dim, 5, padding=2 * d1, dilation=d1)
        self.r2 = nn.Conv1d(rep_dim, rep_dim, 5, padding=2 * d2, dilation=d2)
        self.r3 = nn.Conv1d(rep_dim, rep_dim, 5, padding=2 * d3, dilation=d3)
        self.n1, self.n2, self.n3 = ChannelNorm(rep_dim), ChannelNorm(rep_dim), ChannelNorm(rep_dim)
        self.attn = nn.Linear(rep_dim, 1)
        self.rep_out = nn.Linear(rep_dim + len(REP_FEATURES), rep_dim)
        self.gru = nn.GRU(2 * rep_dim, hidden, batch_first=True)
        self.heads = nn.Linear(hidden, len(HEADS))
        self.aux = nn.Linear(rep_dim, len(AUX))
        self.frame_chunk = None  # set e.g. 2048 to encode frames in chunks (with checkpointing when training)

    # ------------------------------------------------------------------ per frame
    def _frames(self, H, D):
        x = torch.cat([self.stem_a(H), self.stem_b(D)], 1)
        x = F.max_pool2d(self.t1(x), 2)
        x = F.max_pool2d(self.t2(x), (2, 1))
        x = self.t3(x)
        return self.proj(self.drop(x.mean(dim=(-2, -1))))

    def encode_frames(self, H, D):
        """H [N,C,64,16], D [N,1,64,16] -> [N,128]."""
        n = self.frame_chunk
        if not n or H.shape[0] <= n:
            return self._frames(H, D)
        parts = []
        for i in range(0, H.shape[0], n):
            h, d = H[i:i + n], D[i:i + n]
            if self.training and torch.is_grad_enabled():
                parts.append(torch.utils.checkpoint.checkpoint(self._frames, h, d, use_reentrant=False))
            else:
                parts.append(self._frames(h, d))
        return torch.cat(parts)

    # ------------------------------------------------------------------ per rep
    def encode_reps(self, H, D, fmask, feats):
        """H [B,R,T,C,64,16], D [B,R,T,1,64,16], fmask [B,R,T], feats [B,R,2] -> v [B,R,64], frames [B,R,T,128]."""
        B, R, T = fmask.shape
        e = self.encode_frames(H.reshape(B * R * T, *H.shape[3:]), D.reshape(B * R * T, *D.shape[3:]))
        e = e.reshape(B * R, T, -1)
        m = fmask.reshape(B * R, 1, T).to(e.dtype)
        x = e.transpose(1, 2) * m                        # masked frames carry nothing, whatever they contain
        x = F.relu(self.n1(self.r1(x))) * m
        x = x + F.relu(self.n2(self.r2(x))) * m
        x = x + F.relu(self.n3(self.r3(x))) * m
        z = x.transpose(1, 2)                            # [BR, T, 64]
        valid = m.squeeze(1) > 0
        any_valid = valid.any(1, keepdim=True)
        s = self.attn(z).squeeze(-1).masked_fill(~valid, float("-inf"))
        s = torch.where(any_valid, s, torch.zeros_like(s))
        w = torch.softmax(s, 1) * any_valid              # empty (padded) reps pool to 0
        pooled = (w.unsqueeze(-1) * z).sum(1)
        v = self.rep_out(torch.cat([pooled, feats.reshape(B * R, -1).to(pooled.dtype)], -1))
        return v.reshape(B, R, -1)

    # ------------------------------------------------------------------ per set
    def forward(self, batch):
        """batch: H, D, fmask, feats, rmask (the set) and base_H, base_D, base_fmask, base_feats, base_rmask
        (the session's first reps). Returns logits {head: [B,R]} and "aux" [B,R,4]."""
        v = self.encode_reps(batch["H"], batch["D"], batch["fmask"], batch["feats"])
        vb = self.encode_reps(batch["base_H"], batch["base_D"], batch["base_fmask"], batch["base_feats"])
        bm = batch["base_rmask"].unsqueeze(-1).to(v.dtype)
        v_base = (vb * bm).sum(1) / bm.sum(1).clamp(min=1.0)
        h, _ = self.gru(torch.cat([v, v - v_base[:, None]], -1))
        out = self.heads(h)
        res = {name: out[..., k] for k, name in enumerate(HEADS)}
        res["aux"] = self.aux(v)
        return res

    @torch.no_grad()
    def predict(self, batch):
        """Scores 0..1 for every head (sigmoid of the logits)."""
        was = self.training
        self.eval()
        out = self.forward(batch)
        self.train(was)
        return {k: (v if k == "aux" else torch.sigmoid(v)) for k, v in out.items()}

    # ------------------------------------------------------------------ files
    def save(self, path, extra=None):
        torch.save({"state": self.state_dict(), "contract": self.contract.to_dict(),
                    "format": "trnet/1", "extra": extra or {}}, path)

    @classmethod
    def load(cls, path, expected_contract: InputContract | None = None, map_location="cpu"):
        ckpt = torch.load(path, map_location=map_location, weights_only=True)
        contract = InputContract.from_dict(ckpt["contract"])
        if expected_contract is not None:
            diff = contract.differences(expected_contract)
            if diff:
                raise ValueError("weights were trained on different radar input: " + "; ".join(diff))
        net = cls(contract)
        net.load_state_dict(ckpt["state"])
        return net


def count_params(model):
    return sum(p.numel() for p in model.parameters())


def fake_batch(contract: InputContract, B=2, R=4, T=None, n_base=3, seed=0):
    """Random tensors of the right shapes (plumbing tests only)."""
    g = torch.Generator().manual_seed(seed)
    T = T or contract.frames_per_rep
    C = contract.heatmap_channels

    def part(r):
        return {"H": torch.rand(B, r, T, C, 64, 16, generator=g), "D": torch.rand(B, r, T, 1, 64, 16, generator=g),
                "fmask": torch.ones(B, r, T), "feats": torch.rand(B, r, 2, generator=g), "rmask": torch.ones(B, r)}
    batch = part(R)
    batch.update({"base_" + k: v for k, v in part(n_base).items()})
    return batch
