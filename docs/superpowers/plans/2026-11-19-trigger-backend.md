# Drum Trigger Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `trigger` transcription backend — per-band DSP trigger engine — to the drum-midi app, robust to dense genres with all pads active.

**Architecture:** A new module `src/drum_midi/trigger.py` implements a 6-band filterbank + energy-envelope detector with per-band adaptive thresholds, retrigger lockout, velocity-curve mapping, and across-band overlap merge (multi-note events). It dispatches through the existing `transcribe`/`transcribe_dispatch` function as `method='trigger'`, so the pipeline and GUI need minimal wiring.

**Tech Stack:** Python 3.14, numpy, scipy (`signal.butter`/`sosfilt`, `signal.find_peaks`). No new ML deps.

**Spec:** `docs/superpowers/specs/2026-11-19-trigger-backend-design.md`

## Global Constraints

- Input: mono or stereo (downmixed) drum-only WAV. `sr` from `parse_audio`.
- Events: `{'type': str, 'onset_s': float, 'velocity': float}`, sorted by `(onset_s, type)`.
- Types must be valid `config.DRUM_TYPES` (kick, snare, side_stick, rimshot, hat_closed, hat_open, hat_pedal, rack1, rack2, floor, crash1, crash2, ride, ride_bell). Backend maps its bands to these.
- Velocity in [0,1]. Velocity curve is piecewise-linear, default `[[0.0,0.0],[0.5,0.55],[1.0,1.0]]`.
- No new third-party deps beyond numpy/scipy. No ML model load.
- Tests run with `.venv/Scripts/python.exe -m pytest --basetemp=.pytest_tmp -p no:cacheprovider`.
- Commit per task. Do NOT push; local repo.

## Review Focus

1. Simultaneous hits across different bands (kick+snare+crash at same onset) must produce 3 events, not 1 (the anti-collapse guarantee). Pinned in Task 1.
2. A single band alone (e.g. only kick audio) must trigger only that band's type, no phantom hits elsewhere. Pinned in Task 1.
3. Velocity must pass through the configured curve: a peak below the first breakpoint maps accordingly; peak=1.0 → velocity=1.0. Pinned in Task 2.
4. Empty/near-silent input returns `[]` without error. Pinned in Task 1.
5. After wiring (Task 4), `run_pipeline(mode={'input':'stem','tx':'trigger'})` end-to-end writes a MIDI file with the expected notes. Pinned in Task 4.

---

### Task 1: Trigger engine core (bands, envelopes, detection)

**Files:**
- Create: `src/drum_midi/trigger.py`
- Test: `tests/test_trigger.py`

**Interfaces:**
- Consumes: nothing (pure numpy/scipy).
- Produces: `trigger_transcribe(x: np.ndarray | None, sr: int, config: dict | None = None) -> list[dict]` — returns event dicts sorted by `(onset_s, type)`. `config=None` uses defaults.

**Band definition** (fixed defaults, Hz, `scipy.signal.butter` order 4, `sosfilt`):
- kick: 20–150
- snare: 150–500
- floor: 500–1200
- rack2: 1200–2500
- rack1: 2500–5000
- hat: 5000–sr/2 (cap at sr/2 - 50)

- [ ] **Step 1: Write the failing tests** — `tests/test_trigger.py`:

```python
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from drum_midi.trigger import trigger_transcribe

def make_click(sr, freq, dur=0.04, amp=1.0):
    t = np.arange(int(sr*dur)) / sr
    # low-passed impulse-ish tone with decay
    y = amp * np.sin(2*np.pi*freq*t) * np.exp(-t*40)
    return y

def test_simultaneous_hits_all_detected():
    sr = 44100
    kick = make_click(sr, 60, amp=1.0)
    snare = make_click(sr, 250, amp=0.8)
    crash = make_click(sr, 8000, amp=0.6)
    # stack all three at same onset
    audio = np.zeros(int(sr*0.5))
    audio[0:len(kick)] += kick
    audio[0:len(snare)] += snare
    audio[0:len(crash)] += crash
    notes = trigger_transcribe(audio, sr)
    types = {n["type"] for n in notes}
    # anti-collapse: kick, snare, and a high-band hit must each appear
    assert "kick" in types
    assert "snare" in types
    assert types & {"hat_closed", "crash1", "crash2", "ride"}

def test_band_isolation_no_phantom():
    sr = 44100
    audio = np.zeros(int(sr*0.4))
    audio[0:int(sr*0.04)] = make_click(sr, 60, amp=1.0)  # kick only
    notes = trigger_transcribe(audio, sr)
    types = {n["type"] for n in notes}
    assert types == {"kick"}

def test_empty_input_returns_empty():
    sr = 44100
    assert trigger_transcribe(np.zeros(int(sr*0.3)), sr) == []
    assert trigger_transcribe(None, sr) == []
```

- [ ] **Step 2: Run tests to verify they fail** — `pytest tests/test_trigger.py -v` → FAIL (ImportError, no module).

- [ ] **Step 3: Implement `src/drum_midi/trigger.py`** — signature:

