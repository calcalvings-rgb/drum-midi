"""Pure operations for editing transcribed drum notes."""

from drum_midi.maps import DRUM_TYPES


def move_note(notes, index, delta_s):
    """Return a copy of notes with the selected onset shifted by delta_s."""
    result = notes.copy()
    note = result[index].copy()
    note["onset_s"] = max(0, note["onset_s"] + delta_s)
    result[index] = note
    return result


def reassign_note(notes, index, new_type):
    """Return a copy of notes with the selected note assigned a drum type."""
    if new_type not in DRUM_TYPES:
        raise ValueError(f"Unknown drum type: {new_type}")
    result = notes.copy()
    note = result[index].copy()
    note["type"] = new_type
    result[index] = note
    return result


def delete_note(notes, index):
    """Return a copy of notes without the selected note."""
    result = notes.copy()
    del result[index]
    return result
