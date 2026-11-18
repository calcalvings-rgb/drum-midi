import os

import numpy as np
import pytest

from drum_midi.transcribe import (
    STRUM_LANE_TO_TYPE,
    THRESHOLD_PRESETS,
    transcribe_dispatch,
    transcribe_strum,
)


def _sine_clip(dur: float, sr: int = 44100, freq: float = 400.0) -> np.ndarray:
    n = int(dur * sr)
    t = np.arange(n) / sr
    x = np.sin(2 * np.pi * freq * t)
    x *= 0.5
    return x.astype(np.float32)


@pytest.mark.skipif(
    not os.path.isdir(os.environ.get("STRUM_ROOT", "")),
    reason="STRUM checkout not present",
)
def test_strum_lane_map_covers_app_types():
    assert len(STRUM_LANE_TO_TYPE) == 8
    assert "floor" in STRUM_LANE_TO_TYPE
    assert "rack1" in STRUM_LANE_TO_TYPE


def test_strum_presets_exist():
    assert "strum-recall" in THRESHOLD_PRESETS
    assert "strum-balanced" in THRESHOLD_PRESETS
    assert THRESHOLD_PRESETS["strum-recall"]["strum"]["mc_rescue_thr"] == 0.4


@pytest.mark.skipif(
    not os.path.isdir(os.environ.get("STRUM_ROOT", "")),
    reason="STRUM checkout not present",
)
def test_transcribe_dispatch_strum_preset():
    clip = _sine_clip(0.5)
    notes = transcribe_dispatch(clip, 44100, method="strum", threshold_preset="strum-recall")
    assert isinstance(notes, list)
    assert all("type" in n and "onset_s" in n and "velocity" in n for n in notes)
