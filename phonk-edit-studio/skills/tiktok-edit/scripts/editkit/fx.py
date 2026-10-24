"""Transitions and per-frame effects (numpy float32 RGB images, square SxS)."""
import math, random
import numpy as np
from PIL import Image, ImageFilter, ImageDraw


def clamp(x, a=0.0, b=1.0): return a if x < a else b if x > b else x
def eoc(p): p = clamp(p); return 1 - (1 - p) ** 3
def eio(p): p = clamp(p); return p * p * (3 - 2 * p)
def toI(x): return Image.fromarray(np.clip(x, 0, 255).astype(np.uint8))
def toA(im): return np.asarray(im, np.float32)


class FX:
    # name -> default duration (s)
    DUR = {"flash": 0.22, "zoom": 0.2, "whip": 0.18, "whipR": 0.18, "whipU": 0.18, "circle": 0.34, "pip": 0.32,
           "glitch": 0.16, "shake": 0.16, "rgb": 0.16, "spin": 0.22, "tile": 0.3, "cut": 0.0}

    def __init__(self, S):
        self.S = S
        yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
        self.RR = np.sqrt((xx - S / 2) ** 2 + (yy - S / 2) ** 2)
        self.VIG = np.clip(1.22 - self.RR / S * 0.8, 0.68, 1)[..., None]
        nr = np.random.default_rng(4)
        self.GR = [toA(toI(nr.normal(0, 6, (S // 2, S // 2)) + 128).resize((S, S)))[..., None] - 128 for _ in range(6)]

    # ---------- primitives
    def zoom_img(self, x, z, rot=0.0, dx=0, dy=0):
        S = self.S; im = toI(x)
        if rot: im = im.rotate(rot, resample=Image.BICUBIC)
        w = S / z; cx = S / 2 + dx; cy = S / 2 + dy
        return toA(im.transform((S, S), Image.EXTENT, (cx - w / 2, cy - w / 2, cx + w / 2, cy + w / 2), Image.BICUBIC))

    def radial_blur(self, x, amount, n=5):
        acc = np.zeros_like(x)
        for k in range(n): acc += self.zoom_img(x, 1 + amount * k / n)
        return acc / n

    def dir_blur(self, x, px, vertical=False):
        if px < 2: return x
        S = self.S; im = toI(x); s = max(8, int(S / (px / 6)))
        im = (im.resize((S, s), Image.BILINEAR) if vertical else im.resize((s, S), Image.BILINEAR)).resize((S, S), Image.BILINEAR)
        return toA(im)

    @staticmethod
    def rgb_split(x, d):
        d = int(d)
        if d < 1: return x
        y = x.copy(); y[:, d:, 0] = x[:, :-d, 0]; y[:, :-d, 2] = x[:, d:, 2]; return y

    def glitch(self, x, amt, seed):
        S = self.S; r = random.Random(seed); y = x.copy()
        for _ in range(int(5 + 10 * amt)):
            y0 = r.randint(0, S - 40); h = r.randint(8, int(S * 0.075)); dx = int(r.randint(-int(S * 0.11), int(S * 0.11)) * amt)
            y[y0:y0 + h] = np.roll(y[y0:y0 + h], dx, axis=1)
        return self.rgb_split(y, 16 * amt * S / 1080)

    def bloom(self, x, k=0.07):
        S = self.S
        g = toA(toI(x).resize((S // 8, S // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4)).resize((S, S), Image.BILINEAR))
        return 255 - (255 - x) * (255 - g * k) / 255

    def ring(self, r, width=16):
        d = np.abs(self.RR - r); m = np.clip(1 - d / width, 0, 1)
        shade = 0.55 + 0.45 * np.clip((self.RR - r) / width, -1, 1)
        return m[..., None], (np.array([200, 205, 215], np.float32) * shade[..., None])

    # ---------- transitions: p in 0..1 across the cut; a=outgoing, b=incoming. returns (img, white_flash_amount)
    def transition(self, kind, p, a, b, seed=0):
        S = self.S; q = eio(p); sinp = math.sin(math.pi * p)
        if kind == "flash": return (a if p < 0.5 else b), sinp ** 1.5
        if kind == "zoom":
            if p < 0.5: return self.radial_blur(self.zoom_img(a, 1 + 0.5 * q * q), 0.25 * q), 0.15 * q
            return self.radial_blur(self.zoom_img(b, 1 + 0.35 * (1 - q) ** 2), 0.25 * (1 - q)), 0.15 * (1 - q)
        if kind in ("whip", "whipR", "whipU"):
            off = int(S * q); out = np.zeros_like(a)
            if kind == "whipU":
                out[:S - off] = a[off:]; out[S - off:] = b[:off]; return self.dir_blur(out, 240 * sinp * S / 1080, True), 0.0
            if kind == "whip": out[:, :S - off] = a[:, off:]; out[:, S - off:] = b[:, :off]
            else: out[:, off:] = a[:, :S - off]; out[:, :off] = b[:, S - off:]
            return self.dir_blur(out, 240 * sinp * S / 1080), 0.0
        if kind == "circle":
            r0 = S * 0.11; r1 = S * 0.185
            r = r0 + (r1 - r0) * eoc(p / 0.4) if p < 0.4 else r1 + (S * 0.78 - r1) * eio((p - 0.4) / 0.6)
            m = np.clip((r - self.RR) / 3, 0, 1)[..., None]
            rm, rc = self.ring(r, 16 * S / 1080)
            out = a * (1 - m) + b * m
            return out * (1 - rm) + rc * rm, 0.0
        if kind == "pip":
            sc = 0.32 + 0.68 * q
            base = toI(a * (1 - 0.35 * q)).filter(ImageFilter.GaussianBlur(6 * q)).convert("RGBA")
            w = max(4, int(S * sc)); im = toI(b).resize((w, w), Image.BILINEAR).convert("RGBA")
            mask = Image.new("L", (w, w), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, w - 1), int(40 * (1 - q)) + 1, fill=255); im.putalpha(mask)
            sh = Image.new("RGBA", (w, w), (0, 0, 0, 140)); sh.putalpha(mask.point(lambda v: v * 140 // 255))
            base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)), ((S - w) // 2 + 10, (S - w) // 2 + 14))
            base.alpha_composite(im, ((S - w) // 2, (S - w) // 2))
            return toA(base.convert("RGB")), 0.0
        if kind == "glitch": return self.glitch(a if p < 0.5 else b, sinp, seed), 0.0
        if kind == "shake":
            r = random.Random(seed); src = a if p < 0.5 else b
            x = self.zoom_img(src, 1.15, (r.random() * 2 - 1) * 5 * sinp, (r.random() * 2 - 1) * 60 * sinp * S / 1080, (r.random() * 2 - 1) * 60 * sinp * S / 1080)
            return self.dir_blur(x, 90 * sinp * S / 1080), 0.08 * sinp
        if kind == "rgb":
            return self.rgb_split(a if p < 0.5 else b, 50 * sinp * S / 1080), 0.1 * sinp
        if kind == "spin":
            ang = 90 * (q if p < 0.5 else q - 1); src = a if p < 0.5 else b
            acc = np.zeros_like(src)
            for k in range(4): acc += self.zoom_img(src, 1.25, ang * (k + 1) / 4)
            return acc / 4, 0.0
        if kind == "tile":
            sc = 1 - 0.78 * q; ang = 25 * q
            base = toI(b * (0.6 + 0.4 * q)).convert("RGBA")
            im = toI(a).resize((max(2, int(S * sc)),) * 2, Image.BILINEAR).convert("RGBA").rotate(ang, expand=True, resample=Image.BICUBIC)
            cx = S / 2 + 0.24 * S * q; cy = S / 2 - 0.18 * S * q
            base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))
            return toA(base.convert("RGB")), 0.0
        return b, 0.0

    def outro_circle(self, x, q):
        """shrink frame into a circle on black (q 0..1)."""
        S = self.S; sc = 1 - 0.85 * q
        w = max(4, int(S * sc)); im = toI(x).resize((w, w), Image.BILINEAR)
        rad = w / 2 * (1.42 - 0.42 * clamp(q * 1.6))
        mask = Image.new("L", (w, w), 0); ImageDraw.Draw(mask).ellipse((w / 2 - rad, w / 2 - rad, w / 2 + rad, w / 2 + rad), fill=255)
        base = Image.new("RGB", (S, S), (0, 0, 0)); base.paste(im, ((S - w) // 2, (S - w) // 2), mask)
        return toA(base) * (1 - clamp((q - 0.75) / 0.25))


def grade(x, contrast=1.1, sat=1.15):
    x = x / 255.0
    x = np.clip((x - 0.5) * contrast + 0.5, 0, 1); x = x * x * (3 - 2 * x) * 0.25 + x * 0.75
    g = x.mean(-1, keepdims=True); x = np.clip(g + (x - g) * sat, 0, 1)
    return x * 255
