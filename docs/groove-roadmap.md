# Groove Cleanup Roadmap

## Context

```
Drum → Mixer → Stereo Mix → Audio Transcription → MIDI
```

Karena source bukan multitrack maupun trigger, fokus project bukan **Perfect Instrument Recovery** melainkan **Groove Recovery**.

Tujuan utama: **menghasilkan MIDI yang cepat diedit manusia**, bukan MIDI yang 100% identik.

---

## PR-001 — Confidence Gate

**Problem:** backend sering menghasilkan event confidence rendah yang tetap lolos.
```
kick 0.95
snare 0.83
ride 0.18
hh 0.21
```
Noise ikut masuk pipeline.

**Solution:** filter event sebelum clustering.

```python
groove_cleanup(events, min_confidence=0.35)
```

**Flow:** Raw Events → Confidence Filter → Duplicate Collapse → Cluster Merge → MIDI

**Expected:** mengurangi false positive, terutama ride/hh/crash berconfidence rendah.

---

## PR-002 — Cymbal Sustain Suppression

**Problem:** crash sustain sering menghasilkan event tambahan.
```
10.000 Crash 0.95
10.080 Cymbal 0.30
10.140 Cymbal 0.25
```
Padahal hanya satu pukulan.

**Solution:** sustain guard window.

```python
tail_window_ms=150
```

**Logic:** jika event A = cymbal confidence tinggi, lalu event B = cymbal confidence rendah muncul dalam 150ms setelahnya → buang event B.

**Expected:** mengurangi spam cymbal.

---

## PR-003 — Regression Test Suite

**Problem:** heuristic baru berpotensi merusak groove lama.

**Solution:** simpan semua bug yang pernah ditemukan.

```
tests/regression/
  cymbal_tail.py
  dense_chorus.py
  sleep_token_fill.py
  double_kick.py
```

**Rule:** setiap bug → regression test → fix. Tidak boleh langsung fix tanpa test.

---

## PR-004 — Velocity Cleanup

**Problem:** output velocity backend sering ekstrem.
```
127, 10, 123, 15, 119
```

**Solution:** velocity smoothing.

Mode:
- **Percentile:** 5% → 50, 95% → 120
- **Compress:** input 10-127 → output 50-120

**Goal:** lebih usable di FL Studio.

**Status: DONE (master).** `velocity_smooth=False` default; toggle **smooth velocity → 50-120** di UI. Belum divalidasi vs genre nyata.

---

## PR-005 — Groove Density Detection

**Problem:** model sulit membedakan crash spam vs HH pattern.

**Solution:** analisis densitas event. Jika ditemukan pola 1/8, 1/16, 1/16, 1/16 berulang → anggap **continuous groove**, bukan accent hit.

**Status: DONE (master).** `is_continuous_groove` / `dense_groove_indices` + `protect_grooves=False` default; melindungi groove seragam dari sustain suppression (ghost note 16th lemah). Catatan: tes2 hanya 1 crash → on=off (butuh sample cymbal/HH-heavy utk validasi efek nyata).

---

## PR-006 — Instrument Recovery Layer

**Status: jangan dikerjakan sekarang.**

**Reason:** masalah utama saat ini = **timing**, bukan exact instrument.

**Future pipeline:**
```
Audio → Transcriber → Groove Recovery → Kick/Snare/Tom/Cymbal → Instrument Recovery → HH/Crash/Ride/China
```

**Success metrics:**
- BAD: crash accuracy, ride accuracy, china accuracy
- GOOD: hit timing accuracy, kick recall, snare recall, groove similarity, editing time reduction

---

## Final product philosophy

Target:
```
Audio → Transcribe → 10 menit cleanup → Done
```

Bukan:
```
Audio → Perfect AI → Done
```

Karena untuk stereo drum mix, perfect reconstruction sering kali secara informasi memang tidak mungkin. Yang penting: **groove selamat, workflow selamat, kewarasan user selamat.**
