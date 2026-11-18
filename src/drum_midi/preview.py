"""Lightweight MIDI preview: synthesize drum notes to WAV with numpy, play via winsound.

No new dependencies (numpy already present; winsound is stdlib on Windows).
The synth is a crude approximation (FM sine + filtered noise) — good enough to
hear timing/pitch, not a replacement for the real kit.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

_FS = 22050


def _env(n: int, sr: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / sr
    a = np.minimum(t / max(attack, 1e-4), 1.0)
    d = np.exp(-t / decay)
    return a * d


def _noise(n: int, lo: float, hi: float, sr: int) -> np.ndarray:
    rng = np.random.default_rng(0)
    x = rng.standard_normal(n)
    # one-pole high/low pass approximations (cheap, good enough)
    alpha = np.clip(1.0 - lo / (sr / 2), 0.0, 0.999)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(n):
        acc = alpha * acc + (1 - alpha) * x[i]
        y[i] = x[i] - acc
    return y


def _synth_type(dtype: str) -> np.ndarray:
    """Return a single drum hit for a type (mono, float32, ~1.5s max)."""
    # map similar types to neutral synth voices
    if dtype == "kick":
        n = int(0.35 * _FS)
        t = np.arange(n) / _FS
        freq = 60 * np.exp(-t / 0.06) + 40
        phase = np.cumsum(2 * np.pi * freq / _FS)
        body = np.sin(phase) * _env(n, _FS, 0.002, 0.09)
        return body * 0.9
    if dtype in ("snare", "side_stick", "rimshot"):
        n = int(0.2 * _FS)
        noise = _noise(n, 1500, 6000, _FS) * _env(n, _FS, 0.001, 0.05)
        body = np.sin(2 * np.pi * 190 * np.arange(n) / _FS) * _env(n, _FS, 0.001, 0.04)
        return (noise * 0.7 + body * 0.6) * 0.7
    if dtype in ("hat_closed", "hat_pedal"):
        n = int(0.08 * _FS)
        noise = _noise(n, 4000, 12000, _FS) * _env(n, _FS, 0.001, 0.02)
        return noise * 0.5
    if dtype == "hat_open":
        n = int(0.4 * _FS)
        noise = _noise(n, 3000, 12000, _FS) * _env(n, _FS, 0.001, 0.12)
        return noise * 0.5
    if dtype in ("rack1", "rack2", "floor"):
        n = int(0.4 * _FS)
        base = {"rack1": 220, "rack2": 185, "floor": 140}[dtype]
        t = np.arange(n) / _FS
        freq = base * np.exp(-t / 0.1) + 60
        phase = np.cumsum(2 * np.pi * freq / _FS)
        body = np.sin(phase) * _env(n, _FS, 0.002, 0.12)
        return body * 0.7
    # crash / ride / ride_bell
    n = int(1.5 * _FS)
    noise = _noise(n, 2000, 12000, _FS) * _env(n, _FS, 0.001, 0.5)
    return noise * 0.6


def render_preview(notes: list[dict], sr: int = _FS, max_seconds: float = 15.0) -> np.ndarray:
    """Render notes [{type, onset_s, velocity?}] to a mono float32 buffer.

    Preview is capped to the first `max_seconds` so playback is short/immediate.
    """
    notes = [n for n in notes if n.get("type") and n.get("onset_s", 0.0) < max_seconds]
    if not notes:
        return np.zeros(int(0.5 * sr), dtype=np.float32)
    dur = min(max((n.get("onset_s", 0.0) for n in notes), default=0.0) + 2.0, max_seconds)
    buf = np.zeros(int(dur * sr), dtype=np.float64)
    for n in notes:
        start = int(n.get("onset_s", 0.0) * sr)
        hit = _synth_type(n["type"])
        end = start + len(hit)
        if end > len(buf):
            hit = hit[: len(buf) - start]
            end = len(buf)
        vel = n.get("velocity", 0.8)
        buf[start:end] += hit * float(vel)
    peak = np.max(np.abs(buf)) or 1.0
    return (buf / peak * 0.98).astype(np.float32)


def write_preview_wav(notes: list[dict], path: str | Path) -> str:
    data = render_preview(notes)
    pcm = (np.clip(data, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_FS)
        w.writeframes(pcm.tobytes())
    return str(path)


def play_preview(notes: list[dict], path: str | Path | None = None) -> str:
    """Render and play (async, non-blocking). Returns the wav path."""
    import tempfile
    import winsound

    if path is None:
        path = Path(tempfile.gettempdir()) / "drum_preview.wav"
    else:
        path = Path(path)
    write_preview_wav(notes, path)
    try:
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception as exc:
        raise RuntimeError(f"Playback failed: {exc}") from exc
    return str(path)
