"""Lightweight harmonic-percussive source separation."""

import numpy as np
from scipy import ndimage, signal


def separate_percussive(x: np.ndarray, sr: int, method: str = "hpss") -> np.ndarray:
    """Return the percussive component of mono or multichannel audio."""
    if method != "hpss":
        raise ValueError(f"Unsupported separation method: {method}")
    audio = np.asarray(x, dtype=np.float64)
    if audio.ndim > 1:
        audio = audio.mean(axis=-1)
    if audio.ndim != 1:
        raise ValueError("Audio must be a mono or multichannel array")
    if not audio.size:
        return audio.copy()

    nperseg = min(2048, audio.size)
    hop = max(1, nperseg // 4)
    _, _, spectrum = signal.stft(audio, fs=sr, nperseg=nperseg, noverlap=nperseg - hop)
    magnitude = np.abs(spectrum)
    harmonic = ndimage.median_filter(magnitude, size=(1, 17), mode="nearest")
    percussive = ndimage.median_filter(magnitude, size=(17, 1), mode="nearest")
    mask = percussive**2 / (percussive**2 + harmonic**2 + 1e-10)
    _, result = signal.istft(spectrum * mask, fs=sr, nperseg=nperseg, noverlap=nperseg - hop)
    return np.asarray(result[: audio.size], dtype=np.float64)


def separate(x: np.ndarray, sr: int, method: str) -> np.ndarray:
    """Separate audio using the selected backend."""
    if method == "none":
        return x
    if method == "hpss":
        return separate_percussive(x, sr)
    if method == "demucs":
        raise ImportError("Demucs separation is unavailable; install demucs to use method='demucs'.")
    raise ValueError(f"Unknown separation method: {method}")
