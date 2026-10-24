"""Watermarks.
1) 'mark'  : small, semi-transparent logo/text, ALWAYS on screen (anti-theft). From a PNG/JPG/video frame or plain text.
2) 'video' : the creator's animated watermark (e.g. a CapCut intro), luma-keyed (black = transparent),
             played ONCE, centered, without its sound."""
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .prep import auto_crop, probe

FONT_CANDIDATES = ["/usr/share/fonts/opentype/inter/InterDisplay-Black.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                   "C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]


def _font(size):
    for f in FONT_CANDIDATES:
        try: return ImageFont.truetype(f, size)
        except Exception: pass
    return ImageFont.load_default()


def text_mark(text, color=(120, 200, 255)):
    f = _font(120); l, t, r, b = f.getbbox(text); pad = 30
    im = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.text((pad - l, pad - t), text, font=f, fill=color + (255,), stroke_width=4, stroke_fill=(0, 0, 0, 160))
    glow = im.filter(ImageFilter.GaussianBlur(10))
    return Image.alpha_composite(glow, im)


def luma_key(img_rgb, lo=18, span=150):
    x = np.asarray(img_rgb.convert("RGB"), np.float32)
    a = np.clip((x.max(-1) - lo) / span, 0, 1)
    return Image.fromarray(np.dstack([x, a * 255]).astype(np.uint8), "RGBA")


def image_mark(path):
    im = Image.open(path)
    if im.mode == "RGBA" and np.asarray(im)[..., 3].min() < 250:
        rgba = im
    else:  # no alpha: treat dark background as transparent
        rgba = luma_key(im.convert("RGB"))
    bb = rgba.getbbox()
    return rgba.crop(bb) if bb else rgba


def mark_from_video(path, t=None):
    """Grab the brightest compact frame of a logo video (e.g. the text-only part of an intro) as a still mark."""
    c = auto_crop(path, inset=2, expand=True)
    dur = probe(path)["duration"]
    best, best_score = None, -1
    for tt in np.linspace(0.2, max(0.3, dur - 0.2), 16) if t is None else [t]:
        p = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(tt), "-i", path, "-vf", f"crop={c['w']}:{c['h']}:{c['x']}:{c['y']}",
                            "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        x = np.frombuffer(p.stdout, np.uint8).reshape(c["h"], c["w"], 3)
        m = x.max(-1) > 60
        if m.mean() < 0.002: continue
        ys, xs = np.where(m)
        area = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1) / m.size
        cx, cy = xs.mean() / m.shape[1], ys.mean() / m.shape[0]
        score = (1 - area) * (1 - abs(cx - 0.5)) * (1 - abs(cy - 0.5))   # compact, centred bright element = the logo text
        if score > best_score: best_score, best = score, x
    rgba = luma_key(Image.fromarray(best))
    bb = rgba.getchannel("A").point(lambda v: 255 if v > 60 else 0).getbbox()
    if bb:
        pad = 12; bb = (max(0, bb[0] - pad), max(0, bb[1] - pad), min(rgba.width, bb[2] + pad), min(rgba.height, bb[3] + pad))
        rgba = rgba.crop(bb)
    if rgba.width < 300:  # upscale tiny text crisply
        k = 300 / rgba.width; rgba = rgba.resize((int(rgba.width * k), int(rgba.height * k)), Image.LANCZOS).filter(ImageFilter.UnsharpMask(2, 80, 2))
    return rgba


class Marks:
    def __init__(self, S, mark_img=None, mark_width=0.19, mark_opacity=0.68, mark_pos="bottom",
                 video_path=None, video_size=0.52, video_opacity=0.62, video_start=None, video_src=(0.0, None)):
        self.S = S
        self.mark = None
        if mark_img is not None:
            w = int(S * mark_width); im = mark_img.resize((w, max(1, int(mark_img.height * w / mark_img.width))), Image.LANCZOS)
            a = np.asarray(im, np.float32); self.m_rgb = a[..., :3]; self.m_a = a[..., 3:4] / 255 * mark_opacity
            h = self.m_rgb.shape[0]
            self.m_x = (S - w) // 2
            self.m_y = {"bottom": S - h - int(S * 0.037), "center": (S - h) // 2, "top": int(S * 0.037)}.get(mark_pos, S - h - int(S * 0.037))
            self.mark = True
        self.vid = None
        if video_path:
            c = auto_crop(video_path, inset=2, expand=True)                    # also strips screen-recording UI around a CapCut canvas
            sz = int(S * video_size); sz -= sz % 2
            src0, src1 = video_src
            dur = probe(video_path)["duration"]; src1 = min(src1 or dur, src0 + 6.0, dur)
            p = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(src0), "-t", str(src1 - src0), "-i", video_path,
                                "-vf", f"crop={c['w']}:{c['h']}:{c['x']}:{c['y']},fps=30,scale={sz}:{sz}:flags=lanczos",
                                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
            self.vid = np.frombuffer(p.stdout, np.uint8).reshape(-1, sz, sz, 3)
            yy, xx = np.mgrid[0:sz, 0:sz].astype(np.float32)
            self.v_mask = (np.clip((sz / 2 - np.sqrt((xx - sz / 2) ** 2 + (yy - sz / 2) ** 2)) / (sz * 0.125), 0, 1) ** 1.2)[..., None] * video_opacity
            self.v_sz = sz; self.v_start = video_start or 0.0; self.v_len = len(self.vid) / 30.0

    def apply(self, x, t):
        S = self.S
        if self.vid is not None:
            wl = t - self.v_start
            if 0 <= wl < self.v_len:
                k = min(len(self.vid) - 1, int(wl * 30)); v = self.vid[k].astype(np.float32)
                fade = min(1, wl / 0.2) * min(1, (self.v_len - wl) / 0.3)
                al = np.clip((v.max(-1, keepdims=True) - 18) / 150, 0, 1) * self.v_mask * fade
                y0 = (S - self.v_sz) // 2; reg = x[y0:y0 + self.v_sz, y0:y0 + self.v_sz]
                x[y0:y0 + self.v_sz, y0:y0 + self.v_sz] = reg * (1 - al) + v * al
        if self.mark:
            h, w = self.m_rgb.shape[:2]; y0, x0 = self.m_y, self.m_x
            reg = x[y0:y0 + h, x0:x0 + w]; x[y0:y0 + h, x0:x0 + w] = reg * (1 - self.m_a) + self.m_rgb * self.m_a
        return x
