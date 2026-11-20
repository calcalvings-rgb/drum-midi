"""Global-onset drum trigger following Waves InTrigger architecture.

Architecture (extracted from InTrigger bundle XML resources, see
references/intrigger-architecture.md): a SINGLE global onset-strength curve
(whitened, smoothed envelope) -> peak-pick -> a per-event classifier assigns
exactly one type from spectral centroid + duration. This replaces per-band
independent firing, which over-counts because a single hit excites many bands.

Type boundary thresholds are placeholders; calibrate against the InTrigger
oracle (FL-rendered MIDI) once available — see references/intrigger-architecture.md.
"""
import numpy as np
from scipy import signal

BANDS = [
    ("kick", 20, 150),
    ("snare", 150, 500),
    ("floor", 500, 1200),
    ("rack2", 1200, 2500),
    ("rack1", 2500, 5000),
]

DEFAULT_CONFIG = {
    "threshold_k": 1.0,
    "auto_calibrate": True,          # knee-detect flux threshold per file (no knob)
    "min_distance_s": 0.04,
    "overlap_window_s": 0.010,
    "hat_min_hz": 5000.0,
    "crash_decay_s": 0.2,
    # InTrigger-style chain tuning.
    "onset_filter_order": 10,        # MeanOrd: temporal smoothing (kills baseline ripple)
    "envelope_cutoff_hz": 80,        # envelope lowpass cutoff
    "nperseg": 512,
    "hop": 128,
    "flux_smooth": 2,                # smoothing frames for spectral-flux onset
    # Centroid (Hz) class boundaries (fitted on GT tes2.mid).
    "kick_max_hz": 110.0,
    "tom_max_hz": 380.0,
    "tom_lo_hz": 220.0,
    "snare_max_hz": 1000.0,
    "tom_dur_threshold_s": 0.15,     # low/mid band: duration >= => tom/floor
    "crash_dur_threshold_s": 0.12,   # high band: duration >= => crash, else hat
    "velocity_curve": [[0.0, 0.0], [0.5, 0.55], [1.0, 1.0]],
}


def classify_band(band_name: str, decay_s: float, config: dict) -> str:
    if band_name == "hat_closed" and decay_s > config.get("crash_decay_s", 0.2):
        return "crash1"
    return band_name


def apply_velocity_curve(peak: float, curve: list[list[float]]) -> float:
    points = np.asarray(curve, dtype=float)
    return float(np.clip(np.interp(np.clip(peak, 0, 1), points[:, 0], points[:, 1]), 0, 1))


def _whitened_envelope(audio: np.ndarray, sr: int, cfg: dict) -> np.ndarray:
    """Band-pass, rectify, smooth, then moving-average onset filter.

    The moving-average of order `onset_filter_order` smooths the envelope; it is
    used for velocity/duration, not onset timing (which uses spectral flux).
    """
    nyq = sr / 2
    sos_bp = signal.butter(4, [max(1.0, nyq * 0.0005), nyq - 1],
                           "bandpass", fs=sr, output="sos")
    x = signal.sosfilt(sos_bp, audio)
    env = np.abs(x)
    sos_lp = signal.butter(2, min(cfg["envelope_cutoff_hz"], nyq * 0.9),
                           "lowpass", fs=sr, output="sos")
    env = signal.sosfilt(sos_lp, env)
    order = int(cfg["onset_filter_order"])
    if order > 1:
        env = signal.convolve(env, np.ones(order) / order, mode="same")
    return env


def _stft(audio: np.ndarray, sr: int, cfg: dict):
    """STFT magnitude/power plus half-wave-rectified spectral flux.

    Returns (freqs, t, P, flux) where P = |Zxx|^2 (power) and flux is the
    per-frame half-wave-rectified spectral change used for onset detection.
    """
    nperseg = int(cfg["nperseg"])
    hop = int(cfg["hop"])
    f, t, Zxx = signal.stft(audio, sr, nperseg=nperseg, noverlap=nperseg - hop)
    mag = np.abs(Zxx)
    P = mag ** 2
    flux = np.maximum(mag[:, 1:] - mag[:, :-1], 0).sum(axis=0)
    return f, t, P, flux