```python
BANDS = [
    ("kick", 20, 150), ("snare", 150, 500), ("floor", 500, 1200),
    ("rack2", 1200, 2500), ("rack1", 2500, 5000),
]
DEFAULT_CONFIG = {
    "threshold_k": 3.0,
    "min_distance_s": 0.04,
    "overlap_window_s": 0.010,
    "hat_min_hz": 5000.0,
    "velocity_curve": [[0.0, 0.0], [0.5, 0.55], [1.0, 1.0]],
}

def _band_envelope(y, sr, low, high):
    # butterworth bandpass, then rectify + lowpass to ~100 Hz envelope
    ...

def trigger_transcribe(x, sr, config=None) -> list[dict]:
    ...
```

Approach: downmix to mono; for each band compute `sosfilt` bandpass + envelope; derive per-band noise floor as p90 of short-term envelope energy; adaptive threshold `thr = threshold_k * floor`; `signal.find_peaks` on each band's envelope with `distance` from `min_distance_s`; for each peak compute onset, peak value (→ velocity), and decay time (envelope fall below 50% of peak — used to separate hat vs crash, pin in Task 2/3). Collect per-band hits. Then overlap-merge: hits across bands within `overlap_window_s` of each other merge into one timestamp; each contributing band emits its own type (multi-note). Skip bands whose `sr/2 < low`.

- [ ] **Step 4: Run tests to verify they pass** — `pytest tests/test_trigger.py -v` → PASS.

- [ ] **Step 5: Commit** — `git add src/drum_midi/trigger.py tests/test_trigger.py && git commit -m "feat: trigger backend core (band envelopes + per-band detection + overlap merge)"`

---

### Task 2: Velocity curve mapping

**Files:**
- Modify: `src/drum_midi/trigger.py`
- Test: `tests/test_trigger.py`

**Interfaces:**
- Consumes: `DEFAULT_CONFIG["velocity_curve"]` from Task 1.
- Produces: `apply_velocity_curve(peak: float, curve: list[list[float]]) -> float` — piecewise-linear interpolation over `curve` (list of `[x,y]` breakpoints, ascending x, x in [0,1]); clamps to [0,1].

- [ ] **Step 1: Write the failing tests**:

```python
from drum_midi.trigger import apply_velocity_curve, DEFAULT_CONFIG

def test_velocity_curve_interp():
    c = DEFAULT_CONFIG["velocity_curve"]
    # x=0 -> 0; x=1 -> 1; midpoint maps to middle breakpoint
    assert apply_velocity_curve(0.0, c) == 0.0
    assert apply_velocity_curve(1.0, c) == 1.0
    assert apply_velocity_curve(0.5, c) == pytest.approx(0.55)
    # below first breakpoint: linear from (0,0) to first breakpoint
    assert 0.0 < apply_velocity_curve(0.25, c) < 0.55

def test_velocity_curve_clamp():
    c = DEFAULT_CONFIG["velocity_curve"]
    assert apply_velocity_curve(-0.5, c) == 0.0
    assert apply_velocity_curve(1.5, c) == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**.

- [ ] **Step 3: Implement `apply_velocity_curve(peak, curve)`** and call it in `trigger_transcribe` for each event's velocity (replacing raw peak). Use `numpy.interp` on the curve's x/y arrays.

- [ ] **Step 4: Run tests to verify they pass**.

- [ ] **Step 5: Commit** — `git commit -m "feat: velocity curve mapping for trigger backend"`

---

### Task 3: Transient-shape disambiguation (hat vs crash, tom vs snare)

**Files:**
- Modify: `src/drum_midi/trigger.py`
- Test: `tests/test_trigger.py`

**Interfaces:**
- Consumes: per-band peak decay time + peak from Task 1 detection.
- Produces: `classify_band(band_name: str, decay_s: float, config: dict) -> str` — returns the drum type for a band-level hit after applying decay-based adjustments.

- [ ] **Step 1: Write the failing tests**:

```python
from drum_midi.trigger import classify_band
from drum_midi import maps

def test_crash_vs_hat_by_decay():
    # hat band (high) with long decay -> crash/ride; short decay -> closed hat
    assert classify_band("hat", 0.35, {}) in {"crash1", "crash2", "ride"}
    assert classify_band("hat", 0.05, {}) == "hat_closed"

def test_band_types_valid():
    # all band defaults must map to valid drum types
    for b in ["kick","snare","floor","rack2","rack1","hat"]:
        assert classify_band(b, 0.05, {}) in maps.DRUM_TYPES
