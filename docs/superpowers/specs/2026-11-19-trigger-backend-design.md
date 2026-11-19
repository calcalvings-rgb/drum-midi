# Drum Trigger Backend — Design

Date: 2026-11-19
Status: Draft for approval

## Intent

Input mono drum mix (single track) → output MIDI mapped to Mixwave Sleep Token kit, aimed at dense genres that use all drum types where existing transcription backends (ADTOF / dettato / STRUM / bands) lose or misassign overlapping simultaneous hits.

The core problem with existing backends: they run *global* onset detection, then *classify* each hit into a pad. In dense genres, simultaneous hits collapse into one peak (or get misclassified) because spectral bands overlap. The trigger approach flips this: detect per-band, independently, then merge.

## Goals

- Robust detection in dense genres (all pads active, simultaneous hits preserved as multi-notes).
- Per-band adaptive threshold relative to band-specific noise floor (not global peak fraction) — this is the main genre-inconsistency fix.
- Velocity from envelope peak, with a user-configurable velocity curve (default curve provided).
- Backend integrable with existing pipeline/GUI as a new mode (`tx='trigger'`).

## Non-goals / anti-goals

- NOT a real-time trigger; offline batch processing (input file → MIDI).
- No ML model training in phase 1. Pure DSP.
- Not solving physical impossibility: from a single mono mix, tom vs snare vs crash/hat spectral overlap has a ceiling. The trigger reduces misassignment via transient-shape features but cannot guarantee 100% in overlap-all cases.

## Constraints

- Input: mono or stereo (downmixed) drum-only WAV, >= ~40kHz desired.
- Output: MIDI mapped via `maps.PRESETS['mixwave_sleep_token']`.
- Reuse existing `audio.py` wav reading, `midi_out.write_midi`, GUI conventions.
- Python 3.14, numpy/scipy only for phase 1 (no new ML deps). Future template matching may add librosa.

## Approaches

1. **Per-band trigger (chosen).** 6-band filterbank + energy envelopes, independent per-band onset detection, overlap merge. Robust to density because quiet bands stay silent while active bands trigger.
2. Extend `transcribe_bands` heuristics. Rejected: global-peak-then-classify is the root failure; incremental tweaks won't fix simultaneous collapse.
3. STRUM/dettato with tuning. Rejected: they're ML classifiers; the user wants a trigger paradigm, and these already fail in dense genre at the classification step.

## Design

### Module: `src/drum_midi/trigger.py`

```
trigger_transcribe(x, sr, config=None) -> list[dict]
# each dict: {'type': str, 'onset_s': float, 'velocity': float}
```

Pipeline stages:

1. **Band split** — 6 bands via `scipy.signal.butter` (order ~4) + `sosfilt`:
   - kick: 20–150 Hz
   - snare: 150–500
   - floor: 500–1200
   - rack2: 1200–2500
   - rack1: 2500–5000
   - hat: 5000– sr/2 (cap)
2. **Envelope** — per band: rectify + low-pass / `hilbert` magnitude, hop-resolution ~5–10 ms.
3. **Adaptive threshold** — per band: `thr = k * noise_floor_band` where noise floor = percentile (e.g. p90) of short-term energy below running envelope; `k` default ~3. Detects onsets via envelope crossing with min-distance (retrigger lockout) per band.
4. **Transient shape** — per onset, from band envelope: attack time, decay time, peak. Used to disambiguate overlapping classes (crash = long decay vs hat = short; tom vs snare attack).
5. **Overlap merge** — onsets within a small window (e.g. ±10 ms) across bands → one event with multiple pad notes (kick+snare = 2 notes). Merge is the anti-collapse fix.
6. **Velocity** — from envelope peak (0–1), passed through configurable velocity curve `velocity_curve(peak)`. Default curve: linear-ish with soft knee; user can override (flexible).
7. **Mapping** — type → `mixwave_sleep_token` pitch.

### Config (per user, saved as JSON preset)

```
{
  "bands": {  # optional per-band overrides
    "kick":  {"low": 20, "high": 150, "threshold_k": 3.0, "type": "kick"},
    ...
  },
  "velocity_curve": [  # piecewise-linear: (peak_frac, velocity)
    [0.0, 0.0], [0.5, 0.55], [1.0, 1.0]
  ],
  "min_distance_s": 0.04,
  "overlap_window_s": 0.010
}
```

GUI: reuse existing window; a small panel to edit velocity curve + per-band threshold/type (phase 1 minimal: default preset + file-based config).

### Phase 2 (separate plan, not built now): template matching

From detection results, user selects a detected hit segment as reference; the app extracts a spectral/envelope signature; other hits with similar signature auto-group into the same type. Enables user-defined "classification" like Waves InTrigger. Source of reference is the mix itself (per user decision). Not in this build.

## Verification

- Synthetic fixtures (extend `tests/`): dense simultaneous-hit clip (kick+snare+crash at same onset) must produce 3 notes, not 1.
- Band isolation: each band alone triggers only its own type.
- Velocity: peak → curve mapping round-trips.
- Real test: run on a dense-genre mono mix; compare note count/distribution to existing backends (report numbers, not claims).
- Full suite via `.venv/Scripts/python.exe -m pytest --basetemp=.pytest_tmp -p no:cacheprovider`.

## Build order

1. `trigger.py` with filterbank + envelope + threshold + velocity + merge.
2. Synthetic tests.
3. Wire `tx='trigger'` into `pipeline.py` + GUI dropdown.
4. Velocity curve + per-band config preset (default).
5. Real dense-genre verification.
