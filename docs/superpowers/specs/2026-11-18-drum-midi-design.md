# Drum-to-MIDI — Design

## Intent
App konversi audio drum jadi MIDI, kebaca FL Studio piano roll, bisa diedit. Deteksi otomatis: input drum stem atau full mix; kalau full, pisah stem dulu.

## Goals
- Input audio apa aja → output `.mid` GM drum mapping.
- Pipeline modular, tiap stage ada mode, user pilih.
- Default ringan: nol dep ML, jalan lokal CPU.
- On-demand: dep berat lazily install, gak idle di boot.

## Non-goals
- Bukan DAW. Gak ada editing internal, quantize UI, playback.
- Gak support polyphonic non-drum (melodi, vokal) ke MIDI.

## Anti-goals
- Gak nambah dep idle di box. Gak ada server/daemon.
- Gak bikin web UI.

## Constraints
- Windows, box lokal (CPU; GPU kalau ada).
- User cost-conscious: backend berat optional, install pas dipakai.

## Approaches
1. **Full ML** (Demucs + madmom/basic-pitch) — akurat, dep gede, instalasi berat.
2. **Ringan murni** (HPSS + band-split onset, numpy) — zero dep, cepat, kasar di mix rame.
3. **Hybrid default** — startup ringan (HPSS + band-split), pilihan upgrade ML (Demucs/madmom) per stage. **DIPILIH.**

## Parts / user decisions
- GUI: Python tkinter, satu window pipeline.
- Stage: INPUT [auto|stem|full] → SEPARATION [none|HPSS|Demucs] → TRANSCRIPTION [band-split|madmom] → OUTPUT GM MIDI.
- Mapping GM: kick=36, snare=38, closed hat=42, open hat=46, tom low=41, tom mid=45, tom high=48, crash=49, ride=51.
- Format: `.mid` type 1, track per drum, tempo 120 default (konfigurable).

## Left to builder
- Deteksi stem/full heuristik (spektral: ada konten pitched non-drum?).
- Band-split onset: flux per band → peak pick → map ke note.
- Demucs/madmom wrappers, lazy install.
