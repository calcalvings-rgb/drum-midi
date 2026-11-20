# GrooveForge design direction

## Owner direction
Dark mode. Vanilla JavaScript web UI. Sun Valley (`sv-ttk`) desktop theme.
Music-app expression: stronger typography and more visible color, with editing still the focus.
Antislop mode: during, selected for this session only.

Reading this as: a drum-audio editing workspace for musicians using FL Studio, with expressive music-tool typography and restrained controls. ENERGY 2 / RHYTHM 2 / MOTION 1.

## Decisions and purpose
- Charcoal backgrounds reduce competing light beside a DAW and honor the requested dark mode.
- Coral marks the transcription action and kick hits, linking the action to its result rather than decorating every label.
- Mint snare hits and lilac tom hits distinguish actual instrument groups. Other percussion uses light neutral ink; lane labels also identify every voice without color.
- Segoe UI/system sans avoids network fonts and matches desktop controls; larger, heavier product typography adds expression without a promotional hero.
- Monospace is reserved for time, velocity and counts, where aligned digits help editing.
- The timeline has the most width because checking and moving hits is the purpose of the app.
- Source settings remain together; on medium screens they reflow into two groups, and on phones they stack before the editor.
- Compact 8/16/24 spacing groups settings while larger gaps separate source configuration from note editing.
- Panel boundaries separate settings from the timeline; controls have visible edges and 44px minimum targets, not a card for every setting.
- Motion is limited to interaction feedback, with reduced-motion support. No looping decoration.
- No invented logo, avatars, sample hits in empty states, invented metrics, decorative status lights or promotional slogans.
- Engine status is real metadata-fetch status and is written as text. Numeric hit counts come from real transcription responses.
- Native widget hierarchy and editing behavior remain intact in the desktop app. Sun Valley owns the desktop widget visuals; the hand-drawn timeline gets explicit dark, readable ink.

## Verification
Check narrow, medium and wide layouts; all available controls; keyboard note selection and editing; empty, busy, success and error states. Record contrast ratios and click-through evidence in the UI verification report. No unmeasured performance or full WCAG conformance claims.
