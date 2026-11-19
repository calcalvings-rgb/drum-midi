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


def groove_cleanup(events, tempo_bpm=None, flatten_cymbal=False, merge_window=None):
    """Post-process raw transcribed events into clean MIDI events.

    - optional: flatten cymbals to 'cymbal' (when classifier is confused)
    - collapse same-instrument duplicates within adaptive window
    - cluster simultaneous events; merge cymbal clusters (if flatten on)
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
    out = []
    for cl in cluster_events(evs, merge_window * 1.4):
        if flatten_cymbal:
            cl = merge_cymbal_cluster(cl)
        out.extend(cl)
    return sorted(out, key=lambda e: e.time)
