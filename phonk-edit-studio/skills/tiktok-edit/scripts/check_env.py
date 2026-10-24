#!/usr/bin/env python3
"""Check / install what the edit engine needs."""
import importlib.util, shutil, subprocess, sys

NEED = {"numpy": "numpy", "PIL": "pillow", "scipy": "scipy", "librosa": "librosa", "soundfile": "soundfile"}
OPTIONAL = {"faster_whisper": "faster-whisper"}

ok = True
for tool in ("ffmpeg", "ffprobe"):
    if not shutil.which(tool):
        ok = False
        print(f"MISSING: {tool}  -> install ffmpeg (Windows: winget install Gyan.FFmpeg | macOS: brew install ffmpeg | Linux: apt install ffmpeg)")
missing = [pip for mod, pip in NEED.items() if importlib.util.find_spec(mod) is None]
if missing:
    print("installing:", " ".join(missing))
    cmd = [sys.executable, "-m", "pip", "install", "-q"] + missing
    r = subprocess.run(cmd)
    if r.returncode != 0:
        r = subprocess.run(cmd + ["--break-system-packages"])
    ok = ok and r.returncode == 0
for mod, pip in OPTIONAL.items():
    print(f"optional {pip}:", "ok" if importlib.util.find_spec(mod) else f"not installed (only for dialogue edits: pip install {pip})")
print("READY" if ok else "NOT READY")
