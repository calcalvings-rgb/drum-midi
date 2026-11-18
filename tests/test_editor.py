import copy

import pytest

from drum_midi.editor import delete_note, move_note, reassign_note


@pytest.fixture
def notes():
    return [
        {"type": "kick", "onset_s": 0.25, "velocity": 0.9},
        {"type": "snare", "onset_s": 1.0, "velocity": 0.6},
    ]


def test_move_note_shifts_onset_and_preserves_input(notes):
    original = copy.deepcopy(notes)
    result = move_note(notes, 1, 0.5)

    assert result == [notes[0], {"type": "snare", "onset_s": 1.5, "velocity": 0.6}]
    assert result is not notes
    assert result[1] is not notes[1]
    assert notes == original


def test_move_note_clamps_onset_at_zero(notes):
    result = move_note(notes, 0, -1.0)

    assert result[0]["onset_s"] == 0
    assert notes[0]["onset_s"] == 0.25


def test_reassign_note_changes_valid_type(notes):
    result = reassign_note(notes, 0, "hat_closed")

    assert result[0] == {"type": "hat_closed", "onset_s": 0.25, "velocity": 0.9}
    assert result[0] is not notes[0]
    assert notes[0]["type"] == "kick"


def test_reassign_note_rejects_invalid_type(notes):
    with pytest.raises(ValueError):
        reassign_note(notes, 0, "not_a_drum")

    assert notes[0]["type"] == "kick"


def test_delete_note_returns_copy_without_selected_note(notes):
    result = delete_note(notes, 0)

    assert result == [notes[1]]
    assert result is not notes
    assert result[0] is notes[1]
    assert len(notes) == 2
