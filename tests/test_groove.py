import pytest
from drum_midi.groove import (DrumEvent, adaptive_window, collapse_duplicates,
                              cluster_events, dense_groove_indices, groove_cleanup,
                              is_continuous_groove, merge_cymbal_cluster,
                              smooth_velocities)


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


# --- smooth_velocities (PR-004) ---
def test_smooth_velocity_compresses_range():
    evs = [E(10, "kick", vel=v) for v in [10, 20, 60, 100, 127]]
    out = smooth_velocities(evs)
    vs = [e.velocity for e in out]
    assert min(vs) == 50
    assert max(vs) == 120
    assert vs[0] < vs[-1]  # order preserved, range compressed


def test_smooth_velocity_flat_unchanged():
    evs = [E(10, "kick", vel=90), E(11, "snare", vel=90)]
    out = smooth_velocities(evs)
    assert [e.velocity for e in out] == [90, 90]


def test_smooth_velocity_clamps_extremes():
    evs = [E(10, "kick", vel=1), E(11, "snare", vel=127)]
    out = smooth_velocities(evs)
    assert [e.velocity for e in out] == [50, 120]


def test_cleanup_velocity_smooth_flag():
    evs = [E(10, "kick", vel=10), E(11, "snare", vel=127)]
    out = groove_cleanup(evs, velocity_smooth=True)
    vs = [e.velocity for e in out]
    assert min(vs) == 50
    assert max(vs) == 120


def test_cleanup_velocity_smooth_default_off():
    evs = [E(10, "kick", vel=10), E(11, "snare", vel=127)]
    out = groove_cleanup(evs)
    assert [e.velocity for e in out] == [10, 127]


# --- groove density detection (PR-005) ---
def test_is_continuous_groove_uniform_true():
    # 16th hi-hat at 120bpm ~ 0.125s, near-uniform
    times = [10.0 + 0.125 * i for i in range(6)]
    assert is_continuous_groove(times)


def test_is_continuous_groove_erratic_false():
    # crash spam: erratic gaps
    times = [10.0, 10.07, 10.20, 10.22, 10.45, 10.50]
    assert not is_continuous_groove(times)


def test_is_continuous_groove_too_few_false():
    assert not is_continuous_groove([10.0, 10.15, 10.3])


def test_dense_groove_indices_marks_run_inside_noise():
    evs = [E(0.0, "crash1"), E(0.15, "crash1"), E(0.30, "crash1"),
           E(0.45, "crash1"), E(0.60, "crash1"), E(5.0, "crash2")]
    idx = dense_groove_indices(evs)
    assert idx == {0, 1, 2, 3, 4}


def test_dense_groove_indices_per_instrument():
    # steady 16th HH interleaved with kicks; HH run must still be detected
    evs = [E(10.00, "hh", vel=40), E(10.05, "kick", vel=100),
           E(10.10, "hh", vel=42), E(10.15, "kick", vel=100),
           E(10.20, "hh", vel=40), E(10.25, "kick", vel=100),
           E(10.30, "hh", vel=41), E(10.35, "kick", vel=100)]
    idx = dense_groove_indices(evs)
    assert {0, 2, 4, 6} <= idx


def test_cleanup_protect_grooves_keeps_ghost_notes():
    # steady 16th hi-hat (~0.06s gaps) tailing a loud crash: sustain would drop
    # the low-velocity ghost notes unless the groove is protected
    evs = [E(10.00, "crash", vel=95), E(10.06, "hh", vel=40),
           E(10.12, "hh", vel=42), E(10.18, "hh", vel=38),
           E(10.24, "hh", vel=40)]
    out_off = groove_cleanup(evs)                    # protect off -> crash + late hh (3)
    out_on = groove_cleanup(evs, protect_grooves=True)  # keep groove -> 5
    assert len(out_off) == 3
    assert len(out_on) == 5


def test_cleanup_protect_grooves_default_off():
    evs = [E(10.00, "crash", vel=95), E(10.06, "hh", vel=40),
           E(10.12, "hh", vel=42), E(10.18, "hh", vel=38),
           E(10.24, "hh", vel=40)]
    assert len(groove_cleanup(evs)) == 3
