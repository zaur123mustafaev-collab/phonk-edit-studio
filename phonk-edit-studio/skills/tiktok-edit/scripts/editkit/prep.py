"""Clip preparation: probe, auto-crop (borders / clip-pack text overlays), shot detection, frame loading."""
import json, re, subprocess
import numpy as np


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=kw.pop("text", True), **kw)


def probe(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
               "-of", "json", path]).stdout
    d = json.loads(out)
    info = {"duration": float(d["format"]["duration"]), "has_audio": False, "has_video": False}
    for s in d.get("streams", []):
        if s["codec_type"] == "video" and not info["has_video"]:
            n, m = s["r_frame_rate"].split("/")
            info.update(has_video=True, width=s["width"], height=s["height"], fps=float(n) / float(m or 1))
        if s["codec_type"] == "audio":
            info["has_audio"] = True
    return info


def sample_frames(path, n=48, width=None):
    """Grab n frames evenly spread over the clip (full resolution unless width given)."""
    info = probe(path)
    W, H = info["width"], info["height"]
    if width:
        H = int(round(H * width / W / 2) * 2); W = width
    fps = n / max(0.5, info["duration"])
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-vf", f"fps={fps},scale={W}:{H}", "-frames:v", str(n),
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    return a.reshape(-1, H, W, 3), (W, H)


def auto_crop(path, inset=4, square=True, expand=False):
    """Find the region that actually moves (the real footage) and drop static borders,
    letterbox bars and clip-pack text overlays ("4K CLIPS FOR EDITS", "FOLLOW FOR MORE", ...).
    Returns crop box (x, y, w, h) in source pixels."""
    frames, (W, H) = sample_frames(path, n=48)
    f = frames.astype(np.float32).mean(-1)
    std = f.std(0)                                 # temporal variation per pixel
    act = std > max(6.0, np.percentile(std, 35) * 0.5)
    rows = act.mean(1); cols = act.mean(0)
    def span(prof, thr):
        idx = np.where(prof > thr)[0]
        if len(idx) == 0: return 0, len(prof) - 1
        # longest contiguous run (text lines above/below are separate short runs)
        runs, s = [], idx[0]
        for a, b in zip(idx[:-1], idx[1:]):
            if b != a + 1: runs.append((s, a)); s = b
        runs.append((s, idx[-1]))
        return max(runs, key=lambda r: r[1] - r[0])
    y0, y1 = span(rows, 0.45)
    x0, x1 = span(act[y0:y1 + 1].mean(0), 0.45)
    # refine: walk each edge inward while that edge line is mostly static (border / frame colour)
    def edge_ok(line): return line.mean() > 0.7
    for _ in range(max(W, H)):
        moved = False
        if not edge_ok(act[y0:y1 + 1, x0]): x0 += 1; moved = True
        if not edge_ok(act[y0:y1 + 1, x1]): x1 -= 1; moved = True
        if not edge_ok(act[y0, x0:x1 + 1]): y0 += 1; moved = True
        if not edge_ok(act[y1, x0:x1 + 1]): y1 -= 1; moved = True
        if not moved: break
    if expand:  # logo / screen-recording mode: grow until we hit the static app UI around the canvas
        med = np.median(frames.astype(np.float32), 0)
        border = np.concatenate([med[:H // 12].reshape(-1, 3), med[-H // 12:].reshape(-1, 3), med[:, :W // 12].reshape(-1, 3), med[:, -W // 12:].reshape(-1, 3)])
        ui = np.median(border, 0)                                   # dominant app background colour
        tol = min(40.0, 0.5 * float(ui.mean()))                    # light UI: loose, dark UI: strict (canvas is often black)
        ui_like = (std < 3.0) & (np.abs(med - ui).max(-1) < tol)
        for _ in range(600):
            grown = False
            if x0 > 0 and ui_like[y0:y1 + 1, x0 - 1].mean() < 0.5: x0 -= 1; grown = True
            if x1 < W - 1 and ui_like[y0:y1 + 1, x1 + 1].mean() < 0.5: x1 += 1; grown = True
            if y0 > 0 and ui_like[y0 - 1, x0:x1 + 1].mean() < 0.5: y0 -= 1; grown = True
            if y1 < H - 1 and ui_like[y1 + 1, x0:x1 + 1].mean() < 0.5: y1 += 1; grown = True
            if not grown: break
    x0 += inset; y0 += inset; x1 -= inset; y1 -= inset
    w, h = x1 - x0 + 1, y1 - y0 + 1
    if square:
        s = min(w, h); x0 += (w - s) // 2; y0 += (h - s) // 2; w = h = s
    w -= w % 2; h -= h % 2
    return dict(x=int(x0), y=int(y0), w=int(w), h=int(h), src_w=W, src_h=H)


def detect_shots(path, crop=None, thresh=0.22, min_len=0.35):
    vf = (f"crop={crop['w']}:{crop['h']}:{crop['x']}:{crop['y']}," if crop else "") + f"select='gt(scene,{thresh})',showinfo"
    err = run(["ffmpeg", "-hide_banner", "-i", path, "-vf", vf, "-an", "-f", "null", "-"]).stderr
    cuts = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", err)]
    dur = probe(path)["duration"]
    pts = [0.0]
    for c in cuts:
        if c - pts[-1] >= min_len and dur - c >= min_len: pts.append(c)
    pts.append(dur)
    return [(round(a, 3), round(b, 3)) for a, b in zip(pts[:-1], pts[1:])]


def shot_motion(path, shots, crop=None):
    """Rough 'action' score per shot (mean abs frame difference) — used to put high-energy shots on the drop."""
    vf = (f"crop={crop['w']}:{crop['h']}:{crop['x']}:{crop['y']}," if crop else "") + "fps=10,scale=96:96"
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8).reshape(-1, 96, 96).astype(np.float32)
    d = np.abs(np.diff(a, axis=0)).mean((1, 2))
    gx = np.abs(np.diff(a, axis=2)).mean((1, 2)); gy = np.abs(np.diff(a, axis=1)).mean((1, 2))
    sharp = gx + gy                                   # detail per frame (blurry flashes / fades score low)
    med_sharp = float(np.median(sharp)) + 1e-6
    out = []
    for s0, s1 in shots:
        i0, i1 = int(s0 * 10) + 1, max(int(s0 * 10) + 2, int(s1 * 10) - 1)
        seg = d[i0:i1]; sh = sharp[i0:i1]
        m = float(seg.mean()) if len(seg) else 0.0
        k = float(min(1.0, (sh.mean() if len(sh) else 0) / med_sharp))   # penalise blurry / empty shots
        out.append(m * k ** 2)
    return out


def load_frames(path, crop=None, size=None, fps=None):
    """Decode the (cropped) clip to an RGB uint8 array [N, S, S, 3]."""
    vf = []
    if crop: vf.append(f"crop={crop['w']}:{crop['h']}:{crop['x']}:{crop['y']}")
    if fps: vf.append(f"fps={fps}")
    if size: vf.append(f"scale={size}:{size}:flags=lanczos")
    cmd = ["ffmpeg", "-loglevel", "error", "-i", path] + (["-vf", ",".join(vf)] if vf else []) + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.run(cmd, capture_output=True)
    if size: w = h = size
    elif crop: w, h = crop["w"], crop["h"]
    else:
        i = probe(path); w, h = i["width"], i["height"]
    return np.frombuffer(p.stdout, np.uint8).reshape(-1, h, w, 3)
