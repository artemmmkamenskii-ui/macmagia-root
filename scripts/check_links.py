# -*- coding: utf-8 -*-
"""Проверка внутренних ссылок по исходникам, до сборки.

build_blog.py ловит битые ссылки только на собранных страницах — то есть уже
падением деплоя, и вместе с ним не публикуется весь батч. Здесь то же самое,
но по markdown и за секунду.

    python3 scripts/check_links.py

Две ловушки, на которых легко ошибиться:
  * слаг берётся из frontmatter, а не из имени файла: `slovar-styd.md` живёт
    по адресу /blog/slovar/styd.html;
  * ссылка вперёд бьётся не всегда. Между двумя вышедшими статьями порядок дат
    не важен — обе уже на сайте. Битая та, чья цель ещё в очереди.
"""
import datetime as dt, pathlib, re, sys

ART = pathlib.Path("docs/seo/articles")
TODAY = dt.date.today()

pages, by_file = {}, {}
for p in sorted(ART.glob("*.md")):
    t = p.read_text(encoding="utf-8")
    g = lambda k: (re.search(rf"^{k}: *[\"']?([^\"'\n]+)", t, re.M) or [None, None])[1]
    slug = (g("slug") or p.stem).strip()
    sec = g("section")
    d = g("publishedAt")
    path = f"/blog/{sec}/{slug}.html" if sec else f"/blog/{slug}.html"
    pages[path] = dt.date.fromisoformat(d) if d else None
    by_file[p] = (path, pages[path], t)

bad = 0
for p, (src_path, src_date, t) in by_file.items():
    for href in sorted(set(re.findall(r"\]\((/blog/[^)\s]+)\)", t))):
        path = href.split("#")[0]
        if not path.endswith(".html"):
            continue  # хабы разделов
        if path not in pages:
            print(f"  НЕТ СТРАНИЦЫ: {p.stem} → {href}")
            bad += 1
            continue
        d = pages[path]
        # цель ещё не вышла, а источник уже на сайте или выйдет раньше цели
        if d and src_date and d > TODAY and (src_date <= TODAY or d > src_date):
            print(f"  ССЫЛКА ВПЕРЁД: {p.stem} ({src_date}) → {path} (выйдет {d})")
            bad += 1

print(f"статей {len(by_file)}, проблем {bad}")
sys.exit(1 if bad else 0)
