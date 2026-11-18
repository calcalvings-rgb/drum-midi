import sys
import wave
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from drum_midi.audio import load_wav, parse_audio


def write_wav(path: Path, samples: np.ndarray, sample_rate: int, *, channels=1, width=2):
    samples = np.asarray(samples)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.astype("<i2").tobytes())


def test_load_wav_mono_and_resamples(tmp_path):
    source = np.array([0, 1000, -1000, 2000, -2000] * 1000, dtype=np.int16)
    path = tmp_path / "input.wav"
    write_wav(path, source, 22050)

    sr, audio = load_wav(path)

    assert sr == 44100
    assert audio.ndim == 1 and audio.dtype == np.float64
    assert len(audio) == 2 * len(source)
    assert np.max(np.abs(audio)) <= 1


def test_load_wav_downmixes_stereo(tmp_path):
    left = np.full(100, 1000, dtype=np.int16)
    right = np.full(100, -1000, dtype=np.int16)
    path = tmp_path / "stereo.wav"
    write_wav(path, np.column_stack((left, right)), 44100, channels=2)

    sr, audio = load_wav(path)

    assert sr == 44100
    assert audio.ndim == 1
    assert np.allclose(audio, 0)


def test_rejects_unsupported_width():
    from drum_midi.audio import _to_float

    with pytest.raises(ValueError, match="sample width"):
        _to_float(b"\0\0\0\0\0", 5)


def test_parse_mp3_uses_ffmpeg_lazily(monkeypatch, tmp_path):
    import subprocess

    path = tmp_path / "drum.mp3"
    path.touch()
    calls = []

    def fake_run(command, *, capture_output, check):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=np.array([0.25, -0.25], dtype="<f4").tobytes())

    monkeypatch.setattr(subprocess, "run", fake_run)
    sr, audio = parse_audio(path, decode_mp3=True)

    assert calls and "ffmpeg" in calls[0][0]
    assert sr == 44100
    assert audio.dtype == np.float64
    assert np.allclose(audio, [0.25, -0.25])


def test_parse_rejects_non_wav_without_decode(tmp_path):
    path = tmp_path / "drum.mp3"
    path.touch()
    with pytest.raises(ValueError, match="decode_mp3"):
        parse_audio(path)


