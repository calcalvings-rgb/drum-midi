"""Drum audio transcription using band-split onset detection."""

import os
import sys
from pathlib import Path

import numpy as np
from scipy import signal
from typing import Any

from drum_midi.maps import DRUM_TYPES
from drum_midi.trigger import trigger_transcribe

# Per-class ADTOF thresholds in LABELS_5 order (kick, snare, tom, hat, crash).
# Tuned against a pop cover reference: crash heavily over-fires at low thresholds.
ADTOF_THRESHOLDS = [0.08, 0.08, 0.20, 0.08, 0.65]

# dettato outputs GM drum keys directly; map the ones we model to app types.
DETTATO_PITCH_TO_TYPE = {
    27: "crash1",
    28: "crash1",
    29: "crash2",
    30: "crash1",
    36: "kick",
    37: "side_stick",
    38: "snare",
    40: "rimshot",
    41: "floor",
    42: "hat_closed",
    43: "floor",
    44: "hat_open",
    45: "rack2",
    46: "hat_open",
    47: "rack2",
    48: "rack1",
    49: "crash1",
    50: "rack1",
    51: "ride",
    53: "ride_bell",
    57: "crash2",
}

# Default dettato thresholds (loaded weights) — model attrs `th_kit`, `th_drum`,
# `th_timpani`, `th_router` are overwritten per preset.
DETTATO_THRESHOLDS = {"kit": 0.5, "drum": 0.5, "timpani": 0.5, "router": 0.5}

# Named threshold presets, one entry per backend. Backends have incompatible
# threshold shapes (ADTOF: list of 5 class thresholds; dettato: dict).
# "tuned-mixwave" matches the pop cover reference distribution.
THRESHOLD_PRESETS = {
    "tuned-mixwave": {
        "trigger": None,
        "adtof": ADTOF_THRESHOLDS,
        "dettato": {"kit": 0.7, "drum": 0.5, "timpani": 0.5, "router": 0.5},
    },
    "dense": {
        "trigger": None,
        "adtof": [0.08, 0.08, 0.20, 0.08, 0.35],
        "dettato": DETTATO_THRESHOLDS,
    },
    # dettato on GPU: dense base + per-type velocity floor. dettato's single
    # th_kit can't raise snare/tom without also exploding hat_open/crash, so we
    # catch everything at th=0.5 then drop the low-velocity over-detected
    # types (their velocity tails are well-separated from real hits).
    "dettato-gpu": {
        "dettato": {
            "kit": 0.5,
            "drum": 0.5,
            "timpani": 0.5,
            "router": 0.5,
            "vel_floor": {
                "hat_open": 0.77,
                "ride": 0.74,
                "hat_closed": 0.68,
                "crash1": 0.82,
                "crash2": 0.75,
                "rimshot": 0.80,
            },
        },
    },
    "sparse": {
        "trigger": None,
        "adtof": [0.10, 0.10, 0.28, 0.10, 0.80],
        "dettato": {"kit": 0.8, "drum": 0.6, "timpani": 0.6, "router": 0.5},
    },
    # STRUM (hybrid V14+Phase3 MC). 8 lanes -> app types. The MC rescue
    # threshold trades recall (lower = more overlap caught, more FP) vs
    # precision. "recall" preset prioritizes catching every hit (overlap),
    # "balanced" reduces false positives at the cost of missing some overlap.
    "strum-recall": {"strum": {"mc_rescue_thr": 0.4}},
    "strum-balanced": {"strum": {"mc_rescue_thr": 0.5}},
}


