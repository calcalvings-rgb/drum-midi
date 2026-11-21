# Transcription backends & dependencies

`transcribe.py` dispatches on `method`:

| method | model | requires | notes |
|---|---|---|---|
| `trigger` | heuristic (flux + knee + centroid) | numpy/scipy | default web engine; local calibration results are fixture-specific, not a general accuracy guarantee |
| `bands` | heuristic band-split | numpy/scipy | lightweight, coarse on full mix |
| `dettato` | dettato (full GM, 11+ pitch) | torch + librosa + pretty_midi | normalized to canonical drum events before web kit export; needs source ≥40kHz; GPU-capable |
| `strum` | STRUM V14 + phase3 MC head | torch + torchaudio, `STRUM_ROOT` | optional dense/overlapping-hit backend; compare against your own recordings |
| `adtof` | ADTOF (5 classes) | torch + librosa + pretty_midi | vendored in repo |
| `madmom` | madmom | optional `.venv312` package | needs Python 3.12 |

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

Local development has used `.venv`, `.venv311` and `.venv312`; these are optional per-backend environments, not bundled installs. Their disk use varies by installed wheels and model caches.

For the web editor/trigger path, install `requirements-web.txt` (NumPy, SciPy, mido). Desktop theme dependencies are in `requirements-gui.txt` (sv-ttk). Install pytest separately for Python tests. Node's built-in runner is needed only for frontend tests. No React/Vite/Node runtime is required by the served UI.

## Use your own MIDI library

The groove generator (`drum_midi.groovegen`) works from **statistics you derive yourself** — it ships with no licensed groove data. Analyze the MIDI files you own (your own recordings, or packs you are licensed to use) with `experiments/ggd_analyze2.py` as the reference analyzer, output the JSON stats, and pass the path:

```powershell
.venv\Scripts\python.exe -m drum_midi.groovegen --source C:/path/to/your_stats.json --bars 2 --seed 7
```

`source` must be a path to your own stats JSON; the legacy `ggd`/`st` sources are gone. Per-style `slot_probs`/`slot_act`/`accents`/`overall` shape the generated groove — the engine is library-agnostic, so any MIDI corpus you have the rights to works.
