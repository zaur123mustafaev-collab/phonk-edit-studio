# Style guide — what popular edits actually do

Measured frame-by-frame on 14 reference edits in two batches (anime, cartoon, movie, IRL meme, Roblox, cars; 11–19 s each).
Batch 2 (7 edits) is summarised at the end — it added bar flashes, box reveal, fisheye, light leaks, captions and the diamond outro.

## Format
- 1:1 square in 6 of 7 (576–1080 px); one was 9:16 with the square clip centred and black bars.
- 30 or 60 fps. Deliver 1080×1080 @ 60.
- Source clip-pack branding is always gone: no grey frame, no "4K CLIPS FOR EDITS", no "FOLLOW FOR MORE".

## Pace
| edit | avg shot | notes |
|---|---|---|
| ref A (IRL meme) | ~1.3 s | long calm opening (zoom into a phone UI), then medium cuts |
| ref B (cartoon) | 1.34 s | 8 s calm opening with a big glitch watermark, then cuts every beat |
| ref C (cartoon duo) | 0.76 s | cuts on the beat, many on strong hits |
| ref D (movie fight) | 0.56 s | first 3 s handheld shake + motion blur, then a cut on every beat |
- Only ~50 % of cuts sit exactly on a beat — smooth transitions "smear" the cut over 0.15–0.35 s. Hard sync matters on the drop and strong hits.
- Users reacted: 0.25–0.5 s cuts everywhere = "слишком быстро"; 1–1.2 s = "пойдёт". Default: 2 beats per shot, 1 beat only in the hottest bars.

## Transitions seen (and the engine name)
- white flash / overexposure, 0.2–0.3 s — `flash` (always on the drop)
- zoom-in blur into the next shot — `zoom`
- whip pan with directional blur — `whip`, `whipR`, `whipU`
- small circle with a metallic ring, holds, then grows to full frame — `circle`
- picture-in-picture: next clip appears as an inset and grows — `pip`
- horizontal glitch-slice + slide — `glitch`
- shake with motion blur — `shake`
- RGB split — `rgb`
- outro: shrink into a circle on black — plan `"outro": "circle"`
- used rarely: spin, flying tile (`spin`, `tile`); never seen: kaleidoscope, mirror, negative, strobe.

## In-shot effects
- Velocity: shot starts fast and settles (not extreme).
- Small zoom punch on beats, stronger on hits; shake + chromatic split only on strong hits.
- Light glow, light grain, vignette. Colours natural-to-punchy, no heavy colour washes.

## Watermarks seen
- Small text (≈10–12 % of width), semi-transparent, centred horizontally at 75–90 % height, visible the whole video ("ЧЕРВЬ", "LORD").
- Big glitchy logo only in the first seconds (one edit) or a logo outro on black (one edit).
- → Engine default: small mark always at bottom-centre + the creator's animated watermark once, centred, silent.


## Batch 2 — 7 more edits (cartoon, horror/meme, cars, Roblox, IRL meme)
| edit | tempo | avg / median shot | cuts on beat | intro | notable |
|---|---|---|---|---|---|
| horror meme (Minecraft) | 112 | 0.54 / 0.53 s | every beat | none — big caption «SCARIEST ENTITY?» over the first 4.5 s | colour-fill silhouette shots, fisheye, square inset that grows, lyric words popping, outro shrinks into a small rectangle on black |
| cartoon (Pomni → Jerry) | 112 | 0.76 / 0.35 s | 59 % | 4.8 s single shot with slow push-ins; chrome glitch logo at 2 s | drop = white frame burning off, stutter double-cuts (0.1 s), inset rectangle, dark desaturated grade, fade to black |
| cars | 96 | 0.43 / 0.40 s | 54 % | white caption bar on top for 4.5 s; 3-D gold logo at 0.8 s | very heavy motion / zoom blur, pink light leaks, black-and-white high-contrast part, green glow outline |
| Roblox | 89 | 0.91 / 0.67 s | 47 % | 3.2 s calm shot | **overexposure flash every ~2.3 s** (white → burns off in 0.3 s), crisp contrast + vignette, outro: white rotated square grows → white → grey |
| cartoon (Masha) | 129 | 0.59 / 0.47 s | every beat | 2.1 s real-life meme setup shot | flash fade on the drop, then **flash every 4 beats**, extreme face zoom-ins, the same shot sequence played twice, small © text bottom-centre whole video |
| IRL meme | 123 | 0.55 / 0.47 s | 85 % | 1 s | chrome glitch name at 0.3 s and again mid-edit, **white box appears in the centre, next shot inside it, box grows to full frame**, flash every 4 beats, small name bottom-centre, ends white → grey |
| cartoon (Zig & Sharko) | 129 | 0.78 / 0.47 s | 88 % | 4.1 s calm live-action shot, drop on a bubbles transition | very saturated colour, lyric text with glitch, ends grey |

### Frame-by-frame numbers (30 fps, every cut)
| | refs (7) | engine v1.1 (Gojo test) |
|---|---|---|
| shot length | **1 beat** (0.46–0.6 s); 2 edits half a beat | 0.56 s = 1 beat |
| cut on the beat | ±0.03–0.09 s | ±0.04 s |
| plain hard cuts | 0–44 % (≈25 %) | ≈24 % |
| white flashes | 19–35 % of cuts, ≈ every 4 beats | ≈24 %, every bar |
| motion-blurred cuts | 30–72 % | most of the rest |
| zoom inside a shot | 13–22 % (5 of 7) | ≈15 % |
| flash shape | 2–3 frames pure white, then 0.3–0.4 s burn-off while the new shot zooms | same |

### What batch 2 changed in the engine (v1.1)
- Default pace = a cut on every beat (the user approved it after seeing the Gojo test).
- Transition mix: ~1/4 `cut` (hard cut + zoom kick), ~1/4 `expo` on bar downbeats, rest zoom / whip / lens; specials once.
- In-shot: 15–20 % zoom in/out per shot, brightness/colour pop on every beat, light hand-held shake.
- `expo` transition: 2–3 frames of pure white on the cut, then the new shot burns off out of the white in ~0.3 s.
- `box` transition (white card in the centre → next shot inside → grows to full frame), `lens` (fisheye punch on the cut), `leak` (warm light leak sweep).
- Intro length auto: 4 beats on slow tracks, 8 beats on fast ones (≈2.5–4 s).
- Outro: `circle` or `diamond` (white rotated square → white → dark grey), random per seed, or `--outro`.
- `--caption "TEXT"`: white bar with black bold text at the top during the intro (refs used it for «оцени эдит» / question captions).

### Seen but not built (on purpose)
- Lyric words popping on beats — needs exact lyrics + timing; ask the user for the words if they want it.
- Colour-fill silhouette shots and B/W threshold sections — strong look, fits only some clips.
- Big creator logo in the first second — this user wants the animated watermark **once, on the drop**; keep that.
