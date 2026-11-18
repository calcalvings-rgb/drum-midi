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


def separate_demucs(x: np.ndarray, sr: int) -> np.ndarray:
    """Separate drums using Demucs htdemucs (lazy import; heavy first-call)."""
    try:
        from demucs.api import Separator, save_audio
        import torch
    except ImportError as exc:
        raise ImportError(
            "Demucs separation unavailable; install demucs: pip install demucs"
        ) from exc

    import tempfile
    from pathlib import Path

    torch.set_num_threads(4)
    with tempfile.TemporaryDirectory() as tmp:
        in_path = Path(tmp) / "in.wav"
        out_path = Path(tmp) / "drums.wav"
        _write_wav_mono(in_path, x, sr)
        separator = Separator(model="htdemucs", device="cpu")
        _, separated = separator.separate_audio_file(in_path)
        save_audio(separated["drums"], str(out_path), samplerate=separator.samplerate)
        _, drums = _read_wav_mono(out_path)
    return drums


def _write_wav_mono(path, x, sr):
    import wave
    import numpy as np

    pcm = np.clip(x, -1.0, 1.0)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def _read_wav_mono(path):
    import wave
    import numpy as np

    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        nch = w.getnchannels()
        frames = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    if nch > 1:
        frames = frames.reshape(-1, nch).mean(axis=1)
    return sr, frames.astype(np.float64) / 32767


def separate(x: np.ndarray, sr: int, method: str) -> np.ndarray:
    """Separate audio using the selected backend."""
    if method == "none":
        return x
    if method == "hpss":
        return separate_percussive(x, sr)
    if method == "demucs":
        return separate_demucs(x, sr)
    raise ValueError(f"Unknown separation method: {method}")
