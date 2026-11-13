# Video editing starter

A starter folder for editing short vertical videos with Claude.

## Setup (about 30 minutes, once)
1. **Get Claude for desktop:** download it from [claude.ai/download](https://claude.ai/download), install it and sign in. The **Code** tab needs a paid plan (Pro).
2. **Download this folder:** green **Code** button → **Download ZIP**. In Downloads, unzip it (Mac: double-click; Windows: right-click → Extract All). Move the folder to **Documents**.
3. **Open it in Claude:** click **Code** at the top → the folder button under the message box → Documents → this folder → **Open**. If asked, click **Trust**.
4. **Type:** "Set me up: check what this folder needs and install it, one step at a time. Explain each step in simple words and ask me before you install anything." Click **Allow** when Claude asks. Paste your AssemblyAI key into `.env` yourself, never into the chat.
5. **Test:** put a 30-second clip of yourself in `footage/` and type "Edit the clip in footage: cut the long pauses and the 'um's, clean up my voice, and add simple captions." The video appears in `out/`.

All the prompts (4 video types + polish: micro-zooms, text, music…) are in `cheat-sheet.md`.

## What's inside
- `CLAUDE.md`: your rulebook. Claude reads it before every edit. Fill in "My style".
- `cheat-sheet.md`: every prompt from the session.
- `.env`: paste your AssemblyAI key here (never in the chat).
- `footage/`: raw clips go here.
- `out/`: finished videos appear here.
- `scripts/`: tools Claude saves. Already in: `transcribe.py` (speech to text), `find_harmony.py` (where your singing fits a song), `singing_reel.py` and `title_box.html` (render a singing reel with a title).
