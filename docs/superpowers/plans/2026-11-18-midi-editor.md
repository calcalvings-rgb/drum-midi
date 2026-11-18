# MIDI Editor (Tier B) Plan

> Implementation via codex/agy writers, controller verify + commit. Steps checkbox.

**Goal:** Edit hasil transkripsi sebelum export: geser timing, reassign drum type, delete note. Re-export dari hasil edit.

**Scope (user):** minimal — geser timing + pitch (drum type reassign kalo miss) + delete. Gak ada undo/quantize/playback/zoom (itu di DAW).

## Files
- Create: `src/drum_midi/editor.py` — pure note-list ops.
- Create: `tests/test_editor.py`.
- Modify (after Task 8): `src/drum_midi/gui.py` — piano-roll canvas integration.
- Modify: `tests/test_gui.py` — canvas interaction tests.

## Interfaces
- `move_note(notes, index, delta_s)` -> notes (mutate copy) — onset += delta_s, clamp >= 0.
- `reassign_note(notes, index, new_type)` -> notes — ganti type, validate di `DRUM_TYPES`.
- `delete_note(notes, index)` -> notes.
- `notes_from_midi(path)` (bonus, hanya kalau gampang) — baca .mid ke note list. **Skip** — kita simpan note list in-memory antara transcribe & write; gak perlu baca ulang.

### Task E1: editor core (pure ops)
- [ ] Test: move timing, reassign valid/invalid type, delete, clamp delta negatif.
- [ ] Implement `editor.py`.
- [ ] Run suite (flag basetemp), commit `feat: note editor core ops`.

### Task E2: GUI piano-roll integration (setelah Task 8)
- [ ] Canvas render notes (x=time, y=drum type row, warna per type).
- [ ] Drag horizontal = move timing; click+dropdown/keys = reassign; Del = delete.
- [ ] "Edit mode" toggle; hasil edit feed ke write_midi.
- [ ] Run suite, commit.
