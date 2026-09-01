#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка итогового плана из вычищенных частей.

Части `plan-clean-N.csv` готовят редакторы: помечают темы годными или
отбракованными, дают человеческий заголовок вместо вордстатовской
формулировки, чистят ключи. Здесь их куски сходятся в один план, годные
темы получают даты по 25 на день, а отбракованные складываются отдельно —
чтобы было видно, что и почему выпало.

Даты начинаются со следующего дня после последней уже занятой: статьи
с будущим `publishedAt` в сборку не попадают, пока дата не наступит, и
ежедневный деплой выкатывает их сам.

Запуск:
    python3 scripts/merge_clean_plan.py
"""
from __future__ import annotations

import csv
import datetime
import glob
import re
from collections import Counter

PARTS = "docs/seo/plan-clean-*.csv"
ARTICLES = "docs/seo/articles"
OUT = "docs/seo/plan-final.csv"
REJECTED = "docs/seo/plan-otbrakovano.csv"
PER_DAY = 25


def last_date() -> datetime.date:
    dates = []
    for p in glob.glob(f"{ARTICLES}/*.md"):
        m = re.search(r"^publishedAt:\s*(\d{4}-\d\d-\d\d)",
                      open(p, encoding="utf-8").read(600), re.M)
        if m:
            dates.append(datetime.date.fromisoformat(m.group(1)))
    return max(dates) if dates else datetime.date.today()


def main() -> None:
    good, bad, seen = [], [], set()
    for path in sorted(glob.glob(PARTS)):
        for r in csv.DictReader(open(path, encoding="utf-8")):
            if (r.get("годна") or "").strip().lower() in ("да", "yes", "1"):
                slug = (r.get("slug") or "").strip()
                if not slug or slug in seen:      # редакторы работали врозь
                    continue
                seen.add(slug)
                good.append(r)
            else:
                bad.append(r)

    good.sort(key=lambda r: -int(r.get("частота") or 0))
    start = last_date() + datetime.timedelta(days=1)
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["дата", "slug", "заголовок", "категория", "cta",
                    "частота", "ключи"])
        for i, r in enumerate(good):
            day = start + datetime.timedelta(days=i // PER_DAY)
            w.writerow([day.isoformat(), r["slug"], r["заголовок"],
                        r.get("категория", ""), r.get("cta", ""),
                        r.get("частота", ""), r.get("ключи", "")])

    with open(REJECTED, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["slug", "тема", "причина"])
        for r in bad:
            w.writerow([r.get("slug", ""), r.get("заголовок", ""),
                        r.get("причина_отказа", "")])

    days = (len(good) + PER_DAY - 1) // PER_DAY
    print(f"годных тем {len(good)} → {OUT}")
    print(f"отбраковано {len(bad)} → {REJECTED}")
    if good:
        last = start + datetime.timedelta(days=days - 1)
        print(f"публикация: с {start} по {last}, по {PER_DAY} в день ({days} дней)")
    for k, v in Counter(r.get("категория", "") for r in good).most_common():
        print(f"  {v:>4}  {k}")
    print("\nчастые причины отказа:")
    for k, v in Counter((r.get("причина_отказа") or "")[:40]
                        for r in bad).most_common(6):
        print(f"  {v:>4}  {k}")


if __name__ == "__main__":
    main()
