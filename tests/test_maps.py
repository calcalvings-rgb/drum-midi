import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from drum_midi import maps


EXPECTED_DRUM_TYPES = [
    "kick",
    "snare",
    "side_stick",
    "rimshot",
    "hat_closed",
    "hat_open",
    "hat_pedal",
    "rack1",
    "rack2",
    "floor",
    "crash1",
    "crash2",
    "ride",
    "ride_bell",
]


def test_drum_types_list_contents():
    assert isinstance(maps.DRUM_TYPES, list)
    assert set(maps.DRUM_TYPES) == set(EXPECTED_DRUM_TYPES)
    assert len(maps.DRUM_TYPES) == len(EXPECTED_DRUM_TYPES)
    assert len(maps.DRUM_TYPES) == len(set(maps.DRUM_TYPES))  # no duplicates


def test_presets_dict_contains_required_presets():
    assert isinstance(maps.PRESETS, dict)
    assert "gm" in maps.PRESETS
    assert "mixwave_sleep_token" in maps.PRESETS


def test_maps_have_all_types():
    for name, m in maps.PRESETS.items():
        assert isinstance(m, dict), f"Preset {name} must be a dict"
        assert set(m.keys()) == set(maps.DRUM_TYPES), f"Preset {name} missing types or has extras"


def test_preset_notes_are_valid_midi_numbers():
    for name, m in maps.PRESETS.items():
        for drum_type, note in m.items():
            assert isinstance(note, int), f"{name}[{drum_type}] note must be int"
            assert 0 <= note <= 127, f"{name}[{drum_type}] note {note} out of MIDI range 0-127"


def test_mixwave_sleep_token_exact_mapping():
    st_map = maps.PRESETS["mixwave_sleep_token"]
    expected = {
        "kick": 36,
        "snare": 38,
        "side_stick": 37,
        "rimshot": 40,
        "hat_closed": 75,
        "hat_open": 46,
        "hat_pedal": 44,
        "rack1": 50,
        "rack2": 47,
        "floor": 43,
        "crash1": 49,
        "crash2": 57,
        "ride": 51,
        "ride_bell": 53,
    }
    assert st_map == expected


def test_gm_preset_mapping():
    gm_map = maps.PRESETS["gm"]
    assert gm_map["kick"] == 36
    assert gm_map["snare"] == 38
    assert gm_map["side_stick"] == 37
    assert gm_map["rimshot"] == 40
    assert gm_map["hat_closed"] == 42
    assert gm_map["hat_open"] == 46
    assert gm_map["hat_pedal"] == 44
    assert gm_map["rack1"] == 48
    assert gm_map["rack2"] == 45
    assert gm_map["floor"] == 41
    assert gm_map["crash1"] == 49
    assert gm_map["crash2"] == 57
    assert gm_map["ride"] == 51
    assert gm_map["ride_bell"] == 53
