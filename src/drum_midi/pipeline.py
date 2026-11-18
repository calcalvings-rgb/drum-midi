"""Orchestrate audio loading, drum transcription, and MIDI export."""

from .audio import parse_audio
from .detect import detect_stem
from .midi_out import write_midi
from .separate import separate
from .transcribe import transcribe


def run_pipeline(
    input_path,
    mode: dict,
    out_path,
    preset="gm",
    tempo=120,
    decode_mp3=False,
) -> dict:
    """Convert an audio file to MIDI using the selected pipeline stages."""
    sr, audio = parse_audio(input_path, decode_mp3=decode_mp3)
    input_mode = mode.get("input", "auto")
    if input_mode == "auto":
        detected = detect_stem(audio, sr)
    elif input_mode in {"stem", "full"}:
        detected = input_mode
    else:
        raise ValueError(f"Unknown input mode: {input_mode}")

    if detected == "full":
        audio = separate(audio, sr, mode.get("sep", "none"))
    notes = transcribe(audio, sr, method=mode.get("tx", "bands"))
    write_midi(notes, out_path, preset=preset, tempo=tempo)
    return {"detected": detected, "midi": out_path, "notes": len(notes)}
