#!/usr/bin/env python3
"""Find where a singing clip fits a song best.
Usage: find_harmony.py <singing clip (video or audio)> <song> [out.json]
Needs: ffmpeg, and Python packages librosa + numpy (pip install librosa).

What it does (Claude cannot hear, so it measures):
  1. Finds the sung phrases in the clip (and tells talking apart from singing).
  2. Finds the key and tuning of the singer and of the song.
  3. Slides the singing along the song and scores every position:
     how often her note is a chord tone of the song vs. a semitone clash.
  4. If the keys don't fit anywhere, tries shifting the SONG up/down (never her voice).
  5. Suggests micro-zoom points in the breaths between phrases.
Prints a short report and writes the numbers to out.json."""
import json, os, subprocess, sys, tempfile
import numpy as np, librosa

SR, HOP = 22050, 256
FPS = SR / HOP
NOTES = "C C# D D# E F F# G G# A A# B".split()
MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

def load(path):
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vn", "-ac", "1", "-ar", str(SR), tmp], check=True)
    y, _ = librosa.load(tmp, sr=SR); os.remove(tmp); return y

def key_of(profile):
    best = max(((np.corrcoef(np.roll(P, k), profile)[0, 1], k, name) for k in range(12)
                for P, name in ((MAJ, "major"), (MIN, "minor"))))
    return f"{NOTES[best[1]]} {best[2]}"

def main():
    clip, song = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else None
    v, m = load(clip), load(song)

    # 1. phrases: non-silent stretches; singing = mostly held notes, talking = pitch keeps sliding
    f0, voiced, _ = librosa.pyin(v, fmin=80, fmax=1100, sr=SR, hop_length=HOP)
    midi = librosa.hz_to_midi(f0)
    phrases = []
    for a, b in librosa.effects.split(v, top_db=32, frame_length=2048, hop_length=512):
        if b - a < SR * 0.25: continue
        i0, i1 = a // HOP, min(b // HOP, len(midi))
        seg = midi[i0:i1]; vv = voiced[i0:i1]
        held = np.mean(np.abs(np.diff(seg)) < 0.15) if vv.mean() > 0.3 else 0
        # sung phrase: long, fully voiced, notes held steady. Talk: short bits, pitch keeps sliding.
        kind = "sing" if (b - a > 2.5 * SR and vv.mean() > 0.85 and held > 0.85) else "talk"
        phrases.append([round(a / SR, 2), round(b / SR, 2), kind])
    # merge tiny gaps between sung bits
    sung = []
    for p in phrases:
        if p[2] != "sing": continue
        if sung and p[0] - sung[-1][1] < 0.35: sung[-1][1] = p[1]
        else: sung.append(p[:2])
    sung = [s for s in sung if s[1] - s[0] > 1.0]
    if not sung: sys.exit("No singing found in the clip.")
    A, B = sung[0][0], sung[-1][1]

    # 2. key + tuning
    vi = voiced.copy(); vi[: int(A * FPS)] = False; vi[int(B * FPS):] = False
    cents = np.nanmedian((midi[vi] - np.round(midi[vi])) * 100)
    pcs = np.round(midi[vi] - cents / 100).astype(int) % 12
    her_profile = np.bincount(pcs, minlength=12).astype(float)
    C = librosa.feature.chroma_cqt(y=m, sr=SR, hop_length=HOP)
    C = librosa.decompose.nn_filter(C, aggregate=np.median, metric="cosine", width=9)
    C = C / (C.max(0, keepdims=True) + 1e-9)
    song_tuning = librosa.estimate_tuning(y=m, sr=SR) * 100

    # 3. slide her singing along the song
    idx = np.where(vi)[0]; idx_rel = idx - int(A * FPS)
    L = int((B - A) * FPS) + 1
    def scan(Cs):
        rows = []
        r = np.arange(len(idx_rel))
        for o in range(0, Cs.shape[1] - L, 4):
            Cc = Cs[:, o + idx_rel]; s = Cc[pcs, r]
            nb = np.maximum(Cc[(pcs + 1) % 12, r], Cc[(pcs - 1) % 12, r])
            rows.append((np.mean((s < 0.45) & (nb >= 0.85)) * 100, np.mean(s >= 0.7) * 100, o / FPS))
        return np.array(rows)
    res = scan(C)
    if not len(res): sys.exit("The song is shorter than the singing.")
    def pick(r):  # lowest clash; among near-ties (within 0.5%) take the earliest, so the song's intro is kept
        ok = r[r[:, 0] <= r[:, 0].min() + 0.5]
        return ok[np.argmin(ok[:, 2])]
    best = pick(res)
    shift = 0
    # 4. keys don't fit -> try moving the song (ffmpeg can do it; her voice stays natural)
    if best[0] > 8:
        trials = []
        for s in range(-5, 7):
            if s == 0: continue
            r2 = scan(np.roll(C, s, axis=0)); b2 = pick(r2)
            trials.append((b2[0], -b2[1], s, b2))
        t = min(trials)
        if t[0] < best[0] - 3: shift, best = t[2], t[3]

    # 5. zoom points: middle of each breath between sung phrases
    zooms = [round(float(sung[i][1] + sung[i + 1][0]) / 2, 2) for i in range(len(sung) - 1)
             if sung[i + 1][0] - sung[i][1] > 0.3]

    report = {
        "singing_from": A, "singing_to": B, "phrases": sung,
        "talking_parts": [p[:2] for p in phrases if p[2] == "talk"],
        "singer_key": key_of(her_profile), "singer_tuning_cents": round(float(cents)),
        "song_key": key_of(C.mean(1)), "song_tuning_cents": round(float(song_tuning)),
        "song_shift_semitones": shift,
        "best_song_time_at_singing_start": round(float(best[2]), 2),
        "music_at_for_clip_start_0": round(float(best[2] - A), 2),
        "clash_percent": round(float(best[0]), 1), "chord_tone_percent": round(float(best[1])),
        "average_clash_percent_anywhere": round(float(res[:, 0].mean()), 1),
        "zoom_points": zooms,
    }
    print(f"Singing {A:.1f}s → {B:.1f}s in {len(sung)} phrases ({report['singer_key']}, {cents:+.0f} cents).")
    print(f"Song: {report['song_key']}, {song_tuning:+.0f} cents." + (f" Shift the song {shift:+d} semitones." if shift else ""))
    print(f"Best fit: when she starts singing (clip {A:.2f}s) the song should be at {best[2]:.2f}s.")
    print(f"  For singing_reel.py: --music-at = {best[2]:.2f} - {A:.2f} + your --start  (song offset {best[2] - A:+.2f}s)")
    print(f"  Clash {best[0]:.1f}% (average anywhere {res[:, 0].mean():.1f}%). Under ~6% sounds clean.")
    print("Zoom points (clip time):", zooms)
    if out: json.dump(report, open(out, "w"), indent=1)

if __name__ == "__main__":
    main()
