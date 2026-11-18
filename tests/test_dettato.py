import numpy as np
import pytest

from drum_midi.audio import load_wav
from drum_midi.maps import DRUM_TYPES
from drum_midi.transcribe import (
    DETTATO_THRESHOLDS,
    THRESHOLD_PRESETS,
    transcribe,
    transcribe_dettato,
    transcribe_dispatch,
)


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


def test_dettato_threshold_presets_affect_count():
    pytest.importorskip("dettato")
    sr, clip = _drums_clip()
    dense = transcribe_dettato(clip, sr, thresholds=DETTATO_THRESHOLDS)
    sparse_cfg = THRESHOLD_PRESETS["sparse"]["dettato"]
    sparse = transcribe_dettato(clip, sr, thresholds=sparse_cfg)
    # Higher thresholds never add hits, only remove borderline peaks.
    assert len(sparse) <= len(dense)


def test_dettato_gpu_preset_filters_low_velocity():
    pytest.importorskip("dettato")
    sr, clip = _drums_clip()
    dense = transcribe_dettato(clip, sr, thresholds=DETTATO_THRESHOLDS)
    cfg = THRESHOLD_PRESETS["dettato-gpu"]["dettato"]
    gpu = transcribe_dettato(clip, sr, thresholds=cfg)
    assert len(gpu) <= len(dense)
    floor = cfg["vel_floor"]
    for n in gpu:
        if n["type"] in floor:
            assert n["velocity"] >= floor[n["type"]]


def test_transcribe_dispatch_dettato_preset():
    pytest.importorskip("dettato")
    sr, clip = _drums_clip()
    notes = transcribe(clip, sr, method="dettato", threshold_preset="tuned-mixwave")
    assert isinstance(notes, list)
    for n in notes:
        assert n["type"] in DRUM_TYPES
        assert isinstance(n["onset_s"], float)
        assert isinstance(n["velocity"], float)


def test_transcribe_dispatch_passesthrough_unknown_preset():
    pytest.importorskip("dettato")
    sr, clip = _drums_clip()
    # Unknown preset name falls back to the backend default (no KeyError).
    notes = transcribe_dispatch(clip, sr, method="dettato", threshold_preset="nope")
    assert isinstance(notes, list)
