"""Audio stem vs full mix detector."""

import numpy as np
from scipy import ndimage, signal


def detect_stem(x: np.ndarray, sr: int) -> str:
    """Detect whether audio is a drum stem, full mix, or unknown.

    Parameters
    ----------
    x : np.ndarray
        Audio signal (1D mono or 2D multichannel).
    sr : int
        Sample rate in Hz.

    Returns
    -------
    str
        'stem', 'full', or 'unknown'.
    """
    if x is None or len(x) == 0:
        return "unknown"

    audio = np.asarray(x, dtype=np.float64)

    # Downmix to mono if multi-channel
    if audio.ndim > 1:
        audio = np.mean(audio, axis=-1)

    if audio.size == 0:
        return "unknown"

    # Silence or near-silence threshold
    rms = np.sqrt(np.mean(audio**2))
    peak = np.max(np.abs(audio))
    if rms < 1e-4 or peak < 1e-4:
        return "unknown"

    # Minimum duration check (at least 0.2s and at least 1024 samples)
    min_samples = 1024
    if len(audio) < min_samples or (len(audio) / sr) < 0.2:
        return "unknown"

    # Compute Short-Time Fourier Transform (STFT)
    nperseg = min(2048, len(audio))
    hop = nperseg // 4
    _, _, z = signal.stft(audio, fs=sr, nperseg=nperseg, noverlap=nperseg - hop)
    magnitude = np.abs(z)

    if magnitude.shape[1] < 5:
        return "unknown"

    # Median filtering:
    # Harmonic component: median filter across time frames (horizontal)
    # Percussive component: median filter across frequency bins (vertical)
    k_t = min(15, max(3, (magnitude.shape[1] // 2) * 2 + 1))
    k_f = min(15, max(3, (magnitude.shape[0] // 2) * 2 + 1))

    h_med = ndimage.median_filter(magnitude, size=(1, k_t))
    p_med = ndimage.median_filter(magnitude, size=(k_f, 1))

    eps = 1e-10
    # Soft masks for harmonic and percussive separation
    mask_h = (h_med**2) / (h_med**2 + p_med**2 + eps)
    mask_p = (p_med**2) / (h_med**2 + p_med**2 + eps)

    e_harmonic = np.sum((magnitude * mask_h) ** 2)
    e_total = np.sum(magnitude**2) + eps

    harmonic_ratio = e_harmonic / e_total

    # Spectral flux: measure onset/transient burstiness
    diff = np.diff(magnitude, axis=1)
    flux = np.sum(np.maximum(0, diff), axis=0)
    flux_peak_ratio = (np.max(flux) / (np.mean(flux) + eps)) if len(flux) > 0 else 0.0

    # Persistence of sustained tonal peaks across consecutive time frames
    # Drum hits decay rapidly or sweep down; sustained musical notes hold frequency
    peak_mag = np.max(magnitude)
    active_bins = magnitude > (0.15 * peak_mag)
    max_run_frames = 0
    for row in active_bins:
        run = 0
        for val in row:
            if val:
                run += 1
                if run > max_run_frames:
                    max_run_frames = run
            else:
                run = 0
    max_run_s = max_run_frames * hop / sr

    # Classification logic:
    # Full mix: strong harmonic energy or sustained tonal lines
    if harmonic_ratio > 0.6 or (max_run_s >= 0.25 and harmonic_ratio > 0.35):
        return "full"

    # Drum stem: low harmonicity, transient bursts present, no sustained tonal lines
    if harmonic_ratio < 0.45 and max_run_s < 0.2 and flux_peak_ratio >= 2.5:
        return "stem"

    return "unknown"
