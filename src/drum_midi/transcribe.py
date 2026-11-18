"""Drum audio transcription using band-split onset detection."""

import numpy as np
from scipy import signal

from drum_midi.maps import DRUM_TYPES


def transcribe_bands(x: np.ndarray | None, sr: int) -> list[dict]:
    """Transcribe drum hits from audio using band-split spectral flux.

    Parameters
    ----------
    x : np.ndarray or None
        Audio signal (1D mono or 2D multichannel).
    sr : int
        Sample rate in Hz.

    Returns
    -------
    list[dict]
        List of detected drum events: {'type': str, 'onset_s': float, 'velocity': float},
        sorted by onset time ascending.
    """
    if x is None:
        return []

    audio = np.asarray(x, dtype=np.float64)
    if audio.size == 0:
        return []

    if audio.ndim > 1:
        audio = np.mean(audio, axis=-1)

    if audio.size == 0:
        return []

    if np.max(np.abs(audio)) < 1e-4:
        return []

    nperseg = min(1024, len(audio))
    if nperseg < 64:
        return []

    hop = max(1, nperseg // 4)
    pad = nperseg
    padded = np.pad(audio, (pad, pad), mode="constant")

    f, t_s, z = signal.stft(padded, fs=sr, nperseg=nperseg, noverlap=nperseg - hop)
    t_s = t_s - pad / sr
    diff = np.maximum(0.0, np.diff(np.abs(z), axis=1))
    t_diff = t_s[1:]

    scale = max(1e-6, float(np.max(diff)))
    diff_norm = diff / scale

    # Frequency band masks
    mask_kick = (f >= 20) & (f < 150)
    mask_snare = (f >= 150) & (f < 500)
    mask_floor = (f >= 500) & (f < 1200)
    mask_rack2 = (f >= 1200) & (f < 2500)
    mask_rack1 = (f >= 2500) & (f < 5000)
    fmax_hat = max(5000.0, min(18000.0, sr / 2.0 - 50.0))
    mask_hat = (f >= 5000) & (f <= fmax_hat) if fmax_hat > 5000 else (f >= 3000)

    fk = np.mean(diff_norm[mask_kick, :], axis=0) if np.any(mask_kick) else np.zeros(diff.shape[1])
    fs = np.mean(diff_norm[mask_snare, :], axis=0) if np.any(mask_snare) else np.zeros(diff.shape[1])
    ff = np.mean(diff_norm[mask_floor, :], axis=0) if np.any(mask_floor) else np.zeros(diff.shape[1])
    fr2 = np.mean(diff_norm[mask_rack2, :], axis=0) if np.any(mask_rack2) else np.zeros(diff.shape[1])
    fr1 = np.mean(diff_norm[mask_rack1, :], axis=0) if np.any(mask_rack1) else np.zeros(diff.shape[1])
    fh = np.mean(diff_norm[mask_hat, :], axis=0) if np.any(mask_hat) else np.zeros(diff.shape[1])

    flux_total = np.sum(diff_norm, axis=0)
    max_total = float(np.max(flux_total)) if flux_total.size > 0 else 0.0
    if max_total < 1e-4:
        return []

    min_dist_frames = max(1, int(0.05 * sr / hop))
    thresh_total = max(1e-4, max_total * 0.15)
    peaks, _ = signal.find_peaks(flux_total, height=thresh_total, distance=min_dist_frames)

    notes = []
    for p in peaks:
        onset = max(0.0, round(float(t_diff[p]), 4))
        idx_start = int(onset * sr)
        idx_end = min(len(audio), idx_start + int(0.08 * sr))
        seg = audio[idx_start:idx_end]
        vel = round(float(np.clip(np.max(np.abs(seg)) if len(seg) > 0 else 0.5, 0.01, 1.0)), 4)

        k = fk[p]
        s = fs[p]
        fl = ff[p]
        r2 = fr2[p]
        r1 = fr1[p]
        h = fh[p]

        # 1. Hat alone (high frequency with negligible low/mid body)
        if h > 0.08 and s < 0.1 and k < 0.1:
            notes.append({"type": "hat_closed", "onset_s": onset, "velocity": vel})
            continue

        # 2. Tom alone (mid frequency dominance, low high-frequency noise)
        tom_cands = [("floor", fl), ("rack2", r2), ("rack1", r1)]
        best_tom, best_tom_val = max(tom_cands, key=lambda item: item[1])
        if best_tom_val > 0.08 and best_tom_val > 1.3 * s and best_tom_val > 1.3 * k:
            notes.append({"type": best_tom, "onset_s": onset, "velocity": vel})
            continue

        # 3. Kick (low frequency dominance)
        if k > 0.2 and k > 1.5 * s:
            notes.append({"type": "kick", "onset_s": onset, "velocity": vel})
            if h > 0.08:
                notes.append({"type": "hat_closed", "onset_s": onset, "velocity": vel})
            continue

        # 4. Snare (body in 150-500Hz)
        if s > 0.08:
            notes.append({"type": "snare", "onset_s": onset, "velocity": vel})
            if h > 0.15 and h > 1.5 * s:
                notes.append({"type": "hat_closed", "onset_s": onset, "velocity": vel})
            continue

        # Fallback to dominant band
        band_scores = [
            ("kick", k),
            ("snare", s),
            ("hat_closed", h),
            ("floor", fl),
            ("rack2", r2),
            ("rack1", r1),
        ]
        best_type, _ = max(band_scores, key=lambda item: item[1])
        if best_type in DRUM_TYPES:
            notes.append({"type": best_type, "onset_s": onset, "velocity": vel})

    notes.sort(key=lambda n: (n["onset_s"], n["type"]))
    return notes


def transcribe_dispatch(x: np.ndarray | None, sr: int, method: str = "bands") -> list[dict]:
    """Dispatch transcription to the specified backend.

    Parameters
    ----------
    x : np.ndarray or None
        Audio signal.
    sr : int
        Sample rate in Hz.
    method : str
        Transcription backend ('bands' or 'madmom').

    Returns
    -------
    list[dict]
        Transcribed drum notes.
    """
    if method == "bands":
        return transcribe_bands(x, sr)
    if method == "madmom":
        raise ImportError("madmom transcription is unavailable; install madmom to use method='madmom'.")
    raise ValueError(f"Unknown transcription method: {method}")


def transcribe(x: np.ndarray | None, sr: int, method: str = "bands") -> list[dict]:
    """Transcribe percussion audio into drum events.

    Parameters
    ----------
    x : np.ndarray or None
        Audio signal (1D mono or 2D multichannel).
    sr : int
        Sample rate in Hz.
    method : str
        Transcription method (default: 'bands').

    Returns
    -------
    list[dict]
        List of note dicts: {'type': str, 'onset_s': float, 'velocity': float},
        sorted by onset ascending.
    """
    return transcribe_dispatch(x, sr, method=method)
