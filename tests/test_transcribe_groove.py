import numpy as np
import pytest
import drum_midi.groove as groove
from drum_midi import transcribe


def test_transcribe_groove_default_collapses(monkeypatch):
    # two identical kick onsets 10ms apart, diff instruments kept
    notes = [{"type": "kick", "onset_s": 10.0, "velocity": 0.9},
             {"type": "kick", "onset_s": 10.01, "velocity": 0.8},
             {"type": "snare", "onset_s": 10.5, "velocity": 0.7}]
    monkeypatch.setattr(transcribe, "transcribe_dispatch", lambda *a, **k: notes)
    out = transcribe.transcribe(None, 44100, method="trigger")
    kicks = [n for n in out if n["type"] == "kick"]
    assert len(kicks) == 1
    assert len(out) == 2


def test_transcribe_groove_off_keeps_all(monkeypatch):
    notes = [{"type": "kick", "onset_s": 10.0, "velocity": 0.9},
             {"type": "kick", "onset_s": 10.01, "velocity": 0.8},
             {"type": "snare", "onset_s": 10.5, "velocity": 0.7}]
    monkeypatch.setattr(transcribe, "transcribe_dispatch", lambda *a, **k: notes)
    out = transcribe.transcribe(None, 44100, method="trigger", groove=False)
    assert len(out) == 3


def test_transcribe_flatten_cymbal(monkeypatch):
    notes = [{"type": "crash1", "onset_s": 10.0, "velocity": 0.6, "confidence": 0.61},
             {"type": "crash2", "onset_s": 10.003, "velocity": 0.7, "confidence": 0.82}]
    monkeypatch.setattr(transcribe, "transcribe_dispatch", lambda *a, **k: notes)
    out = transcribe.transcribe(None, 44100, method="trigger", flatten_cymbal=True)
    assert len(out) == 1
    assert out[0]["type"] == "cymbal"


def test_transcribe_tempo_fallback_on_no_audio():
    # x=None -> tempo None -> default window; should not raise
    assert transcribe._estimate_tempo(None, 44100) is None


def test_transcribe_velocity_smooth_flag(monkeypatch):
    notes = [{"type": "kick", "onset_s": 1.0, "velocity": 10},
             {"type": "snare", "onset_s": 1.1, "velocity": 127}]
    monkeypatch.setattr(transcribe, "transcribe_dispatch", lambda *a, **k: notes)
    out = transcribe.transcribe(None, 44100, method="trigger", velocity_smooth=True)
    vs = [n["velocity"] for n in out]
    assert max(vs) == 120
    assert min(vs) == 50


def test_transcribe_velocity_smooth_default_off(monkeypatch):
    notes = [{"type": "kick", "onset_s": 1.0, "velocity": 10},
             {"type": "snare", "onset_s": 1.1, "velocity": 127}]
    monkeypatch.setattr(transcribe, "transcribe_dispatch", lambda *a, **k: notes)
    out = transcribe.transcribe(None, 44100, method="trigger")
    assert {n["velocity"] for n in out} == {10, 127}


def test_transcribe_protect_grooves_flag(monkeypatch):
    notes = [{"type": "hh", "onset_s": 1.0, "velocity": 40},
             {"type": "hh", "onset_s": 1.06, "velocity": 42}]
    monkeypatch.setattr(transcribe, "transcribe_dispatch", lambda *a, **k: notes)
    seen = {}
    def fake_cl(*a, **kw):
        seen.update(kw)
        return []
    monkeypatch.setattr(groove, "groove_cleanup", fake_cl)
    transcribe.transcribe(None, 44100, method="trigger", protect_grooves=True)
    assert seen.get("protect_grooves") is True


def test_transcribe_protect_grooves_default_off(monkeypatch):
    notes = [{"type": "hh", "onset_s": 1.0, "velocity": 40}]
    monkeypatch.setattr(transcribe, "transcribe_dispatch", lambda *a, **k: notes)
    seen = {}
    def fake_cl(*a, **kw):
        seen.update(kw)
        return []
    monkeypatch.setattr(groove, "groove_cleanup", fake_cl)
    transcribe.transcribe(None, 44100, method="trigger")
    assert seen.get("protect_grooves") is False
