"""Drum audio transcription using band-split onset detection."""

import numpy as np
from scipy import signal

from drum_midi.maps import DRUM_TYPES

# Per-class ADTOF thresholds in LABELS_5 order (kick, snare, tom, hat, crash).
# Tuned against a pop cover reference: crash heavily over-fires at low thresholds.
ADTOF_THRESHOLDS = [0.08, 0.08, 0.20, 0.08, 0.65]

# dettato outputs GM drum keys directly; map the ones we model to app types.
DETTATO_PITCH_TO_TYPE = {
    27: "crash1",
    28: "crash1",
    29: "crash2",
    30: "crash1",
    36: "kick",
    37: "side_stick",
    38: "snare",
    40: "rimshot",
    41: "floor",
    42: "hat_closed",
    43: "floor",
    44: "hat_open",
    45: "rack2",
    46: "hat_open",
    47: "rack2",
    48: "rack1",
    49: "crash1",
    50: "rack1",
    51: "ride",
    53: "ride_bell",
    57: "crash2",
}


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


def transcribe_adtof(
    x: np.ndarray | None,
    sr: int,
    thresholds: list[float] | None = None,
) -> list[dict]:
    """Transcribe drums using the vendored ADTOF model (lazy import, requires torch+librosa).

    ADTOF (Zehren et al.) outputs 5 GM drum classes: 35 kick, 38 snare,
    47 low tom, 42 closed hat, 49 crash. Per-class thresholds follow the
    same order; defaults are tuned against a pop cover reference.
    """
    if x is None:
        return []
    audio = np.asarray(x, dtype=np.float64)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=-1)
    if audio.size == 0 or np.max(np.abs(audio)) < 1e-4:
        return []

    if thresholds is None:
        thresholds = ADTOF_THRESHOLDS

    try:
        from drum_midi._vendor.adtof_pytorch import transcribe_to_midi
    except ImportError as exc:
        raise ImportError(
            "ADTOF transcription unavailable; required deps (torch, librosa, pretty_midi) missing."
        ) from exc

    import tempfile
    import wave
    from pathlib import Path

    midi_pitch_to_type = {
        35: "kick",
        38: "snare",
        47: "floor",
        42: "hat_closed",
        49: "crash1",
    }

    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "in.wav"
        midi_path = Path(tmp) / "out.mid"
        pcm = np.clip(audio, -1.0, 1.0)
        pcm = (pcm * 32767).astype("<i2")
        with wave.open(str(wav_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm.tobytes())
        transcribe_to_midi(
            str(wav_path), str(midi_path), thresholds=thresholds, device="cpu"
        )
        return _parse_adtof_midi(midi_path, midi_pitch_to_type)


_dettato_model: object | None = None


def transcribe_dettato(x: np.ndarray | None, sr: int) -> list[dict]:
    """Transcribe drums with dettato-drums (GM keys -> app types).

    Requires the `dettato` package and a source recorded at >= 40 kHz.
    The model is loaded once and cached.
    """
    if x is None:
        return []
    audio = np.asarray(x, dtype=np.float32)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=-1)
    if audio.size == 0 or np.max(np.abs(audio)) < 1e-4:
        return []
    if sr < 40000:
        raise ValueError("dettato requires audio recorded at >= 40 kHz (drum model skipped below that).")

    global _dettato_model
    if _dettato_model is None:
        try:
            from dettato.drums import DrumTranscriber
        except ImportError as exc:
            raise ImportError("dettato transcription unavailable; install the dettato package.") from exc
        _dettato_model = DrumTranscriber.from_pretrained("cpu")

    hits = _dettato_model.transcribe(audio, sr=int(sr))
    notes = []
    for h in hits:
        typ = DETTATO_PITCH_TO_TYPE.get(h["pitch"])
        if typ:
            notes.append({"type": typ, "onset_s": float(h["onset"]), "velocity": float(h["velocity"])})
    notes.sort(key=lambda n: (n["onset_s"], n["type"]))
    return notes


def _parse_adtof_midi(path, pitch_to_type) -> list[dict]:
    data = path.read_bytes()
    div = int.from_bytes(data[12:14], "big")
    off = 14
    notes = []
    for _ in range(data.count(b"MTrk")):
        ln = int.from_bytes(data[off + 4 : off + 8], "big")
        trk = data[off + 8 : off + 8 + ln]
        off += 8 + ln
        i = 0
        t = 0
        status = None
        while i < len(trk):
            v = 0
            sh = 0
            while True:
                b = trk[i]
                i += 1
                v |= (b & 0x7F) << sh
                sh += 7
                if not b & 0x80:
                    break
            t += v
            if trk[i] & 0x80:
                status = trk[i]
                i += 1
            st = status
            if st == 0xFF:
                typ = trk[i]
                i += 1
                ln2 = trk[i]
                i += 1
                i += ln2
                continue
            if st in (0xF0, 0xF7):
                continue
            d1 = trk[i]
            i += 1
            if (st & 0xF0) in (0xC0, 0xD0):
                continue
            d2 = trk[i]
            i += 1
            if (st & 0xF0) == 0x90 and d2 > 0:
                onset = t / div
                typ = pitch_to_type.get(d1)
                if typ:
                    notes.append({"type": typ, "onset_s": onset, "velocity": float(d2)})
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
        Transcription backend ('bands', 'madmom', or 'adtof').

    Returns
    -------
    list[dict]
        Transcribed drum notes.
    """
    if method == "bands":
        return transcribe_bands(x, sr)
    if method == "madmom":
        raise ImportError("madmom transcription is unavailable; install madmom to use method='madmom'.")
    if method == "adtof":
        return transcribe_adtof(x, sr)
    if method == "dettato":
        return transcribe_dettato(x, sr)
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
