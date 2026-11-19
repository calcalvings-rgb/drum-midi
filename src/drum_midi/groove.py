"""Groove cleanup post-processing for transcribed drum events.

Pure functions, no deps beyond stdlib. Turns raw noisy note events into
clean MIDI: collapse near-duplicate onsets (keep best-confidence), cluster
simultaneous events (optionally flatten cymbals), adaptive merge window
derived from tempo.
"""
from dataclasses import dataclass
from collections import defaultdict

# Common cymbal family names the backends emit. Used only when flatten is on.
CYMBALS = {"hat_closed", "hat_open", "hat_pedal", "ride", "ride_bell",
           "crash1", "crash2", "hh_closed", "hh_open", "hh", "crash",
           "china", "splash", "ride_bell"}
# Anything containing 'tom' -> generic tom (e.g. rack1/rack2/floor).
_DEFAULT_WINDOW = 0.03


@dataclass
class DrumEvent:
    time: float
    instrument: str
    velocity: int = 100
    confidence: float = 1.0


def normalize_instrument(name, flatten_cymbal=False):
    if flatten_cymbal and name in CYMBALS:
        return "cymbal"
    # keep original case; only map generics when asked
    return name


def adaptive_window(tempo_bpm):
    """Merge window in seconds for a tempo. 16th-note at tempo (approx).
    16th = 60 / (4*bpm) seconds. We merge within ~40% of that so real
    16th notes survive but true double-hits collapse."""
    if not tempo_bpm or tempo_bpm <= 0:
        return _DEFAULT_WINDOW
    sixteenth = 15.0 / tempo_bpm  # 60/(4*bpm)
    return min(0.05, max(0.012, sixteenth * 0.45))


def collapse_duplicates(events, window=0.03):
    """Same-instrument events within `window` -> keep highest confidence."""
    events = sorted(events, key=lambda e: (e.time, e.instrument))
    result = []
    for ev in events:
        if result and ev.instrument == result[-1].instrument and \
                ev.time - result[-1].time <= window:
            if ev.confidence > result[-1].confidence:
                result[-1] = ev
            continue
        result.append(ev)
    return result


def cluster_events(events, window=0.04):
    """Group events that fall within `window` of each other (any instrument)."""
    events = sorted(events, key=lambda e: e.time)
    clusters = []
    cur = []
    for ev in events:
        if cur and ev.time - cur[-1].time > window:
            clusters.append(cur)
            cur = []
        cur.append(ev)
    if cur:
        clusters.append(cur)
    return clusters


def merge_cymbal_cluster(cluster):
    """Within a cluster, pick the highest-confidence cymbal, drop the rest."""
    cymbals = [e for e in cluster if e.instrument in CYMBALS]
    if not cymbals or len(cymbals) == 1:
        return cluster
    best = max(cymbals, key=lambda e: e.confidence)
    # keep non-cymbal events, replace cymbals with the single best
    rest = [e for e in cluster if e.instrument not in CYMBALS]
    return rest + [best]


def suppress_cymbal_sustain(events, tail_window_s=0.15, vel_ratio=0.5):
    """Drop low-velocity cymbal-family events that trail a louder cymbal hit.

    Models crash sustain: a strong hit followed within ~150ms by a much
    weaker cymbal event (same family) is the tail, not a new hit. Events
    whose velocity is >= `vel_ratio` of the recent family peak are kept, so
    rapid 16th hi-hat grooves (comparable velocities) survive.
    """
    events = sorted(events, key=lambda e: e.time)
    out = []
    for ev in events:
        if ev.instrument in CYMBALS and out:
            prevs = [p for p in out
                     if p.instrument in CYMBALS and ev.time - p.time <= tail_window_s]
            if prevs and ev.velocity < max(p.velocity for p in prevs) * vel_ratio:
                continue
        out.append(ev)
    return out


def _percentile(sorted_vals, p):
    """Linear-interpolated percentile from a sorted list (stdlib only)."""
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p / 100.0
    f = int(k)
    c = f if k.is_integer() else min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    frac = k - f
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * frac


def smooth_velocities(events, p_lo=5, p_hi=95, out_lo=50, out_hi=120):
    """Remap the [p_lo, p_hi] velocity percentiles onto [out_lo, out_hi].

    Clamps outliers; leaves a degenerate (flat) distribution untouched.
    """
    vels = sorted(e.velocity for e in events)
    plo = _percentile(vels, p_lo)
    phi = _percentile(vels, p_hi)
    if plo is None or phi is None:
        return events
    span = phi - plo
    if span <= 0:
        return events
    for e in events:
        t = max(0.0, min(1.0, (e.velocity - plo) / span))
        e.velocity = int(round(out_lo + t * (out_hi - out_lo)))
    return events


def groove_cleanup(events, tempo_bpm=None, flatten_cymbal=False,
                   merge_window=None, tail_window_s=0.15, velocity_smooth=False):
    """Post-process raw transcribed events into clean MIDI events.

    - optional: flatten cymbals to 'cymbal' (when classifier is confused)
    - collapse same-instrument duplicates within adaptive window
    - drop cymbal sustain tails (low-velocity family events trailing a hit)
    - cluster simultaneous events; merge cymbal clusters (if flatten on)
    - optional: smooth velocities (percentile remap to [50,120])
    """
    if merge_window is None:
        merge_window = adaptive_window(tempo_bpm)
    evs = []
    for e in events:
        ev = e if isinstance(e, DrumEvent) else DrumEvent(e["time"], e["type"],
                                                          e.get("velocity", 100),
                                                          e.get("confidence", 1.0))
        ev.instrument = normalize_instrument(ev.instrument, flatten_cymbal)
        evs.append(ev)
    evs = collapse_duplicates(evs, merge_window)
    evs = suppress_cymbal_sustain(evs, tail_window_s) if tail_window_s else evs
    out = []
    for cl in cluster_events(evs, merge_window * 1.4):
        if flatten_cymbal:
            cl = merge_cymbal_cluster(cl)
        out.extend(cl)
    if velocity_smooth:
        smooth_velocities(out)
    return sorted(out, key=lambda e: e.time)
