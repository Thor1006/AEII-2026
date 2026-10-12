"""
FMCW radar processing chain + a tiny body simulator (learning sandbox).

Run:   python3 sandbox/fmcw_chain.py
Output: figures in sandbox/out/, numeric checks printed to the terminal.

Only needs numpy + matplotlib. The config below is an EXAMPLE profile chosen to
keep the simulation fast. It is NOT the real AWR1843 config; agree that with the
team before capturing.

Big picture (one radar frame = N_LOOPS x N_TX chirps):

    cube [frames, chirps, antennas, samples]
          |        |        |         '-- range FFT    -> distance
          |        |        '------------ angle FFT    -> direction
          |        '--------------------- Doppler FFT  -> velocity
          '------------------------------ over time    -> micro-Doppler, phase
"""
from pathlib import Path

import numpy as np

# =========================================================================
# 1. Radar config and the numbers that follow from it
# =========================================================================
C = 3e8                 # speed of light [m/s]
FC = 77e9               # chirp start frequency [Hz]
LAM = C / FC            # wavelength [m] (~3.9 mm)
S = 60e12               # chirp slope [Hz/s] (= 60 MHz/us)
FS = 5e6                # ADC sample rate [Hz]
N_S = 128               # ADC samples per chirp
N_TX, N_RX = 3, 4       # antennas
N_LOOPS = 64            # chirps per TX per frame
TC = 60e-6              # chirp period incl. idle time [s]
FRAME_PERIOD = 0.04     # 25 frames per second

T_ADC = N_S / FS                    # sampling time per chirp
B = S * T_ADC                       # bandwidth actually sampled
TC_TX = N_TX * TC                   # time between chirps of the SAME TX (TDM-MIMO)

RANGE_RES = C / (2 * B)
RANGE_MAX = FS * C / (2 * S)
V_MAX = LAM / (4 * TC_TX)
V_RES = LAM / (2 * N_LOOPS * TC_TX)

# What each FFT bin means physically
RANGE_AXIS = np.arange(N_S) * FS / N_S * C / (2 * S)                     # [m]
VEL_AXIS = np.fft.fftshift(np.fft.fftfreq(N_LOOPS, d=TC_TX)) * LAM / 2    # [m/s], + = moving away
N_ANGLE = 64
ANGLE_AXIS = np.degrees(np.arcsin(2 * np.fft.fftshift(np.fft.fftfreq(N_ANGLE))))  # [deg]

# Virtual antenna positions in units of lambda/2: (x = horizontal, z = vertical).
# AWR1843BOOST: TX0 and TX2 are 2*lambda apart horizontally; TX1 sits between
# them, lambda/2 higher. Index = tx * N_RX + rx, assuming chirps fire TX0, TX1, TX2.
# CHECK the order against the real chirp config: it changes which indices form
# the azimuth row.
TX_POS = np.array([[0, 0], [2, 1], [4, 0]])
RX_POS = np.array([[0, 0], [1, 0], [2, 0], [3, 0]])
VIRT_POS = (TX_POS[:, None, :] + RX_POS[None, :, :]).reshape(-1, 2)
AZIMUTH_IDX = [0, 1, 2, 3, 8, 9, 10, 11]    # TX0 + TX2 -> one 8-element horizontal row


