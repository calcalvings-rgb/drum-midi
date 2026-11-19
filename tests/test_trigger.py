import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from drum_midi.trigger import trigger_transcribe, apply_velocity_curve, DEFAULT_CONFIG, classify_band, classify_event
from drum_midi import maps

def make_click(sr, freq, dur=0.04, amp=1.0):
    t = np.arange(int(sr*dur)) / sr
    y = amp * np.sin(2*np.pi*freq*t) * np.exp(-t*40)
    return y

def test_simultaneous_hit_single_type():
    # InTrigger architecture: one onset -> one type per hit (not 3 parallel types).
    sr = 44100
    kick = make_click(sr, 60, amp=1.0)
    snare = make_click(sr, 250, amp=0.8)
    crash = make_click(sr, 8000, amp=0.6)
    audio = np.zeros(int(sr*0.5))
    audio[0:len(kick)] += kick
    audio[0:len(snare)] += snare
    audio[0:len(crash)] += crash
    notes = trigger_transcribe(audio, sr)
    assert len(notes) == 1
    assert notes[0]["type"] in {"kick", "snare", "floor", "rack1",
                                "rack2", "hat_closed", "crash1", "crash2", "ride"}

def test_band_isolation_no_phantom():
    sr = 44100
    audio = np.zeros(int(sr*0.4))
    audio[0:int(sr*0.04)] = make_click(sr, 60, amp=1.0)
    notes = trigger_transcribe(audio, sr)
    assert {n["type"] for n in notes} == {"kick"}

def test_trigger_notes_include_normalized_confidence():
    sr = 44100
    audio = np.zeros(int(sr*0.4))
    audio[:int(sr*0.04)] = make_click(sr, 60)
    notes = trigger_transcribe(audio, sr)
    assert notes
    assert all(0.0 <= n["confidence"] <= 1.0 for n in notes)

def test_empty_input_returns_empty():
    sr = 44100
    assert trigger_transcribe(np.zeros(int(sr*0.3)), sr) == []
    assert trigger_transcribe(None, sr) == []

import pytest

def test_velocity_curve_interp():
    c = DEFAULT_CONFIG["velocity_curve"]
    assert apply_velocity_curve(0.0, c) == 0.0
    assert apply_velocity_curve(1.0, c) == 1.0
    assert apply_velocity_curve(0.5, c) == pytest.approx(0.55)
    assert 0.0 < apply_velocity_curve(0.25, c) < 0.55

def test_velocity_curve_clamp():
    c = DEFAULT_CONFIG["velocity_curve"]
    assert apply_velocity_curve(-0.5, c) == 0.0
    assert apply_velocity_curve(1.5, c) == 1.0

def test_crash_vs_hat_by_decay():
    assert classify_band("hat_closed", 0.35, {}) == "crash1"
    assert classify_band("hat_closed", 0.05, {}) == "hat_closed"

def test_band_types_valid():
    for b in ["kick","snare","floor","rack2","rack1","hat_closed"]:
        assert classify_band(b, 0.05, {}) in maps.DRUM_TYPES

def test_classify_event_boundaries():
    # low centroid (Hz), short -> kick
    assert classify_event(60.0, 0.05, {}) == "kick"
    # tom band: below tom_lo -> floor, above -> rack2
    assert classify_event(150.0, 0.05, {}) == "floor"
    assert classify_event(300.0, 0.05, {}) == "rack2"
    # snare band
    assert classify_event(900.0, 0.05, {}) == "snare"
    # high centroid, short -> hat; long -> crash
    assert classify_event(6000.0, 0.05, {}) == "hat_closed"
    assert classify_event(6000.0, 0.30, {}) == "crash1"

from drum_midi.transcribe import transcribe

def test_transcribe_trigger_dispatch():
    sr = 44100
    audio = np.zeros(int(sr*0.5))
    audio[0:int(sr*0.04)] = make_click(sr, 60, amp=1.0)
    notes = transcribe(audio, sr, method="trigger")
    assert {n["type"] for n in notes} == {"kick"}
