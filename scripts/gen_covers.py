#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор обложек статей 1600x900 (16:9) под Google Discover / og:image.

Discover — визуальная лента: без уникальной большой картинки статья почти не
показывается. Раньше все статьи делили одну /about.jpg, потом рисовались
примитивные градиенты на Pillow. Теперь обложка верстается в HTML
(scripts/cover_template.html) и снимается headless-Chrome — это даёт настоящие
blur-градиенты, Inter, цветные эмодзи и зерно.

Запускать ЛОКАЛЬНО (нужен Google Chrome + Pillow):
    python3 scripts/gen_covers.py                 # только отсутствующие
    python3 scripts/gen_covers.py --force         # перерисовать все
    python3 scripts/gen_covers.py --only apatiya  # одна статья
    python3 scripts/gen_covers.py --demo          # 6 демо-обложек (все варианты)

Сборка (build_blog.py) сама подхватывает blog/covers/<slug>.jpg как og:image.
Если у статьи во фронтматтере задан свой `cover:` (реальное фото) — приоритет у него.

Поля фронтматтера, которые влияют на обложку (все необязательные):
    coverHook:    «АПАТИЯ»      — крупный текст; по умолчанию выводится из title
    coverVariant: 1..6          — цветовая схема; по умолчанию хеш слага
    category, emoji             — пилюля и эмодзи
"""
import argparse
import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
ARTICLES = ROOT / "docs" / "seo" / "articles"
OUT = ROOT / "blog" / "covers"
TEMPLATE = SCRIPTS / "cover_template.html"

W, H = 1600, 900          # обложка статьи (og:image, Discover)
PIN_W, PIN_H = 1000, 1500  # вертикальный пин для Pinterest (2:3)
QUALITY = 85
N_VARIANTS = 6
N_SHIFTS = 3

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# слова, с которых заголовок начинать не стоит — режем «Что такое», «Как ...»
HOOK_STRIP = re.compile(r"^(что такое|что делать,?|как|почему|зачем)\s+", re.I)


def stable_hash(s):
    return int(hashlib.md5(s.encode("utf-8")).hexdigest()[:8], 16)


def make_hook(meta):
    """Короткий крупный текст обложки: 1–4 слова."""
    if meta.get("coverHook"):
        return str(meta["coverHook"]).strip()

    title = str(meta.get("title", "")).strip()
    # левая часть до двоеточия / тире — обычно и есть тема
    head = re.split(r"[:—–]", title, maxsplit=1)[0].strip(" .,")
    head = HOOK_STRIP.sub("", head).strip()
    if 3 <= len(head) <= 30:
        return head

    kw = str(meta.get("primaryKeyword", "")).strip()
    if 3 <= len(kw) <= 30:
        return kw

    # запасной вариант — первые слова заголовка, но не длиннее 30 знаков
    words, acc = title.split(), []
    for w in words:
        if len(" ".join(acc + [w])) > 30:
            break
        acc.append(w)
    return " ".join(acc).strip(" .,:") or title[:30]


def render(hook, category, emoji, variant, shift, out_path, fmt="cover", sub=""):
    w, h = (PIN_W, PIN_H) if fmt == "pin" else (W, H)
    html = TEMPLATE.read_text(encoding="utf-8")
    for k, v in {
        "{{HOOK}}": hook,
        "{{SUB}}": sub,
        "{{CATEGORY}}": category,
        "{{EMOJI}}": emoji or "",
        "{{VARIANT}}": str(variant),
        "{{SHIFT}}": str(shift),
        "{{FORMAT}}": fmt,
    }.items():
        html = html.replace(k, v)

    # временный html кладём рядом с шаблоном — иначе не найдутся fonts/
    tmp = SCRIPTS / f".cover_tmp_{out_path.stem}.html"
    tmp.write_text(html, encoding="utf-8")
    try:
        with tempfile.TemporaryDirectory() as td:
            png = Path(td) / "shot.png"
            subprocess.run(
                [
                    CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=1", "--allow-file-access-from-files",
                    "--virtual-time-budget=2500", f"--window-size={w},{h}",
                    f"--screenshot={png}", tmp.as_uri(),
                ],
                check=True, capture_output=True, timeout=90,
            )
            img = Image.open(png).convert("RGB")
            if img.size != (w, h):
                img = img.resize((w, h), Image.LANCZOS)
            img.save(out_path, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    finally:
        tmp.unlink(missing_ok=True)


def cover_params(meta, slug):
    h = stable_hash(slug)
    variant = meta.get("coverVariant")
    variant = int(variant) if str(variant).isdigit() else h % N_VARIANTS + 1
    shift = (h // 7) % N_SHIFTS
    category = str(meta.get("category") or (meta.get("tags") or ["Блог"])[0])
    # coverLead — продающая фраза крупно, тема уходит мелкой строкой под ней.
    # Заголовок статьи в ленте и так подписан под картинкой, дублировать его
    # на обложке — терять место, которое может работать на CTR.
    lead = str(meta.get("coverLead") or "").strip()
    topic = make_hook(meta)
    big, sub = (lead, topic) if lead else (topic, "")
    return big, category, str(meta.get("emoji") or ""), variant, shift, sub


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


DEMO = [
    ("Апатия", "Арт-терапия", "🌫️"),
    ("Психосоматика", "Психология", "🧠"),
    ("МАК-карты", "Метафорические карты", "🎴"),
    ("Избегающий тип привязанности", "Отношения", "🤍"),
    ("Цели на год", "Цели и развитие", "🧭"),
    ("Дыхание", "Медитации", "🌙"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="перерисовать все")
    ap.add_argument("--only", help="один slug")
    ap.add_argument("--demo", action="store_true", help="6 демо-обложек")
    ap.add_argument("--pins", action="store_true",
                    help="вертикальные пины 1000x1500 для Pinterest в blog/pins/")
    args = ap.parse_args()

    if not Path(CHROME).exists():
        sys.exit(f"Не найден Chrome: {CHROME}")

    if args.demo:
        demo_dir = ROOT / "docs" / "seo" / "cover-demo"
        demo_dir.mkdir(parents=True, exist_ok=True)
        fmt = "pin" if args.pins else "cover"
        for i, (hook, cat, em) in enumerate(DEMO, start=1):
            out = demo_dir / f"{'pin' if args.pins else 'variant'}{i}.jpg"
            render(hook, cat, em, i, i % N_SHIFTS, out, fmt=fmt)
            print(f"  demo {out.relative_to(ROOT)}  [{hook}]")
        return

    out_dir = (ROOT / "blog" / "pins") if args.pins else OUT
    out_dir.mkdir(parents=True, exist_ok=True)
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
        out = out_dir / f"{slug}.jpg"
        if out.exists() and not args.force:
            skipped += 1
            continue
        hook, cat, em, variant, shift, sub = cover_params(meta, slug)
        render(hook, cat, em, variant, shift, out, fmt="pin" if args.pins else "cover", sub=sub)
        made += 1
        print(f"  {out.relative_to(ROOT)}  v{variant}  [{hook}]")
    print(f"\nDone. Сгенерировано {made}, пропущено {skipped}.")


if __name__ == "__main__":
    main()
