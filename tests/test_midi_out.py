import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from drum_midi import maps

from drum_midi.midi_out import note_to_gm, velocity_to_midi, write_midi


def read_varlen(data, offset):
    value = 0
    while True:
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, offset


def parse_midi(path):
    data = Path(path).read_bytes()
    assert data[:4] == b"MThd"
    fmt, track_count, division = struct.unpack(">HHH", data[8:14])
    tracks, offset = [], 14
    for _ in range(track_count):
        assert data[offset:offset + 4] == b"MTrk"
        length = struct.unpack(">I", data[offset + 4:offset + 8])[0]
        tracks.append(data[offset + 8:offset + 8 + length])
        offset += 8 + length
    return fmt, division, tracks


def track_events(track):
    events, offset, tick = [], 0, 0
    while offset < len(track):
        delta, offset = read_varlen(track, offset)
        tick += delta
        status = track[offset]
        offset += 1
        if status == 0xFF:
            kind, size = track[offset], track[offset + 1]
            offset += 2
            payload = track[offset:offset + size]
            offset += size
            events.append((tick, "meta", kind, payload))
            if kind == 0x2F:
                break
        else:
            note, velocity = track[offset:offset + 2]
            offset += 2
            events.append((tick, status & 0xF0, note, velocity))
    return events


def test_write_midi_roundtrip_sleep_token(tmp_path):
    path = tmp_path / "out.mid"
    notes = [
        {"type": "kick", "onset_s": 0.0, "velocity": 0.9},
        {"type": "snare", "onset_s": 0.5, "velocity": 0.5},
    ]
    write_midi(notes, path, preset="mixwave_sleep_token")
    fmt, division, tracks = parse_midi(path)
    assert fmt == 1 and division == 480
    assert len(tracks) == len(maps.DRUM_TYPES) + 1
    events = [event for track in tracks[1:] for event in track_events(track)]
    assert any(event[1:3] == (0x90, 36) for event in events)
    assert any(event[1:3] == (0x90, 38) for event in events)


def test_hihat_closed_uses_preset_note(tmp_path):
    path = tmp_path / "out.mid"
    write_midi([{"type": "hat_closed", "onset_s": 0, "velocity": 0.5}], path,
               preset="mixwave_sleep_token")
    assert any(event[1:3] == (0x90, 75) for track in parse_midi(path)[2][1:] for event in track_events(track))


def test_tempo_is_written_on_conductor_track(tmp_path):
    path = tmp_path / "out.mid"
    write_midi([], path, tempo=100)
    event = track_events(parse_midi(path)[2][0])[0]
    assert event == (0, "meta", 0x51, bytes((0x09, 0x27, 0xC0)))


def test_note_and_velocity_clamp_and_normalized_velocity():
    assert note_to_gm(200) == 127
    assert note_to_gm(-2) == 0
    assert velocity_to_midi(-1) == 0
    assert velocity_to_midi(200) == 127
    assert velocity_to_midi(0.5) == 64