def transcribe_bands(x: np.ndarray | None, sr: int) -> list[dict]:
    """Transcribe drum hits from audio using band-split spectral flux.

    Parameters
    ----------
    x : np.ndarray or None
        Audio signal (1D mono or 2D multichannel).
    sr : int
        Sample rate in Hz.

    Returns
    -------
    list[dict]
        List of detected drum events: {'type': str, 'onset_s': float, 'velocity': float},
        sorted by onset time ascending.
    """
    if x is None:
        return []

    audio = np.asarray(x, dtype=np.float64)
    if audio.size == 0:
        return []

    if audio.ndim > 1:
        audio = np.mean(audio, axis=-1)

    if audio.size == 0:
        return []

    if np.max(np.abs(audio)) < 1e-4:
        return []

    nperseg = min(1024, len(audio))
    if nperseg < 64:
        return []

    hop = max(1, nperseg // 4)
    pad = nperseg
    padded = np.pad(audio, (pad, pad), mode="constant")

    f, t_s, z = signal.stft(padded, fs=sr, nperseg=nperseg, noverlap=nperseg - hop)
    t_s = t_s - pad / sr
    diff = np.maximum(0.0, np.diff(np.abs(z), axis=1))
    t_diff = t_s[1:]

    scale = max(1e-6, float(np.max(diff)))
    diff_norm = diff / scale

    # Frequency band masks
    mask_kick = (f >= 20) & (f < 150)
    mask_snare = (f >= 150) & (f < 500)
    mask_floor = (f >= 500) & (f < 1200)
    mask_rack2 = (f >= 1200) & (f < 2500)
    mask_rack1 = (f >= 2500) & (f < 5000)
    fmax_hat = max(5000.0, min(18000.0, sr / 2.0 - 50.0))
    mask_hat = (f >= 5000) & (f <= fmax_hat) if fmax_hat > 5000 else (f >= 3000)

    fk = np.mean(diff_norm[mask_kick, :], axis=0) if np.any(mask_kick) else np.zeros(diff.shape[1])
    fs = np.mean(diff_norm[mask_snare, :], axis=0) if np.any(mask_snare) else np.zeros(diff.shape[1])
    ff = np.mean(diff_norm[mask_floor, :], axis=0) if np.any(mask_floor) else np.zeros(diff.shape[1])
    fr2 = np.mean(diff_norm[mask_rack2, :], axis=0) if np.any(mask_rack2) else np.zeros(diff.shape[1])
    fr1 = np.mean(diff_norm[mask_rack1, :], axis=0) if np.any(mask_rack1) else np.zeros(diff.shape[1])
    fh = np.mean(diff_norm[mask_hat, :], axis=0) if np.any(mask_hat) else np.zeros(diff.shape[1])

    flux_total = np.sum(diff_norm, axis=0)
    max_total = float(np.max(flux_total)) if flux_total.size > 0 else 0.0
    if max_total < 1e-4:
        return []

    min_dist_frames = max(1, int(0.05 * sr / hop))
    thresh_total = max(1e-4, max_total * 0.15)
    peaks, _ = signal.find_peaks(flux_total, height=thresh_total, distance=min_dist_frames)

    notes = []
    for p in peaks:
        onset = max(0.0, round(float(t_diff[p]), 4))
        idx_start = int(onset * sr)
        idx_end = min(len(audio), idx_start + int(0.08 * sr))
        seg = audio[idx_start:idx_end]
        vel = round(float(np.clip(np.max(np.abs(seg)) if len(seg) > 0 else 0.5, 0.01, 1.0)), 4)

        k = fk[p]
        s = fs[p]
        fl = ff[p]
        r2 = fr2[p]
        r1 = fr1[p]
        h = fh[p]

        # 1. Hat alone (high frequency with negligible low/mid body)
        if h > 0.08 and s < 0.1 and k < 0.1:
            notes.append({"type": "hat_closed", "onset_s": onset, "velocity": vel})
            continue

        # 2. Tom alone (mid frequency dominance, low high-frequency noise)
        tom_cands = [("floor", fl), ("rack2", r2), ("rack1", r1)]
        best_tom, best_tom_val = max(tom_cands, key=lambda item: item[1])
        if best_tom_val > 0.08 and best_tom_val > 1.3 * s and best_tom_val > 1.3 * k:
            notes.append({"type": best_tom, "onset_s": onset, "velocity": vel})
            continue

        # 3. Kick (low frequency dominance)
        if k > 0.2 and k > 1.5 * s:
            notes.append({"type": "kick", "onset_s": onset, "velocity": vel})
            if h > 0.08:
                notes.append({"type": "hat_closed", "onset_s": onset, "velocity": vel})
            continue

        # 4. Snare (body in 150-500Hz)
        if s > 0.08:
            notes.append({"type": "snare", "onset_s": onset, "velocity": vel})
            if h > 0.15 and h > 1.5 * s:
                notes.append({"type": "hat_closed", "onset_s": onset, "velocity": vel})
            continue

        # Fallback to dominant band
        band_scores = [
            ("kick", k),
            ("snare", s),
            ("hat_closed", h),
            ("floor", fl),
            ("rack2", r2),
            ("rack1", r1),
        ]
        best_type, _ = max(band_scores, key=lambda item: item[1])
        if best_type in DRUM_TYPES:
            notes.append({"type": best_type, "onset_s": onset, "velocity": vel})

    notes.sort(key=lambda n: (n["onset_s"], n["type"]))
    return notes


def transcribe_adtof(
    x: np.ndarray | None,
    sr: int,
    thresholds: list[float] | None = None,
) -> list[dict]:
    """Transcribe drums using the vendored ADTOF model (lazy import, requires torch+librosa).

    ADTOF (Zehren et al.) outputs 5 GM drum classes: 35 kick, 38 snare,
    47 low tom, 42 closed hat, 49 crash. Per-class thresholds follow the
    same order; defaults are tuned against a pop cover reference.
    """
    if x is None:
        return []
    audio = np.asarray(x, dtype=np.float64)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=-1)
    if audio.size == 0 or np.max(np.abs(audio)) < 1e-4:
        return []

    if thresholds is None:
        thresholds = ADTOF_THRESHOLDS

    try:
        from drum_midi._vendor.adtof_pytorch import transcribe_to_midi
    except ImportError as exc:
        raise ImportError(
            "ADTOF transcription unavailable; required deps (torch, librosa, pretty_midi) missing."
        ) from exc

    import tempfile
    import wave
    from pathlib import Path

    midi_pitch_to_type = {
        35: "kick",
        38: "snare",
        47: "floor",
        42: "hat_closed",
        49: "crash1",
    }

    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "in.wav"
        midi_path = Path(tmp) / "out.mid"
        pcm = np.clip(audio, -1.0, 1.0)
        pcm = (pcm * 32767).astype("<i2")
        with wave.open(str(wav_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm.tobytes())
        transcribe_to_midi(
            str(wav_path), str(midi_path), thresholds=thresholds, device="cpu"
        )
        return _parse_adtof_midi(midi_path, midi_pitch_to_type)


_dettato_model: Any = None


def transcribe_dettato(x: np.ndarray | None, sr: int, thresholds: dict | None = None) -> list[dict]:
    """Transcribe drums with dettato-drums (GM keys -> app types).

    Requires the `dettato` package and a source recorded at >= 40 kHz.
    The model is loaded once and cached; optional ``thresholds`` dict keys
    (kit/drum/timpani/router) override the model's thresholds for this call.
    """
    if x is None:
        return []
    audio = np.asarray(x, dtype=np.float32)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=-1)
    if audio.size == 0 or np.max(np.abs(audio)) < 1e-4:
        return []
    if sr < 40000:
        raise ValueError("dettato requires audio recorded at >= 40 kHz (drum model skipped below that).")

    global _dettato_model
    if _dettato_model is None:
        try:
            from dettato.drums import DrumTranscriber
        except ImportError as exc:
            raise ImportError("dettato transcription unavailable; install the dettato package.") from exc
        try:
            import torch as _torch
        except ImportError:
            _torch = None
        device = "cuda" if (_torch is not None and _torch.cuda.is_available()) else "cpu"
        _dettato_model = DrumTranscriber.from_pretrained(device)

    if thresholds:
        _dettato_model.th_kit = float(thresholds.get("kit", _dettato_model.th_kit))
        _dettato_model.th_drum = float(thresholds.get("drum", _dettato_model.th_drum))
        _dettato_model.th_timpani = float(thresholds.get("timpani", _dettato_model.th_timpani))
        _dettato_model.th_router = float(thresholds.get("router", _dettato_model.th_router))

    hits = _dettato_model.transcribe(audio, sr=int(sr))
    notes = []
    for h in hits:
        typ = DETTATO_PITCH_TO_TYPE.get(h["pitch"])
        if typ:
            notes.append({"type": typ, "onset_s": float(h["onset"]), "velocity": float(h["velocity"])})
    notes.sort(key=lambda n: (n["onset_s"], n["type"]))

    # Optional per-type velocity floor: drops low-confidence over-detected hits
    # (e.g. hat_open/crash tails) while keeping high-confident snare/tom/kick.
    vel_floor = (thresholds or {}).get("vel_floor")
    if vel_floor:
        notes = [n for n in notes if n["velocity"] >= vel_floor.get(n["type"], 0.0)]
    return notes


