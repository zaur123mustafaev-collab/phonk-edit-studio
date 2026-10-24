"""Render a plan to MP4 (video only). Multiprocess: each worker renders a chunk, then chunks are concatenated."""
import math, os, random, subprocess, tempfile
import numpy as np
from PIL import Image, ImageFilter

from .fx import FX, grade, clamp, eoc, eio, toI, toA

G = {}  # worker globals (filled before fork)


def _env(t, lst, decay, win=0.6):
    v = 0.0
    for b in lst:
        if 0 <= t - b < win: v = max(v, math.exp(-(t - b) * decay))
    return v


def _src_time(seg, t):
    D = max(1e-3, seg["t1"] - seg["t0"]); u = clamp((t - seg["t0"]) / D)
    if seg["kind"] == "dialogue":
        return seg["src"][0] + (t - seg["t0"]), 1.0
    s0, s1 = seg["shot"]; s0 += 0.04; s1 -= 0.04
    start = s0 + (s1 - s0) * seg.get("frac", 0)
    L = min(D * seg.get("speed", 1.0), max(0.1, s1 - start))
    if seg["kind"] == "intro" or seg.get("speed", 1) < 0.6:
        return start + L * u, L / D
    g = eoc(u) * 0.45 + u * 0.55                     # soft velocity: rushes in, settles
    return start + L * g, (L / D) * (1.35 * (1 - u) ** 2 + 0.55)


def _sample(st, spd):
    A = G["frames"]; i0 = max(0, min(len(A) - 1, int(round(st * G["src_fps"]))))
    img = A[i0].astype(np.float32)
    if spd > 2.2: img = (img + A[max(0, i0 - 1)].astype(np.float32)) / 2
    return img


def _seg_frame(seg, t, fi):
    P = G["plan"]; S = P["size"]; SRC = G["frames"].shape[1]
    st, spd = _src_time(seg, t)
    im = toI(grade(_sample(st, spd)))
    lt = t - seg["t0"]; D = max(1e-3, seg["t1"] - seg["t0"])
    if seg["kind"] == "intro":
        zoom = 1.04 + 0.12 * eio(lt / D); pb = ps = 0.0
    elif seg["kind"] == "dialogue":
        ac = 0.0
        for a, s in P.get("accents", []):
            if 0 <= t - a < 0.6: ac = max(ac, s * math.exp(-(t - a) * 7))
        pb, ps = 0.0, ac
        zoom = 1.03 + 0.07 * eio(lt / D) + 0.12 * ac + 0.10 * eio((t - (seg["t1"] - 0.8)) / 0.8)
    else:
        pb = _env(t, P["beats_t"], 10); ps = _env(t, P["strong_t"], 8)
        # refs: every shot zooms 15-20 % (alternating in / out) + a zoom kick on the first frames after a plain cut / flash
        zin = int(seg["t0"] * 1000) % 2 == 0; u = eoc(lt / max(0.2, D))
        zoom = (1.05 + 0.15 * u) if zin else (1.21 - 0.15 * u)
        if seg.get("tr") in ("cut", "expo", None): zoom += 0.12 * math.exp(-lt * 11)
        zoom += 0.06 * pb + 0.05 * ps
    rr = random.Random(fi * 7 + int(seg["t0"] * 100)); shk = (9 * ps + 3 * pb) * SRC / 640
    hh = 0.0 if seg["kind"] == "intro" else SRC * 0.007                 # refs: constant light hand-held shake
    hx = hh * (math.sin(t * 8.1) + 0.6 * math.sin(t * 17.3 + 1.1)); hy = hh * (math.sin(t * 6.7 + 2.0) + 0.6 * math.sin(t * 15.1))
    cw = SRC / zoom
    cx0 = clamp((SRC - cw) / 2 + (rr.random() * 2 - 1) * shk + hx, 0, SRC - cw)
    cy0 = clamp((SRC - cw) / 2 + (rr.random() * 2 - 1) * shk + hy, 0, SRC - cw)
    im = im.resize((S, S), Image.LANCZOS, box=(cx0, cy0, cx0 + cw, cy0 + cw)).filter(ImageFilter.UnsharpMask(1.6, 85, 2))
    x = toA(im)
    return G["fx"].rgb_split(x, (10 * ps + 3 * pb) * S / 1080) if (ps + pb) > 0.08 else x


_CAP = {}
def _caption(x, text, S, t, t_end):
    """refs: meme caption in a white bar at the top during the intro (gone on the drop)."""
    if text not in _CAP:
        from PIL import ImageDraw, ImageFont
        font = None
        for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
                  "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf"):
            try: font = ImageFont.truetype(f, int(S * 0.045)); break
            except Exception: pass
        font = font or ImageFont.load_default()
        words, lines, cur = text.split(), [], ""
        d0 = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        for w in words:                       # wrap to the frame width
            trial = (cur + " " + w).strip()
            if d0.textlength(trial, font=font) > S * 0.9 and cur: lines.append(cur); cur = w
            else: cur = trial
        lines.append(cur)
        lh = int(S * 0.055); h = lh * len(lines) + int(S * 0.025)
        bar = Image.new("RGB", (S, h), (255, 255, 255)); d = ImageDraw.Draw(bar)
        for i, ln in enumerate(lines):
            d.text(((S - d.textlength(ln, font=font)) / 2, int(S * 0.012) + i * lh), ln, font=font, fill=(0, 0, 0))
        _CAP[text] = toA(bar)
    bar = _CAP[text]; h = bar.shape[0]
    a = clamp(t / 0.25) * clamp((t_end - t) / 0.12)
    x[:h] = x[:h] * (1 - a) + bar * a
    return x


