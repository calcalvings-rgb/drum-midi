# Drum-to-MIDI

Convert drum audio (full mix or stem) into a MIDI file editable in the FL Studio piano roll. Desktop app + remote web UI.

## Architecture

Pipeline: **Audio → Transcribe (backend) → Groove cleanup → notes → MIDI export / web editor**

```
src/drum_midi/
  pipeline.py        # legacy orchestrator (input/stem/full, sep, output)
  transcribe.py      # dispatch backend: trigger | bands | dettato | strum | adtof | madmom
  trigger.py         # trigger backend: spectral flux onset + knee auto-calibrate + centroid type classifier
  groove.py          # groove cleanup post-processing (collapse dup, cluster, adaptive window)
  editor.py          # pure note ops: move_note/reassign_note/delete_note (return copy)
  midi_out.py        # write_midi (type 1 multi-track / type 0 single-track ch10 option)
  audio.py           # parse_audio (wav/pcm, mp3 via decode_mp3)
  maps.py            # DRUM_TYPES (14) + PRESETS (gm, mixwave_sleep_token)
  webui.py           # remote web UI: stdlib ThreadingHTTPServer, token auth, piano-roll editor
  gui.py / drum_midi.py  # desktop tkinter GUI
  _vendor/adtof_pytorch/  # ADTOF model (vendor, lazy-import)
```

Transcription backends (`method`):

| method | model | requires | notes |
|---|---|---|---|
| `trigger` | heuristic (flux + knee + centroid) | numpy/scipy | default; onset recall 0.84 @ tes2, type accuracy 86% when onset correct |
| `bands` | heuristic band-split | numpy/scipy | lightweight, coarse on full mix |
| `dettato` | dettato (full GM, 11+ pitch) | torch + librosa + pretty_midi | maps straight to kit; needs source ≥40kHz; GPU-capable |
| `strum` | STRUM V14 + phase3 MC head | torch + torchaudio, `STRUM_ROOT` | best for dense genres (overlap/cymbal) |
| `adtof` | ADTOF (5 classes) | torch + librosa + pretty_midi | vendored in repo |
| `madmom` | madmom | optional `.venv312` package | needs Python 3.12 |

**Groove cleanup** (`groove.py`, post-process after transcription):
- `collapse_duplicates` — same-instrument events within window → keep highest confidence.
- `cluster_events` / `merge_cymbal_cluster` — simultaneous events; if `flatten_cymbal=True`, cymbal cluster merges into 1 best-confidence event.
- `adaptive_window(tempo_bpm)` — merge window derived from tempo (16th-note), so at 220 BPM the window narrows (true 16ths survive), at 80 BPM it widens (double-hits collapse).
- Default **flatten cymbal off** → per-instrument detail kept; flatten is an option.

## Web UI (remote control)

```powershell
# from project folder
.venv\Scripts\python.exe -m drum_midi.webui --host 0.0.0.0 --port 8123 --dir PATH [--token X]
```

- Pure stdlib (`ThreadingHTTPServer`) — no flask/fastapi.
- Token required on all `/api` (`X-Auth-Token`, hmac.compare_digest); random if unset, printed at start for LAN.
- Endpoints: `GET /` (single-page HTML), `GET /api/files`, `GET /api/meta`, `POST /api/run`, `POST /api/edit`, `POST /api/export`, `POST /api/upload?name=<file>`.
- Piano-roll editor (canvas): lane per drum type, drag bar = retime, cross-lane drag = retype, zoom/pan (wheel + buttons), type filter. Select note → edit panel (reassign / ±10ms / del).
- Upload: raw audio bytes, sanitized name (`Path(name).name`), extension whitelist, Content-Length check.

## Dependencies

**Core (required):** Python 3.14 venv `.venv`, `numpy`, `scipy`, `pytest`. Rest is stdlib (`http.server`, `hmac`, `dataclasses`, etc). `tkinter` ships with Windows. **No automatic ML backend install.**

