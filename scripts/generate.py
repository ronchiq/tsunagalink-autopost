#!/usr/bin/env python3
"""つながりんく 自動投稿リールの生成。

使い方:
  python scripts/generate.py                 # 今日の型を自動で選んで作る
  python scripts/generate.py --type kids_faq # 型を指定
  python scripts/generate.py --date 2026-10-26 --dry-run  # 状態を更新しない試作

出力:
  docs/media/<日付>-<型>.mp4 と .json(本文・ハッシュタグ・共同投稿者)
  docs/state.json に使った型を記録
  標準出力の最後の行に、Apps Script へ送る JSON
"""
import argparse, datetime as dt, json, math, os, random, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content" / "posts.json"
ASSETS = ROOT / "assets"
MUSIC = ROOT / "music"
DOCS = ROOT / "docs"
STATE = DOCS / "state.json"
JST = dt.timezone(dt.timedelta(hours=9))
OPEN_TARGET = dt.date(2027, 7, 1)  # 「2027年夏」の目安(月数の計算だけに使う)

W, H = 1080, 1920
BG = (247, 243, 236); BR = (110, 78, 52); SUB = (140, 120, 100); ACC = (122, 90, 58); TEAL = (70, 120, 140)
FONT_DIRS = ["/usr/share/fonts/opentype/noto", "/usr/share/fonts/noto-cjk", "/usr/share/fonts/opentype/noto-cjk"]


def font(weight, size):
    name = {"black": "NotoSansCJK-Black.ttc", "bold": "NotoSansCJK-Bold.ttc"}[weight]
    for d in FONT_DIRS:
        p = Path(d) / name
        if p.exists():
            return ImageFont.truetype(str(p), size, index=0)  # index 0 = JP
    sys.exit(f"font not found: {name}")


# ---------- drawing helpers ----------
def base():
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    for i, col in enumerate([(200, 225, 232), (220, 232, 215)]):
        d.arc((-400, 1700 + i * 40, 1480, 2500 + i * 40), 200, 340, fill=col, width=6)
    return im


