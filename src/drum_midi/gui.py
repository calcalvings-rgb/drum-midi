"""Tkinter GUI for the Drum-to-MIDI pipeline."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

from drum_midi.maps import PRESETS
from drum_midi.pipeline import run_pipeline


class DrumMidiApp:
    """Tkinter application for Drum-to-MIDI conversion."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Drum-to-MIDI Converter")

        self.input_path_var = tk.StringVar(value="")
        self.file_path_var = self.input_path_var

        self.mode_input_var = tk.StringVar(value="auto")
        self.mode_sep_var = tk.StringVar(value="HPSS")
        self.mode_tx_var = tk.StringVar(value="bands")

        kit_options = list(PRESETS.keys()) if PRESETS else ["gm", "mixwave_sleep_token"]
        if "gm" not in kit_options:
            kit_options.insert(0, "gm")
        if "mixwave_sleep_token" not in kit_options:
            kit_options.append("mixwave_sleep_token")
        self.kit_options = kit_options

        self.kit_var = tk.StringVar(value="gm")
        self.tempo_var = tk.StringVar(value="120")
        self.result_var = tk.StringVar(value="Ready")

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding="12 12 12 12")
        frame.grid(row=0, column=0, sticky="nsew")

        # Row 0: File picker
        ttk.Label(frame, text="Audio File:").grid(row=0, column=0, sticky="w", pady=4)
        self.input_entry = ttk.Entry(frame, textvariable=self.input_path_var, width=40)
        self.input_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=4)
        self.browse_button = ttk.Button(frame, text="Browse...", command=self.browse_input_file)
        self.browse_button.grid(row=0, column=2, sticky="e", pady=4)

        # Row 1: Input mode dropdown
        ttk.Label(frame, text="Input Mode:").grid(row=1, column=0, sticky="w", pady=4)
        self.input_dropdown = ttk.Combobox(
            frame,
            textvariable=self.mode_input_var,
            values=["auto", "stem", "full"],
            state="readonly",
        )
        self.input_dropdown.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=4)
        self.mode_input_dropdown = self.input_dropdown

        # Row 2: Separation dropdown
        ttk.Label(frame, text="Separation:").grid(row=2, column=0, sticky="w", pady=4)
        self.sep_dropdown = ttk.Combobox(
            frame,
            textvariable=self.mode_sep_var,
            values=["none", "HPSS", "Demucs"],
            state="readonly",
        )
        self.sep_dropdown.grid(row=2, column=1, columnspan=2, sticky="ew", padx=5, pady=4)
        self.mode_sep_dropdown = self.sep_dropdown

        # Row 3: Transcription dropdown
        ttk.Label(frame, text="Transcription:").grid(row=3, column=0, sticky="w", pady=4)
        self.tx_dropdown = ttk.Combobox(
            frame,
            textvariable=self.mode_tx_var,
            values=["bands", "madmom"],
            state="readonly",
        )
        self.tx_dropdown.grid(row=3, column=1, columnspan=2, sticky="ew", padx=5, pady=4)
        self.mode_tx_dropdown = self.tx_dropdown

        # Row 4: Kit dropdown
        ttk.Label(frame, text="Kit Output:").grid(row=4, column=0, sticky="w", pady=4)
        self.kit_dropdown = ttk.Combobox(
            frame,
            textvariable=self.kit_var,
            values=self.kit_options,
            state="readonly",
        )
        self.kit_dropdown.grid(row=4, column=1, columnspan=2, sticky="ew", padx=5, pady=4)

        # Row 5: Tempo entry
        ttk.Label(frame, text="Tempo (BPM):").grid(row=5, column=0, sticky="w", pady=4)
        self.tempo_entry = ttk.Entry(frame, textvariable=self.tempo_var, width=12)
        self.tempo_entry.grid(row=5, column=1, sticky="w", padx=5, pady=4)

        # Row 6: Process button
        self.process_button = ttk.Button(frame, text="Process", command=self.process)
        self.process_button.grid(row=6, column=0, columnspan=3, pady=10)

        # Row 7: Result label
        self.result_label = ttk.Label(
            frame,
            textvariable=self.result_var,
            wraplength=400,
            font=("TkDefaultFont", 9, "bold"),
        )
        self.result_label.grid(row=7, column=0, columnspan=3, pady=6)

    def browse_input_file(self) -> None:
        """Open a file dialog to pick an audio file."""
        chosen = filedialog.askopenfilename(
            title="Select Drum Audio File",
            filetypes=[
                ("Audio Files", "*.wav;*.mp3;*.flac;*.ogg;*.aiff;*.m4a"),
                ("All Files", "*.*"),
            ],
        )
        if chosen:
            self.input_path_var.set(chosen)

    browse_file = browse_input_file

    def process(self) -> None:
        """Execute the conversion pipeline with current settings."""
        input_path = self.input_path_var.get().strip()
        if not input_path:
            self.result_var.set("Error: Please select an audio file first.")
            return

        input_mode = self.mode_input_var.get().strip().lower()
        sep_mode = self.mode_sep_var.get().strip().lower()
        tx_mode = self.mode_tx_var.get().strip().lower()
        preset = self.kit_var.get().strip()

        try:
            tempo = int(float(self.tempo_var.get().strip()))
        except (ValueError, TypeError):
            tempo = 120

        out_path = str(Path(input_path).with_suffix(".mid"))

        mode = {
            "input": input_mode,
            "sep": sep_mode,
            "tx": tx_mode,
        }

        try:
            result = run_pipeline(
                input_path=input_path,
                mode=mode,
                out_path=out_path,
                preset=preset,
                tempo=tempo,
                decode_mp3=True,
            )
            midi_path = result.get("midi", out_path)
            notes_count = result.get("notes", 0)
            self.result_var.set(f"Completed! Output: {midi_path} ({notes_count} notes)")
        except Exception as exc:
            self.result_var.set(f"Error: {exc}")


def main() -> None:
    """Launch the Drum-to-MIDI application."""
    root = tk.Tk()
    DrumMidiApp(root)
    root.mainloop()
