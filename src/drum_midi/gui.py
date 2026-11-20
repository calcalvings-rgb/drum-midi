"""Tkinter GUI for the Drum-to-MIDI pipeline."""

from pathlib import Path
import warnings
import tkinter as tk
from tkinter import filedialog, ttk

from drum_midi.audio import parse_audio
from drum_midi.detect import detect_stem
from drum_midi.editor import delete_note, move_note, reassign_note
from drum_midi.maps import DRUM_TYPES, PRESETS
from drum_midi.midi_out import write_midi
from drum_midi.separate import separate
from drum_midi.transcribe import THRESHOLD_PRESETS, transcribe


def apply_dark_theme(root: tk.Tk) -> bool:
    """Use Sun Valley when installed; keep the app usable without it."""
    try:
        import sv_ttk
    except ImportError:
        warnings.warn(
            "sv-ttk is not installed. Using the dark fallback. "
            "Install it with: python -m pip install sv-ttk",
            RuntimeWarning, stacklevel=2,
        )
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", background="#0d1017", foreground="#f1f0ed", fieldbackground="#191b20")
        style.configure("TCombobox", fieldbackground="#191b20", foreground="#f1f0ed", arrowcolor="#f1f0ed")
        style.map("TCombobox", fieldbackground=[("readonly", "#191b20")], foreground=[("readonly", "#f1f0ed")])
        style.map("TButton", background=[("active", "#383d45")], foreground=[("disabled", "#b2b7c2")])
        root.configure(background="#0d1017")
        return False
    sv_ttk.set_theme("dark", root=root)
    return True


