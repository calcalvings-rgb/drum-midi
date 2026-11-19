# Drum-to-MIDI — Design

## Intent
Convert drum audio into MIDI readable and editable in the FL Studio piano roll. Automatic detection: input is a drum stem or a full mix; if full, separate the stem first.

## Goals
- Any audio input → `.mid` output with GM drum mapping.
- Modular pipeline, each stage has modes; the user picks.
- Lightweight default: zero ML deps, runs locally on CPU.
- On-demand: heavy deps lazily installed, never idle at boot.

## Non-goals
- Not a DAW. No internal editing, quantize UI, or playback.
- No polyphonic non-drum (melody, vocals) → MIDI support.

## Approaches
1. **Full ML** (Demucs + madmom/basic-pitch) — accurate, heavy deps, heavy install.
2. **Pure lightweight** (HPSS + band-split onset, numpy) — zero deps, fast, coarse on dense mixes.
3. **Hybrid default** — lightweight startup (HPSS + band-split), optional ML upgrade (Demucs/madmom) per stage. **CHOSEN.**

## Left to builder
- Stem/full heuristic detection (spectral: is there pitched non-drum content?).
- Band-split onset: per-band flux → peak picking → map to note.
- Demucs/madmom wrappers, lazy install.