# STRUM lane index -> app type (STRUM orders: Kick, Snare, HiHat, HighTom,
# Ride, LowTom, Crash, FloorTom).
STRUM_LANE_TO_TYPE = ["kick", "snare", "hat_closed", "rack1", "ride", "rack2", "crash1", "floor"]

# Path to the STRUM checkout (V14 + Phase3 checkpoints). Override via env.
_STRUM_ROOT = os.environ.get(
    "STRUM_ROOT", str(Path(__file__).resolve().parents[3] / "strum")
)
_strum_models: dict | None = None


def transcribe_strum(x: np.ndarray | None, sr: int, mc_rescue_thr: float = 0.4) -> list[dict]:
    """Transcribe drums with STRUM (V14 onset + Phase3 multi-class rescue).

    STRUM's V14 CRNN detects onsets (high recall); the Phase3 multi-class head
    provides per-class onset probabilities, so simultaneous hits (e.g. kick +
    snare + crash at one instant) are emitted as multiple events instead of
    being collapsed into one. ``mc_rescue_thr`` is the per-class probability
    threshold at which an extra class is added to an already-detected onset
    frame (lower catches more overlap, more false positives).
    """
    if x is None:
        return []
    audio = np.asarray(x, dtype=np.float32)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=-1)
    if audio.size == 0 or np.max(np.abs(audio)) < 1e-4:
        return []
    if sr != 44100:
        import librosa as _librosa
        audio = _librosa.resample(audio, orig_sr=sr, target_sr=44100)
        sr = 44100

    global _strum_models
    if _strum_models is None:
        try:
            import torch as _torch
            import torchaudio as _torchaudio  # noqa: F401
            import scipy.signal as _sig  # noqa: F401
            import librosa as _librosa  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "STRUM transcription requires torch/torchaudio/scipy/librosa."
            ) from exc
        try:
            sys.path.insert(0, str(_STRUM_ROOT))
            from src.models.drums_v13 import TwoStageDrumsCRNN  # type: ignore
        except ImportError as exc:
            raise ImportError(
                f"STRUM checkout not found at {_STRUM_ROOT!r}; set STRUM_ROOT."
            ) from exc
        device = "cuda" if _torch.cuda.is_available() else "cpu"
        model_kw = dict(
            n_mels=128, conv_channels=[64, 128, 256, 512],
            freq_subbands=[32, 64, 96, 128], subband_proj_dim=256,
            lstm_hidden=640, lstm_layers=3,
            attention_heads=10, attention_type="flash", attention_window=512,
            dropout=0.0, onset_detector_hidden=320, classifier_hidden=640,
            num_classes=8, predict_velocity=False,
        )
        v14 = TwoStageDrumsCRNN(**model_kw)
        v14_ckpt = _torch.load(
            str(Path(_STRUM_ROOT) / "checkpoints" / "drums_v14" / "best.pt"),
            map_location=device, weights_only=False,
        )
        cfg_v = v14_ckpt.get("config", {}).get("model", {})
        for k in ("conv_channels", "freq_subbands", "subband_proj_dim", "lstm_hidden",
                  "lstm_layers", "attention_heads", "attention_type", "attention_window",
                  "onset_detector_hidden", "classifier_hidden"):
            if k in cfg_v:
                model_kw[k] = cfg_v[k]
        v14 = TwoStageDrumsCRNN(**model_kw)
        v14.load_state_dict(v14_ckpt["model_state_dict"], strict=False)
        v14 = v14.to(device).eval()
        p3 = TwoStageDrumsCRNN(**model_kw)
        p3.add_multiclass_onset_head()
        p3_ckpt = _torch.load(
            str(Path(_STRUM_ROOT) / "checkpoints" / "drums_phase3" / "best.pt"),
            map_location=device, weights_only=False,
        )
        cfg_p = p3_ckpt.get("config", {}).get("model", {})
        for k in ("conv_channels", "freq_subbands", "subband_proj_dim", "lstm_hidden",
                  "lstm_layers", "attention_heads", "attention_type", "attention_window",
                  "onset_detector_hidden", "classifier_hidden"):
            if k in cfg_p:
                model_kw[k] = cfg_p[k]
        p3 = TwoStageDrumsCRNN(**model_kw)
        p3.add_multiclass_onset_head()
        p3.load_state_dict(p3_ckpt["model_state_dict"], strict=False)
        p3 = p3.to(device).eval()
        _strum_models = {"v14": v14, "p3": p3, "device": device}

    v14 = _strum_models["v14"]
    p3 = _strum_models["p3"]
    device = _strum_models["device"]

    import torch as _torch
    import torchaudio as _torchaudio
    import librosa as _librosa
    from scipy.signal import find_peaks

    audio_t = _torch.from_numpy(audio).unsqueeze(0)
    mel_t = _torchaudio.transforms.MelSpectrogram(
        sample_rate=44100, n_fft=2048, hop_length=512, n_mels=128
    )
    mel = _torch.log(mel_t(audio_t) + 1e-8)
    tf = mel.shape[-1]
    seg_frames = int(10.0 * 44100 / 512)
    hop_frames = seg_frames // 2
    onset_probs = np.zeros(tf)
    mc = np.zeros((tf, 8))
    cnt = np.zeros(tf)
    with _torch.no_grad():
        for st in range(0, tf, hop_frames):
            en = min(st + seg_frames, tf)
            seg = mel[:, :, st:en]
            if seg.shape[-1] < seg_frames:
                seg = _torch.nn.functional.pad(seg, (0, seg_frames - seg.shape[-1]))
            seg = seg.unsqueeze(0).to(device)
            o1 = v14(seg)
            o2 = p3(seg)
            p1 = o1["onset_probs"].squeeze(0).squeeze(-1).cpu().numpy()
            p2 = o2["mc_onset_probs"].squeeze(0).cpu().numpy()
            a = min(en - st, len(p1), p2.shape[0])
            onset_probs[st:st + a] += p1[:a]
            mc[st:st + a] += p2[:a]
            cnt[st:st + a] += 1
    cnt = np.maximum(cnt, 1)
    onset_probs /= cnt
    mc /= cnt[:, None]

    min_dist = max(1, int(20 / 1000 * 44100 / 512))
    v14_peaks, _ = find_peaks(onset_probs, height=0.3, distance=min_dist)
    final: dict[int, set] = {}
    for f in v14_peaks:
        final[f] = {int(np.argmax(mc[f]))}
    for f in v14_peaks:
        primary = int(np.argmax(mc[f]))
        for c in range(8):
            if c != primary and mc[f, c] >= mc_rescue_thr:
                final[f].add(c)

    notes = []
    for f, cs in final.items():
        onset = f * 512 / 44100
        idx_start = max(0, int(onset * 44100))
        idx_end = min(len(audio), idx_start + int(0.08 * 44100))
        seg_audio = audio[idx_start:idx_end]
        vel = round(float(np.clip(np.max(np.abs(seg_audio)) if len(seg_audio) > 0 else 0.5, 0.01, 1.0)), 4)
        for c in sorted(cs):
            notes.append({"type": STRUM_LANE_TO_TYPE[c], "onset_s": round(onset, 4), "velocity": vel})
    notes.sort(key=lambda n: (n["onset_s"], n["type"]))
    return notes


