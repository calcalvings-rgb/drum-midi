import numpy as np
import pytest

from drum_midi.audio import load_wav
from drum_midi.maps import DRUM_TYPES
from drum_midi.transcribe import transcribe_dettato


def _drums_clip():
    sr, x = load_wav("realtest/sep/htdemucs/cover/drums.wav")
    return sr, x[: int(5.0 * sr)]


def test_dettato_transcribes_and_maps_types():
    pytest.importorskip("dettato")
    sr, clip = _drums_clip()
    notes = transcribe_dettato(clip, sr)
    assert isinstance(notes, list)
    for n in notes:
        assert n["type"] in DRUM_TYPES
        assert isinstance(n["onset_s"], float)
        assert isinstance(n["velocity"], float)


def test_dettato_rejects_low_sample_rate():
    pytest.importorskip("dettato")
    tone = np.sin(2 * np.pi * 200 * np.arange(4000) / 22050).astype(np.float32)
    with pytest.raises(ValueError):
        transcribe_dettato(tone, 22050)
