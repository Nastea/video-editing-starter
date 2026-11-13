"""Singing-over-a-song reel: one continuous take synced to the song, optional micro-zooms, static title.
Usage: python singing_reel.py <clip.mov> <song> <title.webm> <out_prefix> --start S --end E --music-at M
       M = song time that plays at clip time S (find_harmony.py prints it as music_at for clip time 0: add S).
       [--music-shift N  (move the SONG N semitones; her voice is never changed)]
       [--zooms "t:z,t:z,..."  (clip time; first z applies from S)] [--fx 0.5 --fy 0.25 (zoom anchor, upright frame)]
Writes <out_prefix>-final.mp4 (music+voice+title), -voice-only.mp4 (voice+title), -voice.wav."""
import argparse, json, subprocess
ap = argparse.ArgumentParser(); ap.add_argument("clip"); ap.add_argument("music"); ap.add_argument("title"); ap.add_argument("out")
ap.add_argument("--start", type=float, required=True); ap.add_argument("--end", type=float, required=True)
ap.add_argument("--music-at", type=float, required=True)
ap.add_argument("--voice-lufs", type=float, default=-16); ap.add_argument("--music-lufs", type=float, default=-17)
ap.add_argument("--zooms", default=""); ap.add_argument("--fx", type=float, default=0.5); ap.add_argument("--fy", type=float, default=0.25)
ap.add_argument("--music-shift", type=float, default=0)
ap.add_argument("--fade-out", type=float, default=0.3); ap.add_argument("--src-fps", type=float, default=24000/1001)
a = ap.parse_args(); L = a.end - a.start
VOICE = f"atrim=start={a.start}:end={a.end},asetpts=PTS-STARTPTS,aresample=48000,pan=mono|c0=0.5*c0+0.5*c1,highpass=f=80,afade=t=in:d=0.012,afade=t=out:st={L-0.25}:d=0.25"
r = 2 ** (a.music_shift / 12)
SHIFT = f"aresample=48000,asetrate={48000*r:.3f},aresample=48000,atempo={1/r:.6f}," if a.music_shift else "aresample=48000,"
MUSIC = f"atrim=start={a.music_at}:end={a.music_at+L},asetpts=PTS-STARTPTS,{SHIFT}afade=t=in:d=0.25,afade=t=out:st={L-a.fade_out}:d={a.fade_out}"
def loud(src, chain, target):
    e = subprocess.run(["ffmpeg", "-nostats", "-i", src, "-vn", "-af", f"{chain},loudnorm=I={target}:TP=-2:LRA=20:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(e[e.rindex("{"):e.rindex("}") + 1])
    return (f"{chain},loudnorm=I={target}:TP=-2:LRA=20:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']},aresample=48000")
V = loud(a.clip, VOICE, a.voice_lufs); M = loud(a.music, MUSIC, a.music_lufs)
snap = lambda t: round(t * a.src_fps) / a.src_fps
pts = [(a.start, float(z)) for z in [a.zooms.split(",")[0].split(":")[1]]] + \
      [(float(t), float(z)) for t, z in (x.split(":") for x in a.zooms.split(",")[1:])] if a.zooms else [(a.start, 1.0)]
bounds = [snap(a.start)] + [snap(t) for t, _ in pts[1:]] + [a.end]
vin, parts = [], []
for i, (_, z) in enumerate(pts):
    vin += ["-ss", f"{bounds[i]:.5f}", "-t", f"{bounds[i+1]-bounds[i]:.5f}", "-i", a.clip]
    crop = "" if z == 1 else (f"crop=trunc(iw/{z}/2)*2:trunc(ih/{z}/2)*2:"
                              f"min(max(iw*{a.fx}*(1-1/{z})\\,0)\\,iw-ow):min(max(ih*{a.fy}*(1-1/{z})\\,0)\\,ih-oh),")
    parts.append(f"[{i}:v]setpts=PTS-STARTPTS,{crop}scale=1080:1920:flags=lanczos:in_range=pc:out_range=tv,setsar=1[z{i}]")
n = len(pts); T, MU, AU = n, n + 1, n + 2
vid = ";".join(parts) + ";" + "".join(f"[z{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,fps=30[b];" \
      f"[{T}:v]setpts=N/30/TB[t];[b][t]overlay=0:0:format=auto,format=yuv420p[v]"
base = ["ffmpeg", "-v", "error", "-y"] + vin + ["-c:v", "libvpx-vp9", "-i", a.title, "-i", a.music, "-i", a.clip]
enc = ["-c:v", "libx264", "-crf", "17", "-preset", "slow", "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", "30",
       "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", "-map_metadata", "-1", "-t", f"{L:.3f}"]
subprocess.run(base + ["-filter_complex", f"{vid};[{AU}:a]{V},pan=stereo|c0=c0|c1=c0[vo];[{MU}:a]{M}[mu];[vo][mu]amix=inputs=2:normalize=0,alimiter=limit=0.89:level=false[a]",
                       "-map", "[v]", "-map", "[a]"] + enc + [f"{a.out}-final.mp4"], check=True)
subprocess.run(base + ["-filter_complex", f"{vid};[{AU}:a]{V},pan=stereo|c0=c0|c1=c0[a]", "-map", "[v]", "-map", "[a]"] + enc + [f"{a.out}-voice-only.mp4"], check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.clip, "-af", V, "-ar", "48000", "-c:a", "pcm_s24le", f"{a.out}-voice.wav"], check=True)
print("done", round(L, 2), "segments", n, "cuts at", [round(b - a.start, 2) for b in bounds[1:-1]])
