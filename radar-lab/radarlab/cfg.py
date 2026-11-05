"""Read what the viewer needs from a demo config: antenna layout and axis scales."""
import math
from dataclasses import dataclass

C = 3e8


@dataclass
class Layout:
    n_virt: int          # virtual antennas, in the order the static heatmap sends them
    az_index: list       # which of them sit on the azimuth row
    az_cols: list        # their position along that row, in half-wavelengths
    range_res: float     # metres per range bin
    vel_res: float       # m/s per Doppler bin
    doppler_bins: int


def read_lines(path, period_ms=None, num_frames=None):
    """The config's command lines (comments dropped), optionally with a new frame period / count."""
    out = []
    with open(path) as f:  # closed right away (a bare open().read() left it to the garbage collector)
        text = f.read()
    for raw in text.splitlines():
        parts = raw.split("%")[0].split()
        if not parts:
            continue
        if parts[0] == "frameCfg":
            # AWR2944 demo: start end loops numFrames numAdcSamples period trigger delay (8 args);
            # older demos have no numAdcSamples (7 args)
            period_at = 6 if len(parts) == 9 else 5
            if num_frames is not None:
                parts[4] = str(num_frames)
            if period_ms:
                parts[period_at] = f"{period_ms:g}"
        out.append(" ".join(parts))
    return out


def load(path):
    cmds, chirps = {}, []
    for line in read_lines(path):
        parts = line.split()
        name, args = parts[0], [float(a) for a in parts[1:]]
        if name == "chirpCfg":
            chirps.append(args)
        else:
            cmds[name] = args

    rx = [i for i in range(4) if int(cmds["channelCfg"][0]) >> i & 1]
    first, last, loops = (int(v) for v in cmds["frameCfg"][:3])  # numFrames etc. not needed here
    tx_order = []  # TX number of each chirp in one loop
    for c in sorted(chirps):
        for idx in range(int(c[0]), int(c[1]) + 1):
            if first <= idx <= last:
                tx_order.append(int(c[7]).bit_length() - 1)  # txEnable 1/2/4/8 -> TX0..TX3

    # antGeometryCfg: (row, col) for TX0 RX0..RX3, TX1 RX0..RX3, ...; then x and z spacing in wavelengths
    geo = cmds["antGeometryCfg"]
    pairs = [(int(geo[i]), int(geo[i + 1])) for i in range(0, len(geo) - 2, 2)]
    if geo[-2] != 0.5:
        raise ValueError(f"antGeometryCfg x spacing {geo[-2]} λ: radar-lab assumes 0.5 λ")
    virt = [pairs[tx * 4 + r] for tx in tx_order for r in rx]
    rows = [row for row, _ in virt]
    az_row = max(set(rows), key=rows.count)
    az_index = [k for k, (row, _) in enumerate(virt) if row == az_row]
    cols = [virt[k][1] for k in az_index]
    az_cols = [c - min(cols) for c in cols]

    # profileCfg: id, startFreq GHz, idle us, adcStart us, rampEnd us, ..., slope MHz/us, txStart, nAdc, fs ksps
    p = cmds["profileCfg"]
    start_ghz, idle_us, ramp_us, slope, n_adc, fs_ksps = p[1], p[2], p[4], p[7], p[9], p[10]
    n_fft = 2 ** math.ceil(math.log2(n_adc))
    range_res = C * fs_ksps * 1e3 / (2 * slope * 1e12 * n_fft)
    doppler_bins = 2 ** math.ceil(math.log2(loops))
    wavelength = C / (start_ghz * 1e9)
    vel_res = wavelength / (2 * doppler_bins * (idle_us + ramp_us) * 1e-6 * len(tx_order))
    return Layout(len(virt), az_index, az_cols, range_res, vel_res, doppler_bins)