# =========================================================================
# 2. Simulator: a person as a handful of point reflectors
# =========================================================================
def body_points(t, *, dist=1.0, arm_x=0.18, forearm=0.28, rom_deg=135.0,
                rep_period=2.5, curl=True, shoulder_lift=0.0,
                trunk_lean_deg=0.0, breath_mm=4.0):
    """Reflector positions at times t.

    Radar at the origin looking along +y; the subject sits facing it at `dist` m
    and curls a dumbbell with the right arm. Coordinates: x right, y away from
    radar, z up (radar height = 0).

    Compensation knobs (both peak at the top of each curl):
      shoulder_lift   [m]    shoulder + arm rise (shoulder elevation)
      trunk_lean_deg  [deg]  upper body rotates backwards about the hip

    Returns pos (T, P, 3) and amp (P,).
    """
    t = np.atleast_1d(t).astype(float)
    g = 0.5 * (1 - np.cos(2 * np.pi * (t % rep_period) / rep_period))   # 0 -> 1 -> 0 each rep
    if not curl:
        g = np.zeros_like(t)
    theta = np.radians(rom_deg) * g                                    # elbow angle, 0 = arm hanging

    T = len(t)
    elbow = np.array([arm_x, dist + 0.03, 0.02])
    fdir = np.stack([np.zeros(T), -np.sin(theta), -np.cos(theta)], axis=1)  # forearm direction

    pts = [
        np.tile([0.0, dist, 0.15], (T, 1)),            # 0 chest (breathes)
        np.tile([0.0, dist + 0.02, -0.10], (T, 1)),    # 1 belly
        np.tile([arm_x, dist + 0.03, 0.30], (T, 1)),   # 2 right shoulder
        np.tile([arm_x, dist, 0.16], (T, 1)),          # 3 upper arm / biceps
        np.tile(elbow, (T, 1)),                        # 4 elbow
        elbow + 0.40 * forearm * fdir,                 # 5 forearm
        elbow + 0.75 * forearm * fdir,                 # 6 forearm
        elbow + 1.00 * forearm * fdir,                 # 7 hand + dumbbell
    ]
    pos = np.stack(pts, axis=1)                                 # (T, P, 3)
    amp = np.array([1.0, 0.8, 0.6, 0.4, 0.4, 0.35, 0.35, 1.2])

    # breathing: chest moves toward/away from the radar
    pos[:, 0, 1] -= breath_mm * 1e-3 * np.sin(2 * np.pi * 0.25 * t)

    # shoulder elevation: shoulder + arm move up
    pos[:, 2:, 2] += shoulder_lift * g[:, None]

    # trunk lean back: rotate everything above the hip about the hip, in the y-z plane
    phi = np.radians(trunk_lean_deg) * g[:, None]
    hy, hz = dist + 0.05, -0.35
    y, z = pos[..., 1] - hy, pos[..., 2] - hz
    pos[..., 1] = hy + y * np.cos(phi) + z * np.sin(phi)
    pos[..., 2] = hz - y * np.sin(phi) + z * np.cos(phi)
    return pos, amp


def simulate(n_frames, *, noise=0.3, single_antenna=False, rng=None, **body):
    """Ideal FMCW beat signal for the body model -> cube [frames, chirps, antennas, samples].

    Each reflector at distance R adds  amp * exp(j * (2*pi * (2*S*R/c) * t_fast + 4*pi*R/lambda + antenna phase)).
    The first term is the beat frequency (-> range); the second is the phase
    (-> velocity, displacement); the third depends on direction (-> angle).
    """
    rng = rng or np.random.default_rng(0)
    t_fast = np.arange(N_S) / FS
    txs = [0] if single_antenna else range(N_TX)
    rxs = [0] if single_antenna else range(N_RX)
    cube = np.zeros((n_frames, N_LOOPS, len(txs) * len(rxs), N_S), np.complex64)

    for f in range(n_frames):
        for ti, tx in enumerate(txs):
            t_chirp = f * FRAME_PERIOD + (np.arange(N_LOOPS) * N_TX + tx) * TC   # TDM: TXs take turns
            pos, amp = body_points(t_chirp, **body)
            R = np.linalg.norm(pos, axis=-1)                          # (L, P)
            u = pos / R[..., None]                                    # unit direction
            beat = 2 * np.pi * (2 * S * R / C)[..., None] * t_fast    # (L, P, N_S)
            for ri, rx in enumerate(rxs):
                v = tx * N_RX + rx
                ant = np.pi * (VIRT_POS[v, 0] * u[..., 0] + VIRT_POS[v, 1] * u[..., 2])
                ph = beat + (4 * np.pi * R / LAM + ant)[..., None]
                cube[f, :, ti * len(rxs) + ri] = (amp[None, :, None] * np.exp(1j * ph)).sum(axis=1)

    cube += noise * (rng.standard_normal(cube.shape) + 1j * rng.standard_normal(cube.shape))
    return cube


# =========================================================================
# 3. Real data loader (DCA1000 .bin) — untested until we have a capture
# =========================================================================
def load_bin(path, n_frames):
    """DCA1000 raw file -> cube [frames, chirps, virtual antennas, samples].

    VERIFY against TI's DCA1000 docs / the mmWave Studio MATLAB read script:
    the [I0 I1 Q0 Q1] interleave depends on LVDS lanes and capture settings.
    If the first range plot looks like noise, this function is the usual culprit.
    """
    raw = np.fromfile(path, dtype=np.int16).reshape(-1, 4)
    iq = np.empty(raw.shape[0] * 2, dtype=np.complex64)
    iq[0::2] = raw[:, 0] + 1j * raw[:, 2]
    iq[1::2] = raw[:, 1] + 1j * raw[:, 3]
    cube = iq.reshape(n_frames, N_LOOPS, N_TX, N_RX, N_S)
    return cube.reshape(n_frames, N_LOOPS, N_TX * N_RX, N_S)


