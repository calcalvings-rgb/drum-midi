"""Single-track GM drums MIDI, tempo doubled (compressed), channel 10."""
import pretty_midi
from pathlib import Path

src = Path(r"C:\Users\ccalv\workspace\coding\drum-test_stems\drums.mid")
out = Path(r"C:\Users\ccalv\workspace\coding\drum-test_stems\drums_min.mid")

pm = pretty_midi.PrettyMIDI(str(src))
tempo = float(pm.get_tempo_changes()[1][0]) * 2  # 2x

m = pretty_midi.PrettyMIDI(initial_tempo=tempo)
inst = pretty_midi.Instrument(program=0, is_drum=True, name="drums")
for i in pm.instruments:
    for n in i.notes:
        inst.notes.append(pretty_midi.Note(velocity=n.velocity, pitch=n.pitch, start=n.start, end=n.end))
inst.notes.sort(key=lambda n: (n.start, n.pitch))
m.instruments.append(inst)
m.write(str(out))
print("wrote", out, "notes", len(inst.notes), "BPM", round(tempo, 2))
