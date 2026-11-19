# Drum-to-MIDI

Ubah audio drum (full mix atau stem) menjadi file MIDI yang bisa diedit di piano roll FL Studio. Desktop app + remote web UI.

## Arsitektur

Pipeline: **Audio → Transcribe (backend) → Groove cleanup → notes → MIDI export / web editor**

```
src/drum_midi/
  pipeline.py        # orchestrator lama (input/stem/full, sep, output)
  transcribe.py      # dispatch backend: trigger | bands | dettato | strum | adtof | madmom
  trigger.py         # backend trigger: spectral flux onset + knee auto-calibrate + centroid type classifier
  groove.py          # groove cleanup post-processing (collapse dup, cluster, adaptive window)
  editor.py          # pure note ops: move_note/reassign_note/delete_note (return copy)
  midi_out.py        # write_midi (type 1 multi-track / opsi type 0 single-track ch10)
  audio.py           # parse_audio (wav/pcm, mp3 via decode_mp3)
  maps.py            # DRUM_TYPES (14) + PRESETS (gm, mixwave_sleep_token)
  webui.py           # remote web UI: stdlib ThreadingHTTPServer, token auth, piano-roll editor
  gui.py / drum_midi.py  # desktop tkinter GUI
  _vendor/adtof_pytorch/  # ADTOF model (vendor, lazy-import)
```

Backend transkripsi (`method`):
| method | model | butuh | catatan |
|---|---|---|---|
| `trigger` | heuristik (flux + knee + centroid) | numpy/scipy | default; onset recall 0.84 @ tes2, type accuracy 86% saat onset bener |
| `bands` | heuristik band-split | numpy/scipy | ringan, kasar di full mix |
| `dettato` | dettato (GM penuh, 11+ pitch) | torch + librosa + pretty_midi | mapping langsung ke kit; butuh source ≥40kHz; GPU-capable |
| `strum` | STRUM V14 + phase3 MC head | torch + torchaudio, `STRUM_ROOT` | terbaik buat genre rapat (overlap/cymbal) |
| `adtof` | ADTOF (5 kelas) | torch + librosa + pretty_midi | vendor di repo |
| `madmom` | madmom | paket opsional `.venv312` | butuh Python 3.12 |

**Groove cleanup** (`groove.py`, post-process setelah transcribe):
- `collapse_duplicates` — event sama-instrument dalam window → keep confidence tertinggi.
- `cluster_events` / `merge_cymbal_cluster` — event simultan; kalau `flatten_cymbal=True`, kumpulan cymbal di-merge ke 1 event conf terbaik.
- `adaptive_window(tempo_bpm)` — window merge diturunkan dari tempo (16th-note), jadi di 220 BPM window sempit (16th asli selamat), di 80 BPM lebar (double-hit ke-collapse).
- Default **flatten cymbal off** → detail per-instrument dipertahankan; flatten = opsi.

## Web UI (remote control)

```powershell
# dari folder proyek
.venv\Scripts\python.exe -m drum_midi.webui --host 0.0.0.0 --port 8123 --dir PATH [--token X]
```

- Stdlib murni (`ThreadingHTTPServer`) — tanpa flask/fastapi.
- Token wajib di semua `/api` (`X-Auth-Token`, hmac.compare_digest); random kalau tak di-set, di-print saat start untuk LAN.
- Endpoint: `GET /` (HTML single-page), `GET /api/files`, `GET /api/meta`, `POST /api/run`, `POST /api/edit`, `POST /api/export`, `POST /api/upload?name=<file>`.
- Editor piano roll (canvas): lane per type drum, drag bar = ubah timing, drag lintas lane = ganti type, zoom/pan (wheel + tombol), filter type. Select note → panel edit (reassign / −+10ms / del).
- Upload: raw audio bytes, nama disanitize (`Path(name).name`), ekstensi whitelist, cek Content-Length.

## Deps

**Dasar (wajib):** Python 3.14 venv `.venv`, `numpy`, `scipy`, `pytest`. Stdlib sisanya (`http.server`, `hmac`, `dataclasses`, dll). `tkinter` bawaan distribusi Windows. **Tidak ada instalasi backend ML otomatis.**

