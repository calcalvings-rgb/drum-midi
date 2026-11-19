"""Double tempo meta without rescaling note ticks -> compressed timeline."""
import mido

src = r"C:\Users\ccalv\workspace\coding\drum-test_stems\drums.mid"
out = r"C:\Users\ccalv\workspace\coding\drum-test_stems\drums_tempo2x.mid"

m = mido.MidiFile(src)
for t in m.tracks:
    for e in t:
        if e.type == "set_tempo":
            e.tempo = e.tempo // 2  # 2x tempo
m.save(out)
print("wrote", out)

# verify
m2 = mido.MidiFile(out)
for t in m2.tracks:
    for e in t:
        if e.type == "set_tempo":
            print("tempo meta", e.tempo, "=> BPM", round(60e6 / e.tempo, 2))
