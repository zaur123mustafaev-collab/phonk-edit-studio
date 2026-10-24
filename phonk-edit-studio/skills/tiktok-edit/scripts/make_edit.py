#!/usr/bin/env python3
"""TikTok edit maker — CLI.

  python make_edit.py analyze --clip CLIP.mp4 [--music TRACK.mp3] [--transcribe] --work WORK
  python make_edit.py plan    --work WORK [--music-source auto|file|clip|phonk] [--pace calm|medium|fast]
                              [--style clean|hype] [--target 18] [--dialogue 11.1-16.5] [--drop 3.55] [--seed 7]
  python make_edit.py preview --work WORK [--times 1,5,9]           -> WORK/preview.jpg (contact sheet)
  python make_edit.py render  --work WORK --out EDIT.mp4 [--mark-video WM.mp4] [--mark-image LOGO.png | --mark-text NAME]
                              [--wm-video WM.mp4 --wm-start 7.2] [--fps 60] [--size 1080]
  python make_edit.py auto    --clip CLIP.mp4 [--music ...] --out EDIT.mp4 [all options above]

WORK is a folder; every step reads/writes WORK/analysis.json and WORK/plan.json (edit plan.json by hand if needed).
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from editkit import prep, audio, plan as planmod, render as rend, audio_mix, phonk
from editkit.watermark import Marks, image_mark, text_mark, mark_from_video


def jload(p): return json.load(open(p))
def jsave(o, p): json.dump(o, open(p, "w"), indent=1, ensure_ascii=False)


def cmd_analyze(a):
    os.makedirs(a.work, exist_ok=True)
    info = prep.probe(a.clip)
    crop = prep.auto_crop(a.clip, square=True) if not a.no_crop else dict(x=0, y=0, w=min(info["width"], info["height"]), h=min(info["width"], info["height"]), src_w=info["width"], src_h=info["height"])
    shots = prep.detect_shots(a.clip, crop)
    motion = prep.shot_motion(a.clip, shots, crop)
    res = dict(clip=os.path.abspath(a.clip), info=info, crop=crop, shots=shots, motion=[round(m, 2) for m in motion])
    if info["has_audio"]:
        w = audio.to_wav(a.clip, os.path.join(a.work, "clip.wav"))
        res["clip_music"] = audio.music_presence(w)
        if res["clip_music"]["score"] >= 0.6: res["clip_music_analysis"] = audio.analyze_music(w)
        if a.transcribe:
            w16 = audio.to_wav(a.clip, os.path.join(a.work, "clip16.wav"), sr=16000)
            res["transcript"] = audio.transcribe(w16)
    else:
        res["clip_music"] = dict(score=0.0, silent=True)
    if a.music:
        res["music_file"] = os.path.abspath(a.music)
        mw = audio.to_wav(a.music, os.path.join(a.work, "music.wav"))
        res["music_analysis"] = audio.analyze_music(mw)
    jsave(res, os.path.join(a.work, "analysis.json"))
    # shot contact sheet
    try:
        from PIL import Image, ImageDraw
        import subprocess
        cols = 8; th = 160; rows = (len(shots) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * th, rows * (th + 18)), (25, 25, 25))
        for i, (s0, s1) in enumerate(shots):
            p = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str((s0 + s1) / 2), "-i", a.clip, "-vf",
                                f"crop={crop['w']}:{crop['h']}:{crop['x']}:{crop['y']},scale={th}:{th}", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
            im = Image.frombytes("RGB", (th, th), p.stdout)
            x, y = (i % cols) * th, (i // cols) * (th + 18)
            sheet.paste(im, (x, y)); ImageDraw.Draw(sheet).text((x + 3, y + th + 2), f"{i}: {s0:.1f}-{s1:.1f} m{motion[i]:.0f}", fill=(255, 220, 0))
        sheet.save(os.path.join(a.work, "shots.jpg"), quality=85)
    except Exception as e:
        print("contact sheet failed:", e)
    cm = res["clip_music"]
    print(json.dumps(dict(crop=crop, n_shots=len(shots), clip_has_audio=info["has_audio"], clip_music_score=round(cm.get("score", 0), 2),
                          music_file=bool(a.music), transcript_lines=len(res.get("transcript", [])),
                          drop_guess=(res.get("music_analysis") or res.get("clip_music_analysis") or {}).get("drop")), ensure_ascii=False, indent=1))
    for s in res.get("transcript", []): print(f"  [{s['start']:.2f}-{s['end']:.2f}] {s['text']}")


def cmd_plan(a):
    A = jload(os.path.join(a.work, "analysis.json"))
    src = a.music_source
    if src == "auto":
        src = "file" if A.get("music_file") else ("clip" if A["clip_music"].get("score", 0) >= 0.6 else "phonk")
    if src == "file":
        music_path = A["music_file"]; M = A["music_analysis"]
    elif src == "clip":
        music_path = os.path.join(a.work, "clip.wav"); M = A.get("clip_music_analysis") or audio.analyze_music(music_path)
    else:
        music_path = os.path.join(a.work, "phonk.wav")
        M = phonk.generate(music_path, duration=a.target + 6, seed=a.seed, bpm=a.bpm)
    dialogue = tuple(float(x) for x in a.dialogue.split("-")) if a.dialogue else None
    P = planmod.build_plan(A["shots"], A["motion"], M, A["info"]["duration"], pace=a.pace, style=a.style, target=a.target,
                           dialogue=dialogue, drop=a.drop, seed=a.seed, size=a.size, fps=a.fps, intro_beats=a.intro_beats)
    P["music_source"] = src; P["music_path"] = music_path; P["clip"] = A["clip"]; P["crop"] = A["crop"]
    if dialogue and A.get("transcript"):  # zoom accents on the last word of each sentence of the dialogue
        acc = []
        for s in A["transcript"]:
            if s["words"] and dialogue[0] <= s["words"][-1]["t"] <= dialogue[1]:
                acc.append([round(P["timeline"]["dialogue"][0] + s["words"][-1]["t"] - dialogue[0], 3), 0.7])
        if acc: acc[-1][1] = 1.0
        P["accents"] = acc
    jsave(P, os.path.join(a.work, "plan.json"))
    print(json.dumps(dict(music_source=src, total=P["total"], drop_at=P["timeline"]["drop"], segments=len(P["segments"])), indent=1))
    for s in P["segments"]:
        print(f"  {s['kind']:8s} {s['t0']:6.2f}-{s['t1']:6.2f}  shot={s.get('shot') or s.get('src')}  tr={s.get('tr')}")


def _frames(P):
    return prep.load_frames(P["clip"], P["crop"]), prep.probe(P["clip"])["fps"]


def _marks(a, P):
    mark = None
    if a.mark_image: mark = image_mark(a.mark_image)
    elif a.mark_text: mark = text_mark(a.mark_text)
    elif a.mark_video: mark = mark_from_video(a.mark_video)
    if mark is None and not a.wm_video: return None
    # default: the brightest moment of the watermark animation lands on the drop
    return Marks(P["size"], mark_img=mark, video_path=a.wm_video, video_start=a.wm_start, video_anchor=P["timeline"]["drop"],
                 video_src=(a.wm_src0, a.wm_src1), mark_width=a.mark_width, mark_opacity=a.mark_opacity)


def cmd_preview(a):
    P = jload(os.path.join(a.work, "plan.json"))
    frames, fps = _frames(P)
    times = [float(x) for x in a.times.split(",")] if a.times else [round(s["t0"] + (s["t1"] - s["t0"]) * 0.5, 2) for s in P["segments"]][:16]
    ims = rend.preview_frames(P, frames, fps, times, marks=_marks(a, P))
    from PIL import Image
    th = 270; cols = min(8, len(ims)); rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * th, rows * th))
    for i, im in enumerate(ims): sheet.paste(im.resize((th, th)), ((i % cols) * th, (i // cols) * th))
    out = os.path.join(a.work, "preview.jpg"); sheet.save(out, quality=88); print(out, times)


def cmd_render(a):
    P = jload(os.path.join(a.work, "plan.json"))
    frames, fps = _frames(P)
    vid = os.path.join(a.work, "video.mp4")
    rend.render(P, frames, fps, vid, marks=_marks(a, P), workers=a.workers, crf=a.crf)
    wav = audio_mix.build(P, P["music_path"], P["clip"], os.path.join(a.work, "audio.wav"), boom=not a.no_boom)
    audio_mix.mux(vid, wav, a.out)
    print("done:", a.out, f"{P['total']:.1f}s")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    def common(p):
        p.add_argument("--work", default="edit_work")
    def plan_args(p):
        p.add_argument("--music-source", default="auto", choices=["auto", "file", "clip", "phonk"])
        p.add_argument("--pace", default="medium", choices=["calm", "medium", "fast"])
        p.add_argument("--style", default="clean", choices=["clean", "hype"])
        p.add_argument("--target", type=float, default=18.0)
        p.add_argument("--dialogue", default=None, help="clip seconds, e.g. 11.1-16.5")
        p.add_argument("--drop", type=float, default=None, help="override drop time in the music (seconds)")
        p.add_argument("--intro-beats", type=int, default=4)
        p.add_argument("--seed", type=int, default=7)
        p.add_argument("--bpm", type=int, default=None, help="phonk generator tempo")
        p.add_argument("--size", type=int, default=1080)
        p.add_argument("--fps", type=int, default=60)
    def mark_args(p):
        p.add_argument("--mark-image"); p.add_argument("--mark-text"); p.add_argument("--mark-video", help="take the small always-on mark from a logo video")
        p.add_argument("--mark-width", type=float, default=0.19); p.add_argument("--mark-opacity", type=float, default=0.68)
        p.add_argument("--wm-video", help="animated watermark video, played once, centred, silent")
        p.add_argument("--wm-start", type=float, default=None); p.add_argument("--wm-src0", type=float, default=0.0); p.add_argument("--wm-src1", type=float, default=None, help="default: auto - exactly one pass of the animation (loops in the recording are cut), max 6 s")
    p = sub.add_parser("analyze"); common(p); p.add_argument("--clip", required=True); p.add_argument("--music"); p.add_argument("--transcribe", action="store_true"); p.add_argument("--no-crop", action="store_true")
    p = sub.add_parser("plan"); common(p); plan_args(p)
    p = sub.add_parser("preview"); common(p); p.add_argument("--times"); mark_args(p)
    p = sub.add_parser("render"); common(p); p.add_argument("--out", required=True); mark_args(p)
    p.add_argument("--workers", type=int, default=None); p.add_argument("--crf", type=int, default=14); p.add_argument("--no-boom", action="store_true")
    p = sub.add_parser("auto"); common(p); p.add_argument("--clip", required=True); p.add_argument("--music"); p.add_argument("--transcribe", action="store_true")
    p.add_argument("--no-crop", action="store_true"); p.add_argument("--out", required=True); plan_args(p); mark_args(p)
    p.add_argument("--workers", type=int, default=None); p.add_argument("--crf", type=int, default=14); p.add_argument("--no-boom", action="store_true")
    a = ap.parse_args()
    if a.cmd == "analyze": cmd_analyze(a)
    elif a.cmd == "plan": cmd_plan(a)
    elif a.cmd == "preview": cmd_preview(a)
    elif a.cmd == "render": cmd_render(a)
    elif a.cmd == "auto":
        cmd_analyze(a); cmd_plan(a); cmd_render(a)


if __name__ == "__main__":
    main()
