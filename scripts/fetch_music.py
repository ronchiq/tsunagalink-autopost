#!/usr/bin/env python3
"""music/sources.txt に書いたURLの曲を、まだ無ければダウンロードして mp3 にする。

sources.txt の書き方(1行1曲):  ファイル名 URL
例: hawaiian_01 https://example.com/track.wav
"""
import subprocess, urllib.request, tempfile
from pathlib import Path

MUSIC = Path(__file__).resolve().parent.parent / "music"
src = MUSIC / "sources.txt"
if not src.exists():
    raise SystemExit(0)
for line in src.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    name, url = line.split(None, 1)
    out = MUSIC / f"{name}.mp3"
    if out.exists():
        continue
    with tempfile.NamedTemporaryFile(suffix=".audio") as tmp:
        urllib.request.urlretrieve(url, tmp.name)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp.name, "-ac", "2", "-ar", "44100", "-b:a", "192k", str(out)], check=True)
    print("downloaded", out.name)
