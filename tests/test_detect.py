import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from drum_midi.detect import detect_stem


def make_drum_only(sr: int = 44100, dur: float = 2.0) -> np.ndarray:
    """Generate synthetic drum stem with kicks, snares, and hi-hats."""
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    audio = np.zeros_like(t)

    # Kicks at 0.0, 0.5, 1.0, 1.5s (pitch-dropping sine burst)
    for onset in [0.0, 0.5, 1.0, 1.5]:
        if onset + 0.12 > dur:
            continue
        idx = int(onset * sr)
        kick_len = int(0.12 * sr)
        tk = np.linspace(0, 0.12, kick_len)
        freq = 150 * np.exp(-tk * 25)
        phase = 2 * np.pi * np.cumsum(freq) / sr
        audio[idx : idx + kick_len] += 0.8 * np.sin(phase) * np.exp(-tk * 20)

    # Snares at 0.25, 0.75, 1.25, 1.75s (decaying noise burst)
    rng = np.random.default_rng(42)
    for onset in [0.25, 0.75, 1.25, 1.75]:
        if onset + 0.15 > dur:
            continue
        idx = int(onset * sr)
        snare_len = int(0.15 * sr)
        noise = rng.uniform(-1, 1, snare_len)
        env = np.exp(-np.linspace(0, 1, snare_len) * 15)
        audio[idx : idx + snare_len] += 0.5 * noise * env

    # Hi-hats every 1/8 note (short click bursts)
    for onset in np.arange(0, dur, 0.125):
        if onset + 0.03 > dur:
            continue
        idx = int(onset * sr)
        hat_len = int(0.03 * sr)
        noise = rng.uniform(-1, 1, hat_len)
        env = np.exp(-np.linspace(0, 1, hat_len) * 30)
        audio[idx : idx + hat_len] += 0.3 * noise * env

    return audio


def make_drum_plus_sine(sr: int = 44100, dur: float = 2.0, freq: float = 440.0) -> np.ndarray:
    """Generate synthetic full mix: drum stem + sustained tonal sine wave."""
    drum = make_drum_only(sr=sr, dur=dur)
    t = np.linspace(0, dur, len(drum), endpoint=False)
    tonal = 0.35 * np.sin(2 * np.pi * freq * t)
    return drum + tonal


def test_pure_drum_is_stem():
    audio = make_drum_only()
    assert detect_stem(audio, 44100) == "stem"


def test_with_tonal_is_full():
    audio = make_drum_plus_sine()
    assert detect_stem(audio, 44100) == "full"


def test_with_chord_is_full():
    sr = 44100
    dur = 2.0
    drum = make_drum_only(sr=sr, dur=dur)
    t = np.linspace(0, dur, len(drum), endpoint=False)
    # C major chord (C4, E4, G4)
    chord = 0.2 * np.sin(2 * np.pi * 261.63 * t) + 0.2 * np.sin(2 * np.pi * 329.63 * t) + 0.2 * np.sin(2 * np.pi * 392.00 * t)
    assert detect_stem(drum + chord, sr) == "full"


def test_pure_tonal_without_drums_is_full():
    sr = 44100
    dur = 2.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    sine = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    assert detect_stem(sine, sr) == "full"


def test_silence_is_unknown():
    sr = 44100
    audio = np.zeros(sr * 2)
    assert detect_stem(audio, sr) == "unknown"


def test_near_silence_is_unknown():
    sr = 44100
    rng = np.random.default_rng(123)
    noise_floor = rng.normal(0, 1e-6, sr * 2)
    assert detect_stem(noise_floor, sr) == "unknown"


def test_empty_audio_is_unknown():
    assert detect_stem(np.array([], dtype=np.float64), 44100) == "unknown"


def test_too_short_audio_is_unknown():
    assert detect_stem(np.ones(100, dtype=np.float64), 44100) == "unknown"


def test_stationary_noise_is_unknown():
    sr = 44100
    dur = 2.0
    rng = np.random.default_rng(999)
    flat_noise = rng.uniform(-0.1, 0.1, int(sr * dur))
    assert detect_stem(flat_noise, sr) == "unknown"


def test_stereo_input_supported():
    drum = make_drum_only(dur=1.5)
    stereo_drum = np.column_stack((drum, drum))
    assert detect_stem(stereo_drum, 44100) == "stem"

    full = make_drum_plus_sine(dur=1.5)
    stereo_full = np.column_stack((full, full))
    assert detect_stem(stereo_full, 44100) == "full"


def test_different_sample_rate():
    audio = make_drum_only(sr=22050, dur=2.0)
    assert detect_stem(audio, 22050) == "stem"
