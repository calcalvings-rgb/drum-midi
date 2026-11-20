import sys
import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from drum_midi.gui import DrumMidiApp


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    try:
        r.destroy()
    except Exception:
        pass


def test_gui_builds_and_defaults(root):
    app = DrumMidiApp(root)
    # Assert input-mode var defaults to 'auto'
    assert app.mode_input_var.get() == "auto"

    # Assert kit dropdown includes gm + mixwave_sleep_token
    kit_values = list(app.kit_dropdown["values"])
    assert "gm" in kit_values
    assert "mixwave_sleep_token" in kit_values
    assert app.kit_var.get() in kit_values


def test_gui_dropdown_options(root):
    app = DrumMidiApp(root)

    # Input options: auto, stem, full
    input_values = list(app.input_dropdown["values"])
    assert set(input_values) == {"auto", "stem", "full"}
    assert app.mode_input_var.get() == "auto"

    # Separation options: none, HPSS, Demucs
    sep_values = [str(v).lower() for v in app.sep_dropdown["values"]]
    assert "none" in sep_values
    assert "hpss" in sep_values
    assert "demucs" in sep_values

    # Transcription options: bands, madmom, adtof, dettato
    tx_values = [str(v).lower() for v in app.tx_dropdown["values"]]
    assert "bands" in tx_values
    assert "madmom" in tx_values
    assert "adtof" in tx_values
    assert "dettato" in tx_values

    # Threshold preset dropdown exists, defaults to tuned-mixwave, lists presets
    from drum_midi.transcribe import THRESHOLD_PRESETS

    assert "tuned-mixwave" in app.threshold_preset_dropdown["values"]
    assert set(app.threshold_preset_dropdown["values"]) == set(THRESHOLD_PRESETS)
    assert app.threshold_preset_var.get() == "tuned-mixwave"
    assert app.mode_tx_var.get().lower() == "adtof"

    # Tempo entry default 120
    assert str(app.tempo_var.get()) == "120"


def test_gui_file_picker(root, monkeypatch):
    from tkinter import filedialog

    app = DrumMidiApp(root)
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **kwargs: "C:/drums/kick_snare.wav")

    app.browse_input_file()
    assert app.input_path_var.get() == "C:/drums/kick_snare.wav"


def test_gui_process_calls_pipeline(root, monkeypatch, tmp_path):
    import drum_midi.gui as gui_mod

    app = DrumMidiApp(root)

    test_audio = tmp_path / "song.wav"
    test_audio.write_bytes(b"dummy")
    app.input_path_var.set(str(test_audio))
    app.mode_input_var.set("stem")
    app.mode_sep_var.set("HPSS")
    app.mode_tx_var.set("bands")
    app.kit_var.set("mixwave_sleep_token")
    app.tempo_var.set("140")

    monkeypatch.setattr(gui_mod, "parse_audio", MagicMock(return_value=(44100, [0])))
    monkeypatch.setattr(gui_mod, "transcribe", MagicMock(return_value=[{"type": "kick", "onset_s": 0.1, "velocity": 0.8}]))

    app.process()
    gui_mod.parse_audio.assert_called_once_with(str(test_audio), decode_mp3=True)
    gui_mod.transcribe.assert_called_once()
    assert app.notes[0]["type"] == "kick"
    assert "ready to edit" in app.result_var.get()
    assert app.result_label.cget("text") == app.result_var.get()


def test_gui_process_missing_file_reports_error(root, monkeypatch):
    import drum_midi.gui as gui_mod

    app = DrumMidiApp(root)
    app.input_path_var.set("")

    app.process()
    assert "error" in app.result_var.get().lower() or "select" in app.result_var.get().lower()


def test_gui_process_handles_pipeline_exception(root, monkeypatch, tmp_path):
    import drum_midi.gui as gui_mod

    app = DrumMidiApp(root)
    test_audio = tmp_path / "song.wav"
    test_audio.write_bytes(b"dummy")
    app.input_path_var.set(str(test_audio))

    monkeypatch.setattr(gui_mod, "parse_audio", MagicMock(side_effect=ImportError("Demucs is not installed")))

    app.process()
    assert "demucs" in app.result_var.get().lower() or "error" in app.result_var.get().lower()