def _parse_adtof_midi(path, pitch_to_type) -> list[dict]:
    data = path.read_bytes()
    div = int.from_bytes(data[12:14], "big")
    off = 14
    notes = []
    for _ in range(data.count(b"MTrk")):
        ln = int.from_bytes(data[off + 4 : off + 8], "big")
        trk = data[off + 8 : off + 8 + ln]
        off += 8 + ln
        i = 0
        t = 0
        status = None
        while i < len(trk):
            v = 0
            sh = 0
            while True:
                b = trk[i]
                i += 1
                v |= (b & 0x7F) << sh
                sh += 7
                if not b & 0x80:
                    break
            t += v
            if trk[i] & 0x80:
                status = trk[i]
                i += 1
            st = status
            if st == 0xFF:
                typ = trk[i]
                i += 1
                ln2 = trk[i]
                i += 1
                i += ln2
                continue
            if st in (0xF0, 0xF7):
                continue
            d1 = trk[i]
            i += 1
            if (st & 0xF0) in (0xC0, 0xD0):
                continue
            d2 = trk[i]
            i += 1
            if (st & 0xF0) == 0x90 and d2 > 0:
                onset = t / div
                typ = pitch_to_type.get(d1)
                if typ:
                    notes.append({"type": typ, "onset_s": onset, "velocity": float(d2)})
    notes.sort(key=lambda n: (n["onset_s"], n["type"]))
    return notes


