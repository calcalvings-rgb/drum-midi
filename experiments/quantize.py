"""Reduce note count: quantize onsets to grid + merge simultaneous same-pitch hits."""
import pretty_midi
from pathlib import Path

src = Path(r"C:\Users\ccalv\workspace\coding\drum-test_stems\drums.mid")
tempo = float(pretty_midi.PrettyMIDI(str(src)).get_tempo_changes()[1][0])

# grid = 1/16 note
sixteenth = 60.0 / tempo / 4.0  # seconds

for grid_mult, name in [(1, "grid16"), (2, "grid8"), (4, "grid4")]:
    grid = sixteenth * grid_mult
    pm = pretty_midi.PrettyMIDI(str(src))
    m = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    inst = pretty_midi.Instrument(program=0, is_drum=True, name="drums")
    slots = {}
    for i in pm.instruments:
        for n in i.notes:
            s = round(n.start / grid)
            key = (s, n.pitch)
            if key in slots:  # merge same slot+pitch, keep max velocity
                slots[key] = max(slots[key], n.velocity)
            else:
                slots[key] = n.velocity
    for (s, pitch), vel in slots.items():
        start = s * grid
        inst.notes.append(pretty_midi.Note(velocity=vel, pitch=pitch, start=start, end=start + 0.05))
    inst.notes.sort(key=lambda n: (n.start, n.pitch))
    m.instruments.append(inst)
    out = src.parent / f"drums_{name}.mid"
    m.write(str(out))
    print(name, "notes", len(inst.notes), "->", out)
