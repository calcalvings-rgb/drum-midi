# Production web-editor integration verification

## Scope

The approved editor is now served by the main `drum_midi.webui` entry point, not a separate prototype process. The owner explicitly approved AGPL for combined application code. Root LICENSE and third-party notices are present; pinned vendor sources and their licenses are retained unmodified. Native tkinter runtime and transcription algorithms are unchanged.

## Evidence

- Full Python suite: 202 passed, 2 skipped, 3 existing librosa short-input warnings.
- Frontend modules: 26 tests passed, including seconds-to-beats conversion, flattened/unknown instrument handling, view-only filtering, delta history, invalid-edit rollback, drop validation and waveform timing.
- Real main-server browser loop: local synthetic WAV uploaded to the engine, trigger transcription returned 15 hits, editor loaded them at 90 BPM, physical drag snapped a hit by a quarter beat, Ctrl+Z restored it, and MixWave download exported all 15 hits while only 3 were visible through a filter.
- The actual downloaded file was reopened independently. It is type 0, channel 10; note pitches match the selected kit mapping exactly once, positions/durations match the snapshot within one tick, and tempo is 89.999955 BPM (SMF rounding of 90 BPM).
- New browser startup has no prototype demo button or `window.spike` hook.
- Selecting an engine WAV fetches that file through authenticated `/api/audio` and displays the 4.250-second reference.
- Filtering after a move and then undoing cannot leave an invisible instrument selected; velocity controls remain disabled when visible selection is empty.
- Canceling transcription on a dirty take preserves edits and issues no upload or inference request. The browser confirm result was simulated for this cancellation check, not the backend response.
- Wrong-token snapshot export returns 403. Real HTTP tests also cover malformed/non-object JSON, size limits before body reads, traversal/sibling/symlink containment and non-overwriting duplicate uploads.
- The actual public source link downloads a valid archive containing application source; internal plans, `.env` files and `.pth` model weights are absent. A release manifest controls the offered paths, not a broad filesystem traversal.
- A separate browser test with actual 500ms network latency reproduced an unlocked source selector during refresh. The file list now serializes refresh, keeps source controls locked until completion and recovers after the response.
- One engine inference runs at a time; a concurrent HTTP request receives 409 rather than starting a second backend.
- Browser error/unhandled-rejection arrays were empty in the recorded production workflows.

Raw JSON, actual downloaded MIDI and real synthetic-data screenshots are retained in the task-specific scratch evidence folder. No private or licensed audio was used, no model API was called, and no new model/dependency installation was performed. Screenshot pixels are not claimed to have had a vision-model aesthetic review.

## Test-environment finding

`test_dark_theme_applies_sun_valley` failed under pytest fd capture on Win32/Tcl 9 with `couldn't read file ... sv.tcl: No error`. The same file could be opened and sourced in a standalone interpreter, and the exact test passed with `-s`. The Tk fixture now restores native handles during its lifecycle using `capfd.disabled()`. The unchanged runtime theme and full suite then passed. This is recorded rather than hidden or fixed by weakening its assertion.

## Operational limits

- Browser note/history state is per tab, not persistent across reload. Export unsaved work before refreshing.
- Import/export is note-event-only and constant-tempo 4/4. Other tempo/meter maps are rejected; controller/program metadata is not preserved.
- Editor pitches are canonical GM. Unknown pitches can be downloaded as GM but a non-GM kit rejects unmapped pitches instead of guessing.
- New UI export is a browser download, not an engine-side overwrite. Legacy API export retains its previous contract for existing clients.
- Audio references are decoded locally; local audio is sent to the configured local/LAN engine only when transcription is requested. No playback was added.
- Delta history is capped by 100 steps and an estimated 16 MiB serialized-size budget, with one newest oversized gesture retained. This is not a browser-heap benchmark.
- Broad musical accuracy and third-party model/data licensing audits are not part of this UI integration. Existing third-party terms remain separate from the application license.

## Scoped antislop gate

Direction retained: expressive dark/coral music tool, ENERGY 2 / RHYTHM 2 / MOTION 1. The piano roll is the working focal point; processing controls are grouped above it, with advanced options collapsible. No new logo, stock illustration, synthetic customer claim, third-party font request or runtime build framework.

Hard gate: PASS for new controls' actual loading/error/empty behavior, native labels/focus, source/privacy boundaries, real-data feedback and local-source license links. Runtime and real file download were exercised as recorded above; existing geometry and approved high-contrast editor styling are retained. This is not a full WCAG certification of unchanged GridSound internals.

Purpose gate: PASS. Coral/peach identifies notes and selected notes; mint represents actual waveform data. The time grid encodes beats, not decoration. System fonts avoid downloads and remain consistent with the approved prototype. No glass/glow/card grid/marketing hero or decorative motion was introduced.

Liveliness and quality: PASS within this integration scope. Original rhythm/identity remains; source controls support the real transcription workflow. State messages and measured counts are factual. MIDI export reflects full canonical state rather than filtered view or shared server note state.

## Review

One fresh read-only review was requested for commits 59f329a..2c8a873. Final findings and their disposition are recorded after its return; no merge or push is performed without owner instruction.
