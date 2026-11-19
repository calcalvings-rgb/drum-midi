import os
os.environ["STRUM_ROOT"] = r"C:\Users\ccalv\workspace\coding\strum"
from drum_midi.audio import parse_audio
from drum_midi.transcribe import transcribe
from drum_midi.midi_out import write_midi

wav = r"C:\Users\ccalv\workspace\coding\drum-test_drums_pcm.wav"
out = r"C:\Users\ccalv\workspace\coding\drum_strum.mid"

sr, x = parse_audio(wav)
print("audio", sr, x.shape)
notes = transcribe(x, sr, method="strum", threshold_preset="strum-balanced")
print("notes", len(notes))
from collections import Counter
c = Counter(n["type"] for n in notes)
print("types", dict(c))
write_midi(notes, out, preset="mixwave_sleep_token", tempo=139.67)
print("wrote", out)
