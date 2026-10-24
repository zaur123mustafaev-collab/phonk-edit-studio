"""Build the soundtrack for a plan: music intro -> (optional dialogue over a quiet music bed + riser) -> drop -> tail."""
import subprocess
import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000


def _load(path, start=0.0, end=None):
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", str(max(0, start)), "-i", path]
    if end is not None: cmd += ["-t", str(max(0.01, end - start))]
    cmd += ["-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    p = subprocess.run(cmd, capture_output=True)
    return np.frombuffer(p.stdout, np.float32).reshape(-1, 2).astype(np.float64)


def _rms_db(x): return 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9)


def _fade(x, fi=0.0, fo=0.0):
    x = x.copy()
    if fi > 0 and len(x): k = min(len(x), int(fi * SR)); x[:k] *= np.linspace(0, 1, k)[:, None]
    if fo > 0 and len(x): k = min(len(x), int(fo * SR)); x[-k:] *= np.linspace(1, 0, k)[:, None]
    return x


def _riser(dur, rng):
    n = int(dur * SR); noise = rng.normal(0, 1, (n, 2)); out = np.zeros_like(noise)
    for j in range(10):
        a, b = j * n // 10, (j + 1) * n // 10; fc = 400 * (14 ** (j / 9))
        sos = butter(2, [fc * 0.7, min(fc * 1.4, 20000)], "band", fs=SR, output="sos"); out[a:b] = sosfilt(sos, noise, axis=0)[a:b]
    return out * ((np.arange(n) / n) ** 2.5)[:, None] * 0.25


def _boom(dur=1.4):
    n = int(dur * SR); t = np.arange(n) / SR; f = 30 + 70 * np.exp(-t * 9)
    b = np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.45) * 2.2) * 0.55
    return np.stack([b, b], 1)


def build(plan, music_path, clip_path, out_wav, boom=True):
    rng = np.random.default_rng(1)
    M = plan["music"]; TL = plan["timeline"]; total = plan["total"]
    out = np.zeros((int(total * SR) + SR, 2))
    def put(x, t, g=1.0):
        i = int(t * SR); n = max(0, min(len(x), len(out) - i)); out[i:i + n] += x[:n] * g
    drop_part = _load(music_path, M["drop"], M["end"] + M["tail"])
    ref = _rms_db(drop_part[: int(8 * SR)])
    # intro music (no loudness filter on short pieces — same gain as the track)
    put(_fade(_load(music_path, M["start"], M["drop"] + 0.05), 0.0, 0.05), 0.0)
    if TL.get("dialogue"):
        d0, d1 = TL["dialogue"]; dl = d1 - d0
        # quiet low-passed bed: loop the intro bar(s)
        loop = _load(music_path, M["start"], M["drop"])
        if len(loop) > SR * 0.5:
            bed = np.concatenate([loop] * (int(dl / (len(loop) / SR)) + 2))[: int(dl * SR)]
            bed = sosfilt(butter(4, 650, "low", fs=SR, output="sos"), bed, axis=0)
            put(_fade(bed, 0.15, 0.1), d0, 10 ** (-13 / 20))
        seg = [s for s in plan["segments"] if s["kind"] == "dialogue"][0]
        dlg = _load(clip_path, seg["src"][0], seg["src"][1])
        g = 10 ** ((ref - 2 - _rms_db(dlg)) / 20)
        put(_fade(dlg * g, 0.02, 0.06), d0)
        put(_riser(min(1.3, dl * 0.4), rng), TL["drop"] - min(1.3, dl * 0.4))
    put(_fade(drop_part, 0.0, M["tail"]), TL["drop"])
    if boom: put(_boom(), TL["drop"])
    out = out[: int(total * SR)]
    pk = np.abs(out).max() + 1e-9
    out = np.tanh(out / pk * 1.15) * 0.93
    import soundfile as sf
    sf.write(out_wav, out, SR)
    return out_wav


def mux(video, wav, out_mp4):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart", out_mp4], check=True)
    return out_mp4