# =========================================================================
# 4. The processing chain
# =========================================================================
def range_fft(cube):
    """FFT over fast time (samples): beat frequency -> distance."""
    x = cube - cube.mean(axis=-1, keepdims=True)                  # DC removal
    return np.fft.fft(x * np.hanning(N_S), axis=-1).astype(np.complex64)


def remove_static(r):
    """Subtract the mean over chirps: anything not moving within a frame disappears."""
    return r - r.mean(axis=1, keepdims=True)


def doppler_fft(r):
    """FFT over slow time (chirps): phase rotation speed -> velocity."""
    win = np.hanning(N_LOOPS)[None, :, None, None]
    return np.fft.fftshift(np.fft.fft(r * win, axis=1), axes=1)


def range_azimuth(r):
    """FFT across the 8-element horizontal antenna row -> angle. Returns (frames, angle, range).

    Note: no TDM motion compensation here (TX0 and TX2 fire at different times),
    so fast-moving targets get slightly smeared in angle.
    """
    win = np.hanning(len(AZIMUTH_IDX) + 2)[1:-1][None, None, :, None]   # tames sidelobes
    a = np.fft.fft(r[:, :, AZIMUTH_IDX, :] * win, n=N_ANGLE, axis=2)
    return np.abs(np.fft.fftshift(a, axes=2)).mean(axis=1)


def ca_cfar(power_db, guard=2, train=6, offset_db=10.0):
    """1-D cell-averaging CFAR: a cell is a detection if it beats the average
    of its neighbours (excluding guard cells) by offset_db."""
    p = 10 ** (power_db / 10)
    k = np.ones(2 * (guard + train) + 1)
    k[train:train + 2 * guard + 1] = 0
    noise = np.convolve(p, k / k.sum(), mode="same")
    return power_db > 10 * np.log10(noise + 1e-12) + offset_db


def micro_doppler(rd, r_lo, r_hi):
    """Velocity-vs-time image: Doppler energy of the chosen range bins, per frame.
    Returns dB array (velocity bins, frames)."""
    bins = (RANGE_AXIS >= r_lo) & (RANGE_AXIS <= r_hi)
    prof = (np.abs(rd[..., bins]) ** 2).sum(axis=(2, 3))         # (frames, doppler)
    return 10 * np.log10(prof.T + 1e-12)


def strongest_velocity(md_db, ignore_slow=1):
    """Per frame, velocity of the strongest moving bin (skipping the zero-velocity bins)."""
    md = md_db.copy()
    mid = N_LOOPS // 2
    md[mid - ignore_slow:mid + ignore_slow + 1] = -np.inf
    return VEL_AXIS[np.argmax(md, axis=0)]


def phase_displacement(r, bin_idx):
    """Sub-mm motion from phase at one range bin, one sample per frame.
    Use the range FFT WITHOUT static removal (breathing is too slow to survive it)."""
    sig = r[:, 0, 0, bin_idx]
    sig = sig - sig.mean()                       # remove static clutter in the bin (circle centre)
    phi = np.unwrap(np.angle(sig))
    d = phi * LAM / (4 * np.pi)
    return d - d.mean()                          # + = moving away


