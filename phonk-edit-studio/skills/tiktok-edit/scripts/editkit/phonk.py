"""Original drift-phonk beat generator (no samples, no copyright): cowbell riff, 808 with glides, kick, clap, hats.
Returns exact beat / drop timing so the edit can sync perfectly."""
import json, math
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR = 44100
NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def hz(semi_from_a4): return 440.0 * 2 ** (semi_from_a4 / 12)


def bp(x, lo, hi, o=2): return sosfilt(butter(o, [lo, min(hi, SR / 2 - 100)], "band", fs=SR, output="sos"), x)
def lp(x, f, o=2): return sosfilt(butter(o, min(f, SR / 2 - 100), "low", fs=SR, output="sos"), x)
def hp(x, f, o=2): return sosfilt(butter(o, f, "high", fs=SR, output="sos"), x)


def env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)


def cowbell(f, dur=0.32, rng=None):
    n = int(dur * SR); t = np.arange(n) / SR
    sq = lambda fr: np.sign(np.sin(2 * np.pi * fr * t))
    x = 0.6 * sq(f) + 0.45 * sq(f * 1.4836)
    x = bp(x, f * 0.8, f * 4.5)
    x += 0.25 * np.sin(2 * np.pi * f * t)
    return x * env(n, 0.001, dur * 0.28)


def kick(dur=0.5):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 42 + 140 * np.exp(-t * 28)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.18)
    click = hp(np.random.default_rng(3).normal(0, 1, n), 2500) * env(n, 0.0003, 0.004) * 0.5
    return np.tanh((x + click) * 2.2) * 0.9


def clap(dur=0.35, rng=None):
    rng = rng or np.random.default_rng(5); n = int(dur * SR)
    noise = bp(rng.normal(0, 1, n), 900, 5200)
    e = np.zeros(n)
    for k, d in enumerate([0, 0.011, 0.022]):
        i = int(d * SR); e[i:] += env(n - i, 0.0005, 0.012 if k < 2 else 0.11)
    body = np.sin(2 * np.pi * 190 * np.arange(n) / SR) * env(n, 0.001, 0.05) * 0.4
    return np.tanh((noise * e + body) * 1.5) * 0.75


def hat(dur=0.05, open_=False, rng=None):
    rng = rng or np.random.default_rng(7); n = int((0.25 if open_ else dur) * SR)
    return hp(rng.normal(0, 1, n), 7000) * env(n, 0.0005, 0.08 if open_ else 0.012) * 0.35


def bass808(notes, beat, n_total):
    """notes: list of (start_s, dur_s, semitone_from_A4, glide_to_semitone_or_None)."""
    out = np.zeros(n_total)
    for s, d, semi, glide in notes:
        n = int(d * SR); i = int(s * SR)
        if i >= n_total: continue
        t = np.arange(n) / SR
        f0 = hz(semi); f = np.full(n, f0)
        if glide is not None:
            g0 = int(n * 0.55); f[g0:] = f0 * (hz(glide) / f0) ** np.clip((t[g0:] - t[g0]) / 0.09, 0, 1)
        ph = 2 * np.pi * np.cumsum(f) / SR
        x = np.sin(ph) + 0.15 * np.sin(2 * ph)
        x *= np.minimum(1, t / 0.004) * np.exp(-t / max(0.25, d * 0.9))
        x = np.tanh(x * 2.6) * 0.8
        m = min(n, n_total - i); out[i:i + m] += x[:m]
    return lp(out, 900)


SCALES = {  # phrygian-ish minor riffs (semitone offsets inside one octave)
    "riffs": [
        [0, 0, 3, 0, 0, 7, 5, 3, 0, 0, 3, 0, 10, 8, 7, 5],
        [0, 3, 0, 7, 0, 3, 8, 7, 0, 3, 0, 7, 5, 3, 1, 0],
        [7, 7, 5, 3, 7, 7, 8, 7, 5, 5, 3, 1, 3, 3, 0, -2],
        [0, 0, 12, 0, 10, 0, 8, 7, 0, 0, 12, 0, 8, 7, 5, 3],
    ],
    "roots": [[0, 0, -4, -2], [0, -4, -5, -2], [0, 1, -2, 0], [0, -2, -4, -5]],
}


