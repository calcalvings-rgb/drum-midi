"""Validated, note-only MIDI I/O for the browser editor's canonical GM state."""
from __future__ import annotations
import io
import math
from collections import defaultdict, deque
from .maps import PRESETS

MAX_NOTES = 50000
MAX_BEATS = 100000


def _mido():
    try:
        import mido
    except ImportError as exc:
        raise RuntimeError('Install the web dependencies: python -m pip install -r requirements-web.txt') from exc
    return mido


def _number(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be finite and between {low} and {high}')
    return value


def read_editor_midi(payload: bytes) -> dict:
    mido = _mido()
    midi = mido.MidiFile(file=io.BytesIO(payload))
    if midi.type == 2:
        raise ValueError('Type-2 multi-song MIDI is not supported')
    if midi.ticks_per_beat <= 0:
        raise ValueError('MIDI requires positive PPQN timing; SMPTE timing is unsupported')
    merged = list(mido.merge_tracks(midi.tracks))
    tick, tempo = 0, 500000
    for msg in merged:
        tick += msg.time
        if msg.type == 'set_tempo':
            if msg.tempo <= 0:
                raise ValueError('MIDI tempo must be positive')
            if tick > 0 and msg.tempo != tempo:
                raise ValueError('Variable-tempo MIDI is not supported; import a constant-tempo take')
            tempo = msg.tempo
        if msg.type == 'time_signature' and (msg.numerator, msg.denominator) != (4, 4):
            raise ValueError('Only constant 4/4 MIDI is supported by this editor')
    bpm = float(mido.tempo2bpm(tempo))
    _number(bpm, 20, 400, 'BPM')
    active, notes, tick = defaultdict(deque), [], 0
    for msg in merged:
        tick += msg.time
        if msg.type == 'note_on' and msg.velocity > 0:
            active[(msg.channel, msg.note)].append((tick, msg.velocity))
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            queue = active[(msg.channel, msg.note)]
            if queue:
                start, velocity = queue.popleft()
                when = start / midi.ticks_per_beat
                duration = max(1, tick - start) / midi.ticks_per_beat
                _number(when, 0, MAX_BEATS, 'Note beat')
                _number(duration, .000001, MAX_BEATS, 'Note duration')
                notes.append({'key': msg.note, 'when': when, 'duration': duration, 'gain': velocity / 127})
                if len(notes) > MAX_NOTES:
                    raise ValueError(f'At most {MAX_NOTES} notes are supported')
    if any(active.values()):
        raise ValueError('MIDI has unclosed note events')
    notes.sort(key=lambda n: (n['when'], n['key']))
    return {'notes': notes, 'bpm': bpm, 'warning': 'GM pitch input, note events only; output kit is applied on export. Controllers and other MIDI metadata are not retained.'}


def write_editor_midi(data: dict) -> bytes:
    mido = _mido()
    if not isinstance(data, dict):
        raise ValueError('Expected an editor snapshot object')
    bpm = _number(data.get('bpm'), 20, 400, 'BPM')
    notes, kit = data.get('notes'), data.get('kit', 'gm')
    if not isinstance(kit, str) or kit not in PRESETS:
        raise ValueError('Unknown output kit')
    if not isinstance(notes, list) or len(notes) > MAX_NOTES:
        raise ValueError(f'Expected at most {MAX_NOTES} notes')
    canonical = {pitch: name for name, pitch in PRESETS['gm'].items()}
    midi = mido.MidiFile(type=0, ticks_per_beat=960)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm), time=0))
    track.append(mido.MetaMessage('time_signature', numerator=4, denominator=4, time=0))
    events = []
    for note in notes:
        if not isinstance(note, dict):
            raise ValueError('Every note must be an object')
        key = note.get('key')
        if isinstance(key, bool) or not isinstance(key, int) or not 0 <= key <= 127:
            raise ValueError('MIDI pitch must be an integer between 0 and 127')
        when = _number(note.get('when'), 0, MAX_BEATS, 'Note beat')
        duration = _number(note.get('duration'), .000001, MAX_BEATS, 'Note duration')
        gain = _number(note.get('gain'), 0, 1, 'Note velocity')
        if kit != 'gm':
            if key not in canonical:
                raise ValueError(f'GM pitch {key} has no mapping in {kit}; choose GM or reassign the note')
            key = PRESETS[kit][canonical[key]]
        if gain == 0:
            continue
        start = round(when * midi.ticks_per_beat)
        end = max(start + 1, round((when + duration) * midi.ticks_per_beat))
        events.append((start, 1, mido.Message('note_on', channel=9, note=key, velocity=max(1, round(gain * 127)))))
        events.append((end, 0, mido.Message('note_off', channel=9, note=key, velocity=0)))
    previous = 0
    for tick, _, msg in sorted(events, key=lambda item: (item[0], item[1])):
        msg.time = tick - previous
        previous = tick
        track.append(msg)
    output = io.BytesIO()
    midi.save(file=output)
    return output.getvalue()
