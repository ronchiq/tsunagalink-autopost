#!/usr/bin/env python3
"""投稿済みの古い動画(30日より前)を docs/media から消す。インスタには残るので問題なし。"""
import datetime as dt
from pathlib import Path

MEDIA = Path(__file__).resolve().parent.parent / "docs" / "media"
limit = dt.date.today() - dt.timedelta(days=30)
for p in MEDIA.glob("*"):
    try:
        d = dt.date.fromisoformat(p.name[:10])
    except ValueError:
        continue
    if d < limit:
        p.unlink(); print("removed", p.name)
