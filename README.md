# Drum MIDI

Aplikasi desktop Python untuk mengubah audio drum menjadi file MIDI Type 1 yang bisa diedit di piano roll FL Studio. GUI memakai tkinter. Mode default menggunakan NumPy, SciPy, dan pustaka standar Python; backend machine learning bersifat opsional.

## Cara pakai

Dari folder proyek, jalankan:

```powershell
.venv\Scripts\python.exe drum_midi.py
```

Atau jika Python dan dependensi sudah tersedia di PATH:

```bash
python drum_midi.py
```

Pilih file audio, mode pipeline, preset kit, dan tempo, lalu klik **Process**. Hasil `.mid` disimpan di lokasi output yang ditampilkan aplikasi.

## Tahapan pipeline dan mode

1. **Input** — `auto` mendeteksi apakah audio terdengar seperti drum stem atau full mix; `stem` dan `full` memaksa klasifikasi.
2. **Separation** — pada input full, `none` memakai mix apa adanya, `HPSS` menonjolkan bagian percussive, dan `Demucs` memilih backend opsional. Input yang dikenali sebagai stem melewati separation.
3. **Transcription** — `bands` memakai deteksi onset berbasis pita frekuensi (ringan, kasar untuk full mix); `ADTOF` memakai model drum terlatih (Zehren et al., 5 kelas: kick/snare/tom/hat/crash) — akurat untuk full mix; `madmom` backend opsional.
4. **Output** — MIDI Type 1, tempo awal 120 BPM, dengan track terpisah per tipe drum.

`auto` dan `bands` adalah pilihan ringan yang tersedia tanpa model ML. Hasil mode ringan berupa estimasi onset dan bisa kurang akurat pada mix yang padat.

## Preset drum

- `gm` — General MIDI: kick 36, snare 38, closed hat 42, open hat 46, tom low/mid/high 41/45/48, crash 49, ride 51.
- `mixwave_sleep_token` — mapping kit Mixwave Sleep Token, termasuk kick 36, snare 38, closed hat 75, open hat 46, rack/floor tom, crash, ride, dan ride bell.

## Instalasi dependensi

Gunakan Python 3.11 atau lebih baru. Dari folder proyek, buat virtual environment dan pasang dependensi dasar:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install numpy scipy pytest
```

`tkinter` biasanya disertakan pada distribusi Python Windows. Tidak ada instalasi backend ML saat aplikasi dibuka.

### Upgrade backend opsional

- **MP3/format non-WAV:** pasang FFmpeg dan pastikan `ffmpeg` tersedia di PATH. Decoder baru dipanggil saat input non-WAV diminta.
- **Demucs:** pasang dengan `.venv\Scripts\python.exe -m pip install demucs`; pilih separation `Demucs` saat diperlukan.
- **madmom:** pasang dengan `.venv\Scripts\python.exe -m pip install madmom`; pilih transcription `madmom` saat diperlukan. Ketersediaan instalasi dapat bergantung pada versi Python dan platform.
- **ADTOF:** model sudah di-vendor di `src/drum_midi/_vendor/adtof_pytorch` (termasuk bobot). Cukup pastikan `torch`, `librosa`, dan `pretty_midi` terpasang; pilih transcription `ADTOF`.

Aplikasi tidak memasang paket opsional secara otomatis. Jika backend belum terpasang, aplikasi memberi pesan instalasi saat mode itu dipilih.

## Fixtures sintetis

Buat ulang fixture WAV yang dipakai tes:

```powershell
.venv\Scripts\python.exe -m tests.make_fixtures
```

Generator membuat `fixtures/drum_stem.wav` (drum saja) dan `fixtures/drum_full.wav` (drum ditambah nada sinus berkelanjutan), berdasarkan fungsi sintesis di `tests/test_detect.py`.

## Menjalankan tes

```powershell
.venv\Scripts\python.exe -m pytest --basetemp=.pytest_tmp -p no:cacheprovider
```