```

- [ ] **Step 2: Run tests to verify they fail**.

- [ ] **Step 3: Implement `classify_band(band_name, decay_s, config)`** — default mapping: kick→kick, snare→snare, floor→floor, rack2→rack2, rack1→rack1, hat→hat_closed. Adjustment: for `hat` band, if `decay_s > config.get("crash_decay_s", 0.2)` → `crash1` (crashes ring; closed hats decay fast). `config` may override any band's type or `crash_decay_s`. Wire into `trigger_transcribe`: compute decay per peak (Task 1 already budgets it), pass to `classify_band` before type assignment. Keep tom-vs-snare as band-based (floor/rack2/rack1 distinct bands); no extra heuristic in this task.

- [ ] **Step 4: Run tests to verify they pass**.

- [ ] **Step 5: Commit** — `git commit -m "feat: decay-based hat/crash disambiguation in trigger backend"`

---

### Task 4: Wire into pipeline + dispatch + GUI

**Files:**
- Modify: `src/drum_midi/transcribe.py` (`transcribe_dispatch`, `THRESHOLD_PRESETS`)
- Modify: `src/drum_midi/pipeline.py` (no change needed — `tx='trigger'` flows through `transcribe`)
- Modify: `src/drum_midi/gui.py` (add `trigger` to the transcription-method dropdown, if a hardcoded list exists there)
- Test: `tests/test_trigger.py` (add end-to-end)

**Interfaces:**
- Consumes: `trigger_transcribe` (Task 1), `transcribe_dispatch` dispatch pattern.
- Produces: `method='trigger'` handled in `transcribe_dispatch`; `THRESHOLD_PRESETS["tuned-mixwave"]["trigger"]` (may be `None`/`{}`).

- [ ] **Step 1: Add `trigger` to `transcribe_dispatch`** — `if method == "trigger": return trigger_transcribe(x, sr, config=config)` where `config = THRESHOLD_PRESETS.get(threshold_preset, {}).get("trigger")`. Add `"trigger": None` (or `{}`) to the `tuned-mixwave` preset (and `dense`/`sparse`) in `THRESHOLD_PRESETS`.

- [ ] **Step 2: Write the end-to-end test** in `tests/test_trigger.py`:

```python
from drum_midi.transcribe import transcribe
from drum_midi.pipeline import run_pipeline

def test_transcribe_trigger_dispatch():
    sr = 44100
    audio = np.zeros(int(sr*0.5))
    audio[0:int(sr*0.04)] = make_click(sr, 60, amp=1.0)
    notes = transcribe(audio, sr, method="trigger")
    assert {n["type"] for n in notes} == {"kick"}

def test_pipeline_trigger_end_to_end(tmp_path):
    import tempfile, wave
    sr = 44100
    audio = np.zeros(int(sr*0.6))
    audio[0:int(sr*0.04)] = make_click(sr, 60, amp=1.0)
    audio[int(sr*0.3):int(sr*0.34)] = make_click(sr, 250, amp=0.8)
    wav = tmp_path / "in.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(audio,-1,1)*32767).astype("<i2").tobytes())
    out = tmp_path / "out.mid"
    res = run_pipeline(str(wav), {"input":"stem","tx":"trigger"}, str(out), preset="mixwave_sleep_token", tempo=120)
    assert res["notes"] >= 2
    assert out.exists()
```

- [ ] **Step 3: Run tests to verify they pass** — `pytest tests/test_trigger.py -v`.

- [ ] **Step 4: Add `trigger` to GUI transcription-method dropdown** — find the dropdown's options list in `src/drum_midi/gui.py`; if it is a hardcoded tuple of methods, append `"trigger"`. Verify by grepping `gui.py` for the existing method list; if the dropdown derives from `transcribe_dispatch`/a backend registry, no change needed (state which in the commit message).

- [ ] **Step 5: Run full suite** — `.venv/Scripts/python.exe -m pytest --basetemp=.pytest_tmp -p no:cacheprovider` → all pass.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: wire trigger backend into dispatch, pipeline, and GUI"`

---

### Task 5: Real dense-genre verification

**Files:**
- Test: `tests/test_trigger.py` (no new code required; verification run)

- [ ] **Step 1: Run trigger backend on a dense mono drum mix** — locate a real dense-genre drum-only file (reuse `realtest/` or `challange/` assets already in repo; if stereo, downmix in the run). Report per-band note counts + total, compared against `method='bands'` (and `dettato` if fast enough) on the same file. Command:

```bash
.venv/Scripts/python.exe -c "from drum_midi import transcribe,audio; sr,x=audio.parse_audio('realtest/<file>.wav'); import numpy as np; x=np.mean(x,axis=-1);\nprint({m: len(transcribe.transcribe(x,sr,method=m)) for m in ['bands','trigger']})"
```

- [ ] **Step 2: Sanity-check the output** — distribution is sensible for the genre (e.g. kick/snare dominant, no implausible 10x crash). If a band's threshold is clearly off (e.g. tom yields 0 where genre expects toms), note it and either adjust a default `threshold_k` (document in commit) or record it as a known limit. Do not chase perfect genre coverage — the guarantee is dense-simultaneous detection, not genre-perfect labels.

- [ ] **Step 3: Commit any default tuning change** — `git commit -m "tune: trigger backend defaults on dense real mix"` (only if Step 2 changed thresholds).

---

## Review

The plan covers: band engine + anti-collapse (T1), velocity curve (T2), decay disambiguation (T3), full integration + E2E (T4), real verification (T5). Review Focus items 1-4 pinned in T1/T2; item 5 in T4. No spec requirement is left without a task. Types consistent across tasks (event dict shape, `config` dict, `trigger_transcribe` signature reused).
