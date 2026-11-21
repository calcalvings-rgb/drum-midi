# Hermes workflow (drums → FL)

GrooveForge provides a web editor, a desktop UI and a Python engine. Automated FL Studio integration goes through **[flstudio-mcp](https://github.com/calcalvings-rgb/flstudio-mcp)**, orchestrated by Hermes. For manual cleanup, use the [web editor](WEBUI.md), preview the source WAV against the moving playhead, then download kit-mapped MIDI for FL Studio. WAV playback does not synthesize edited MIDI notes.

Automated workflow:

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
