#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор обложек статей 1600x900 (16:9) под Google Discover / og:image.

Discover — визуальная лента: без уникальной большой картинки статья почти не
показывается. Раньше все статьи делили одну /about.jpg. Этот скрипт рисует
уникальную брендовую обложку на каждую статью: фирменный градиент + emoji +
заголовок + вордмарк. Кладёт в blog/covers/<slug>.jpg.

Запускать ЛОКАЛЬНО (нужен Pillow, есть только локально — в CI не тянем):
    python3 scripts/gen_covers.py            # только отсутствующие
    python3 scripts/gen_covers.py --force    # перерисовать все

Сборка (build_blog.py) сама подхватывает blog/covers/<slug>.jpg как og:image.
Если у статьи в фронтматтере задан свой `cover:` (реальное фото) — приоритет у него.
"""
import argparse
import os
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "docs" / "seo" / "articles"
OUT = ROOT / "blog" / "covers"

W, H = 1600, 900

# 6 брендовых градиентов (фиолет/розовый, в тон styles.css). (top-left, bottom-right)
GRADIENTS = {
    1: ("#efe6ff", "#cbb6f7"),
    2: ("#ffe4f0", "#f7b8d6"),
    3: ("#e9e0ff", "#b79df9"),
    4: ("#e2ecff", "#b7c8f7"),
    5: ("#fde8ff", "#d9a8f0"),
    6: ("#e6f0ff", "#a9c2f2"),
}
INK = (60, 20, 100)        # тёмно-фиолетовый заголовок
INK_SOFT = (108, 74, 150)  # приглушённый (категория/вордмарк)

EMOJI_FONT = "/System/Library/Fonts/Apple Color Emoji.ttc"
EMOJI_STRIKE = 160  # валидный размер strike у Apple Color Emoji

TITLE_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
]
REG_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def first_font(cands, size):
    for p in cands:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def gradient_bg(c1, c2):
    """Диагональный градиент 135deg через горизонтальную интерполяцию + поворот."""
    a, b = hex2rgb(c1), hex2rgb(c2)
    # строим по диагонали: t зависит от (x+y)
    base = Image.new("RGB", (W, H))
    px = base.load()
    maxd = (W + H)
    for y in range(H):
        for x in range(0, W, 2):  # шаг 2 для скорости, потом не критично
            t = (x + y) / maxd
            r = int(a[0] + (b[0] - a[0]) * t)
            g = int(a[1] + (b[1] - a[1]) * t)
            bl = int(a[2] + (b[2] - a[2]) * t)
            px[x, y] = (r, g, bl)
            if x + 1 < W:
                px[x + 1, y] = (r, g, bl)
    return base


def render_emoji(ch, target=300):
    try:
        ef = ImageFont.truetype(EMOJI_FONT, EMOJI_STRIKE)
        layer = Image.new("RGBA", (EMOJI_STRIKE * 2, EMOJI_STRIKE * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.text((0, 0), ch, font=ef, embedded_color=True)
        bbox = layer.getbbox()
        if not bbox:
            return None
        layer = layer.crop(bbox)
        scale = target / max(layer.width, layer.height)
        return layer.resize(
            (max(1, int(layer.width * scale)), max(1, int(layer.height * scale))),
            Image.LANCZOS,
        )
    except Exception as e:
        print(f"    emoji '{ch}' skip: {e}", file=sys.stderr)
        return None


def wrap(draw, text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_cover(meta, path):
    grad = GRADIENTS.get(int(meta.get("coverGradient", 1) or 1) if str(meta.get("coverGradient", 1)).isdigit() else 1,
                         GRADIENTS[1])
    img = gradient_bg(*grad)
    draw = ImageDraw.Draw(img)

    pad = 96
    # emoji справа сверху
    em = render_emoji(meta.get("emoji", "📖"), target=300)
    if em:
        img.paste(em, (W - pad - em.width, pad), em)

    # категория (пилюля) сверху слева
    cat = (meta.get("category") or (meta.get("tags") or ["Блог"])[0]).upper()
    fcat = first_font(REG_CANDIDATES, 30)
    cw = draw.textlength(cat, font=fcat)
    draw.rounded_rectangle([pad, pad, pad + cw + 56, pad + 58], radius=29, fill=(255, 255, 255, 230))
    draw.text((pad + 28, pad + 13), cat, font=fcat, fill=INK_SOFT)

    # заголовок (низ, крупно, перенос)
    ftitle = first_font(TITLE_CANDIDATES, 86)
    lines = wrap(draw, meta["title"], ftitle, W - pad * 2)
    if len(lines) > 4:  # уменьшить если длинно
        ftitle = first_font(TITLE_CANDIDATES, 68)
        lines = wrap(draw, meta["title"], ftitle, W - pad * 2)
    lh = int(ftitle.size * 1.16)
    total = lh * len(lines)
    y = H - pad - total - 70
    for ln in lines:
        draw.text((pad, y), ln, font=ftitle, fill=INK)
        y += lh

    # вордмарк снизу
    fw = first_font(TITLE_CANDIDATES, 34)
    draw.text((pad, H - pad - 6), "МакМагия", font=fw, fill=INK_SOFT)

    img.save(path, "JPEG", quality=86, optimize=True)


def load_meta(md_path):
    txt = md_path.read_text(encoding="utf-8")
    if not txt.startswith("---"):
        return None
    end = txt.find("\n---", 3)
    if end == -1:
        return None
    fm = yaml.safe_load(txt[3:end])
    fm["__slug"] = fm.get("slug", md_path.stem)
    return fm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="перерисовать все")
    ap.add_argument("--only", help="один slug для теста")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    made = skipped = 0
    for md in sorted(ARTICLES.glob("*.md")):
        meta = load_meta(md)
        if not meta:
            continue
        slug = meta["__slug"]
        if args.only and slug != args.only:
            continue
        if meta.get("cover"):  # своё реальное фото — не трогаем
            continue
        out = OUT / f"{slug}.jpg"
        if out.exists() and not args.force:
            skipped += 1
            continue
        make_cover(meta, out)
        made += 1
        print(f"  cover blog/covers/{slug}.jpg")
    print(f"\nDone. Сгенерировано {made}, пропущено {skipped}.")


if __name__ == "__main__":
    main()
