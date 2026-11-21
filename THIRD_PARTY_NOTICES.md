# Third-party notices

GrooveForge application code is licensed under GNU AGPL version 3; see LICENSE. This does not relicense third-party dependencies, model weights or data.

## Web editor

Vendored source under `src/drum_midi/webui_static/vendor/`:

- GridSound gs-ui-components, AGPL-3.0, commit `350f079212648cf8786749c801453404f75ffb02`.
- GridSound gs-utils, AGPL-3.0, commit `66172d129dda482315da6e5ac67d06a422d7abfb` (the UI repository's matching submodule revision).

The repositories, commits and terms are recorded in `vendor/VENDOR.json`. Each directory retains its original LICENSE. WAV playback uses native browser media controls; transport synchronization adds no third-party library. Documentation screenshots show the running application with synthetic test data, not third-party audio. Vendor source is unmodified; application adapters and CSS overrides live outside those directories. No upstream font packs, audio examples or test corpus are included.

## Runtime dependencies and existing model code

mido (MIT) is a required dependency for web-editor MIDI import/export, installed through requirements-web.txt. Its license remains MIT. Existing NumPy, SciPy, tkinter/Sun Valley, transcription dependencies and vendored ADTOF code retain their respective original terms. Consult their upstream distributions and docs/BACKENDS.md; root LICENSE is not a new permission grant over third-party weights, libraries or data. No new model weights or proprietary MIDI/audio data are introduced by the editor integration.
