"""Subset only kick+snare / kick only to test note-count scaling in FL."""
import pretty_midi
from pathlib import Path

src = Path(r"C:\Users\ccalv\workspace\coding\drum-test_stems\drums.mid")
pm = pretty_midi.PrettyMIDI(str(src))
tempo = float(pm.get_tempo_changes()[1][0])

# kick=36, snare=38 in mixwave preset
for label, pitches in [("kick_snare", {36, 38}), ("kick_only", {36})]:
    m = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    inst = pretty_midi.Instrument(program=0, is_drum=True, name=label)
    for i in pm.instruments:
        for n in i.notes:
            if n.pitch in pitches:
                inst.notes.append(pretty_midi.Note(velocity=n.velocity, pitch=n.pitch, start=n.start, end=n.end))
    inst.notes.sort(key=lambda n: (n.start, n.pitch))
    m.instruments.append(inst)
    out = src.parent / f"drums_{label}.mid"
    m.write(str(out))
    print(label, "notes", len(inst.notes), "->", out)
