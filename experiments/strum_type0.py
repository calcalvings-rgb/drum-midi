"""STRUM result -> single-track type-0 GM drums for FL."""
import pretty_midi
from pathlib import Path
from collections import Counter

src = Path(r"C:\Users\ccalv\workspace\coding\drum_strum.mid")
out = Path(r"C:\Users\ccalv\workspace\coding\drum_strum_type0.mid")

pm = pretty_midi.PrettyMIDI(str(src))
tempo = float(pm.get_tempo_changes()[1][0])

m = pretty_midi.PrettyMIDI(initial_tempo=tempo)
inst = pretty_midi.Instrument(program=0, is_drum=True, name="drums")
for i in pm.instruments:
    for n in i.notes:
        inst.notes.append(pretty_midi.Note(velocity=n.velocity, pitch=n.pitch, start=n.start, end=n.end))
inst.notes.sort(key=lambda n: (n.start, n.pitch))
m.instruments.append(inst)
m.write(str(out))
c = Counter(n.pitch for n in inst.notes)
print("wrote", out, "notes", len(inst.notes), "BPM", round(tempo, 2), "types", dict(sorted(c.items())))
