"""Entrypoint for the Drum-to-MIDI application."""

import sys
from pathlib import Path

_src = str(Path(__file__).resolve().parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

__path__ = [str(Path(_src) / "drum_midi")]

from drum_midi.gui import DrumMidiApp, main

__all__ = ["DrumMidiApp", "main"]


if __name__ == "__main__":
    main()
