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

ST_PITCH = {35:"kick",36:"kick",25:"snare",37:"snare",38:"snare",39:"snare",40:"snare",
            19:"tom",21:"tom",23:"tom",41:"tom",43:"tom",45:"tom",47:"tom",48:"tom",50:"tom",
            32:"hat_pedal",33:"hat_pedal",42:"hat_closed",44:"hat_pedal",46:"hat_open",
            73:"hat_closed",74:"hat_closed",75:"hat_closed",76:"hat_closed",77:"hat_open",
            78:"hat_open",79:"hat_open",81:"hat_open",83:"hat_open",84:"hat_open",85:"hat_open",
            49:"crash1",51:"ride",52:"china",53:"ride_bell",54:"crash2",55:"splash",56:"splash",
            57:"crash2",59:"ride",60:"ride",61:"crash1",62:"stack",63:"stack",64:"china",
            66:"crash2",67:"splash",68:"splash",69:"crash2",71:"ride",90:"crash1",91:"crash1",
            92:"crash2",93:"crash2",94:"splash",95:"crash2",98:"splash",99:"splash",100:"china",
            101:"china",102:"crash2",103:"crash2",107:"crash2",108:"stack",109:"stack",31:"sticks"}

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
st = mine(ST_ROOT, ST_PITCH, offset=24)
json.dump(st, open(os.path.join(W,"st_stats.json"),"w"), indent=1)

print("=== GGD ===")
for d,s in ggd.items():
    print(f"  {d}: grooves={s['grooves']} density={s['density_mean']} ghost={s['ghost_ratio']} top={sorted(s['overall'], key=lambda t:-s['overall'][t])[:4]}")
print("=== SLEEP TOKEN ===")
for d,s in st.items():
    print(f"  {d}: grooves={s['grooves']} density={s['density_mean']} ghost={s['ghost_ratio']} top={sorted(s['overall'], key=lambda t:-s['overall'][t])[:4]}")
print(f"\nwrote {os.path.getsize(os.path.join(W,'ggd_stats.json'))} B (ggd) + {os.path.getsize(os.path.join(W,'st_stats.json'))} B (st)")
