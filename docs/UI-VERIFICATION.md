# UI verification (historical initial rework)

This report describes the initial canvas/Sun Valley milestone, not the current GridSound web editor. Its test totals and controls are historical. Current operation is documented in [WEBUI.md](WEBUI.md); subsequent integration and transport evidence is in [EDITOR-INTEGRATION-VERIFICATION.md](EDITOR-INTEGRATION-VERIFICATION.md). Changes were subsequently merged into master and pushed after owner approval.

## Result

Implemented on `feature/modern-dark-ui`, based on `master` at `ca725cc`.

- Python: 161 passed, 2 skipped, 3 existing librosa short-input warnings.
- JavaScript renderer: 5 passed, 0 failed, using Node's built-in test runner. Node is not required to run GrooveForge.
- Read-only final code review of `ca725cc..9021027`: no concrete Critical, Important or Minor findings.
- No merge or push performed. The local test server on port 18123 was stopped.
- Screenshots were captured, but the image-inspection tool returned `model_not_found`. This report does not claim pixel-level visual approval, full WCAG conformance, or a measured performance score.

## Exercised controls and states

Browser tests used a synthesized three-second WAV, not a real recording or an invented API response. Requests went through the running Python server.

| Control or state | Observed result |
|---|---|
| Initial empty editor | Names the missing recording and tells the user to transcribe audio. |
| File selector | Chooses the uploaded audio; transcription payload contains its filename. |
| File input and Upload audio | A real WAV uploads and becomes selected. An `.exe` is rejected with an error; controls recover. |
| Engine selector | Existing metadata supplies the options; trigger was executed. Other neural engines were not run for this visual task. |
| MIDI output kit | `gm` was selected and reached the export request. |
| Remove duplicate hits | Toggling reaches the request as `groove: false`. |
| Group cymbals | Toggling reaches the request as `flatten_cymbal: true`. |
| Smooth velocity | Toggling reaches the request as `velocity_smooth: true`. |
| Protect steady grooves | Toggling reaches the request as `protect_grooves: true`. |
| Transcribe audio | Synthetic fixture produces 6 hits. Busy text appears and overlapping UI actions are disabled. |
| Mouse selection and drag | A hit moves to another lane and time; both API edits return 200. |
| Touch drag | Touch events move a hit across lanes and in time; both API edits return 200. |
| Keyboard selection and nudge | Up/Down selects a hit; Right changes onset by 0.01 seconds. Native app also exercises keyboard deletion. |
| Instrument selector | Selected hit becomes `snare`. |
| Negative and positive nudge buttons | Both issue real edit requests. |
| Delete hit | Hit count decreases from 6 to 5. |
| Filter | Filtering an absent instrument displays `0 / 6 note events`; clearing it restores the take. |
| Zoom in, out, Fit and wheel | Controls redraw the timeline; fit restores the range. |
| Drag empty space while zoomed | Timeline pans and changes the canvas image. |
| Export MIDI | Actual export returns 5 hits. Native smoke test reopens the written file with mido and counts 5 note-on events. |
| Zero-hit transcription | Uploaded silence produces a visible `No hits detected` state with a suggestion to try a different engine or recording. |
| Wrong token | The page reports unauthorized access and leaves processing controls disabled. |
| Keyboard Tab and Space | Native browser events move focus from the first cleanup checkbox to the next, show a 3px solid outline, and toggle a checkbox. |
| Browser runtime errors | Captured error and unhandled-rejection arrays remain empty during the instrumented workflow and state checks. |
| Native theme | Actual Tk root reports `sun-valley-dark`; missing-package test verifies a warning and dark clam fallback. |
| Native settings and editing | Real controls select stem/none/trigger/threshold/gm/120 BPM. Processing yields 6 hits; select, nudge, reassign, delete and export yield 5. |
| Native empty actions | Transcribe, Preview and Export display actionable missing-input messages. |
| Native file picker | Automated test verifies the dialog call and propagation of its selected path. The OS dialog was not manually inspected. |
| Native preview audio | Empty-state behavior and preview-renderer tests run; actual sound playback was not auditioned. |

## Measured layout and contrast

- Browser widths checked: 320, 390, 800, 1024 and 1440 CSS pixels. No horizontal overflow; no undersized enabled control targets. Checkbox targets are their associated full-row labels.
- Canvas backing width matches the rendered container at all five widths: 290, 360, 735, 959 and 1035 pixels respectively.
- Doubling root text from 15px to 30px at a 390px viewport produces no horizontal overflow or escaped button/label/heading/paragraph text.
- Eight rendered enabled-text color/background pairs were computed with the WCAG luminance formula. Minimum measured ratio: 7.6678:1. This is evidence for those pairs, not a full accessibility certification.
- Native widget bounds fit inside the window at 1220x760 and 1080x640 in the smoke script.

## Antislop delivery gate

These are source, interaction and measured-layout checks. Screenshot aesthetics remain unapproved because image inspection was unavailable.

### Hard gate

