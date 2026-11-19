"""Simple band-energy drum trigger transcription."""

import numpy as np
from scipy import signal

BANDS = [("kick", 20, 150), ("snare", 150, 500), ("floor", 500, 1200), ("rack2", 1200, 2500), ("rack1", 2500, 5000)]
DEFAULT_CONFIG = {"threshold_k": 3.0, "min_distance_s": 0.04, "overlap_window_s": 0.010, "hat_min_hz": 5000.0, "velocity_curve": [[0.0, 0.0], [0.5, 0.55], [1.0, 1.0]]}


def trigger_transcribe(x, sr, config=None) -> list[dict]:
    if x is None or sr <= 0:
        return []
    audio = np.asarray(x, dtype=float)
    if audio.size == 0:
        return []
    if audio.ndim > 1:
        audio = audio.mean(axis=1 if audio.shape[0] < audio.shape[1] else 0)
    audio = np.nan_to_num(audio.reshape(-1))
    if not audio.size:
        return []

    cfg = DEFAULT_CONFIG | (config or {})
    nyquist = sr / 2
    envelope_sos = signal.butter(2, min(100, nyquist * 0.9), "lowpass", fs=sr, output="sos")
    distance = max(1, round(cfg["min_distance_s"] * sr))
    events = []
    bands = list(BANDS)
    if nyquist > cfg["hat_min_hz"]:
        bands.append(("hat_closed", cfg["hat_min_hz"], nyquist - 50))

    for name, low, high in bands:
        if nyquist < low or high <= low:
            continue
        sos = signal.butter(4, [low, min(high, nyquist - 1)], "bandpass", fs=sr, output="sos")
        envelope = signal.sosfilt(envelope_sos, np.abs(signal.sosfilt(sos, audio)))
        floor = np.percentile(envelope, 90)
        # Keep filter leakage from a strong neighboring band below the trigger threshold.
        threshold = max(cfg["threshold_k"] * floor, np.max(np.abs(audio)) * 0.10)
        peaks, _ = signal.find_peaks(envelope, height=threshold, distance=distance)
        for peak in peaks:
            value = envelope[peak]
            half = value * 0.5
            end = peak + 1
            while end < len(envelope) and envelope[end] >= half:
                end += 1
            # Envelope peak is the onset proxy; scale to the strongest band peak.
            velocity = float(np.clip(np.interp(value, [0, envelope.max() or 1], [0, 1]), 0, 1))
            events.append({"type": name, "onset_s": peak / sr, "velocity": velocity})

    # Align near-simultaneous band hits to one timestamp while retaining each type.
    events.sort(key=lambda n: (n["onset_s"], n["type"]))
    window = cfg["overlap_window_s"]
    i = 0
    while i < len(events):
        group = [events[i]]
        j = i + 1
        while j < len(events) and events[j]["onset_s"] - group[0]["onset_s"] <= window:
            group.append(events[j])
            j += 1
        timestamp = min(n["onset_s"] for n in group)
        for note in group:
            note["onset_s"] = timestamp
        i = j
    return sorted(events, key=lambda n: (n["onset_s"], n["type"]))