def classify_event(centroid_hz: float, duration: float, config: dict) -> str:
    """Assign one drum type from spectral centroid (Hz) + duration.

    Boundaries fitted supervised on GT tes2.mid (75 notes, Kontakt): macro-F1
    0.719 with kick<110, tom<380, snare<1000, else crash. Duration separates
    kick from floor/tom and hat from crash (InTrigger-style).
    """
    cfg = config or {}
    tom_dur = cfg.get("tom_dur_threshold_s", 0.15)
    crash_dur = cfg.get("crash_dur_threshold_s", 0.12)
    tom_lo = cfg.get("tom_lo_hz", 220.0)
    k_kick = cfg.get("kick_max_hz", 110.0)
    k_snare = cfg.get("snare_max_hz", 1000.0)
    if centroid_hz < k_kick:
        return "floor" if duration >= tom_dur else "kick"
    if centroid_hz < cfg.get("tom_max_hz", 380.0):
        # rack2 (higher-pitched rack tom) has the LOWER centroid in this feature
        # space; floor (bigger, lower pitch) reads higher. Verified on GT
        # tes2.mid: rack2 114-218 Hz, floor 225-367 Hz.
        return "rack2" if centroid_hz < tom_lo else "floor"
    if centroid_hz < k_snare:
        return "snare"
    return "crash1" if duration >= crash_dur else "hat_closed"


def _calibrate_threshold(flux: np.ndarray, sr: int, cfg: dict) -> float:
    """Auto-calibrate an onset threshold with no GT and no manual knob.

    Sweep a percentile threshold over the flux distribution, count peaks at
    each, and pick the corner (knee) of the count-vs-percentile curve — where
    real hits saturate and the noise tail begins. Fall back to a fixed
    low percentile if the curve is degenerate (no clear knee).
    """
    frame_dist = max(1, round(cfg["min_distance_s"] * sr / int(cfg["hop"])))
    pcts = np.arange(85.0, 99.5, 0.5)
    counts = np.empty_like(pcts)
    for i, p in enumerate(pcts):
        thr = float(np.percentile(flux, p))
        counts[i] = len(signal.find_peaks(flux, height=thr, distance=frame_dist)[0])
    x = np.arange(len(counts))
    x0, y0, x1, y1 = x[0], counts[0], x[-1], counts[-1]
    num = np.abs((y1 - y0) * x - (x1 - x0) * counts + x1 * y0 - y1 * x0)
    den = float(np.hypot(y1 - y0, x1 - x0))
    k = int(np.argmax(num / den)) if den > 0 else 0
    return float(np.percentile(flux, pcts[k]))


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
    env = _whitened_envelope(audio, sr, cfg)
    f, t, Pw, flux = _stft(audio, sr, cfg)

    # Onset detection on spectral flux (tight timing), smoothed to avoid
    # fighting baseline ripple.
    smooth = int(cfg.get("flux_smooth", 2))
    if smooth > 1:
        flux = np.convolve(flux, np.ones(smooth) / smooth, mode="same")
    if cfg.get("auto_calibrate", True):
        thr = _calibrate_threshold(flux, sr, cfg)
    else:
        thr = max(cfg["threshold_k"] * np.percentile(flux, 90), 0.03 * flux.max())
    frame_dist = max(1, round(cfg["min_distance_s"] * sr / int(cfg["hop"])))
    peaks, _ = signal.find_peaks(flux, height=thr, distance=frame_dist)
    # flux index i corresponds to time t[i+1]
    fl = f.reshape(-1, 1)
    hop = int(cfg["hop"])
    events = []
    for frame in peaks:
        onset = t[frame + 1]
        # Anchor the spectral classifier on the envelope peak (steady state)
        # that follows the transient onset — the attack is broadband and muddies
        # the centroid.
        idx = int(round(onset * sr))
        win = env[idx:idx + int(0.03 * sr)]
        if len(win) == 0:
            continue
        pidx = idx + int(np.argmax(win))
        value = env[pidx]

        half = value * 0.5
        end = pidx + 1
        while end < len(env) and env[end] >= half:
            end += 1
        duration = (end - pidx) / sr

        lo_f = max(0, int(pidx // hop) - max(1, round(0.01 * sr / hop)))
        hi_f = min(Pw.shape[1] - 1, int(pidx // hop) + round(0.05 * sr / hop))
        seg = Pw[:, lo_f:hi_f + 1].sum(axis=1)
        total = seg.sum()
        centroid = float((fl[:, 0] * seg).sum() / total) if total > 0 else 0.0

        kind = classify_event(centroid, duration, cfg)
        velocity = apply_velocity_curve(value / (env.max() or 1), cfg["velocity_curve"])
        events.append({"type": kind, "onset_s": onset, "velocity": velocity})

    return sorted(events, key=lambda n: (n["onset_s"], n["type"]))