def generate(out_wav, duration=22.0, bpm=None, intro_bars=2, seed=None, key=None):
    rng = np.random.default_rng(seed)
    bpm = bpm or int(rng.choice([132, 136, 140, 144, 150]))
    beat = 60.0 / bpm; bar = 4 * beat; s16 = beat / 4
    n_bars = max(intro_bars + 4, int(math.ceil(duration / bar)))
    N = int((n_bars * bar + 1.5) * SR)
    key_semi = NOTE[key] - 9 if key else int(rng.integers(-5, 3))     # relative to A
    riff = SCALES["riffs"][int(rng.integers(len(SCALES["riffs"])))]
    roots = SCALES["roots"][int(rng.integers(len(SCALES["roots"])))]
    drop_t = intro_bars * bar

    bells = np.zeros(N); drums = np.zeros(N); hats = np.zeros(N); bass_notes = []
    K = kick(); C = clap(rng=rng)
    kick_times = []
    for b in range(n_bars):
        t0 = b * bar; root = roots[b % 4]
        intro = b < intro_bars
        # cowbell riff 16ths (+ an octave answer on every 2nd bar)
        for i, semi in enumerate(riff):
            if intro and i % 2: continue
            f = hz(key_semi + root * 0 + semi + 12)           # riff stays on the key; bass carries chord movement
            x = cowbell(f, 0.3)
            st = int((t0 + i * s16) * SR); m = min(len(x), N - st); bells[st:st + m] += x[:m] * (1.0 if intro else 0.75)
        if intro:
            continue
        # drums
        for k in [0, 2.5, 3.0] if b % 2 else [0, 1.75, 2.5]:
            st = int((t0 + k * beat) * SR); m = min(len(K), N - st); drums[st:st + m] += K[:m]; kick_times.append(t0 + k * beat)
        for k in [1, 3]:
            st = int((t0 + k * beat) * SR); m = min(len(C), N - st); drums[st:st + m] += C[:m]
        for i in range(16):
            roll = (b % 4 == 3) and i >= 12
            sub = 3 if roll else 1
            for r in range(sub):
                tt = t0 + i * s16 + r * s16 / sub
                h = hat(open_=(i % 4 == 2 and not roll), rng=rng)
                st = int(tt * SR); m = min(len(h), N - st); hats[st:st + m] += h[:m] * (0.8 if i % 2 == 0 else 0.55)
        # 808: root on 1, answer on the "and" of 2, glide into next bar
        nxt = roots[(b + 1) % 4]
        bass_notes += [(t0, beat * 1.6, key_semi + root - 36, None),
                       (t0 + 1.75 * beat, beat * 1.1, key_semi + root - 36, None),
                       (t0 + 2.5 * beat, beat * 1.5, key_semi + root - 36, key_semi + nxt - 36 if b % 2 else None)]
    bass = bass808(bass_notes, beat, N)

    # intro filter on bells, sidechain duck on kick
    intro_n = int(drop_t * SR)
    bells[:intro_n] = lp(bells[:intro_n], 2200) * 2.2
    # intro: low 808 drone so it does not feel empty
    t_ = np.arange(intro_n) / SR
    drone = np.tanh(np.sin(2 * np.pi * hz(key_semi + roots[0] - 36) * t_) * 1.8) * 0.5 * np.minimum(1, t_ / 0.6)
    bass[:intro_n] += lp(drone, 500)
    duck = np.ones(N)
    for kt in kick_times:
        i = int(kt * SR); n = int(0.18 * SR)
        if i < N: duck[i:i + n] = np.minimum(duck[i:i + n], 0.35 + 0.65 * (np.arange(min(n, N - i)) / n))
    bells *= duck; bass *= duck
    # riser into the drop
    rn = int(bar * SR); rs = max(0, intro_n - rn)
    noise = rng.normal(0, 1, rn); riser = np.zeros(rn)
    for j in range(8):
        a, c = j * rn // 8, (j + 1) * rn // 8; fc = 500 * (10 ** (j / 7))
        riser[a:c] = bp(noise, fc * 0.7, fc * 1.4)[a:c]
    riser *= (np.arange(rn) / rn) ** 2.2 * 0.35
    # stereo mix
    L = bells * 0.42 + bass * 0.95 + drums * 0.85 + hats * 0.9
    R = bells * 0.38 + bass * 0.95 + drums * 0.85 + hats * 0.75
    L[rs:rs + rn] += riser; R[rs:rs + rn] += riser[::-1] * 0 + riser
    st = np.stack([L, R], 1)
    end = int((n_bars * bar + 0.8) * SR); st = st[:end]
    st[-int(0.8 * SR):] *= np.linspace(1, 0, int(0.8 * SR))[:, None]
    st = np.tanh(st / (np.abs(st).max() + 1e-9) * 1.4); st = st / np.abs(st).max() * 0.92
    wavfile.write(out_wav, SR, (st * 32767).astype(np.int16))
    beats = [round(i * beat, 4) for i in range(int(n_bars * 4) + 1)]
    meta = dict(bpm=bpm, beat=beat, bar=bar, drop=round(drop_t, 4), duration=round(len(st) / SR, 3), beats=beats,
                strong=[round(drop_t + i * bar, 4) for i in range(0, n_bars - intro_bars, 2)],
                key_semi=key_semi, generated=True)
    meta["strong"] = sorted(meta["strong"])
    json.dump(meta, open(out_wav.rsplit(".", 1)[0] + ".json", "w"), indent=1)
    return meta


if __name__ == "__main__":
    import sys
    m = generate(sys.argv[1] if len(sys.argv) > 1 else "phonk.wav", duration=float(sys.argv[2]) if len(sys.argv) > 2 else 20, seed=int(sys.argv[3]) if len(sys.argv) > 3 else None)
    print(json.dumps({k: v for k, v in m.items() if k not in ("beats", "strong")}))
