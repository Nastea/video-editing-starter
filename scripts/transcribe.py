#!/usr/bin/env python3
"""Transcribe an audio/video file with AssemblyAI (word-level, keeps fillers).
Usage: transcribe.py <media> <out.json> [language_code|auto]
Reads ASSEMBLYAI_API_KEY from the .env file in the project folder.
"""
import json, os, sys, time, urllib.request, pathlib

root = pathlib.Path(__file__).resolve().parent.parent
key = os.environ.get("ASSEMBLYAI_API_KEY")
if not key:
    for line in (root / ".env").read_text().splitlines():
        if line.startswith("ASSEMBLYAI_API_KEY="):
            key = line.split("=", 1)[1].strip().strip('"\'')
H = {"authorization": key}

def req(url, data=None, headers=None, method=None):
    r = urllib.request.Request(url, data=data, headers={**H, **(headers or {})}, method=method)
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read())

src, out = sys.argv[1], sys.argv[2]
lang = sys.argv[3] if len(sys.argv) > 3 else "auto"
with open(src, "rb") as f:
    up = req("https://api.assemblyai.com/v2/upload", data=f.read(),
             headers={"content-type": "application/octet-stream"})
body = {"audio_url": up["upload_url"], "disfluencies": True, "speaker_labels": True}
if lang == "auto":
    body["language_detection"] = True
else:
    body["language_code"] = lang
job = req("https://api.assemblyai.com/v2/transcript", data=json.dumps(body).encode(),
          headers={"content-type": "application/json"})
while True:
    t = req(f"https://api.assemblyai.com/v2/transcript/{job['id']}")
    if t["status"] in ("completed", "error"):
        break
    time.sleep(10)
if t["status"] == "error":
    sys.exit(t["error"])
json.dump(t, open(out, "w"), ensure_ascii=False)
print("ok", t.get("language_code"), len(t.get("words", [])), "words")
