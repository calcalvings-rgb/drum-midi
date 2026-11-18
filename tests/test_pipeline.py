import sys
import wave
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from drum_midi.pipeline import run_pipeline


SR = 44100


def _write_fixture(path: Path, *, full: bool = False) -> None:
    duration = 2.0
    samples = np.zeros(int(SR * duration), dtype=np.float64)
    rng = np.random.default_rng(17)
    for onset in np.arange(0, duration, 0.25):
        start = int(onset * SR)
        length = int(0.04 * SR)
        envelope = np.exp(-np.linspace(0, 10, length))
        samples[start : start + length] += 0.7 * rng.uniform(-1, 1, length) * envelope
    if full:
        t = np.arange(samples.size) / SR
        samples += 0.35 * np.sin(2 * np.pi * 440 * t)
    pcm = np.clip(samples, -1, 1)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SR)
        wav.writeframes(pcm.tobytes())


@pytest.fixture
def drum_stem(tmp_path):
    path = tmp_path / "drum_stem.wav"
    _write_fixture(path)
    return path


@pytest.fixture
def drum_full(tmp_path):
    path = tmp_path / "drum_full.wav"
    _write_fixture(path, full=True)
    return path


def test_pipeline_stem_skips_separation(drum_stem, tmp_path, monkeypatch):
    from drum_midi import pipeline

    def unexpected_separation(*args, **kwargs):
        pytest.fail("stem input must skip separation")

    monkeypatch.setattr(pipeline, "separate", unexpected_separation)
    out = tmp_path / "stem.mid"
    result = run_pipeline(drum_stem, {"input": "auto", "sep": "hpss", "tx": "bands"}, out)
    assert result == {"detected": "stem", "midi": out, "notes": result["notes"]}
    assert out.is_file()


def test_pipeline_full_separates(drum_full, tmp_path, monkeypatch):
    from drum_midi import pipeline

    calls = []
    original = pipeline.separate

    def recording_separation(audio, sr, method):
        calls.append(method)
        return original(audio, sr, method)

    monkeypatch.setattr(pipeline, "separate", recording_separation)
    out = tmp_path / "full.mid"
    result = run_pipeline(drum_full, {"input": "auto", "sep": "hpss", "tx": "bands"}, out)
    assert result["detected"] == "full"
    assert result["midi"] == out
    assert result["notes"] >= 0
    assert calls == ["hpss"]
    assert out.is_file()


def test_pipeline_explicit_full_none_transcribes_original(drum_stem, tmp_path, monkeypatch):
    from drum_midi import pipeline

    calls = []
    monkeypatch.setattr(pipeline, "separate", lambda x, sr, method: calls.append(method) or x)
    out = tmp_path / "explicit.mid"
    result = run_pipeline(drum_stem, {"input": "full", "sep": "none", "tx": "bands"}, out)
    assert result["detected"] == "full"
    assert calls == ["none"]
    assert out.is_file()
