"""Audio analysis: beats, strong hits, drop, 'is there music in this clip?', optional speech transcription."""
import subprocess
import numpy as np


def to_wav(src, dst, sr=22050, start=None, end=None, mono=True):
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    if start is not None: cmd += ["-ss", str(start)]
    cmd += ["-i", src]
    if end is not None: cmd += ["-t", str(end - (start or 0))]
    cmd += ["-vn", "-ar", str(sr)] + (["-ac", "1"] if mono else ["-ac", "2"]) + [dst]
    subprocess.run(cmd, check=True)
    return dst


def analyze_music(wav):
    """Return tempo, beat grid, strong hits, a drop estimate and per-second energy."""
    import librosa
    y, sr = librosa.load(wav, sr=22050)
    dur = len(y) / sr
    on = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, beats = librosa.beat.beat_track(onset_envelope=on, sr=sr, units="time")
    tempo = float(np.atleast_1d(tempo)[0])
    pk = librosa.onset.onset_detect(onset_envelope=on, sr=sr, units="time")
    st = on[librosa.time_to_frames(pk, sr=sr)] if len(pk) else np.array([])
    strong = [float(t) for t, s in zip(pk, st) if s > np.percentile(st, 78)] if len(st) else []
    # bass energy curve -> drop = biggest rise in low-end energy (after the first second)
    S = np.abs(librosa.stft(y)); fr = librosa.fft_frequencies(sr=sr)
    bass = S[fr < 150].mean(0); tb = librosa.times_like(bass, sr=sr)
    win = max(1, int(0.5 * sr / 512))
    sm = np.convolve(bass, np.ones(win) / win, mode="same")
    rise = np.zeros_like(sm); lag = int(1.0 * sr / 512)
    rise[lag:] = sm[lag:] - sm[:-lag]
    valid = (tb > 1.0) & (tb < dur * 0.7)
    if valid.any():
        rv = np.where(valid, rise, -1e9)
        big = np.where(rv > 0.6 * rv.max())[0]          # first big rise = the drop (not a later re-entry)
        drop = float(tb[big[0]]) if len(big) else float(tb[np.argmax(rv)])
    else:
        drop = 0.0
    # snap drop to the nearest strong onset / beat
    cand = strong + [float(b) for b in beats]
    if cand: drop = min(cand, key=lambda c: abs(c - drop))
    rms = librosa.feature.rms(y=y)[0]; tr = librosa.times_like(rms, sr=sr)
    energy = [float(rms[(tr >= s) & (tr < s + 1)].mean()) for s in range(int(dur) + 1) if ((tr >= s) & (tr < s + 1)).any()]
    return dict(duration=dur, tempo=tempo, beat=60.0 / tempo if tempo else 0.5, beats=[float(b) for b in beats],
                strong=strong, drop=drop, energy=energy)


def music_presence(wav):
    """Heuristic 0..1: how much this audio looks like music with a steady beat (vs speech / silence)."""
    import librosa
    y, sr = librosa.load(wav, sr=22050)
    if len(y) < sr or np.sqrt((y ** 2).mean()) < 1e-3:
        return dict(score=0.0, silent=True)
    h, p = librosa.effects.hpss(y)
    perc_ratio = float((p ** 2).mean() / ((y ** 2).mean() + 1e-9))
    on = librosa.onset.onset_strength(y=y, sr=sr)
    ac = librosa.autocorrelate(on - on.mean()); ac = ac / (ac[0] + 1e-9)
    lo, hi = int(0.3 * sr / 512), int(1.2 * sr / 512)       # beat periods 0.3..1.2 s
    pulse = float(ac[lo:hi].max()) if hi < len(ac) else 0.0
    S = np.abs(librosa.stft(y)); fr = librosa.fft_frequencies(sr=sr)
    bass_share = float(S[fr < 150].sum() / (S.sum() + 1e-9))
    silent_frac = float((librosa.feature.rms(y=y)[0] < 0.01).mean())
    score = np.clip(0.55 * pulse / 0.5 + 0.25 * min(1, bass_share / 0.12) + 0.2 * min(1, perc_ratio / 0.25), 0, 1) * (1 - silent_frac)
    return dict(score=float(score), pulse=pulse, bass_share=bass_share, perc_ratio=perc_ratio, silent_frac=silent_frac)


def transcribe(wav16, model="small"):
    """Word-level transcript (needs faster-whisper; downloads the model on first use). Returns [] if unavailable."""
    try:
        from faster_whisper import WhisperModel
        import soundfile as sf
    except Exception:
        return []
    a, sr = sf.read(wav16, dtype="float32")
    if a.ndim > 1: a = a.mean(1)
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, info = m.transcribe(a, word_timestamps=True)
    out = []
    for s in segs:
        out.append(dict(start=round(s.start, 2), end=round(s.end, 2), text=s.text.strip(),
                        words=[dict(w=w.word.strip(), t=round(w.start, 2)) for w in (s.words or [])]))
    return out
