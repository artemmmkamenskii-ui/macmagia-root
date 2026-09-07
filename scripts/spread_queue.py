# -*- coding: utf-8 -*-
"""Разложить хвост очереди по N статей в день.

Агенты ставят всем статьям партии одну дату — так проще писать, но в очереди
получается яма (15 сентября восемь статей) и горб (17-го — сорок). Скрипт
разравнивает хвост, начиная с первого дня, который ещё не выложен.

    python3 scripts/spread_queue.py --from 2026-09-15 --per-day 20 [--apply]

Без --apply только показывает, что сделает. После раскладки проверяет ссылки
вперёд: сдвинув статью на два дня назад, легко получить ссылку на ещё не
вышедшую — на такой падает сборка, а с ней и весь батч публикации.
"""
import argparse, datetime as dt, pathlib, re, sys

ART = pathlib.Path("docs/seo/articles")
DATE = re.compile(r"^(publishedAt|updatedAt): *(\d{4}-\d{2}-\d{2})", re.M)
LINK = re.compile(r"\]\(/blog/(?:[a-z]+/)?([a-z0-9-]+)/?\)")


def read(p):
    t = p.read_text(encoding="utf-8")
    m = re.search(r"^publishedAt: *(\d{4}-\d{2}-\d{2})", t, re.M)
    return t, (dt.date.fromisoformat(m.group(1)) if m else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--per-day", type=int, default=20)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    start = dt.date.fromisoformat(a.start)
    today = dt.date.today()
    if start <= today:
        sys.exit(f"нельзя двигать {start}: этот день уже на сайте (сегодня {today})")

    arts = {}
    for p in sorted(ART.glob("*.md")):
        t, d = read(p)
        if d:
            arts[p.stem] = (p, t, d)

    # порядок: сохраняем текущий (кто стоял раньше — раньше и выйдет),
    # внутри дня — по имени, чтобы раскладка была воспроизводимой
    tail = sorted([v for v in arts.values() if v[2] >= start], key=lambda v: (v[2], v[0].stem))
    print(f"в хвосте с {start}: {len(tail)} статей → по {a.per_day} в день")

    plan, day, n = {}, start, 0
    for p, t, d in tail:
        if n == a.per_day:
            day, n = day + dt.timedelta(days=1), 0
        plan[p.stem] = day
        n += 1

    moved = [(s, arts[s][2], d) for s, d in plan.items() if arts[s][2] != d]
    for s, was, now in sorted(moved, key=lambda x: x[2]):
        print(f"  {s:48} {was} → {now}")
    print(f"переставлено {len(moved)}, последний день {max(plan.values())}")

    # ссылка битая, если цель выходит позже источника
    bad = 0
    for s, d in plan.items():
        for tgt in set(LINK.findall(arts[s][1])):
            if tgt in arts:
                td = plan.get(tgt, arts[tgt][2])
                if td > d:
                    print(f"  ССЫЛКА ВПЕРЁД: {s} ({d}) → {tgt} ({td})")
                    bad += 1
    print(f"ссылок вперёд: {bad}")

    if not a.apply:
        print("\n(пробный прогон, файлы не тронуты — добавьте --apply)")
        return
    if bad:
        sys.exit("не применяю: сначала почините ссылки вперёд, иначе упадёт сборка")
    for s, d in plan.items():
        p, t, was = arts[s]
        if was == d:
            continue
        p.write_text(DATE.sub(lambda m: f"{m.group(1)}: {d}", t), encoding="utf-8")
    print(f"готово: {len(moved)} файлов")


main()
