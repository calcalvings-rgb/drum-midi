"""Mine GGD + MixWave Sleep Token groove packs -> per-slot per-family stats.
Output: data/ggd_stats.json (GGD), data/st_stats.json (Sleep Token).
Family-level map so generator can sample across both.
"""
import os, json
from collections import Counter, defaultdict
import mido

W = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(W, exist_ok=True)

GGD_ROOT = r"H:/Drum Grooves/GGD/GGD_Free_Grooves_Vol2"
ST_ROOT = r"H:/Kontakt Library/Sleep Token - II [MixWave]/MIDI Files/Sleep Token II - Groove Pack LITE"

GGD_GM = {36:"kick",35:"kick",38:"snare",40:"snare",37:"side_stick",39:"rimshot",
           42:"hat_closed",44:"hat_pedal",46:"hat_open",49:"crash1",57:"crash2",
           51:"ride",53:"ride_bell",41:"tom",43:"tom",45:"tom",47:"tom",48:"tom",50:"tom"}

ST_NKA = r"C:/Users/ccalv/OneDrive/Documents/Sleep Token - II/Data/defaultforhermes.nka"
ST_OFFSET = 35  # groove pitch + 35 -> note Kontakt (diverifikasi via distribusi musikal)


def load_st_map():
    """Baca user-mapping Kontakt (*.nka) -> {slot: {label, note, family}}."""
    txt = open(ST_NKA, encoding="utf-8").read()
    nums = [int(l.strip()) for l in txt.splitlines() if l.strip() and not l.startswith("%")]
    fam = {0:"kick",1:"kick",2:"snare",3:"snare",4:"snare",5:"snare",6:"snare",
           7:"tom",8:"tom",9:"tom",10:"tom",11:"tom",12:"tom",
           13:"hat_closed",14:"hat_closed",15:"hat_open",16:"hat_open",17:"hat_open",
           18:"hat_closed",19:"hat_closed",20:"hat_open",21:"hat_open",22:"hat_open",
           23:"hat_pedal",24:"hat_open",25:"hat_pedal",26:"hat_pedal",
           27:"ride",28:"ride_bell",29:"ride",30:"ride",31:"ride",
           32:"crash1",33:"crash1",34:"crash1",35:"crash2",36:"crash2",37:"crash2",
           38:"crash2",39:"crash2",40:"crash2",41:"crash2",43:"splash",44:"splash",
           45:"splash",46:"splash",47:"splash",48:"splash",49:"stack",50:"stack",
           51:"stack",52:"stack",53:"china",54:"china",55:"china",56:"sticks"}
    return {nums[i]: fam.get(i, "other") for i in range(len(nums)) if nums[i] != -1}

def parse(path):
    mid = mido.MidiFile(path)
    tpb = mid.ticks_per_beat or 480
    tempo = 500000; bpm = 120.0; meter = (4,4)
    rows = []
    for tr in mid.tracks:
        t = 0.0
        for m in tr:
            t += m.time
            if m.type == "set_tempo": tempo = m.tempo; bpm = 60e6/tempo
            elif m.type == "time_signature": meter = (m.numerator, m.denominator)
            elif m.type == "note_on" and m.velocity > 0:
                rows.append((t/tpb * (tempo/1e6), m.note, m.velocity))
    return rows, bpm, meter

def slot_of(sec, bpm, meter, subdiv=4):
    beats = sec * bpm / 60.0
    bar = meter[0]
    return int((beats % bar) * subdiv) % (bar*subdiv)

def mine(root, pitch_map, offset=0):
    songs = {}
    for d in sorted(os.listdir(root)):
        dp = os.path.join(root, d)
        if not os.path.isdir(dp): continue
        slot_type = Counter(); slot_hits = Counter()
        vel = defaultdict(list); density = []; ghost = 0; nhit = 0
        for f in sorted(os.listdir(dp)):
            if not f.lower().endswith(".mid"): continue
            rows, bpm, meter = parse(os.path.join(dp, f))
            types = []
            for sec, note, velv in rows:
                p = note + offset
                typ = pitch_map.get(p, "other")
                types.append(typ); nhit += 1
                if velv < 60: ghost += 1
                vel[typ].append(velv)
                s = slot_of(sec, bpm, meter)
                slot_type[(s, typ)] += 1; slot_hits[s] += 1
            density.append(len(types))
        probs = defaultdict(dict)
        for (s, typ), c in slot_type.items():
            probs[s][typ] = round(c / max(1, slot_hits[s]), 4)
        ngrooves = max(1, sum(1 for f in os.listdir(dp) if f.lower().endswith(".mid")))
        slot_act = {str(s): round(min(1.0, c/ngrooves), 3) for s, c in slot_hits.items()}
        type_total = Counter()
        for (s, typ), c in slot_type.items(): type_total[typ] += c
        overall = {t: round(c/max(1,nhit),4) for t,c in type_total.items()}
        acc = {t: round(sum(v)/len(v),1) for t,v in vel.items() if v}
        songs[d] = {
            "grooves": sum(1 for f in os.listdir(dp) if f.lower().endswith(".mid")),
            "density_mean": round(sum(density)/len(density),2) if density else 0,
            "ghost_ratio": round(ghost/max(1,nhit),3),
            "slot_probs": {str(s): p for s,p in sorted(probs.items())},
            "slot_act": slot_act,
            "overall": overall,
            "accents": acc,
        }
    return songs

ggd = mine(GGD_ROOT, GGD_GM)
json.dump(ggd, open(os.path.join(W,"ggd_stats.json"),"w"), indent=1)
st_map = load_st_map()
st = mine(ST_ROOT, st_map, offset=ST_OFFSET)
json.dump(st, open(os.path.join(W,"st_stats.json"),"w"), indent=1)

print("=== GGD ===")
for d,s in ggd.items():
    print(f"  {d}: grooves={s['grooves']} density={s['density_mean']} ghost={s['ghost_ratio']} top={sorted(s['overall'], key=lambda t:-s['overall'][t])[:4]}")
print("=== SLEEP TOKEN ===")
for d,s in st.items():
    print(f"  {d}: grooves={s['grooves']} density={s['density_mean']} ghost={s['ghost_ratio']} top={sorted(s['overall'], key=lambda t:-s['overall'][t])[:4]}")
print(f"\nwrote {os.path.getsize(os.path.join(W,'ggd_stats.json'))} B (ggd) + {os.path.getsize(os.path.join(W,'st_stats.json'))} B (st)")