- R-02 PASS: revised UI copy contains no em dash; labels describe actual actions.
- R-03 PASS: five viewport widths show no overflow; enabled control targets meet 44px in the measured states.
- R-17 PASS: displayed hit counts come from transcription responses; no promotional statistics.
- R-18 PASS: no testimonials, avatars or invented people.
- R-23 PASS: product name is text; the invented logo and sample-hit decoration were removed. No new visual asset was generated.
- R-24 PASS: the only navigation link skips to the existing workspace.
- R-25 PASS: measured enabled-text pairs meet AA contrast; explicit high-contrast focus and control edges are in source. This is not a full conformance claim.
- R-26 PASS: controls retain actual API or native callbacks; behavior is recorded above.
- R-27 PASS: initial empty, zero-hit, busy, upload-error and auth-error states were exercised.
- R-28 PASS: no FAQ section.
- R-32 PASS: keyboard note selection/editing, logical Tab behavior, native checkbox Space activation and visible focus are exercised.
- R-33 PASS: features live in HTML, JS, CSS and Python source. No shipped runtime source-rewriter or CSS-patching script.
- R-34 PASS: the shipped web theme is dark only, as requested. Native Sun Valley and missing-package fallback paths are tested; no broken theme toggle is offered.
- R-35 PASS: real browser and native app run; the control-by-control evidence above states exactly what was exercised and what was not auditioned.
- R-36 PASS: no invented compliance, security, customer or performance claims.
- R-37 PASS: owner selected expressive music-app character during execution; DESIGN.md records the direction and dials before the revised design was written.
- R-38 PASS: visible take names and counts use actual state; no disguised sample data.
- R-39 PASS: named native controls, visible labels, pointer affordances, focus feedback, disabled states, landmarks, language/title and reduced-motion handling are in source.
- R-40 PASS: local assets only; no third-party blocking scripts or unsized image/video/iframe assets. No unmeasured Web Vitals or Lighthouse claims.

### Purpose gate

- R-01 PASS: coral identifies the primary transcription action and kick hits; the purpose is written in DESIGN.md. No page-wide gradients or glow.
- R-04 PASS: no invented logo or generic decorative icon set.
- R-06 PASS: larger system-sans typography gives the requested expression; monospace is reserved for numeric editing data.
- R-07 PASS: no background pattern. The timeline grid represents real time and lanes.
- R-08 PASS: no decorative button arrows.
- R-09 PASS: no marketing capsules or eyebrow badge.
- R-10 PASS: no glassmorphism.
- R-12 PASS: no floating-card shadow system; any pressed feedback indicates interaction.
- R-13 PASS: no decorative glow.
- R-14 PASS: no feature-card grid; settings and editor are separate because they perform different work.
- R-19 PASS: motion is limited to interaction feedback with reduced-motion support.
- R-22 PASS: no generic illustration or fake screenshot in an empty state.

### Liveliness

- PASS: ENERGY 2 / RHYTHM 2 / MOTION 1 is explicit in DESIGN.md.
- PASS: stronger product typography and actual instrument colors supply expression without a promotional hero.
- PASS: the timeline receives the most working space; transcription is the primary action.
- PASS: spacing separates source configuration from note editing, with distinct medium and narrow reflows.
- PASS: coral is the deliberate action accent, not a decoration on every label.
- PASS: instrument-colored vertical hits and aligned timing data supply the product-specific motif.
- PASS: the revised Design Read was stated before revising the UI.

### Craftsmanship and quality locks

- C-1 / R-31 PASS: DESIGN.md gives a reason for palette, type, hierarchy, spacing, panels and motion.
- C-2 PASS: exercised controls perform actual work or report their missing prerequisite.
- C-3 / R-05 PASS: no promotional hero, filler statistics, fake terminal, testimonials or template footer.
- C-4 PASS: recorded empty, busy, success, failure, narrow, medium, wide and keyboard paths hold in the measured checks.
- C-5 PASS: no fabricated claims or responses; test audio is explicitly synthesized.
- R-11 PASS: a small radius scale distinguishes panels, controls and functional switches; not every element is a pill.
- R-15 PASS: action labels are Upload audio, Transcribe audio, Export MIDI and Delete hit.
- R-16 PASS: no marketing buzzwords in revised interface copy.
- R-20 PASS: hierarchy follows drum transcription and hit editing, with identity choices recorded in DESIGN.md.
- R-21 PASS: dark mode is an explicit owner request for a music-production tool.
- R-29 PASS: neutral surfaces, a coral action accent and semantic instrument colors have documented roles.
- R-30 PASS: no popular product was requested or used as a page template; native widgets intentionally use the selected Sun Valley theme.

## Rulings and limitations

1. Used a dedicated feature branch in the existing checkout to retain the local venv and audio fixtures. Tradeoff: no separate worktree isolation.
2. Extracted the functional frontend in the static-serving commit rather than shipping placeholders between tasks. Tradeoff: extraction happened earlier in the plan, with no intended behavior change.
3. Used an exact public filename allowlist plus path containment instead of string-prefix checking. Tradeoff: adding a future static asset requires updating the allowlist.
4. Missing sv-ttk emits a warning and uses dark clam instead of silently falling back. Tradeoff: the missing-dependency appearance differs from Sun Valley.
5. Kept Sun Valley's native control appearance rather than repainting library widgets to match every web accent. Tradeoff: the desktop action accent can differ from web coral.
6. Kept native transcription synchronous with busy feedback. Tradeoff: the window cannot interact while the backend runs; a worker-thread rewrite remains outside this visual change.
7. Final reviewer declined pixel-level screenshot judgment because image inspection failed. No pixel-level approval is claimed; visual polish defects could remain.
8. Broad audio-corpus accuracy was not evaluated because transcription algorithms were unchanged. UI smoke audio does not prove musical accuracy.
9. Multi-client concurrency was not tested or redesigned. The existing backend shares one note session; documentation warns against simultaneous editing.

Deferred minor code findings: none reported by the final reviewer.