# =========================================================================
# 5. Demo + self-checks
# =========================================================================
def _true_radial_velocity(frames, idx, **body):
    t = np.arange(frames) * FRAME_PERIOD
    dt = 1e-3
    r1 = np.linalg.norm(body_points(t - dt, **body)[0][:, idx], axis=-1)
    r2 = np.linalg.norm(body_points(t + dt, **body)[0][:, idx], axis=-1)
    return (r2 - r1) / (2 * dt)


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(__file__).parent / "out"
    out.mkdir(exist_ok=True)

    print(f"range res {RANGE_RES*100:.1f} cm | max range {RANGE_MAX:.1f} m | "
          f"max vel {V_MAX:.2f} m/s | vel res {V_RES:.3f} m/s | bandwidth {B/1e9:.2f} GHz")

    # --- session A: 3 correct curls ----------------------------------------
    n = int(3 * 2.5 / FRAME_PERIOD)
    r = range_fft(simulate(n))
    rm = remove_static(r)
    rd = doppler_fft(rm)

    # range profile + CFAR (frame 0, raw: shows static body too)
    prof_db = 20 * np.log10(np.abs(r[0]).mean(axis=(0, 1)) + 1e-12)
    keep = RANGE_AXIS < 3.0
    det = ca_cfar(prof_db[keep])
    print("CFAR detections at [m]:", np.round(RANGE_AXIS[keep][det], 2))

    md = micro_doppler(rd, 0.5, 1.5)
    v_est = strongest_velocity(md)
    v_true = _true_radial_velocity(n, 7)                     # hand
    moving = np.abs(v_true) > 0.15
    mae = np.mean(np.abs(v_est[moving] - v_true[moving]))
    print(f"micro-Doppler hand velocity MAE: {mae:.3f} m/s (velocity bin = {V_RES:.3f} m/s)")

    ra = range_azimuth(rm).mean(axis=0)                      # (angle, range)
    peak_frame = int(np.argmax(np.abs(v_true)))
    rd_peak = 20 * np.log10(np.abs(rd[peak_frame]).sum(axis=1) + 1e-12)   # (doppler, range)

    # --- session B: sitting still, breathing -------------------------------
    nb = int(12 / FRAME_PERIOD)
    rb = range_fft(simulate(nb, curl=False))
    chest_bin = int(np.argmin(np.abs(RANGE_AXIS - 1.0)))
    d_est = phase_displacement(rb, chest_bin)
    tb = np.arange(nb) * FRAME_PERIOD
    d_true = -4e-3 * np.sin(2 * np.pi * 0.25 * tb)
    d_true -= d_true.mean()
    corr = np.corrcoef(d_est, d_true)[0, 1]
    print(f"breathing via phase: est p-p {np.ptp(d_est)*1e3:.2f} mm vs true {np.ptp(d_true)*1e3:.2f} mm, "
          f"corr {corr:.3f}")

    # --- session C: curls WITH trunk lean (what the classifier must spot) ---
    rc = doppler_fft(remove_static(range_fft(simulate(n, trunk_lean_deg=10, shoulder_lift=0.0))))
    md_lean = micro_doppler(rc, 0.5, 1.5)

    # --- figure --------------------------------------------------------------
    t = np.arange(n) * FRAME_PERIOD
    fig, ax = plt.subplots(2, 3, figsize=(16, 9))

    a = ax[0, 0]
    a.plot(RANGE_AXIS[keep], prof_db[keep])
    a.plot(RANGE_AXIS[keep][det], prof_db[keep][det], "rx", label="CFAR detection")
    a.set(title="1. Range profile (frame 0)", xlabel="range [m]", ylabel="dB")
    a.legend()

    a = ax[0, 1]
    rk = RANGE_AXIS < 2.0
    a.imshow(rd_peak[:, rk], aspect="auto", origin="lower", vmin=rd_peak.max() - 40,
             extent=[0, RANGE_AXIS[rk][-1], VEL_AXIS[0], VEL_AXIS[-1]])
    a.set(title=f"2. Range-Doppler (t={peak_frame*FRAME_PERIOD:.2f}s, static removed)",
          xlabel="range [m]", ylabel="velocity [m/s]")

    a = ax[0, 2]
    ra_db = 20 * np.log10(ra[:, rk] + 1e-12)
    a.imshow(ra_db, aspect="auto", origin="lower", vmin=ra_db.max() - 30,
             extent=[0, RANGE_AXIS[rk][-1], ANGLE_AXIS[0], ANGLE_AXIS[-1]])
    a.axhline(np.degrees(np.arctan(0.18 / 1.0)), color="w", ls="--", lw=0.8)
    a.set(title="3. Range-azimuth (moving parts; dashed = true arm angle)",
          xlabel="range [m]", ylabel="azimuth [deg]")

    for a, img, title in [(ax[1, 0], md, "4. Micro-Doppler: correct curls"),
                          (ax[1, 2], md_lean, "6. Micro-Doppler: curls + 10 deg trunk lean")]:
        a.imshow(img, aspect="auto", origin="lower", vmin=img.max() - 40,
                 extent=[0, t[-1], VEL_AXIS[0], VEL_AXIS[-1]])
        a.set(title=title, xlabel="time [s]", ylabel="velocity [m/s] (+ = away)", ylim=(-2, 2))
    ax[1, 0].plot(t, v_true, "w--", lw=1, label="true hand velocity")
    ax[1, 0].legend(loc="upper right")

    a = ax[1, 1]
    a.plot(tb, d_true * 1e3, label="true chest motion")
    a.plot(tb, d_est * 1e3, "--", label="from radar phase")
    a.set(title="5. Phase displacement at chest bin", xlabel="time [s]", ylabel="mm")
    a.legend()

    fig.tight_layout()
    fig.savefig(out / "fmcw_chain_demo.png", dpi=110)
    print(f"saved {out / 'fmcw_chain_demo.png'}")


if __name__ == "__main__":
    main()