**Optional (per backend):**

| backend | pip | notes |
|---|---|---|
| trigger / bands / groove | — | stdlib + numpy/scipy |
| dettato | `torch librosa pretty_midi` | GPU: torch cu128 (`--index-url https://download.pytorch.org/whl/cu128`) |
| strum | `torch torchaudio` | + `STRUM_ROOT` = checkout `C:/Users/ccalv/workspace/coding/strum` (V14 + phase3 checkpoints, ~1GB) |
| adtof | `torch librosa pretty_midi` | model vendored in repo |
| madmom | `madmom` | Python 3.12 (`.venv312`) |
| mp3/other formats | ffmpeg | `ffmpeg` required on PATH |

Env: `.venv` (main 3.14, torch/Demucs/ADTOF), `.venv311` (3.11 TF/basic-pitch), `.venv312` (3.12 madmom). **Total ~2.9GB.**

## Usage

Desktop GUI:
```powershell
.venv\Scripts\python.exe drum_midi.py
```

Web UI (LAN):
```powershell
.venv\Scripts\python.exe -m drum_midi.webui --host 0.0.0.0 --port 8123 --dir "C:/Users/ccalv/workspace/coding/drum-midi/challange" --token <token>
```
open `http://<IP-desktop>:8123/?token=<token>` from another device.

## Hermes workflow (drums → FL)

This repo is a pure engine (library); FL Studio integration goes through **[flstudio-mcp](https://github.com/calcalvings-rgb/flstudio-mcp)**, orchestrated by Hermes. Pattern used:

```
record real drums (WAV) → transcribe (dettato GPU) → humanize → apply in FL @ song tempo
```

1. **Transcribe**: `drum_midi.transcribe.transcribe(x, sr, method="dettato", threshold_preset="tuned-mixwave", groove=True)` → `[{type, onset_s, velocity}]`.
2. **MIDI**: `drum_midi.midi_out.write_midi(notes, out, preset="mixwave_sleep_token", tempo=...)`.
3. **Song tempo**: librosa `beat_track` on full mix (must be mono — `np.mean(y, axis=1)`; stereo makes librosa allocate hundreds of GB). Bass stem alone is invalid (lower tempo).
4. **Set FL tempo + apply notes** via flstudio-mcp daemon `:9787`:
   - `set_tempo` / `get_tempo` for tempo.
   - `apply_notes` is a top-level op (`{"op":"apply_notes","notes":...,"mode":"replace","trigger":true}`), NOT a `cmd` inside `call`. `time_bars = t * BPM / 240.0`.
   - If notes don't appear: run "MCP Apply" once from Piano roll → Scripting (the only manual step; arming the shortcut is not automatable).
5. **Humanize**: downbeat (kick/snare) solid — jitter ±1.5ms, vel ±3%; off-beat (hi-hat) alive — jitter ±5ms, vel ±8%; cymbal in between.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest --basetemp=.pytest_tmp -p no:cacheprovider
```
(BOTH flags required: `--basetemp=.pytest_tmp` because default points at hermes scratch → teardown fails on Windows; `-p no:cacheprovider` because TMPDIR hermes scratch.)

Synthetic fixtures: `python -m tests.make_fixtures`.

## Kit mapping

- `gm`: kick 36, snare 38, hat_closed 42, hat_open 46, tom 41/45/48, crash 49, ride 51.
- `mixwave_sleep_token`: kick 36, snare 38, side_stick 37, rimshot 40, hat_closed 75, hat_open 46, hat_pedal 44, rack 50/47, floor 43, crash 49/57, ride 51, ride_bell 53.

Note: FL Studio uses the C-2 convention — kick 36 shows as C1 in FL, not C3. Confirm pitch by MIDI number, not octave label.

> Disclaimer: measurement statistics and mappings derived from commercially-licensed groove packs (e.g. Sleep Token II by MixWave, GetGood Drums) are kept local-only and are not part of this repository.
