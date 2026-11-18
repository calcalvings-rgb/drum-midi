import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from drum_midi.separate import separate, separate_percussive


def make_drum_plus_sine(sr: int = 44100, dur: float = 2.0, freq: float = 440.0) -> np.ndarray:
    t = np.arange(int(sr * dur)) / sr
    drum = np.zeros_like(t)
    rng = np.random.default_rng(42)
    for onset in np.arange(0, dur, 0.25):
        start = int(onset * sr)
        length = min(int(0.03 * sr), len(t) - start)
        env = np.exp(-np.linspace(0, 8, length))
        drum[start : start + length] += rng.uniform(-1, 1, length) * env
    return drum + 0.35 * np.sin(2 * np.pi * freq * t)


def spectral_energy_tonal(x: np.ndarray, sr: int = 44100, freq: float = 440.0) -> float:
    spectrum = np.abs(np.fft.rfft(x))
    frequencies = np.fft.rfftfreq(len(x), 1 / sr)
    return float(np.sum(spectrum[np.abs(frequencies - freq) < 5] ** 2))


def test_hpss_reduces_tonal():
    x = make_drum_plus_sine()
    y = separate_percussive(x, 44100)
    assert y.shape == x.shape
    assert y.dtype == np.float64
    assert spectral_energy_tonal(y) < spectral_energy_tonal(x)


def test_none_returns_original_array():
    x = make_drum_plus_sine()
    assert separate(x, 44100, "none") is x


def test_hpss_dispatch_matches_percussive_extraction():
    x = make_drum_plus_sine()
    np.testing.assert_array_equal(separate(x, 44100, "hpss"), separate_percussive(x, 44100))


def test_demucs_is_lazy_and_has_install_guidance():
    with pytest.raises(ImportError, match="demucs") as exc:
        separate(np.zeros(16), 44100, "demucs")
    assert "install" in str(exc.value).lower()


def test_unknown_method_raises_value_error():
    with pytest.raises(ValueError, match="method"):
        separate(np.zeros(16), 44100, "unknown")
