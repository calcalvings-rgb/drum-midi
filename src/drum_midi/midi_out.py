"""Write standard type-1 MIDI files for transcribed drum hits."""

import math
import struct
from pathlib import Path


def note_to_gm(note):
    return max(0, min(127, int(note)))


def velocity_to_midi(v):
    value = float(v)
    if 0 <= value <= 1:
        value = round(value * 127)
    return max(0, min(127, int(value)))


def _varlen(value):
    value = max(0, int(value))
    encoded = bytearray((value & 0x7F,))
    value >>= 7
    while value:
        encoded.insert(0, (value & 0x7F) | 0x80)
        value >>= 7
    return bytes(encoded)


def _track_chunk(events):
    data = bytearray()
    previous_tick = 0
    for tick, payload in sorted(events, key=lambda event: event[0]):
        data.extend(_varlen(tick - previous_tick))
        data.extend(payload)
        previous_tick = tick
    data.extend(b"\x00\xff\x2f\x00")
    return b"MTrk" + struct.pack(">I", len(data)) + data


def write_midi(notes, path, preset="gm", tempo=120, ticks_per_beat=480):
    from . import maps

    mapping = maps.PRESETS[preset]
    if tempo <= 0 or ticks_per_beat <= 0:
        raise ValueError("tempo and ticks_per_beat must be positive")

    microseconds_per_beat = round(60_000_000 / tempo)
    conductor = [(0, b"\xff\x51\x03" + microseconds_per_beat.to_bytes(3, "big"))]
    chunks = [_track_chunk(conductor)]

    types = maps.DRUM_TYPES
    for drum_type in types:
        events = [(0, b"\xff\x03" + bytes((len(drum_type.encode("utf-8")),)) + drum_type.encode("utf-8"))]
        note_number = note_to_gm(mapping[drum_type])
        for note in notes:
            if note["type"] != drum_type:
                continue
            onset = float(note["onset_s"])
            if not math.isfinite(onset) or onset < 0:
                raise ValueError("note onset_s must be finite and nonnegative")
            start_tick = round(onset * tempo * ticks_per_beat / 60)
            end_tick = start_tick + max(1, ticks_per_beat // 8)
            velocity = velocity_to_midi(note["velocity"])
            events.extend(((start_tick, bytes((0x99, note_number, velocity))),
                          (end_tick, bytes((0x89, note_number, 0)))))
        chunks.append(_track_chunk(events))

    midi = b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), ticks_per_beat) + b"".join(chunks)
    Path(path).write_bytes(midi)
