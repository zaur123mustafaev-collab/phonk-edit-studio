"""Build an edit plan (JSON) from shots + music analysis. The plan is human/Claude-editable before rendering."""
import random

PACE = {  # beats per cut (outside / inside dense parts), velocity speed range
    "calm": dict(base=2, dense=2, speed=(0.9, 1.1)),         # ~1-1.2 s per shot
    "medium": dict(base=1, dense=1, speed=(1.0, 1.2)),       # default = reference edits: a cut on EVERY beat (0.45-0.65 s); 2 beats if the tempo is very fast
    "fast": dict(base=1, dense=1, speed=(1.2, 1.6)),         # every beat + faster velocity
}
TRANSITIONS = {
    # refs: ~1/3 of cuts are plain hard cuts (with a zoom kick on the new shot), most others are motion-blur transitions,
    # flashes sit on bar downbeats (added by the planner), "special" transitions (box, pip, circle, leak) are rare
    "clean": ["cut", "zoom", "whip", "cut", "lens", "whipU", "cut", "zoom", "box", "cut", "whipR", "shake", "cut", "zoom", "glitch",
              "cut", "whip", "leak", "cut", "lens", "pip", "cut", "whipU", "rgb", "cut", "zoom", "circle"],
    "hype": ["cut", "zoom", "lens", "whip", "cut", "glitch", "whipU", "box", "cut", "spin", "rgb", "zoom", "cut", "leak", "shake",
             "whipR", "cut", "tile", "lens", "pip", "cut", "circle", "whip"],
}


def snap(t, grid):
    return min(grid, key=lambda g: abs(g - t)) if grid else t


