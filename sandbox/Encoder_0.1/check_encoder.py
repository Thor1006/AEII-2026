"""
Sanity checks for FrameEncoder v0.1. All inputs are RANDOM synthetic tensors:
these checks prove the plumbing works, NOT that it learns radar features.

Run:   python3 sandbox/Encoder_0.1/check_encoder.py
"""
import tempfile
import time

import torch
import torch.nn as nn

from frame_encoder import FrameEncoder, FrameEncoderConfig, InputContract, count_params

torch.manual_seed(0)
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


cfg = FrameEncoderConfig()
enc = FrameEncoder(cfg)
E = cfg.embed_dim

# 1. shapes for several input sizes ------------------------------------------
for h, w in [(64, 32), (128, 64), (112, 48), (76, 48), (16, 8)]:
    out = enc.eval()(torch.rand(3, 1, h, w))
    check(f"shape {h}x{w} -> [3, {E}]", tuple(out.shape) == (3, E))
check("too-small input is rejected", raises(lambda: enc(torch.rand(2, 1, 3, 32))))
check("wrong channel count is rejected", raises(lambda: enc(torch.rand(2, 2, 64, 32))))
check("NaN input is rejected", raises(lambda: enc(torch.full((1, 1, 64, 32), float("nan")))))

# 2. encode_sequence == frame-by-frame -----------------------------------------
enc.eval()
seq = torch.rand(2, 5, 1, 64, 32)
with torch.no_grad():
    a = enc.encode_sequence(seq)
    b = torch.stack([enc(seq[:, t]) for t in range(seq.shape[1])], dim=1)
check("encode_sequence shape [2, 5, E]", tuple(a.shape) == (2, 5, E))
check("encode_sequence matches per-frame loop", torch.allclose(a, b, atol=1e-5),
      f"max diff {(a - b).abs().max():.1e}")

# 3. finite outputs + every parameter gets a gradient -------------------------
enc.train()
out = enc(torch.rand(4, 1, 64, 32))
check("outputs finite", torch.isfinite(out).all().item())
out.pow(2).mean().backward()
no_grad = [n for n, p in enc.named_parameters() if p.grad is None or p.grad.abs().sum() == 0]
check("all parameters receive non-zero gradients", not no_grad, ", ".join(no_grad[:5]))
enc.zero_grad()

# 4. size: parameters + activation memory -------------------------------------
act_bytes = 0
def hook(_m, _i, o):
    global act_bytes
    act_bytes += o.numel() * o.element_size()
hooks = [m.register_forward_hook(hook) for m in enc.modules() if isinstance(m, (nn.Conv2d, nn.GroupNorm, nn.BatchNorm2d))]
with torch.no_grad():
    enc.eval()(torch.rand(32, 1, 128, 64))
for hk in hooks:
    hk.remove()
n_params = count_params(enc)
print(f"       parameters: {n_params:,} ({n_params * 4 / 1e6:.2f} MB fp32)")
print(f"       activations (conv+norm outputs, batch 32 of 128x64): ~{act_bytes / 1e6:.0f} MB")

# 5. CPU vs MPS ------------------------------------------------------------------
def timed(model, x, device, reps=10):
    model, x = model.to(device), x.to(device)
    sync = torch.mps.synchronize if device == "mps" else (lambda: None)
    model.train()
    for _ in range(2):                                  # warm-up
        model(x).sum().backward()
    sync()
    t0 = time.perf_counter()
    for _ in range(reps):
        model.zero_grad()
        model(x).sum().backward()
    sync()
    return (time.perf_counter() - t0) / reps * 1e3

x = torch.rand(32, 1, 128, 64)
print(f"       CPU fwd+bwd (batch 32, 128x64): {timed(enc, x, 'cpu'):.1f} ms")
if torch.backends.mps.is_available():
    enc_cpu = enc.cpu().eval()
    with torch.no_grad():
        ref = enc_cpu(x)
    enc_mps = FrameEncoder(cfg).eval()
    enc_mps.load_state_dict(enc_cpu.state_dict())
    enc_mps = enc_mps.to("mps")
    with torch.no_grad():
        got = enc_mps(x.to("mps")).cpu()
    check("CPU and MPS outputs match", torch.allclose(ref, got, atol=1e-3),
          f"max diff {(ref - got).abs().max():.1e}")
    print(f"       MPS fwd+bwd (batch 32, 128x64): {timed(enc_mps, x, 'mps'):.1f} ms")
    enc = enc_cpu
else:
    print("       MPS not available, skipped")

# 6. can it overfit a tiny batch? (learning sanity check) ----------------------
torch.manual_seed(0)
model = nn.Sequential(FrameEncoder(FrameEncoderConfig(dropout=0.0)), nn.Linear(E, 3))
xs, ys = torch.rand(8, 1, 64, 32), torch.randint(0, 3, (8,))
opt = torch.optim.AdamW(model.parameters(), lr=3e-3)
for _ in range(200):
    opt.zero_grad()
    loss = nn.functional.cross_entropy(model(xs), ys)
    loss.backward()
    opt.step()
check("overfits 8 random samples", loss.item() < 0.05, f"final loss {loss.item():.4f}")

# 7. save / load round trip + mismatch refusal ---------------------------------
contract = InputContract(view="range_doppler", shape=(1, 64, 32))
enc = FrameEncoder(cfg, contract).eval()
x = torch.rand(2, 1, 64, 32)
with tempfile.TemporaryDirectory() as d:
    enc.save(d)
    loaded = FrameEncoder.load(d, expected_contract=contract).eval()
    with torch.no_grad():
        check("save -> load gives identical outputs", torch.equal(enc(x), loaded(x)))
    other = InputContract(view="micro_doppler", shape=(1, 64, 48))
    check("load refuses a different input contract",
          raises(lambda: FrameEncoder.load(d, expected_contract=other)))
check("contract.check rejects wrong H", raises(lambda: contract.check(torch.rand(1, 1, 60, 32))))

print(f"\n{sum(results)}/{len(results)} checks passed")
raise SystemExit(0 if all(results) else 1)