def transcribe_dispatch(
    x: np.ndarray | None, sr: int, method: str = "bands", threshold_preset: str = "tuned-mixwave"
) -> list[dict]:
    """Dispatch transcription to the specified backend.

    ``threshold_preset`` names an entry in :data:`THRESHOLD_PRESETS`; the
    backend-specific threshold config for ``method`` is passed through.
    """
    config = THRESHOLD_PRESETS.get(threshold_preset, {}).get(method)
    if method == "bands":
        return transcribe_bands(x, sr)
    if method == "madmom":
        raise ImportError("madmom transcription is unavailable; install madmom to use method='madmom'.")
    if method == "adtof":
        return transcribe_adtof(x, sr, thresholds=config) if config else transcribe_adtof(x, sr)
    if method == "dettato":
        return transcribe_dettato(x, sr, thresholds=config) if config else transcribe_dettato(x, sr)
    if method == "strum":
        mc_thr = (config or {}).get("mc_rescue_thr", 0.4)
        return transcribe_strum(x, sr, mc_rescue_thr=mc_thr)
    if method == "trigger":
        return trigger_transcribe(x, sr, config=config)
    raise ValueError(f"Unknown transcription method: {method}")


def _estimate_tempo(x: np.ndarray | None, sr: int) -> float | None:
    """Best-effort tempo (BPM) via librosa; None on any failure (no hard dep)."""
    if x is None:
        return None
    try:
        from librosa import beat
        tempo, _ = beat.beat_track(y=x, sr=sr)
        arr = np.atleast_1d(tempo)
        return float(arr[0])
    except Exception:
        return None


