import numpy as np
import wave

from drum_midi.preview import render_preview, write_preview_wav


def test_render_empty_is_short():
    buf = render_preview([])
    assert len(buf) == int(0.5 * 22050)


def test_render_duration_spans_last_note():
    notes = [{"type": "kick", "onset_s": 0.0}, {"type": "snare", "onset_s": 0.5}]
    buf = render_preview(notes)
    assert len(buf) >= int((0.5 + 2.0) * 22050)


def test_types_produce_distinct_signal():
    kick = render_preview([{"type": "kick", "onset_s": 0.0}])
    hat = render_preview([{"type": "hat_open", "onset_s": 0.0}])
    assert not np.allclose(kick, hat)


def test_write_preview_wav(tmp_path):
    notes = [{"type": "kick", "onset_s": 0.0}]
    path = write_preview_wav(notes, tmp_path / "p.wav")
    with wave.open(path) as w:
        assert w.getnchannels() == 1
        assert w.getframerate() == 22050
        assert w.getnframes() > 0
