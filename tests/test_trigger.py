import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from drum_midi.trigger import trigger_transcribe, apply_velocity_curve, DEFAULT_CONFIG

def make_click(sr, freq, dur=0.04, amp=1.0):
    t = np.arange(int(sr*dur)) / sr
    y = amp * np.sin(2*np.pi*freq*t) * np.exp(-t*40)
    return y

def test_simultaneous_hits_all_detected():
    sr = 44100
    kick = make_click(sr, 60, amp=1.0)
    snare = make_click(sr, 250, amp=0.8)
    crash = make_click(sr, 8000, amp=0.6)
    audio = np.zeros(int(sr*0.5))
    audio[0:len(kick)] += kick
    audio[0:len(snare)] += snare
    audio[0:len(crash)] += crash
    notes = trigger_transcribe(audio, sr)
    types = {n["type"] for n in notes}
    assert "kick" in types
    assert "snare" in types
    assert types & {"hat_closed", "crash1", "crash2", "ride"}

def test_band_isolation_no_phantom():
    sr = 44100
    audio = np.zeros(int(sr*0.4))
    audio[0:int(sr*0.04)] = make_click(sr, 60, amp=1.0)
    notes = trigger_transcribe(audio, sr)
    assert {n["type"] for n in notes} == {"kick"}

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