def test_render_creates_note_items(root):
    app = DrumMidiApp(root)
    app.notes = [{"type": "kick", "onset_s": 0.5, "velocity": 0.8}]
    app.render_notes()
    assert app.roll.find_withtag("note:0")


def test_select_and_reassign_changes_type(root):
    app = DrumMidiApp(root)
    app.notes = [{"type": "kick", "onset_s": 0.5, "velocity": 0.8}]
    app.render_notes()
    app.on_canvas_click(type("Event", (), {"x": 202, "y": 8})())
    app.reassign_selected("snare")
    assert app.notes[0]["type"] == "snare"


def test_delete_removes_selected_note(root):
    app = DrumMidiApp(root)
    app.notes = [{"type": "kick", "onset_s": 0.5, "velocity": 0.8}]
    app.selected_note = 0
    app.delete_selected()
    assert app.notes == []


def test_drag_updates_onset(root):
    app = DrumMidiApp(root)
    app.notes = [{"type": "kick", "onset_s": 0.5, "velocity": 0.8}]
    app.selected_note = 0
    app._drag_x = 150
    app.on_drag(type("Event", (), {"x": 170})())
    assert app.notes[0]["onset_s"] == 0.7


def test_entrypoint_drum_midi():
    import runpy

    entrypoint_path = Path(__file__).resolve().parents[1] / "drum_midi.py"
    assert entrypoint_path.is_file()
    env = runpy.run_path(str(entrypoint_path), run_name="drum_midi_entrypoint")
    assert "DrumMidiApp" in env
    assert "main" in env


def test_dark_theme_applies_sun_valley(root):
    from drum_midi.gui import apply_dark_theme
    assert apply_dark_theme(root) is True
    assert root.tk.call("ttk::style", "theme", "use") == "sun-valley-dark"


def test_missing_theme_has_clear_warning_and_dark_fallback(root, monkeypatch):
    import sys
    from drum_midi.gui import apply_dark_theme
    monkeypatch.setitem(sys.modules, "sv_ttk", None)
    with pytest.warns(RuntimeWarning, match="sv-ttk"):
        assert apply_dark_theme(root) is False
    assert root.tk.call("ttk::style", "theme", "use") == "clam"
    assert root.cget("background") == "#0d1017"


def test_transcription_shows_busy_state_before_backend_work(root, monkeypatch, tmp_path):
    import drum_midi.gui as gui
    app = DrumMidiApp(root)
    source = tmp_path / "busy.wav"
    source.write_bytes(b"fixture")
    app.input_path_var.set(str(source))
    app.mode_input_var.set("stem")
    monkeypatch.setattr(gui, "parse_audio", lambda *a, **k: (44100, [0]))
    observed = []
    def transcribe(*args, **kwargs):
        observed.append(("transcribing" in app.result_var.get().lower(), app.process_button.instate(["disabled"])))
        return []
    monkeypatch.setattr(gui, "transcribe", transcribe)
    app.process()
    assert observed == [(True, True)]
    assert "Completed" in app.result_var.get()
    assert app.process_button.instate(["!disabled"])


def test_keyboard_selects_and_retimes_without_pointer(root):
    app = DrumMidiApp(root)
    app.notes = [{"type": "kick", "onset_s": .5, "velocity": .8}]
    app._on_key(type("Event", (), {"keysym": "Down"})())
    assert app.selected_note == 0
    app._on_key(type("Event", (), {"keysym": "Right"})())
    assert app.notes[0]["onset_s"] == pytest.approx(.51)
    app._on_key(type("Event", (), {"keysym": "Escape"})())
    assert app.selected_note is None


def test_editor_canvas_matches_dark_theme(root):
    app = DrumMidiApp(root)
    assert app.roll.cget("background") == "#131518"
    assert app.root.title() == "GrooveForge"
    app.notes = [{"type": "kick", "onset_s": .5, "velocity": .8}]
    app.selected_note = 0
    app.render_notes()
    item = app.roll.find_withtag("note:0")[0]
    assert app.roll.itemcget(item, "outline") == "#e6e8ec"