class DrumMidiApp:
    """Tkinter application for Drum-to-MIDI conversion."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("GrooveForge")

        self.input_path_var = tk.StringVar(value="")
        self.file_path_var = self.input_path_var

        self.mode_input_var = tk.StringVar(value="auto")
        self.mode_sep_var = tk.StringVar(value="HPSS")
        self.mode_tx_var = tk.StringVar(value="adtof")

        kit_options = list(PRESETS.keys()) if PRESETS else ["gm", "mixwave_sleep_token"]
        if "gm" not in kit_options:
            kit_options.insert(0, "gm")
        if "mixwave_sleep_token" not in kit_options:
            kit_options.append("mixwave_sleep_token")
        self.kit_options = kit_options

        self.kit_var = tk.StringVar(value="gm")
        self.tempo_var = tk.StringVar(value="120")
        self.result_var = tk.StringVar(value="Ready")
        self.notes = []
        self.selected_note = None
        self._drag_x = None
        self.seconds_per_pixel = 0.01
        self.note_colors = {kind: "#c9cbd1" for kind in DRUM_TYPES}
        self.note_colors.update(kick="#f58b62", snare="#8dd6c2", floor="#b7a4e8", rack1="#b7a4e8", rack2="#b7a4e8")

        self._build_ui()

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        style.configure("Brand.TLabel", font=("Segoe UI", 24, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 15, "bold"))
        shell = ttk.Frame(self.root, padding=24)
        shell.grid(row=0, column=0, sticky="nsew")
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(2, weight=1)
        shell.grid_columnconfigure(1, weight=1)
        ttk.Label(shell, text="GrooveForge", style="Brand.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(shell, text="Drum audio to MIDI").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 24))
        frame = ttk.LabelFrame(shell, text="Audio", padding=16)
        frame.grid(row=2, column=0, sticky="ns", padx=(0, 20))
        frame.grid_columnconfigure(1, weight=1)
        editor = ttk.LabelFrame(shell, text="Notes", padding=16)
        editor.grid(row=2, column=1, sticky="nsew")
        editor.grid_columnconfigure(1, weight=1)
        editor.grid_rowconfigure(1, weight=1)
        self.note_status_var = tk.StringVar(master=self.root, value="Select a recording, then transcribe audio.")
        ttk.Label(editor, textvariable=self.note_status_var, wraplength=520).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        # Row 0: File picker
        ttk.Label(frame, text="Audio File:").grid(row=0, column=0, sticky="w", pady=4)
        self.input_entry = ttk.Entry(frame, textvariable=self.input_path_var, width=20)
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
            values=["bands", "madmom", "adtof", "dettato", "strum", "trigger"],
            state="readonly",
        )
        self.tx_dropdown.grid(row=3, column=1, columnspan=2, sticky="ew", padx=5, pady=4)
        self.mode_tx_dropdown = self.tx_dropdown

        # Row 4: Threshold preset dropdown
        ttk.Label(frame, text="Threshold Preset:").grid(row=4, column=0, sticky="w", pady=4)
        self.threshold_preset_var = tk.StringVar(value="tuned-mixwave")
        self.threshold_preset_dropdown = ttk.Combobox(
            frame,
            textvariable=self.threshold_preset_var,
            values=list(THRESHOLD_PRESETS),
            state="readonly",
        )
        self.threshold_preset_dropdown.grid(row=4, column=1, columnspan=2, sticky="ew", padx=5, pady=4)

        # Row 5: Kit dropdown
        ttk.Label(frame, text="Kit Output:").grid(row=5, column=0, sticky="w", pady=4)
        self.kit_dropdown = ttk.Combobox(
            frame,
            textvariable=self.kit_var,
            values=self.kit_options,
            state="readonly",
        )
        self.kit_dropdown.grid(row=5, column=1, columnspan=2, sticky="ew", padx=5, pady=4)

        # Row 6: Tempo entry
        ttk.Label(frame, text="Tempo (BPM):").grid(row=6, column=0, sticky="w", pady=4)
        self.tempo_entry = ttk.Entry(frame, textvariable=self.tempo_var, width=12)
        self.tempo_entry.grid(row=6, column=1, sticky="w", padx=5, pady=4)

        # Row 7: Process button
        self.process_button = ttk.Button(frame, text="Transcribe audio", command=self.process, style="Accent.TButton")
        self.process_button.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(20, 10))

        # Row 8: Result label
        self.result_label = ttk.Label(
            frame,
            textvariable=self.result_var,
            wraplength=300,
            font=("TkDefaultFont", 9, "bold"),
        )
        self.result_label.grid(row=8, column=0, columnspan=3, pady=6)

        self.roll = tk.Canvas(editor, width=600, height=260, background="#131518", highlightthickness=1, relief="flat", highlightbackground="#737984", highlightcolor="#ffd1b9", takefocus=True)
        self.roll.grid(row=1, column=0, columnspan=3, sticky="nsew")
        self.roll_sbx = ttk.Scrollbar(editor, orient="horizontal", command=self.roll.xview)
        self.roll_sbx.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 12))
        self.roll.configure(xscrollcommand=self.roll_sbx.set)
        self.roll.bind("<Button-1>", self.on_canvas_click)
        self.roll.bind("<B1-Motion>", self.on_drag)
        self.roll.bind("<ButtonRelease-1>", lambda _event: setattr(self, "_drag_x", None))
        self.roll.bind("<Delete>", self.delete_selected)
        self.roll.bind("<KeyPress>", self._on_key)
        self.type_var = tk.StringVar(value=DRUM_TYPES[0])
        self.type_dropdown = ttk.Combobox(editor, textvariable=self.type_var, values=DRUM_TYPES, state="readonly")
        ttk.Label(editor, text="Selected instrument").grid(row=3, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self.type_dropdown.grid(row=4, column=0, sticky="ew", padx=(0, 10))
        self.type_dropdown.bind("<<ComboboxSelected>>", lambda _event: self.reassign_selected())
        self.export_button = ttk.Button(editor, text="Export MIDI", command=self.export)
        self.export_button.grid(row=4, column=1, sticky="ew", padx=(0, 10))
        self.preview_button = ttk.Button(editor, text="Preview", command=self.preview)
        self.preview_button.grid(row=4, column=2, sticky="ew")
        ttk.Label(editor, text="Up/Down selects a hit. Left/Right moves it by 10ms. Delete removes it.", wraplength=520).grid(row=5, column=0, columnspan=3, sticky="w", pady=(14, 0))

        self.render_notes()

    def render_notes(self) -> None:
        self.roll.delete("all")
        if self.selected_note is not None and self.selected_note < len(self.notes):
            note = self.notes[self.selected_note]
            self.note_status_var.set(f"{note['type']} at {note['onset_s']:.3f}s, velocity {note['velocity']:.2f}")
        elif self.notes:
            self.note_status_var.set(f"{len(self.notes)} hits. Select a hit to adjust timing or instrument.")
        else:
            self.note_status_var.set("Select a recording, then transcribe audio.")
        for row, kind in enumerate(DRUM_TYPES):
            y = row * 18
            self.roll.create_text(4, y + 8, text=kind, anchor="w", fill="#e6e8ec")
        if self.notes:
            dur = max(note["onset_s"] for note in self.notes) + 2.0
            width = self.roll.winfo_width()
            if width <= 10:
                width = 600
            self.seconds_per_pixel = dur / max(width - 110, 50)
        else:
            self.roll.create_text(
                350, 130, text="No hits yet. Transcribe audio to start editing.",
                fill="#b2b7c2",
            )
        for i, note in enumerate(self.notes):
            x = 100 + note["onset_s"] / self.seconds_per_pixel
            y = DRUM_TYPES.index(note["type"]) * 18
            self.roll.create_rectangle(x, y + 2, x + 12, y + 15, fill=self.note_colors[note["type"]], outline="#e6e8ec" if i == self.selected_note else "", tags=(f"note:{i}",))

        if self.notes:
            last = max(note["onset_s"] for note in self.notes) + 2.0
            max_x = 100 + last / self.seconds_per_pixel
        else:
            max_x = 100
        self.roll.configure(scrollregion=(0, 0, max_x + 30, len(DRUM_TYPES) * 18 + 20))

    def on_canvas_click(self, event):
        x = self.roll.canvasx(event.x)
        y = self.roll.canvasy(event.y)
        hits = self.roll.find_overlapping(x, y, x, y)
        selected = next((int(tag.split(":")[1]) for item in hits for tag in self.roll.gettags(item) if tag.startswith("note:")), None)
        self.selected_note = selected
        self._drag_x = event.x
        if selected is not None:
            self.type_var.set(self.notes[selected]["type"])
        self.render_notes()
        self.roll.focus_set()
        return selected

    def on_drag(self, event):
        if self.selected_note is None or self._drag_x is None:
            return
        delta = (event.x - self._drag_x) * self.seconds_per_pixel
        self.notes = move_note(self.notes, self.selected_note, delta)
        self._drag_x = event.x
        self.render_notes()

    def reassign_selected(self, new_type=None):
        if self.selected_note is None:
            return
        self.notes = reassign_note(self.notes, self.selected_note, new_type or self.type_var.get())
        self.type_var.set(self.notes[self.selected_note]["type"])
        self.render_notes()

    def delete_selected(self, _event=None):
        if self.selected_note is None:
            return
        self.notes = delete_note(self.notes, self.selected_note)
        self.selected_note = None
        self.render_notes()

    def _on_key(self, event):
        key = event.keysym
        if key == "Escape":
            self.selected_note = None
            self.render_notes()
        elif key in {"Up", "Down", "Home", "End"} and self.notes:
            order = sorted(range(len(self.notes)), key=lambda i: self.notes[i]["onset_s"])
            pos = order.index(self.selected_note) if self.selected_note in order else -1
            if key == "Home":
                pos = 0
            elif key == "End":
                pos = len(order) - 1
            elif key == "Down":
                pos = min(pos + 1, len(order) - 1)
            else:
                pos = len(order) - 1 if pos < 0 else max(0, pos - 1)
            self.selected_note = order[pos]
            self.type_var.set(self.notes[self.selected_note]["type"])
            self.render_notes()
        elif key in {"Left", "Right"} and self.selected_note is not None:
            self.notes = move_note(self.notes, self.selected_note, -.01 if key == "Left" else .01)
            self.render_notes()
        elif key == "Delete":
            self.delete_selected()
        elif event.keysym in {str(i) for i in range(1, len(DRUM_TYPES) + 1)} and self.selected_note is not None:
            self.type_var.set(DRUM_TYPES[int(event.keysym) - 1])
            self.reassign_selected()

    def preview(self):
        if not self.notes:
            self.result_var.set("Error: Process audio before previewing.")
            return
        try:
            from drum_midi.preview import play_preview

            path = play_preview(self.notes)
            self.result_var.set(f"Preview playing ({Path(path).name}).")
        except Exception as exc:
            self.result_var.set(f"Error: {exc}")

    def export(self):
        if not self.notes:
            self.result_var.set("Error: Process audio before exporting.")
            return
        input_path = self.input_path_var.get().strip()
        try:
            tempo = int(float(self.tempo_var.get().strip()))
        except (ValueError, TypeError):
            tempo = 120
        out_path = str(Path(input_path).with_suffix(".mid"))
        write_midi(self.notes, out_path, preset=self.kit_var.get().strip(), tempo=tempo)
        self.result_var.set(f"Exported! Output: {out_path} ({len(self.notes)} notes)")

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
        threshold_preset = self.threshold_preset_var.get().strip() or "tuned-mixwave"

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

        self.process_button.state(["disabled"])
        self.result_var.set("Transcribing audio, please wait…")
        self.root.update_idletasks()
        try:
            sr, audio = parse_audio(input_path, decode_mp3=True)
            detected = detect_stem(audio, sr) if input_mode == "auto" else input_mode
            if detected == "full":
                audio = separate(audio, sr, sep_mode)
            self.notes = transcribe(audio, sr, method=tx_mode, threshold_preset=threshold_preset)
            self.selected_note = None
            self.render_notes()
            self.result_var.set(f"Completed! {len(self.notes)} notes ready to edit and export.")
        except Exception as exc:
            self.result_var.set(f"Error: {exc}")
        finally:
            self.process_button.state(["!disabled"])


def main() -> None:
    """Launch the Drum-to-MIDI application."""
    root = tk.Tk()
    apply_dark_theme(root)
    root.geometry("1220x760")
    root.minsize(1080, 640)
    DrumMidiApp(root)
    root.mainloop()