def build_plan(shots, motion, music, clip_dur, *, pace="medium", style="clean", target=18.0, intro_beats=None,
               dialogue=None, drop=None, seed=7, size=1080, fps=60, music_is_clip=False):
    """
    shots   : [(s0, s1)] in clip seconds (already cropped clip)
    motion  : action score per shot
    music   : dict from audio.analyze_music or phonk meta (beats, strong, drop, duration, beat)
    dialogue: optional (src_start, src_end) in clip seconds -> music intro, then this dialogue (clip audio), then the drop
    """
    rng = random.Random(seed)
    P = PACE.get(pace, PACE["medium"]); TR = TRANSITIONS.get(style, TRANSITIONS["clean"])
    beat = music.get("beat") or 0.5
    if pace == "medium" and beat < 0.4: P = dict(P, base=2)      # >150 BPM: every beat would be < 0.4 s
    beats = sorted(music["beats"]); strong = sorted(music.get("strong", []))
    drop = drop if drop is not None else music["drop"]
    drop = snap(drop, beats + strong)
    # full beat grid (fill gaps the tracker missed)
    grid = []
    t = drop
    while t > -0.01: grid.append(round(t, 4)); t -= beat
    t = drop + beat
    while t < music["duration"]: grid.append(round(t, 4)); t += beat
    grid = sorted(set(grid))
    for b in beats:  # prefer detected beats when close
        k = min(range(len(grid)), key=lambda i: abs(grid[i] - b))
        if abs(grid[k] - b) < beat * 0.25: grid[k] = b
    grid = sorted(grid)

    if intro_beats is None:   # refs: a calm opening of ~2.5-4 s before the drop (4 beats on slow tracks, 8 on fast ones)
        intro_beats = 4 if beat * 8 > 4.4 else 8
        while intro_beats > 2 and drop - intro_beats * beat < 0: intro_beats -= 2
    m_start = max(0.0, drop - intro_beats * beat)
    if music_is_clip:  # use the clip's own soundtrack in place: video time == music time is not required, but keep length sane
        pass
    # montage length: target minus intro/dialogue, end on a bar boundary
    intro_len = drop - m_start
    dlg_len = (dialogue[1] - dialogue[0]) if dialogue else 0.0
    mont_len = max(4 * beat * 2, target - intro_len - dlg_len)
    bars = max(2, round(mont_len / (4 * beat)))
    m_end = min(music["duration"] - 0.4, drop + bars * 4 * beat)
    m_end = snap(m_end, [g for g in grid if g > drop + 4 * beat]) if grid else m_end
    tail = 0.9

    # ---------- output timeline
    T_intro0, T_intro1 = 0.0, intro_len
    T_drop = T_intro1 + dlg_len
    def m2t(m): return T_drop + (m - drop)
    total = m2t(m_end) + tail

    # ---------- shot ordering: strongest motion first on the drop, never repeat until all used
    usable = [i for i, (a, b) in enumerate(shots) if b - a >= 0.3]
    if dialogue:  # do not reuse dialogue footage in the montage if we have enough other shots
        other = [i for i in usable if shots[i][1] <= dialogue[0] - 0.05 or shots[i][0] >= dialogue[1] + 0.05]
        if len(other) >= 6: usable = other
    by_motion = sorted(usable, key=lambda i: -motion[i])
    calm_shot = min(usable, key=lambda i: motion[i] - 0.15 * (shots[i][1] - shots[i][0])) if usable else 0
    longish = [i for i in by_motion[: max(3, len(by_motion) // 2)] if shots[i][1] - shots[i][0] >= 1.0]
    hero = (longish or by_motion or [0])[0]           # strong, sharp and long enough for the slow-mo ending
    queue = [i for i in by_motion if i not in (calm_shot, hero)] or [hero]
    # interleave: high-motion first, then mix
    order = []
    hi, lo = queue[: len(queue) // 2], queue[len(queue) // 2:]
    rng.shuffle(lo)
    while hi or lo:
        if hi: order.append(hi.pop(0))
        if lo: order.append(lo.pop(0))
    if not order: order = [calm_shot]

    # ---------- montage cut points
    energy = music.get("energy") or []
    post = sorted(energy[int(drop):int(m_end) + 1]) if energy else []
    med_e = post[len(post) // 2] if post else 0
    def dense(m):  # only the clearly hottest seconds after the drop get 1-beat cuts
        s = int(m)
        return bool(energy) and s < len(energy) and med_e > 0 and energy[s] > med_e * 1.12
    cuts = [drop]; m = drop
    sgrid = [g for g in grid if drop < g < m_end - beat * 0.9]
    while True:
        step = P["dense"] if dense(m) else P["base"]
        nxt = [g for g in sgrid if g > m + beat * (step - 0.5)]
        if not nxt: break
        n = nxt[0]
        # if a strong hit sits within half a beat of this cut, move the cut onto it
        hits = [s for s in strong if abs(s - n) <= beat * 0.3 and s > m + beat * 0.7]
        if hits: n = min(hits, key=lambda s: abs(s - n))
        cuts.append(n); m = n
    # the last bar is the hero/outro shot
    last_bar = m_end - 4 * beat * (1 if bars > 2 else 0.5)
    cuts = [c for c in cuts if c < last_bar - beat * 0.5] + [snap(last_bar, grid)]
    cuts = sorted(set(cuts))

    # refs: overexposure flash on every bar downbeat (every 4 beats) after the drop -> the cut closest to it
    expo_k = set()
    bar_beats = 4 if P["base"] == 1 else 8
    j = 1
    while drop + bar_beats * j * beat < m_end - 2 * beat:
        d = drop + bar_beats * j * beat
        k_best = min(range(1, len(cuts) - 1), key=lambda i: abs(cuts[i] - d), default=None)
        if k_best is not None and abs(cuts[k_best] - d) <= beat * 1.01: expo_k.add(k_best)
        j += 1

    segs = []
    segs.append(dict(kind="intro", t0=T_intro0, t1=T_intro1, shot=list(shots[calm_shot]), frac=0.1, speed=0.6, tr=None))
    if dialogue:
        segs.append(dict(kind="dialogue", t0=T_intro1, t1=T_drop, src=list(dialogue), tr="flash"))
    oi = 0
    for k, c in enumerate(cuts):
        last = k == len(cuts) - 1
        c1 = m_end if last else cuts[k + 1]
        if last: si = hero
        else: si = order[oi % len(order)]; oi += 1
        a, b = shots[si]
        D = c1 - c
        sp = 0.45 if last else rng.uniform(*P["speed"])
        frac = 0.0 if (b - a) < D * sp * 1.4 else rng.uniform(0, 0.4)
        tr = "flash" if k == 0 else ("zoom" if last else TR[(k - 1) % len(TR)])
        recent = [x.get("tr") for x in segs[-3:]]
        if not last and k > 0 and any(abs(s - c) < 0.06 for s in strong) and tr in ("whip", "whipR", "whipU"):
            tr = "lens" if "lens" not in recent else "shake"       # strong hit -> punchy transition (flashes stay on bars)
        if k in expo_k: tr = "expo"
        elif tr in ("flash", "expo") and k > 0: tr = "zoom"
        segs.append(dict(kind="montage", t0=round(m2t(c), 4), t1=round(m2t(c1), 4), shot=[a, b], frac=round(frac, 3), speed=round(sp, 3), tr=tr))
    segs[-1]["t1"] = round(total, 4)

    accents = []
    plan = dict(size=size, fps=fps, total=round(total, 4), outro=rng.choice(["circle", "diamond"]),
                music=dict(start=round(m_start, 4), drop=round(drop, 4), end=round(m_end, 4), tail=tail),
                timeline=dict(intro=[T_intro0, T_intro1], dialogue=[T_intro1, T_drop] if dialogue else None, drop=T_drop),
                beats_t=[round(m2t(g), 4) for g in grid if drop <= g <= m_end],
                strong_t=[round(m2t(s), 4) for s in strong if drop <= s <= m_end],
                accents=accents, segments=segs)
    return plan
