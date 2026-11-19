"""Unit tests untuk groovegen.py (level-2 generator)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from drum_midi.groovegen import load_stats, generate_groove, pick_style, weighted_choice


# Fixture sintetik — stats dibuat manual (bukan data proprietary).
SYNTH_STATS = {
    "rock_song": {
        "slot_probs": {
            "0": {"kick": 0.0, "snare": 0.0, "hat_closed": 1.0},
            "4": {"kick": 1.0, "snare": 0.0, "hat_closed": 0.0},
            "8": {"kick": 0.0, "snare": 1.0, "hat_closed": 0.0},
        },
        "slot_act": {"0": 1.0, "4": 1.0, "8": 1.0},
        "accents": {"kick": 110, "snare": 100, "hat_closed": 90},
        "overall": {"density": 0.6},
    },
}


def test_load_stats_requires_path():
    with pytest.raises(ValueError):
        load_stats("ggd")
    with pytest.raises(ValueError):
        load_stats("st")
    with pytest.raises(FileNotFoundError):
        load_stats("/nonexistent/stats.json")


def test_generate_deterministic_seed():
    s = SYNTH_STATS
    style = pick_style(s, seed=3)
    a = generate_groove(s, style=style, seed=9, bars=2)
    b = generate_groove(s, style=style, seed=9, bars=2)
    assert a == b
    assert all("type" in n and "onset_s" in n and "velocity" in n for n in a)
    assert all(0 < n["velocity"] <= 127 for n in a)


def test_generate_sorted_onset():
    s = SYNTH_STATS
    n = generate_groove(s, seed=1, bars=1)
    ons = [x["onset_s"] for x in n]
    assert ons == sorted(ons), "onset harus sorted"


def test_weighted_choice_matches_probs():
    import random
    rng = random.Random(0)
    probs = {"kick": 0.5, "snare": 0.3, "hat": 0.2}
    counts = {}
    for _ in range(2000):
        k = weighted_choice(probs, rng)
        counts[k] = counts.get(k, 0) + 1
    assert counts["kick"] > counts["snare"] > counts["hat"]
