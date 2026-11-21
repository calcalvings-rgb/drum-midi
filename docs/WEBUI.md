# Web editor and transcription engine

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-web.txt
.venv\Scripts\python.exe -m drum_midi.webui --host 127.0.0.1 --port 8123 --dir PATH
```

Open the private token URL printed by the server. The browser stores the token in its own session and sends `X-Auth-Token` on every API request. If session storage works, the token is removed from the visible URL. Keep the printed URL private. For trusted LAN use, bind `--host 0.0.0.0`; built-in HTTP does not provide TLS.

## Audio to editable MIDI

1. Drop a local WAV into the import area, or select audio already on the engine. WAV references are decoded locally in the browser. Selecting an engine WAV fetches the same file through an authenticated request.
2. Set the source BPM, engine and threshold preset. Existing duplicate/cymbal/velocity/density cleanup toggles remain available.
3. Click **Transcribe audio**. A local file is uploaded to this local/LAN engine when needed, using a new filename if the name already exists. No cloud upload or model API is used by the UI.
4. Results load into the GridSound editor at the visible BPM without automatic quantization. The waveform uses seconds from the same source, mapped to beats through that BPM.
5. Edit, then choose the output kit and **Download MIDI**. The download uses the current tab's complete note state, even while notes are filtered. It is type-0 MIDI on drum channel 10 at the visible BPM; it does not save over the engine's source audio.

The engine uses the selected existing transcription backend. Neural backends still require their separately installed dependencies/weights; the UI does not install or download them. Other engine audio formats need ffmpeg; WAV, including common float WAV exports, is the direct path.

## Editing

- Snap: Off or 1/4 through 1/64. Changing snap preserves original offsets. Quantize selected explicitly aligns existing hits.
- Shift-drag selects an area. Drag hits or their edges to move/resize; use the lower velocity lane or labelled range control.
- Ctrl+A selects visible notes, Ctrl+B duplicates, Delete/right-click removes, arrows nudge/transpose, Ctrl+Z undoes, Ctrl+Y/Ctrl+Shift+Z redoes.
- Local delta history preserves a whole gesture as one operation. It keeps up to 100 steps within an estimated 16 MiB serialized-history budget; one oversized newest gesture is retained so it can still be undone. This is not a measured browser-heap limit.
- The note filter affects the view/selection only, not the take or export. Exported pitches are canonical GM in the editor and mapped once through the selected kit.
- MIDI import is GM pitch, note-event-only, constant-tempo 4/4. Unsupported meter/tempo maps and unclosed notes are rejected. Controller/program metadata is not retained. Unknown pitches remain intact for GM output; a non-GM kit rejects unmapped pitches rather than silently changing them.
- WAV has native browser play/pause, volume and seek controls below the reference picker. Playback uses the same local or authenticated engine WAV, without autoplay or an extra upload. Clearing/changing the source stops playback and releases its object URL. Audio starts at zero seconds / the first beat; playback is not synchronized to the MIDI editor playhead. Source changes do not rewrite note placement.

## Limits and state

MIDI/JSON requests: 8 MiB. Audio upload/reference: 256 MiB. Up to 50000 notes and 100000 beats per onset/duration. Browser decoding can temporarily use more memory than the WAV file. File drops validate at most one MIDI and one WAV before starting; canceling replacement skips its paired WAV. For paired drops, WAV decoding is staged before replacing MIDI. If decoding or MIDI parsing fails, the existing take, undo history and reference remain intact. Canceling replacement also keeps the original pair.

Notes and history are per browser tab and vanish on reload. Export before refreshing. Replacing dirty notes prompts first; a result finishing after newer edits also asks before replacement. One engine transcription runs at a time, returning 409 for a concurrent request. Legacy server-side note endpoints remain shared and should not be edited from multiple clients simultaneously.

## API compatibility

All API routes require `X-Auth-Token`:

- Existing: `GET /api/files`, `GET /api/meta`, `POST /api/upload?name=...`, `POST /api/run`, `POST /api/edit`, `POST /api/export`.
- `GET /api/audio?file=...`: bounded reference fetch within the input directory.
- `POST /api/editor/import`: raw MIDI bytes; returns canonical note objects and BPM.
- `POST /api/editor/export`: `{bpm,kit,notes:[{key,when,duration,gain}]}`; returns MIDI bytes from that snapshot. Times/durations are quarter-note beats; gain is 0-1.

Legacy export keeps its prior engine-side write contract. The new UI uses the independent browser-download endpoint.

## Assets, license and source offer

GridSound UI/utilities are pinned in `src/drum_midi/webui_static/vendor/VENDOR.json`; original licenses remain in each vendor directory. Application styling and behavior are outside vendor source. No npm install, build step, runtime Node or third-party font request is needed.

Public `/source.zip` offers the application source from an explicit `source_manifest.json`. It does not expose untracked files, model weights, licensed local data or internal plans. From a Git checkout, stage newly distributable code, run `.venv\Scripts\python.exe tools/update_source_manifest.py`, then commit the updated manifest. Source distribution must include every manifested file; incomplete packaged installs return 503 rather than an incomplete archive. Third-party model/code terms are not replaced by the application's root license.

The tkinter desktop app remains the existing Sun Valley interface; this integration changes the web editor only.
