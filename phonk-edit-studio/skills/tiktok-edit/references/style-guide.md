# Style guide — what popular edits actually do

Measured frame-by-frame on 7 reference edits (anime, cartoon, movie, IRL meme edits; 12–19 s each).

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
