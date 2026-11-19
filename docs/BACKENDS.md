# Transcription backends & dependencies

`transcribe.py` dispatches on `method`:

| method | model | requires | notes |
|---|---|---|---|
| `trigger` | heuristic (flux + knee + centroid) | numpy/scipy | default; onset recall 0.84 @ tes2, type accuracy 86% when onset correct |
| `bands` | heuristic band-split | numpy/scipy | lightweight, coarse on full mix |
| `dettato` | dettato (full GM, 11+ pitch) | torch + librosa + pretty_midi | maps straight to kit; needs source ≥40kHz; GPU-capable |
| `strum` | STRUM V14 + phase3 MC head | torch + torchaudio, `STRUM_ROOT` | best for dense genres (overlap/cymbal) |
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

Env: `.venv` (main 3.14, torch/Demucs/ADTOF), `.venv311` (3.11 TF/basic-pitch), `.venv312` (3.12 madmom). **Total ~2.9GB.**

## Use your own MIDI library

The groove generator (`drum_midi.groovegen`) works from **statistics you derive yourself** — it ships with no licensed groove data. Analyze the MIDI files you own (your own recordings, or packs you are licensed to use) with `experiments/ggd_analyze2.py` as the reference analyzer, output the JSON stats, and pass the path:

```powershell
.venv\Scripts\python.exe -m drum_midi.groovegen --source C:/path/to/your_stats.json --bars 2 --seed 7
```

`source` must be a path to your own stats JSON; the legacy `ggd`/`st` sources are gone. Per-style `slot_probs`/`slot_act`/`accents`/`overall` shape the generated groove — the engine is library-agnostic, so any MIDI corpus you have the rights to works.