def lines_center(d, lines, y, f, fill, lh, stroke=0, sfill=None):
    for l in lines:
        d.text((W // 2, y), l, font=f, fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=sfill)
        y += lh
    return y


def fit_size(lines, weight, start, maxw=960):
    s = start
    while s > 36:
        f = font(weight, s)
        if all(f.getlength(l) <= maxw for l in lines):
            return s
        s -= 4
    return s


def cover(path):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    w, h = im.size
    tw = int(h * 9 / 16)
    if tw <= w:
        x = (w - tw) // 2; im = im.crop((x, 0, x + tw, h))
    else:
        th = int(w * 16 / 9); y = (h - th) // 2; im = im.crop((0, y, w, y + th))
    return im.resize((W, H), Image.LANCZOS)


def card(path, w, rot):
    ph = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    im = ph.resize((w, int(w * ph.height / ph.width)), Image.LANCZOS)
    m = Image.new("L", im.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, *im.size), 28, fill=255)
    pad = 18
    c = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(c).rounded_rectangle((0, 0, *c.size), 36, fill=(255, 255, 255, 255))
    c.paste(im, (pad, pad), m)
    sh = Image.new("RGBA", (c.width + 80, c.height + 80), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((40, 48, 40 + c.width, 48 + c.height), 36, fill=(0, 0, 0, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(16)); sh.alpha_composite(c, (40, 40))
    return sh.rotate(rot, expand=True, resample=Image.BICUBIC)


def label_pill(d, text, y, fill=ACC):
    f = font("bold", 42)
    tw = d.textlength(text, font=f)
    d.rounded_rectangle((W / 2 - tw / 2 - 28, y, W / 2 + tw / 2 + 28, y + 72), 20, fill=fill)
    d.text((W // 2, y + 36), text, font=f, fill="white", anchor="mm")


# ---------- frame kinds ----------
def f_photo(fr):
    im = cover(ASSETS / "photos" / fr["photo"])
    d = ImageDraw.Draw(im, "RGBA")
    lines = fr["lines"]; size = fit_size(lines, "black", 88)
    lh = int(size * 1.35)
    top = 300
    hgt = (100 if fr.get("label") else 0) + lh * len(lines) + 70
    d.rectangle((0, top - 40, W, top - 40 + hgt + 30), fill=(0, 0, 0, 115))
    y = top
    if fr.get("label"):
        label_pill(d, fr["label"], y); y += 110
    lines_center(d, lines, y + lh // 2, font("black", size), "white", lh, 6, "black")
    return im


def f_text(fr):
    im = base(); d = ImageDraw.Draw(im)
    lines = fr["lines"]; size = fit_size(lines, "black", 84)
    lh = int(size * 1.45)
    block = lh * len(lines) + (150 if fr.get("sub") else 0)
    y = (H - block) // 2 - 60
    y = lines_center(d, lines, y + lh // 2, font("black", size), BR, lh)
    if fr.get("sub"):
        d.line((470, y + 10, 610, y + 10), fill=ACC, width=3)
        s = fr["sub"]; ssize = fit_size([s], "bold", 42)
        d.text((W // 2, y + 80), s, font=font("bold", ssize), fill=SUB, anchor="mm")
    return im


def f_card(fr):
    im = base(); d = ImageDraw.Draw(im)
    if fr.get("label"):
        d.text((W // 2, 300), fr["label"], font=font("bold", 46), fill=TEAL, anchor="mm")
    c = card(ASSETS / "photos" / fr["photo"], 900 if Image.open(ASSETS / "photos" / fr["photo"]).width > Image.open(ASSETS / "photos" / fr["photo"]).height else 640, 2)
    im.paste(c, ((W - c.width) // 2, 380), c)
    y = 380 + c.height + 40
    names = fr.get("names", [])
    n = len(names)
    for i, (small, big) in enumerate(names):
        x = W // 2 if n == 1 else int(W * (i + 1) / (n + 1))
        d.text((x, y + 30), small, font=font("bold", 42), fill=SUB, anchor="mm")
        d.text((x, y + 105), big, font=font("black", 66), fill=BR, anchor="mm")
    return im


def f_table(fr):
    im = base(); d = ImageDraw.Draw(im)
    rows = fr["rows"]; rh = 150
    block = 130 + len(rows) * (rh + 20) + (100 if fr.get("note") else 0)
    top = max(320, (H - block) // 2 - 80)
    d.text((W // 2, top), fr["title"], font=font("black", 72), fill=BR, anchor="mm")
    y0 = top + 130
    for i, (a, b) in enumerate(rows):
        y = y0 + i * (rh + 20)
        d.rounded_rectangle((110, y, 970, y + rh), 28, fill=(255, 255, 255), outline=(225, 215, 200), width=3)
        sa = fit_size([a], "bold", 56, 420)
        d.text((150, y + rh // 2), a, font=font("bold", sa), fill=SUB, anchor="lm")
        d.text((930, y + rh // 2), b, font=font("black", 70), fill=BR, anchor="rm")
    if fr.get("note"):
        y = y0 + len(rows) * (rh + 20) + 70
        s = fr["note"]; ss = fit_size([s], "black", 50)
        d.text((W // 2, y), s, font=font("black", ss), fill=(196, 92, 60), anchor="mm")
    return im


def f_list(fr):
    im = base(); d = ImageDraw.Draw(im)
    allparts = [p for it in fr["items"] for p in it.split("\n")]
    size = fit_size(allparts, "bold", 54, 740)  # 全項目で同じ文字サイズ
    f = font("bold", size); lh = int(size * 1.45)
    heights = [lh * len(it.split("\n")) + 56 for it in fr["items"]]
    block = 130 + sum(heights) + 28 * (len(heights) - 1)
    top = max(320, (H - block) // 2 - 80)
    d.text((W // 2, top), fr["title"], font=font("black", 70), fill=BR, anchor="mm")
    y = top + 130
    for it, h in zip(fr["items"], heights):
        parts = it.split("\n")
        d.rounded_rectangle((110, y, 970, y + h), 28, fill=(255, 255, 255), outline=(225, 215, 200), width=3)
        d.ellipse((145, y + h // 2 - 14, 173, y + h // 2 + 14), fill=(120, 170, 150))
        ty = y + 28 + lh // 2
        for p in parts:
            d.text((205, ty), p, font=f, fill=BR, anchor="lm"); ty += lh
        y += h + 28
    return im


def f_qa(fr):
    im = base(); d = ImageDraw.Draw(im)
    d.text((W // 2, 560), "Q", font=font("black", 120), fill=TEAL, anchor="mm")
    qs = fit_size([fr["q"]], "black", 76)
    d.text((W // 2, 720), fr["q"], font=font("black", qs), fill=BR, anchor="mm")
    d.line((470, 830, 610, 830), fill=ACC, width=3)
    d.text((W // 2, 950), "A", font=font("black", 90), fill=(196, 92, 60), anchor="mm")
    parts = fr["a"].split("\n"); asz = fit_size(parts, "bold", 54)
    lines_center(d, parts, 1080, font("bold", asz), BR, int(asz * 1.55))
    return im


def f_end(line, sub):
    im = base(); d = ImageDraw.Draw(im)
    logo = Image.open(ASSETS / "brand" / "logo.jpg").convert("RGB")
    lw = 640; logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    im.paste(logo, ((W - lw) // 2, 360))
    y = 360 + logo.height + 110
    s = fit_size([line], "black", 56)
    d.text((W // 2, y), line, font=font("black", s), fill=BR, anchor="mm")
    d.text((W // 2, y + 90), sub, font=font("bold", 38), fill=SUB, anchor="mm")
    return im


KINDS = {"photo": f_photo, "text": f_text, "card": f_card, "table": f_table, "list": f_list, "qa": f_qa}
DUR = {"photo": 3.4, "text": 3.6, "card": 3.6, "table": 4.6, "list": 4.6, "qa": 4.2, "end": 3.4}
FADE = 0.4


# ---------- choosing ----------
def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"history": []}


def choose_type(types, state, today, rng):
    hist = state.get("history", [])
    recent = [h["type"] for h in hist[-6:]]
    last_date = {}
    for h in hist:
        last_date[h["type"]] = h["date"]
    cands = []
    for t in types:
        gap = t.get("min_gap_days")
        if gap and t["id"] in last_date:
            if (today - dt.date.fromisoformat(last_date[t["id"]])).days < gap:
                continue
        if t["id"] in recent:
            continue
        cands.append(t)
    if not cands:  # 全部最近使った → 一番昔に使ったもの
        order = {h["type"]: i for i, h in enumerate(hist)}
        cands = [min(types, key=lambda t: order.get(t["id"], -1))]
    weights = [t.get("weight", 1.0) for t in cands]
    return rng.choices(cands, weights=weights, k=1)[0]


def fill(s, ctx):
    return s.replace("{months}", str(ctx["months"])) if isinstance(s, str) else s


def deep_fill(o, ctx):
    if isinstance(o, dict):
        return {k: deep_fill(v, ctx) for k, v in o.items()}
    if isinstance(o, list):
        return [deep_fill(v, ctx) for v in o]
    return fill(o, ctx)


# ---------- video ----------
def render_video(frames, out, rng, tmp):
    clips = []
    for i, (im, kind) in enumerate(frames):
        p = Path(tmp) / f"f{i}.jpg"; im.save(p, quality=93)
        d = DUR[kind]; n = int(d * 30)
        c = Path(tmp) / f"c{i}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(p), "-vf",
                        f"scale=1188:2112,zoompan=z='1+0.0006*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps=30,format=yuv420p",
                        "-frames:v", str(n), "-c:v", "libx264", "-crf", "18", str(c)], check=True)
        clips.append((c, d))
    inputs = []; [inputs.extend(["-i", str(c)]) for c, _ in clips]
    parts = []; prev = "[0]"; off = 0.0
    for i in range(1, len(clips)):
        off += clips[i - 1][1] - FADE
        tag = f"[v{i}]"
        parts.append(f"{prev}[{i}]xfade=transition=fade:duration={FADE}:offset={off:.2f}{tag}")
        prev = tag
    total = sum(d for _, d in clips) - FADE * (len(clips) - 1)
    vf = ";".join(parts) + f";{prev}format=yuv420p[v]" if parts else "[0]format=yuv420p[v]"
    tracks = sorted([p for p in MUSIC.glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg")])
    if tracks:
        tr = rng.choice(tracks)
        inputs += ["-stream_loop", "-1", "-i", str(tr)]
        a = f"[{len(clips)}:a]atrim=0:{total:.2f},asetpts=PTS-STARTPTS,volume=0.8,afade=t=in:d=0.6,afade=t=out:st={total - 1.8:.2f}:d=1.8[a]"
        music = tr.name
    else:
        inputs += ["-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
        a = f"[{len(clips)}:a]anull[a]"
        music = None
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", vf + ";" + a,
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                    "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)], check=True)
    return round(total, 1), music


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type"); ap.add_argument("--date"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out-dir")
    args = ap.parse_args()
    cfg = json.loads(CONTENT.read_text())
    today = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(JST).date()
    rng = random.Random(today.toordinal())
    state = load_state()
    types = cfg["types"]
    t = next(x for x in types if x["id"] == args.type) if args.type else choose_type(types, state, today, rng)
    months = max(1, round((OPEN_TARGET - today).days / 30.4))
    t = deep_fill(t, {"months": months})
    dflt = cfg["defaults"]

    frames = [(KINDS[fr["kind"]](fr), fr["kind"]) for fr in t["frames"]]
    frames.append((f_end(t.get("end_line", dflt["end_line"]), t.get("end_sub", dflt["end_sub"])), "end"))

    out_dir = Path(args.out_dir) if args.out_dir else DOCS / "media"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{today.isoformat()}-{t['id']}"
    mp4 = out_dir / f"{stem}.mp4"
    with tempfile.TemporaryDirectory() as tmp:
        dur, music = render_video(frames, mp4, rng, tmp)
        frames[0][0].save(out_dir / f"{stem}.jpg", quality=85)
    caption = t["caption"] + f"\n\n{dflt['end_line']}\n2027年夏、オープン予定です。"
    meta = {
        "date": today.isoformat(),
        "type": t["id"],
        "caption": caption,
        "hashtags": " ".join(t["hashtags"][:5]),
        "collaborators": ",".join(t.get("collaborators", dflt["collaborators"])),
        "schedule": f"{today.strftime('%Y/%m/%d')} 21:00",
        "file": f"media/{stem}.mp4",
        "duration": dur,
        "music": music,
    }
    (out_dir / f"{stem}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    if not args.dry_run:
        state.setdefault("history", []).append({"date": today.isoformat(), "type": t["id"]})
        state["history"] = state["history"][-60:]
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
