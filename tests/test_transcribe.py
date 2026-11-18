import sys
from pathlib import Path

import numpy as np
import pytest
from scipy import signal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from drum_midi.transcribe import transcribe, transcribe_dispatch


def make_synthetic_kick(sr: int = 44100, dur: float = 0.2, freq_start: float = 150.0, freq_end: float = 40.0) -> np.ndarray:
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    freq = freq_end + (freq_start - freq_end) * np.exp(-t * 25)
    phase = 2 * np.pi * np.cumsum(freq) / sr
    return 0.85 * np.sin(phase) * np.exp(-t * 20)


def make_synthetic_snare(sr: int = 44100, dur: float = 0.2, seed: int = 42) -> np.ndarray:
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    rng = np.random.default_rng(seed)
    noise = rng.uniform(-1, 1, len(t))
    body = np.sin(2 * np.pi * 200.0 * t)
    sig = 0.5 * body + 0.5 * noise
    return 0.8 * sig * np.exp(-t * 20)


def make_synthetic_hat(sr: int = 44100, dur: float = 0.05, seed: int = 42) -> np.ndarray:
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    rng = np.random.default_rng(seed)
    raw = rng.uniform(-1, 1, len(t)) * np.exp(-t * 60)
    sos = signal.butter(4, min(6000, sr / 2 - 500), "hp", fs=sr, output="sos")
    return 0.6 * signal.sosfilt(sos, raw)


def make_synthetic_tom(sr: int = 44100, dur: float = 0.25, freq: float = 800.0) -> np.ndarray:
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    return 0.7 * np.sin(2 * np.pi * freq * t) * np.exp(-t * 15)


def make_drum_pattern(sr: int = 44100, dur: float = 1.0) -> np.ndarray:
    """Create a test pattern with kick@0.0, hat@0.25, and snare@0.5."""
    audio = np.zeros(int(sr * dur), dtype=np.float64)

    # Kick at 0.0s
    kick = make_synthetic_kick(sr=sr, dur=0.15)
    audio[: len(kick)] += kick

    # Hat at 0.25s
    hat = make_synthetic_hat(sr=sr, dur=0.04)
    idx_hat = int(0.25 * sr)
    audio[idx_hat : idx_hat + len(hat)] += hat

    # Snare at 0.5s
    snare = make_synthetic_snare(sr=sr, dur=0.18)
    idx_snare = int(0.5 * sr)
    audio[idx_snare : idx_snare + len(snare)] += snare

    return audio


def test_transcribe_drum_pattern():
    sr = 44100
    x = make_drum_pattern(sr=sr)
    notes = transcribe(x, sr)

    assert isinstance(notes, list)
    assert len(notes) >= 3

    # Check presence of instruments
    types = [n["type"] for n in notes]
    assert "kick" in types
    assert "snare" in types
    assert "hat_closed" in types

    # Check onset timings within 50ms of ground truth
    kick_notes = [n for n in notes if n["type"] == "kick"]
    assert any(abs(n["onset_s"] - 0.0) <= 0.05 for n in kick_notes)

    hat_notes = [n for n in notes if n["type"] == "hat_closed"]
    assert any(abs(n["onset_s"] - 0.25) <= 0.05 for n in hat_notes)

    snare_notes = [n for n in notes if n["type"] == "snare"]
    assert any(abs(n["onset_s"] - 0.5) <= 0.05 for n in snare_notes)

    # Check sorting by onset
    onsets = [n["onset_s"] for n in notes]
    assert onsets == sorted(onsets)

    # Check velocity
    for n in notes:
        assert isinstance(n["velocity"], float)
        assert 0.0 <= n["velocity"] <= 1.0


def test_transcribe_kick_only():
    sr = 44100
    x = make_synthetic_kick(sr=sr, dur=0.5)
    notes = transcribe(x, sr)
    assert len(notes) >= 1
    assert notes[0]["type"] == "kick"
    assert abs(notes[0]["onset_s"] - 0.0) <= 0.05
    assert 0.0 < notes[0]["velocity"] <= 1.0


def test_transcribe_snare_only():
    sr = 44100
    x = np.zeros(int(sr * 0.6))
    idx = int(0.2 * sr)
    snare = make_synthetic_snare(sr=sr, dur=0.2)
    x[idx : idx + len(snare)] = snare

    notes = transcribe(x, sr)
    assert any(n["type"] == "snare" for n in notes)
    snare_note = [n for n in notes if n["type"] == "snare"][0]
    assert abs(snare_note["onset_s"] - 0.2) <= 0.05


def test_transcribe_hat_only():
    sr = 44100
    x = np.zeros(int(sr * 0.5))
    idx = int(0.15 * sr)
    hat = make_synthetic_hat(sr=sr, dur=0.05)
    x[idx : idx + len(hat)] = hat

    notes = transcribe(x, sr)
    assert any(n["type"] == "hat_closed" for n in notes)
    hat_note = [n for n in notes if n["type"] == "hat_closed"][0]
    assert abs(hat_note["onset_s"] - 0.15) <= 0.05


def test_transcribe_tom_detection():
    sr = 44100
    x = np.zeros(int(sr * 0.6))
    idx = int(0.1 * sr)
    tom = make_synthetic_tom(sr=sr, dur=0.25, freq=800.0)
    x[idx : idx + len(tom)] = tom

    notes = transcribe(x, sr)
    assert len(notes) >= 1
    assert any(n["type"] in {"floor", "rack1", "rack2"} for n in notes)


def test_transcribe_empty_and_none():
    assert transcribe(None, 44100) == []
    assert transcribe(np.array([], dtype=np.float64), 44100) == []


def test_transcribe_silence():
    sr = 44100
    silence = np.zeros(sr)
    assert transcribe(silence, sr) == []

    noise_floor = np.random.default_rng(0).normal(0, 1e-6, sr)
    assert transcribe(noise_floor, sr) == []


def test_transcribe_short_audio():
    sr = 44100
    short_audio = np.ones(100, dtype=np.float64) * 0.5
    # Should not crash on very short input
    result = transcribe(short_audio, sr)
    assert isinstance(result, list)


def test_transcribe_stereo_input():
    sr = 44100
    mono = make_drum_pattern(sr=sr)
    stereo = np.column_stack([mono, mono])
    notes = transcribe(stereo, sr)
    assert len(notes) >= 3
    assert any(n["type"] == "kick" for n in notes)
    assert any(n["type"] == "snare" for n in notes)


def test_transcribe_different_sample_rate():
    sr = 22050
    x = make_drum_pattern(sr=sr)
    notes = transcribe(x, sr)
    assert any(n["type"] == "kick" for n in notes)
    assert any(n["type"] == "snare" for n in notes)


def test_transcribe_dispatch_bands():
    sr = 44100
    x = make_drum_pattern(sr=sr)
    res_direct = transcribe(x, sr, method="bands")
    res_dispatch = transcribe_dispatch(x, sr, method="bands")
    assert res_direct == res_dispatch


def test_transcribe_dispatch_madmom_lazy_raises_import_error():
    sr = 44100
    x = np.zeros(16)
    with pytest.raises(ImportError, match="madmom") as exc:
        transcribe_dispatch(x, sr, method="madmom")
    assert "install" in str(exc.value).lower()

    # Also calling transcribe with method='madmom' should raise ImportError
    with pytest.raises(ImportError, match="madmom"):
        transcribe(x, sr, method="madmom")


def test_transcribe_dispatch_unknown_method_raises_value_error():
    sr = 44100
    x = np.zeros(16)
    with pytest.raises(ValueError, match="method"):
        transcribe_dispatch(x, sr, method="unsupported_method")
