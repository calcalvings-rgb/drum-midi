# Architecture

Pipeline: **Audio → Transcribe (backend) → Groove cleanup → notes → MIDI export / web editor**

```
src/drum_midi/
  pipeline.py        # legacy orchestrator (input/stem/full, sep, output)
  transcribe.py      # dispatch backend: trigger | bands | dettato | strum | adtof | madmom
  trigger.py         # trigger backend: spectral flux onset + knee auto-calibrate + centroid type classifier
  groove.py          # groove cleanup post-processing (collapse dup, cluster, adaptive window)
  editor.py          # pure note ops: move_note/reassign_note/delete_note (return copy)
  midi_out.py        # write_midi (type 1 multi-track / type 0 single-track ch10 option)
  audio.py           # PCM/float WAV, other codecs via ffmpeg
  web_editor.py      # validated GM beat-state import and kit-aware type-0 MIDI export
  source_offer.py    # explicit-manifest corresponding-source archive
  webui_static/      # vanilla ES modules, GridSound, waveform and WAV transport
  maps.py            # DRUM_TYPES (14) + PRESETS (gm, mixwave_sleep_token)
  webui.py           # remote web UI: stdlib ThreadingHTTPServer, token auth, piano-roll editor
  gui.py / drum_midi.py  # desktop tkinter GUI
  _vendor/adtof_pytorch/  # ADTOF model (vendor, lazy-import)
```

## Browser editing state

The stdlib server retains token-authenticated transcription and legacy endpoints. The browser owns canonical GM notes in quarter-note beats, bounded delta history and selection. Editor export sends only key/when/duration/gain with BPM and kit; filtering does not remove notes from the exported take. GridSound is pinned and vendored; there is no npm build. WAV stays the audio clock: playhead beat = seconds × BPM / 60. Ruler seeking performs the inverse conversion. See [WEBUI.md](WEBUI.md) for endpoints and limits.

## Groove cleanup

`groove.py` — post-process after transcription:

- `collapse_duplicates` — same-instrument events within window → keep highest confidence.
- `cluster_events` / `merge_cymbal_cluster` — simultaneous events; if `flatten_cymbal=True`, cymbal cluster merges into 1 best-confidence event.
- `adaptive_window(tempo_bpm)` — merge window derived from tempo (16th-note), so at 220 BPM the window narrows (true 16ths survive), at 80 BPM it widens (double-hits collapse).
- Default **flatten cymbal off** → per-instrument detail kept; flatten is an option.

## Kit mapping

- `gm`: kick 36, snare 38, hat_closed 42, hat_open 46, tom 41/45/48, crash 49, ride 51.
- `mixwave_sleep_token`: kick 36, snare 38, side_stick 37, rimshot 40, hat_closed 75, hat_open 46, hat_pedal 44, rack 50/47, floor 43, crash 49/57, ride 51, ride_bell 53.

Note: FL Studio uses the C-2 convention — kick 36 shows as C1 in FL, not C3. Confirm pitch by MIDI number, not octave label.

> Disclaimer: measurement statistics and mappings derived from commercially-licensed groove packs (e.g. Sleep Token II by MixWave, GetGood Drums) are kept local-only and are not part of this repository.
