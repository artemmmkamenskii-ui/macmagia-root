#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""План публикации: отбирает темы под статьи и раскладывает их по датам.

Отбор идёт по квотам блоков. Без квот план перекашивается туда, где просто
больше спроса: свободных тем в словаре и «для психологов» втрое больше, чем
в эмоциях, и месяц ушёл бы в терминологию.

Даты назначаются пачками по 25 на день, начиная со следующего свободного дня.
Публикацию делает сборка: статья с `publishedAt` в будущем в неё не попадает,
пока дата не наступит, а ежедневный деплой по расписанию её выкатывает.

Запуск:
    python3 scripts/plan_batch.py 800 --out docs/seo/plan-800.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime
import glob
import re
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
from build_blog import transliterate_for_slug

SRC = "docs/seo/temy-100.csv"
ARTICLES = "docs/seo/articles"
PER_DAY = 25

# Доли блоков в плане. Завышать «для психологов» нет смысла: там почти всё —
# профстандарты и циклограммы, а не то, что читает наша аудитория.
QUOTA = {
    "01": 0.28,   # Отношения и близость
    "02": 0.20,   # Словарь и термины
    "03": 0.17,   # Тревога и депрессия
    "04": 0.05,   # Эмоции и состояния
    "05": 0.15,   # Дети и подростки
    "06": 0.09,   # Самооценка и личность
    "07": 0.06,   # Выгорание и работа
}

# Блоки «Для психологов» и «Практики и тесты» в план не идут: первый почти
# весь про поиск специалиста и делопроизводство, второй — диагностические
# шкалы, а диагностику мы не пишем (решение от 31.08.2026).
SKIP_BLOCKS = {"08", "09"}

# Объекты, вокруг которых семантика не про переживание, а про услугу и медицину.
SKIP_OBJ = {"психолог", "психотерапия", "психосоматика", "невроз", "ипохондрия"}

# Тема должна читаться как запрос живого человека: предлог, вопросительное
# слово или устойчивый термин из двух длинных слов («избегающая привязанность»).
READS = re.compile(
    r"\b(как|что|почему|зачем|чем|когда|если|в|на|с|у|для|после|при|от|до|без|к)\b")


def looks_like_topic(t: str) -> bool:
    words = t.split()
    if len(words) < 2:
        return False
    return bool(READS.search(t)) or all(len(w) > 4 for w in words)


# Внутренняя кухня профессии и делопроизводство: читать это никто не придёт.
OFFTOPIC = re.compile(
    r"профстандарт|циклограмм|должност|приказ|кабинет|ставк|оклад|зп\b|"
    r"часы|табел|отчет|отчёт|документац|номенклатур|аттестац|"
    r"план работы|учебный план|годовой план|программа работы|"
    r"курсы|обучени|повышени квалификац|стандарт|профессиональн стандарт|"
    r"воспитател|учитель|методист|конспект|занятия|"
    r"россии|рф\b|конституц|закон|прав[оа]\b|кодекс|компенсац|моральн|"
    r"перенос отпуска|заработ|стоит ли психолог|лечение|лечить",
    re.I,
)


def taken_slugs() -> set:
    return {p.rsplit("/", 1)[-1][:-3] for p in glob.glob(f"{ARTICLES}/*.md")}


def last_date() -> datetime.date:
    """Последняя дата, на которую уже что-то запланировано."""
    dates = []
    for p in glob.glob(f"{ARTICLES}/*.md"):
        m = re.search(r"^publishedAt:\s*(\d{4}-\d\d-\d\d)",
                      open(p, encoding="utf-8").read(600), re.M)
        if m:
            dates.append(datetime.date.fromisoformat(m.group(1)))
    return max(dates) if dates else datetime.date.today()


def make_slug(theme: str, used: set) -> str:
    base = transliterate_for_slug(theme)[:60].strip("-")
    slug, i = base, 2
    while slug in used:
        slug = f"{base}-{i}"
        i += 1
    used.add(slug)
    return slug


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("count", type=int)
    ap.add_argument("--out", default="docs/seo/plan-800.csv")
    ap.add_argument("--src", default=SRC)
    a = ap.parse_args()

    by_block = defaultdict(list)
    for r in csv.DictReader(open(a.src, encoding="utf-8")):
        if r["покрыто"] or OFFTOPIC.search(r["тема"]):
            continue
        if r["блок"] in SKIP_BLOCKS or r["объект"] in SKIP_OBJ:
            continue
        if r["тип_вопроса"] == "тест" or not looks_like_topic(r["тема"]):
            continue
        by_block[r["блок"]].append(r)
    for b in by_block:
        by_block[b].sort(key=lambda r: -int(r["частота"]))

    picked, rest = [], []
    for b, share in QUOTA.items():
        limit = round(a.count * share)
        picked += by_block[b][:limit]
        rest += by_block[b][limit:]
    # Блоки, где тем меньше квоты, добираем самыми частотными из остальных.
    rest.sort(key=lambda r: -int(r["частота"]))
    picked += rest[:max(0, a.count - len(picked))]
    picked.sort(key=lambda r: -int(r["частота"]))
    picked = picked[:a.count]

    used = taken_slugs()
    start = last_date() + datetime.timedelta(days=1)
    with open(a.out, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["дата", "slug", "тема", "частота", "блок", "cta",
                    "тип_вопроса", "ключи"])
        for i, r in enumerate(picked):
            day = start + datetime.timedelta(days=i // PER_DAY)
            w.writerow([day.isoformat(), make_slug(r["тема"], used), r["тема"],
                        r["частота"], r["название_блока"], r["cta"],
                        r["тип_вопроса"], r["ключи"]])

    days = (len(picked) + PER_DAY - 1) // PER_DAY
    last = start + datetime.timedelta(days=days - 1)
    print(f"отобрано {len(picked)} тем → {a.out}")
    print(f"публикация: с {start} по {last}, по {PER_DAY} в день ({days} дней)")
    cnt = defaultdict(int)
    for r in picked:
        cnt[r["название_блока"]] += 1
    for k, v in sorted(cnt.items(), key=lambda x: -x[1]):
        print(f"  {v:>4}  {k}")


if __name__ == "__main__":
    main()
