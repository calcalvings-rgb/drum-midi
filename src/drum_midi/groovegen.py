"""Groove generator (level-2, statistik slot). Pure stdlib, no deps.

Membaca stats yang dihasilkan user dari library MIDI sendiri (format JSON,
lihat experiments/ggd_analyze2.py sebagai referensi analyzer), lalu generate pola
drum baru via sampling per-slot.

Output: list[dict] {type, onset_s, velocity} — kontrak sama pipeline transcribe.
"""
import json, os, random
from pathlib import Path

FAMILY_DEFAULT_VEL = {
    "kick": 110, "snare": 104, "hat_closed": 100, "hat_open": 92, "ride": 100,
    "crash1": 112, "crash2": 110, "splash": 106, "tom": 100, "ride_bell": 95,
    "sticks": 90, "hat_pedal": 80, "china": 108, "stack": 100, "side_stick": 95,
    "rimshot": 104, "other": 100,
}


def load_stats(source):
    """Baca stats JSON dari path file (wajib path).

    `source` = path ke file JSON (struktur: {style: {slot_probs, slot_act,
    accents, overall}}). Name lama "ggd"/"st" tidak lagi didukung — stats
    proprietary tidak disertakan di repo ini; hasilkan dari library MIDI
    sendiri (lihat experiments/ggd_analyze2.py).
    """
    if source in ("ggd", "st"):
        raise ValueError(
            f'source "{source}" tidak lagi didukung. Stats groove-pack berlisensi '
            "tidak disertakan di repo ini. Hasilkan stats sendiri dari library "
            "MIDI Anda (lihat experiments/ggd_analyze2.py) dan berikan path JSON."
        )
    p = Path(source)
    if not p.is_file():
        raise FileNotFoundError(f"stats file tidak ditemukan: {p}")
    return json.load(open(p, encoding="utf-8"))


def pick_style(stats, style=None, seed=None):
    """Pilih satu style/song dari stats. style=None -> random. seed -> deterministic."""
    if seed is not None:
        random.seed(seed)
    names = [k for k in stats if stats[k].get("slot_probs")]
    if not names:
        raise ValueError("stats kosong (tanpa slot_probs)")
    if style is None:
        style = random.choice(names)
    if style not in stats:
        raise KeyError(f"style {style} tidak ada di stats. Tersedia: {names}")
    return style


def weighted_choice(probs, rng):
    total = sum(probs.values())
    if total <= 0:
        return None
    r = rng.random() * total
    for k, v in probs.items():
        r -= v
        if r <= 0:
            return k
    return list(probs.keys())[-1]


def generate_groove(stats, style=None, bars=1, subdiv=4, seed=None,
                    tempo_bpm=None, humanize=True, ghost_prob=0.0):
    """Generate pola. Return list[dict] {type, onset_s, velocity}.

    - style: nama song di stats (None = random).
    - bars: jumlah bar (4/4 default; subdiv 4 = 16th).
    - seed: buat reproducibility.
    - humanize: jitter timing (±4ms) + velocity ±6% (kecuali low-velocity).
    - ghost_prob: probabilitas ghost-note (velocity ~50) tambahan di slot non-aktif.
    """
    rng = random.Random(seed)
    style = pick_style(stats, style, seed if seed is not None else None)
    st = stats[style]
    slot_probs = st.get("slot_probs", {})
    slot_act = st.get("slot_act", {})
    accents = st.get("accents", {})
    overall = st.get("overall", {})

    # tempo default: asumsikan dari density/level — pakai 120 kalau gak given
    if tempo_bpm is None:
        tempo_bpm = 120.0
    bar_seconds = 4 * 60.0 / tempo_bpm  # 4/4
    slot_dur = bar_seconds / (4 * subdiv)  # durasi 1 slot

    total_slots = 4 * subdiv * bars
    notes = []
    for si in range(total_slots):
        bar_idx = si // (4 * subdiv)
        slot = si % (4 * subdiv)
        abs_t = (bar_idx * bar_seconds) + (si % (4 * subdiv)) * slot_dur

        act = float(slot_act.get(str(slot), 0.0))
        probs = slot_probs.get(str(slot), {})
        fire = rng.random() < act
        if fire and probs:
            typ = weighted_choice(probs, rng)
            if typ is None:
                continue
            base_vel = int(accents.get(typ, FAMILY_DEFAULT_VEL.get(typ, 100)))
            vel = base_vel
            if humanize:
                vel = int(round(base_vel * rng.uniform(0.94, 1.06)))
            vel = max(1, min(127, vel))
            t = abs_t
            if humanize:
                t += rng.uniform(-0.004, 0.004)
            notes.append({"type": typ, "onset_s": round(t, 4),
                          "velocity": vel})
        elif ghost_prob > 0 and rng.random() < ghost_prob:
            # ghost note di slot non-aktif (jaringan 16th pelan)
            typ = weighted_choice(probs, rng) if probs else None
            if typ is None:
                continue
            t = abs_t + (rng.uniform(-0.002, 0.002) if humanize else 0)
            notes.append({"type": typ, "onset_s": round(t, 4),
                          "velocity": rng.randint(35, 58)})

    notes.sort(key=lambda n: n["onset_s"])
    return notes


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="path ke stats JSON (hasil analyzer library MIDI sendiri)")
    ap.add_argument("--style")
    ap.add_argument("--bars", type=int, default=1)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--bpm", type=float)
    ap.add_argument("--ghost", type=float, default=0.0)
    a = ap.parse_args()
    stats = load_stats(a.source)
    notes = generate_groove(stats, style=a.style, bars=a.bars, seed=a.seed,
                            tempo_bpm=a.bpm, ghost_prob=a.ghost)
    from collections import Counter
    print(f"source={a.source} style={a.style or 'random'} bars={a.bars} "
          f"seed={a.seed} -> {len(notes)} notes")
    for t, c in Counter(n["type"] for n in notes).most_common():
        print(f"  {t}: {c}")
