"""Turn heatmap TLVs into images."""
import numpy as np


def range_azimuth(payload, virt_ant, az_ant=None, angle_bins=64, flip=False,
                  az_index=None, az_cols=None):
    """Azimuth static heatmap -> |angle FFT|, shape [range_bins, angle_bins].

    The payload is, for each range bin, `virt_ant` complex int16 samples stored
    imaginary first. It comes from the zero-Doppler bin, so it holds everything
    that is NOT moving -- empty if the firmware's clutter removal is on.

    az_index/az_cols (from cfg.load) put each azimuth antenna at its real
    position; gaps stay zero. Without them the antennas are assumed evenly spaced.
    """
    iq = np.frombuffer(payload, "<i2").reshape(-1, virt_ant, 2).astype(np.float32)
    x = iq[..., 1] + 1j * iq[..., 0]
    if az_index is not None:
        row = np.zeros((x.shape[0], max(az_cols) + 1), complex)
        row[:, az_cols] = x[:, az_index]
        x = row
    elif az_ant:
        x = x[:, :az_ant]  # e.g. xWR18xx: the first 8 virtual antennas are the azimuth row
    spec = np.fft.fftshift(np.fft.fft(x, angle_bins, axis=1), axes=1)
    mag = np.abs(spec)
    return mag[:, ::-1] if flip else mag


def angles_deg(angle_bins):
    """Angle of each FFT bin for a half-wavelength array (after fftshift)."""
    s = np.arange(-angle_bins // 2, angle_bins // 2) / (angle_bins / 2)
    return np.degrees(np.arcsin(np.clip(s, -1, 1)))


def range_doppler(payload, range_bins):
    """Range-Doppler heatmap -> [range_bins, doppler_bins], zero speed in the middle."""
    rd = np.frombuffer(payload, "<u2").astype(np.float32)
    return np.fft.fftshift(rd.reshape(range_bins, -1), axes=1)


def to_db(mag, floor=1e-3):
    return 20 * np.log10(np.maximum(mag, floor))
