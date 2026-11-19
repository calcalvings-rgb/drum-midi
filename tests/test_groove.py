import pytest
from drum_midi.groove import (DrumEvent, adaptive_window, collapse_duplicates,
                              cluster_events, groove_cleanup,
                              merge_cymbal_cluster)


def E(t, inst, conf=1.0, vel=100):
    return DrumEvent(t, inst, vel, conf)


# --- adaptive_window ---
def test_window_fast_tempo_small():
    # 220 BPM 16th ~= 68ms; window ~30ms -> survives 16ths
    w = adaptive_window(220)
    assert w < 0.04
    assert w > 0.015


def test_window_slow_tempo_big():
    # slower tempo -> wider window (relative, avoids clamp boundary)
    assert adaptive_window(80) > adaptive_window(220)


def test_window_no_tempo_default():
    assert adaptive_window(None) == 0.03


def test_window_nonpositive_falls_back():
    assert adaptive_window(0) == 0.03


# --- collapse_duplicates ---
def test_collapse_same_instr_keeps_best():
    evs = [E(10.000, "crash", 0.61), E(10.004, "crash", 0.82),
           E(10.007, "crash", 0.77)]
    out = collapse_duplicates(evs)
    assert len(out) == 1
    assert out[0].confidence == 0.82


def test_collapse_keeps_different_instrument():
    evs = [E(10.0, "kick"), E(10.02, "snare")]
    assert len(collapse_duplicates(evs)) == 2


def test_collapse_outside_window_kept():
    evs = [E(10.0, "kick"), E(10.06, "kick")]
    assert len(collapse_duplicates(evs, 0.03)) == 2


# --- cluster_events ---
def test_cluster_separates_by_gap():
    evs = [E(10.0, "kick"), E(10.01, "snare"), E(11.0, "kick")]
    cls = cluster_events(evs, 0.04)
    assert len(cls) == 2
    assert [e.time for e in cls[0]] == [10.0, 10.01]


def test_cluster_single_wide_gap():
    assert len(cluster_events([E(0, "kick"), E(2, "snare")], 0.04)) == 2


# --- merge_cymbal_cluster ---
def test_merge_picks_best_cymbal():
    cl = [E(10.0, "crash", 0.61), E(10.003, "hh", 0.72),
          E(10.007, "ride", 0.55)]
    out = merge_cymbal_cluster(cl)
    assert len(out) == 1
    assert out[0].instrument == "hh"
    assert out[0].confidence == 0.72


def test_merge_keeps_nonceymbal():
    cl = [E(10.0, "kick", 0.9), E(10.003, "ride", 0.55)]
    out = merge_cymbal_cluster(cl)
    assert len(out) == 2


# --- groove_cleanup end-to-end ---
def test_cleanup_collapses_and_flattens():
    evs = [E(10.000, "crash1", 0.61), E(10.004, "crash2", 0.82),
           E(10.007, "ride", 0.55), E(10.5, "kick", 0.9),
           E(10.5, "snare", 0.8)]
    out = groove_cleanup(evs, flatten_cymbal=True)
    # crash cluster -> single cymbal; kick+snare kept as two
    assert len(out) == 3
    assert [e.instrument for e in out] == ["cymbal", "kick", "snare"]


def test_cleanup_default_keeps_instrument_detail():
    evs = [E(10.000, "crash1", 0.61), E(10.004, "crash2", 0.82)]
    out = groove_cleanup(evs)  # flatten default off
    assert len(out) == 2  # detail kept: different instruments not merged
    assert {e.instrument for e in out} == {"crash1", "crash2"}


def test_cleanup_accepts_dict_input():
    evs = [{"time": 1.0, "type": "kick", "velocity": 100, "confidence": 0.9},
           {"time": 1.02, "type": "kick", "velocity": 100, "confidence": 0.5}]
    out = groove_cleanup(evs, tempo_bpm=120)
    assert len(out) == 1
    assert isinstance(out[0], DrumEvent)


def test_cleanup_filters_confidence_before_collapse():
    evs = [E(10.0, "kick", 0.2), E(10.01, "snare", 0.9)]
    out = groove_cleanup(evs, min_confidence=0.35)
    assert [e.confidence for e in out] == [0.9]


def test_cleanup_confidence_threshold_boundary_and_zero():
    evs = [E(10.0, "kick", 0.2), E(11.0, "snare", 0.35), E(12.0, "ride", 0.9)]
    assert [e.confidence for e in groove_cleanup(evs, min_confidence=0.35)] == [0.35, 0.9]
    assert len(groove_cleanup(evs)) == 3  # default off


# --- suppress_cymbal_sustain (PR-002) ---
def test_sustain_drops_low_velocity_tail():
    evs = [E(10.00, "crash", vel=95), E(10.08, "crash", vel=30),
           E(10.14, "ride", vel=20)]
    out = groove_cleanup(evs)
    assert len(out) == 1
    assert out[0].time == 10.00


def test_sustain_keeps_comparable_velocity():
    # loud pair within window, second still 80% of peak -> real hits
    evs = [E(10.00, "crash", vel=90), E(10.06, "crash", vel=80)]
    out = groove_cleanup(evs)
    assert len(out) == 2


def test_sustain_ignores_non_cymbal():
    evs = [E(10.0, "kick", vel=95), E(10.08, "kick", vel=30)]
    assert len(groove_cleanup(evs)) == 2


def test_sustain_keeps_hh_groove():
    # 16th hi-hat pattern at 140bpm (~107ms), comparable velocities
    evs = [E(10.000, "hh", vel=70), E(10.107, "hh", vel=68),
           E(10.214, "hh", vel=72)]
    out = groove_cleanup(evs)
    assert len(out) == 3


def test_sustain_off_disables_suppression():
    evs = [E(10.0, "crash", vel=95), E(10.06, "ride", vel=30)]
    assert len(groove_cleanup(evs, tail_window_s=0)) == 2
