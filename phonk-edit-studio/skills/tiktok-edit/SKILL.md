---
name: tiktok-edit
description: Make TikTok / Reels / Shorts edits from a user's clip — auto-crops clip-pack borders and text, cuts on the beat, velocity, transitions, the creator's watermark, and music (the user's track, the phonk already in the clip, or an original generated phonk). Use whenever someone sends a clip and asks for an edit / эдит / монтаж под фонк.
---

# TikTok edit maker

You turn a raw clip (anime/cartoon/movie "4K clips for edits", gameplay, IRL) into a finished beat-synced edit with code.
The engine is in `scripts/` (Python + ffmpeg). You plan, check and explain; the engine renders.
Reply in the user's language (most users write Russian).

## 0. Environment (first time in a session)
```bash
python scripts/check_env.py          # checks ffmpeg + installs numpy pillow scipy librosa soundfile if missing
```
`faster-whisper` is optional (only for dialogue edits; it downloads a speech model on first use).

## 1. Collect inputs — ask only for what is missing
- **Clip** (required). Files only — TikTok links usually cannot be downloaded from the sandbox; ask the user to download via ssstik/snaptik and attach.
- **Watermark** (optional but most creators want it). Two kinds, use both if given:
  - *small mark* — always on screen, small, semi-transparent, bottom-centre: `--mark-image logo.png`, `--mark-text NAME`, or `--mark-video intro.mp4` (the logo is cut out of the creator's animated intro automatically).
  - *animated watermark video* (e.g. a CapCut intro with the creator's name): `--wm-video intro.mp4` — played **once** (exactly one pass of the animation — recordings that loop it are cut to a single cycle automatically, never repeated or stretched), centred, **without its sound**, black background keyed out; its brightest moment lands on the drop. Screen recordings of CapCut are fine: the canvas is detected and the app UI is cropped away.
- **Music** (optional) — see §3.
- **Wishes**: length (default 18 s), pace (calm / medium / fast), effects (clean / hype), dialogue part (yes/no), format (default 1:1, 1080, 60 fps).

## 2. Analyze
```bash
python scripts/make_edit.py analyze --clip CLIP.mp4 [--music TRACK.mp3] [--transcribe] --work W
```
Then **look** at `W/shots.jpg` (Read it): numbered shots with time range and motion score. Check the crop is clean (no grey frame, no "FOLLOW FOR MORE" text). If the crop is wrong, fix `W/analysis.json → crop` by hand.

## 3. Music — decision rules (always tell the user which one you used)
1. The user sent a track → use it (`--music`).
2. Else the clip already has phonk/music (`clip_music_score ≥ 0.6` in analyze output) → use the clip's own audio.
3. Else → generate an **original** drift-phonk beat (`--music-source phonk`, optional `--bpm 140 --seed N`; a new seed = a different beat). It is synthesized from scratch: no samples, no copyright problems.
- Never download songs from the internet (copyright; the sandbox usually blocks it anyway). If the user names a famous track, ask them to attach the mp3.
- You cannot hear audio. Drop / beats are found by analysis; say so, and ask the user to check sync after the first version. Override a wrong drop with `--drop SECONDS`.

## 4. Dialogue edits (music → talk → drop)
Run analyze with `--transcribe`, read the transcript, pick **4–8 s** of the strongest lines that end on a punchline, and pass `--dialogue START-END` (clip seconds, start a bit before the first word, end just after the last). The engine then plays: music intro → dialogue (lip-synced, music continues as a quiet muffled bed, zoom accents on the last word of each sentence, riser) → the drop on the music's drop.

## 5. Plan → preview → render
```bash
python scripts/make_edit.py plan    --work W [--pace medium] [--style clean] [--target 18] [--dialogue 11.1-16.5] [--drop 3.55]
python scripts/make_edit.py preview --work W [marks...]          # -> W/preview.jpg, Read it
python scripts/make_edit.py render  --work W --out EDIT.mp4 [--mark-video X | --mark-image X | --mark-text X] [--wm-video X]
```
- `W/plan.json` is editable: change a segment's `shot`, `speed`, `tr` (transition) and re-preview. Transitions: flash, zoom, whip, whipR, whipU, circle, pip, glitch, shake, rgb, spin, tile, cut.
- Drafts: `--fps 30 --size 720` in `plan` renders ~4× faster. Final: 1080 / 60 fps.
- Render time at 1080p60 ≈ 15–20 s per second of video on 2 CPU cores (more cores = faster). Tell the user it takes a few minutes.
- One-shot: `make_edit.py auto --clip ... --out ... [all options]`.

## 6. Check before delivering (never skip)
- Contact sheet: `ffmpeg -i EDIT.mp4 -vf "fps=3,scale=150:150,tile=9x6" -frames:v 1 sheet.png` → Read it. Look for: wrong crop, black/blank frames, watermark missing or too big, same shot repeated back-to-back.
- Audio levels per second (no silent intro!) — e.g. with soundfile/numpy on `W/audio.wav`.
- Then deliver the file and say in 2–4 lines what you did and what you could not verify (you did not listen to it).

## Style rules (learned from popular reference edits — details in `references/style-guide.md`)
- Square 1:1, 1080 px, 60 fps. Clean crop — nothing of the clip-pack branding left.
- Calm intro 2–4 s on one slow shot, then cuts on the beat: **0.6–1.2 s per shot** (every 2 beats; 1 beat only in the hottest bars). Users find 0.3 s cuts "too fast".
- Every cut has a transition, varied; flash on the drop. Effects are **clean**: velocity (fast-in, settle), zoom punch on beats, shake + RGB split on strong hits, soft glow, light grain. Mirrors / kaleidoscope / negative / strobe — rarely or never.
- Best/strongest-motion shots on the drop; never the same shot twice in a row; end on a hero shot in slow motion, then shrink into a circle on black.
- Watermarks: small semi-transparent mark **always** (anti-theft); the creator's animated watermark **once**, centred, silent, around the drop. Never put the watermark only at the very start.
- Quality: nearest-frame sampling (no ghosting), Lanczos scaling + sharpening, high bitrate. If the source is small (≤ 640 px), say a higher-res clip would look sharper.

## Feedback → what to change
| user says | do |
|---|---|
| слишком быстро / too fast | `--pace calm` or keep medium and use fewer 1-beat cuts |
| медленно, мало эффектов | `--pace fast` and/or `--style hype` |
| нет звука в начале | check audio levels of the first 2 s; the intro must be the track at full level |
| вотермарка повторяется / много раз | it must be ONE pass: the engine auto-cuts one loop cycle; if it still repeats, set `--wm-src0 A --wm-src1 B` to one cycle (look at a contact sheet of the watermark video) |
| вотермарка не та / не там | re-ask which file is the animated one and which is the small mark; adjust `--mark-width`, `--mark-opacity`, `--wm-start` |
| криво / качество | check contact sheet for ghosting, blur, crop; render final at 1080/60, crf 13–14 |

## Limits to be honest about
You cannot hear the result, cannot generate AI video, and cannot download TikTok videos or songs. Everything visual is code-made from the user's footage.