def transcribe(
    x: np.ndarray | None, sr: int, method: str = "bands", threshold_preset: str = "tuned-mixwave",
    groove: bool = True, flatten_cymbal: bool = False,
    velocity_smooth: bool = False,
) -> list[dict]:
    """Transcribe percussion audio into drum events.

    ``threshold_preset`` selects the per-backend threshold preset
    (see ``THRESHOLD_PRESETS``). ``groove`` runs post-processing cleanup
    (collapse near-duplicate onsets, adaptive tempo window); ``flatten_cymbal``
    merges ambiguous cymbal clusters into a single ``cymbal`` event;
    ``velocity_smooth`` remaps velocity percentiles onto [50, 120].
    """
    notes = transcribe_dispatch(x, sr, method=method, threshold_preset=threshold_preset)
    if not groove:
        return notes
    from drum_midi.groove import DrumEvent, groove_cleanup
    tempo = _estimate_tempo(x, sr)
    evs = [DrumEvent(n["onset_s"], n["type"], n.get("velocity", 100),
                     n.get("confidence", 1.0)) for n in notes]
    cleaned = groove_cleanup(evs, tempo_bpm=tempo, flatten_cymbal=flatten_cymbal,
                             velocity_smooth=velocity_smooth)
    return [{"type": e.instrument, "onset_s": e.time, "velocity": e.velocity}
            for e in cleaned]
