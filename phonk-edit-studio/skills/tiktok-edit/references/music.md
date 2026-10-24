# Music

## Priority
1. Track the user attached.
2. Phonk already inside the clip (clip-packs often ship with music): `clip_music_score ≥ 0.6`.
3. Original generated phonk (`editkit/phonk.py`).

## Generated phonk
- Drift-phonk structure: 2-bar filtered cowbell intro + riser → drop with cowbell riff, 808 with glides, kick, clap on 2 & 4, 16th hats with triplet rolls, sidechain ducking.
- 132–150 BPM (random per seed, or `--bpm`). Different `--seed` = different riff / key / chord movement.
- Exact beat grid and drop are returned in `phonk.json` — sync is perfect, no detection needed.
- Fully synthesized (no samples) → no copyright claims. It is a simple beat; for a specific famous track the user must attach the mp3.

## Analysis of a real track
- Beats: librosa beat tracker + a regular grid from the drop (fills gaps).
- Drop: first big rise of low-end (<150 Hz) energy, snapped to the nearest strong onset. It can be off by one beat — check `drop_guess`, override with `--drop`.
- Strong hits: top ~22 % onset strengths → cut / flash / shake candidates.

## Dialogue mix
music intro (full level) → dialogue (loudness-matched) over a quiet low-passed loop of the intro bar + riser → drop (+ sub boom) → fade-out tail.