**Opsional (per backend):**
| backend | pip | catatan |
|---|---|---|
| trigger / bands / groove | — | stdlib + numpy/scipy |
| dettato | `torch librosa pretty_midi` | GPU: torch cu128 (`--index-url https://download.pytorch.org/whl/cu128`) |
| strum | `torch torchaudio` | + `STRUM_ROOT` = checkout `C:/Users/ccalv/workspace/coding/strum` (V14 + phase3 checkpoints, ~1GB) |
| adtof | `torch librosa pretty_midi` | model vendor di repo |
| madmom | `madmom` | Python 3.12 (`.venv312`) |
| mp3/format lain | ffmpeg | wajib `ffmpeg` di PATH |

Env: `.venv` (main 3.14, torch/Demucs/ADTOF), `.venv311` (3.11 TF/basic-pitch), `.venv312` (3.12 madmom). **Total ~2.9GB.**

## Cara pakai

Desktop GUI:
```powershell
.venv\Scripts\python.exe drum_midi.py
```

Web UI (LAN):
```powershell
.venv\Scripts\python.exe -m drum_midi.webui --host 0.0.0.0 --port 8123 --dir "C:/Users/ccalv/workspace/coding/drum-midi/challange" --token <token>
```
buka `http://<IP-desktop>:8123/?token=<token>` dari device lain.

## Workflow via Hermes (drum → FL)

Repo ini adalah mesin murni (library); integrasi FL Studio **lewat [flstudio-mcp](https://github.com/calcalvings-rgb/flstudio-mcp)**, diorchestrasi oleh Hermes. Pola yang dipakai:

```
main drum asli (WAV) → transcribe (dettato GPU) → humanize → apply ke FL @ tempo lagu
```

1. **Transcribe**: `drum_midi.transcribe.transcribe(x, sr, method="dettato", threshold_preset="tuned-mixwave", groove=True)` → `[{type, onset_s, velocity}]`.
2. **MIDI**: `drum_midi.midi_out.write_midi(notes, out, preset="mixwave_sleep_token", tempo=...)`.
3. **Tempo lagu**: librosa `beat_track` pada full mix (harus mono — `np.mean(y, axis=1)`; stereo bikin librosa alokasi ratusan GB). Stem bass doang gak valid (tempo lebih rendah).
4. **Set tempo FL + apply notes** via daemon flstudio-mcp `:9787`:
   - `set_tempo` / `get_tempo` untuk tempo.
   - `apply_notes` = op top-level (`{"op":"apply_notes","notes":...,"mode":"replace","trigger":true}`), BUKAN `cmd` di dalam `call`. `time_bars = t * BPM / 240.0`.
   - Kalau notes tak muncul: jalankan "MCP Apply" sekali dari Piano roll → Scripting (satu-satunya langkah manual; arm shortcut tidak bisa di-automasi).
5. **Humanize**: downbeat (kick/snare) solid — jitter ±1.5ms, vel ±3%; off-beat (hi-hat) hidup — jitter ±5ms, vel ±8%; cymbal di tengah.

## Tes

```powershell
.venv\Scripts\python.exe -m pytest --basetemp=.pytest_tmp -p no:cacheprovider
```
(WAJIB dua flag: `--basetemp=.pytest_tmp` karena default nunjuk hermes scratch → teardown gagal di Windows; `-p no:cacheprovider` karena TMPDIR hermes scratch.)

Fixtures sintetik: `python -m tests.make_fixtures`.

## Mapping kit

- `gm`: kick 36, snare 38, hat_closed 42, hat_open 46, tom 41/45/48, crash 49, ride 51.
- `mixwave_sleep_token`: kick 36, snare 38, side_stick 37, rimshot 40, hat_closed 75, hat_open 46, hat_pedal 44, rack 50/47, floor 43, crash 49/57, ride 51, ride_bell 53.

Catatan: FL Studio pakai konvensi C-2 — kick 36 tampil sebagai C1 di FL, bukan C3. Konfirmasi pitch pakai MIDI number, bukan label oktav UI.
