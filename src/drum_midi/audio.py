"""WAV loading and optional ffmpeg decoding."""

import subprocess
import wave
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

TARGET_SR = 44100


def _to_float(samples: bytes, width: int) -> np.ndarray:
    if width == 1:
        return (np.frombuffer(samples, dtype=np.uint8).astype(np.float64) - 128) / 128
    if width == 2:
        return np.frombuffer(samples, dtype="<i2").astype(np.float64) / 32768
    if width == 3:
        raw = np.frombuffer(samples, dtype=np.uint8).reshape(-1, 3)
        values = raw[:, 0].astype(np.int32) | (raw[:, 1].astype(np.int32) << 8) | (raw[:, 2].astype(np.int32) << 16)
        values = (values ^ 0x800000) - 0x800000
        return values.astype(np.float64) / 8388608
    if width == 4:
        return np.frombuffer(samples, dtype="<i4").astype(np.float64) / 2147483648
    raise ValueError(f"Unsupported WAV sample width: {width} bytes")


def _resample(mono: np.ndarray, sample_rate: int) -> np.ndarray:
    if sample_rate <= 0:
        raise ValueError(f"Invalid WAV sample rate: {sample_rate}")
    if sample_rate != TARGET_SR and mono.size:
        from math import gcd

        divisor = gcd(TARGET_SR, sample_rate)
        mono = resample_poly(mono, TARGET_SR // divisor, sample_rate // divisor)
    return np.asarray(mono, dtype=np.float64)


def load_wav(path: str | Path) -> tuple[int, np.ndarray]:
    """Read PCM WAV, mix channels to mono, and resample to 44.1 kHz."""
    with wave.open(str(path), "rb") as wav:
        if wav.getcomptype() != "NONE":
            raise ValueError(f"Unsupported WAV compression: {wav.getcomptype()}")
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        frames = wav.readframes(wav.getnframes())
        audio = _to_float(frames, width)
        if channels < 1 or audio.size % channels:
            raise ValueError("Invalid WAV channel data")
        if channels > 1:
            audio = audio.reshape(-1, channels).mean(axis=1)
        audio = _resample(audio, wav.getframerate())
    return TARGET_SR, audio


def parse_audio(path: str | Path, decode_mp3: bool = False) -> tuple[int, np.ndarray]:
    """Load WAV directly, or optionally decode another format through ffmpeg."""
    path = Path(path)
    if path.suffix.lower() in {".wav", ".wave"}:
        return load_wav(path)
    if not decode_mp3:
        raise ValueError("Non-WAV input requires decode_mp3=True")
    try:
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(TARGET_SR), "-f", "f32le", "-"],
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg was not found; install ffmpeg to decode this audio format") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.decode(errors="replace").strip() if exc.stderr else "unknown ffmpeg error"
        raise ValueError(f"ffmpeg could not decode {path}: {message}") from exc
    audio = np.frombuffer(result.stdout, dtype="<f4").astype(np.float64)
    return TARGET_SR, audio