def render_frame(fi):
    P = G["plan"]; fx = G["fx"]; S = P["size"]; segs = P["segments"]
    t = fi / P["fps"]
    k = 0
    for k, s in enumerate(segs):
        if t < s["t1"]: break
    seg = segs[k]; nxt = segs[k + 1] if k + 1 < len(segs) else None
    flash = 0.0
    if nxt and nxt.get("tr") and FX.DUR.get(nxt["tr"], 0) > 0 and t > seg["t1"] - FX.DUR[nxt["tr"]] / 2:
        d = FX.DUR[nxt["tr"]]; p = (t - (seg["t1"] - d / 2)) / d
        x, flash = fx.transition(nxt["tr"], p, _seg_frame(seg, t, fi), _seg_frame(nxt, t, fi), fi)
    elif k > 0 and seg.get("tr") and FX.DUR.get(seg["tr"], 0) > 0 and t < seg["t0"] + FX.DUR[seg["tr"]] / 2:
        d = FX.DUR[seg["tr"]]; p = (t - (seg["t0"] - d / 2)) / d
        x, flash = fx.transition(seg["tr"], p, _seg_frame(segs[k - 1], t, fi), _seg_frame(seg, t, fi), fi)
    else:
        x = _seg_frame(seg, t, fi)
    x = fx.bloom(x, 0.07)
    if t >= P["timeline"]["drop"]:                                       # refs: brightness / colour pop on every beat
        pulse = _env(t, P["beats_t"], 14, 0.3)
        if pulse > 0.02:
            g = x.mean(-1, keepdims=True); x = g + (x - g) * (1 + 0.3 * pulse); x = x * (1 + 0.08 * pulse) + 8 * pulse
    x = x * fx.VIG + fx.GR[fi % len(fx.GR)] * 0.2
    flash = max(flash, _env(t, P["strong_t"], 20, 0.2) * 0.12)
    if flash > 0: x = x + (255 - x) * flash
    if P.get("caption") and t < P["timeline"]["drop"]:
        x = _caption(x, P["caption"], S, t, P["timeline"]["drop"])
    if P.get("outro") == "circle" and t > P["total"] - 0.75:
        x = fx.outro_circle(x, eio((t - (P["total"] - 0.75)) / 0.75))
    elif P.get("outro") == "diamond" and t > P["total"] - 0.8:
        x = fx.outro_diamond(x, (t - (P["total"] - 0.8)) / 0.8)
    elif t > P["total"] - 0.4:
        x = x * clamp((P["total"] - t) / 0.4)
    if t < 0.08: x = x * (t / 0.08)
    if G.get("marks") is not None: x = G["marks"].apply(x, t)
    return np.clip(x, 0, 255).astype(np.uint8)


def _worker(args):
    f0, f1, out = args
    P = G["plan"]; S = P["size"]
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{S}x{S}", "-r", str(P["fps"]), "-i", "-",
                          "-c:v", "libx264", "-preset", "slow", "-crf", str(G.get("crf", 14)), "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        p.stdin.write(render_frame(fi).tobytes())
    p.stdin.close(); p.wait()
    return out


def render(plan, frames, src_fps, out_mp4, marks=None, workers=None, crf=14, progress=True):
    import multiprocessing as mp
    G.update(plan=plan, frames=frames, src_fps=src_fps, fx=FX(plan["size"]), marks=marks, crf=crf)
    n = int(plan["total"] * plan["fps"])
    workers = workers or max(1, min(os.cpu_count() or 2, 8))
    if not hasattr(os, "fork"):   # Windows: worker processes would not inherit the loaded frames -> render in-process
        workers = 1
    chunk = math.ceil(n / workers)
    tmp = tempfile.mkdtemp(prefix="edit_")
    jobs = [(i * chunk, min(n, (i + 1) * chunk), os.path.join(tmp, f"part{i:02d}.mp4")) for i in range(workers) if i * chunk < n]
    ctx = mp.get_context("fork") if hasattr(os, "fork") else mp.get_context()
    if len(jobs) == 1:
        parts = [_worker(jobs[0])]
    else:
        with ctx.Pool(len(jobs)) as pool:
            parts = pool.map(_worker, jobs)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        for p_ in parts: f.write(f"file '{p_}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out_mp4], check=True)
    return out_mp4


def preview_frames(plan, frames, src_fps, times, marks=None):
    G.update(plan=plan, frames=frames, src_fps=src_fps, fx=FX(plan["size"]), marks=marks)
    return [Image.fromarray(render_frame(int(t * plan["fps"]))) for t in times]
