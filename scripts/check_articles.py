#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Приёмка статей: проверяет то, что не ловит сборка.

`build_blog.py` роняет сборку на эзотерике и битых внутренних ссылках —
этого достаточно, чтобы плохая статья не уехала на сайт, но мало, чтобы
поймать статью просто слабую. При двадцати пяти статьях в день глазами
их не просмотреть, поэтому здесь собрано то, что проверяется машиной:
объём, обязательные блоки из брифа, ловушки вёрстки и следы AI-письма.

Запуск:
    python3 scripts/check_articles.py                    # все статьи
    python3 scripts/check_articles.py --date 2026-09-09  # только за день
    python3 scripts/check_articles.py slug1 slug2        # точечно
"""
from __future__ import annotations

import argparse
import collections
import glob
import re
import sys

ARTICLES = "docs/seo/articles"

# Требования брифа к обычной статье. Словарная короче и живёт по своим.
NEED = {
    "::: pullquote": "нет вставки pullquote",
    "::: cta": "нет блока cta",
    "## Частые вопросы": "нет раздела «Частые вопросы»",
    "## Коротко": "нет раздела «Коротко»",
}
WORDS = (1300, 1800)
WORDS_SLOVAR = (600, 900)

# Лид не должен начинаться с однобуквенного предлога: CSS-буквица склеит
# «С утра» в «Сутра».
DROPCAP = re.compile(r"^[СВКОУсвкоу]\s")

# Следы AI-письма из edit-brief-stylistic.md.
AI_MARKS = [
    (re.compile(r"\bпарадокс", re.I), "«парадокс»"),
    (re.compile(r"две стороны (одной )?медали", re.I), "«две стороны медали»"),
    (re.compile(r"в современном мире", re.I), "«в современном мире»"),
    (re.compile(r"важно понимать, что", re.I), "«важно понимать, что»"),
    (re.compile(r"в этой статье мы", re.I), "«в этой статье мы»"),
]
ANTITHESIS = re.compile(r"\bне [а-яё]+[,]? а [а-яё]+", re.I)

# Список, приклеенный к абзацу: markdown склеит его в сплошной текст.
# Ищем строку, которая сама не пункт списка, а следом сразу пункт.
GLUED_LIST = re.compile(r"^(?!\s*[-*>#])\S.*\n[-*] ", re.M)


def front(text: str) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    return dict(re.findall(r"^(\w+):\s*\"?([^\"\n]*)", m.group(1), re.M))


def body(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)


def check(path: str) -> list:
    text = open(path, encoding="utf-8").read()
    fm, md = front(text), body(text)
    slug = path.rsplit("/", 1)[-1][:-3]
    out = []

    for k in ("slug", "title", "description", "publishedAt", "primaryKeyword"):
        if not fm.get(k):
            out.append(f"нет поля {k}")
    # У словарных файл называется slovar-<term>.md, а slug внутри бывает и
    # «<term>», и «<term>-slovar» — оба варианта в корпусе живут и собираются.
    ok = {slug}
    if slug.startswith("slovar-"):
        term = slug[len("slovar-"):]
        ok |= {term, f"{term}-slovar"}
    if fm.get("slug") and fm["slug"] not in ok:
        out.append(f"slug в файле ({fm['slug']}) не совпадает с именем файла")

    d = fm.get("description", "")
    if d and not 100 <= len(d) <= 200:
        out.append(f"description {len(d)} знаков, нужно 140–180")

    n = len(md.split())
    lo, hi = WORDS_SLOVAR if slug.startswith("slovar-") else WORDS
    if not lo <= n <= hi:
        out.append(f"объём {n} слов, нужно {lo}–{hi}")

    if not slug.startswith("slovar-"):
        for mark, why in NEED.items():
            if mark not in md:
                out.append(why)

    lead = next((p for p in md.split("\n\n") if p.strip()
                 and not p.startswith(("#", ":::", "-", "*"))), "")
    if DROPCAP.match(lead.strip()):
        out.append("лид начинается с однобуквенного предлога — буквица склеит")

    for rx, why in AI_MARKS:
        if rx.search(md):
            out.append(f"штамп {why}")
    if len(ANTITHESIS.findall(md)) > 2:
        out.append(f"антитез «не X, а Y» — {len(ANTITHESIS.findall(md))}, можно две")
    if GLUED_LIST.search(md):
        out.append("список без пустой строки перед ним — склеится в абзац")

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*")
    ap.add_argument("--date", help="проверить статьи с этим publishedAt")
    a = ap.parse_args()

    paths = sorted(glob.glob(f"{ARTICLES}/*.md"))
    if a.slugs:
        paths = [p for p in paths if p.rsplit("/", 1)[-1][:-3] in a.slugs]
    if a.date:
        paths = [p for p in paths
                 if f"publishedAt: {a.date}" in open(p, encoding="utf-8").read(600)]

    if not paths:
        print("нечего проверять")
        return

    # Одинаковые title и description Вебмастер считает дублями.
    titles, descs, leads = collections.defaultdict(list), collections.defaultdict(list), {}
    problems = {}
    for p in paths:
        text = open(p, encoding="utf-8").read()
        fm = front(text)
        slug = p.rsplit("/", 1)[-1][:-3]
        titles[fm.get("title", "")].append(slug)
        descs[fm.get("description", "")].append(slug)
        first = body(text).strip().split(".")[0][:40]
        leads.setdefault(first, []).append(slug)
        found = check(p)
        if found:
            problems[slug] = found

    for slug, found in problems.items():
        print(f"\n{slug}")
        for f in found:
            print(f"   · {f}")

    for label, group in (("title", titles), ("description", descs)):
        for value, slugs in group.items():
            if value and len(slugs) > 1:
                print(f"\nодинаковый {label} у {len(slugs)}: {', '.join(slugs[:6])}")
    for value, slugs in leads.items():
        if len(slugs) > 1:
            print(f"\nлиды начинаются одинаково у {len(slugs)}: {', '.join(slugs[:6])}")

    print(f"\nпроверено {len(paths)}, с замечаниями {len(problems)}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
