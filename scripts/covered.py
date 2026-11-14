#!/usr/bin/env python3
"""Что в корпусе уже написано по этим словам.

Запускать ПЕРЕД сбором по новому направлению, а не после. Трижды подряд
направление заказывалось со словами «в корпусе нет ничего», и трижды оно
оказывалось закрытым: про угасшее влечение стояло шесть статей, про
отношения между детьми — три, про переезд — одна, забиравшая 47% спроса.
Сбор на 6500 фраз ради двух тем — цена этой непроверки.

    python3 scripts/covered.py переезд ностальгия
    python3 scripts/covered.py --full тоска по дому     # ещё и по телу статей

Ищет по корню слова (без окончаний) в заголовке, primaryKeyword,
lsiKeywords и тегах. С --full — ещё и в тексте, это медленнее и шумнее.
"""

import glob
import pathlib
import re
import sys


def stem(word: str) -> str:
    """Грубое отсечение окончания: нам нужен поиск по корню, не морфология."""
    w = word.lower().replace("ё", "е")
    for end in ("ение", "ение", "ами", "ями", "ость", "ия", "ие", "ый", "ой",
                "ая", "ое", "ов", "ам", "ах", "ом", "ей", "ью", "и", "ы", "а",
                "о", "е", "у", "я"):
        if len(w) > 5 and w.endswith(end):
            return w[: -len(end)]
    return w


def fields(text: str) -> str:
    """Шапка статьи: заголовок, ключи, теги — то, на что она нацелена."""
    head = text.split("---", 2)[1] if text.startswith("---") else text[:1500]
    keep = []
    for line in head.split("\n"):
        if re.match(r"^(title|primaryKeyword|tags|category):", line) or \
           re.match(r"^\s+-\s", line):
            keep.append(line)
    return "\n".join(keep).lower().replace("ё", "е")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    full = "--full" in sys.argv
    if not args:
        print(__doc__)
        return 2

    stems = [stem(a) for a in args]
    hits = {}
    for path in sorted(glob.glob("docs/seo/articles/*.md")):
        text = pathlib.Path(path).read_text(encoding="utf-8")
        hay = fields(text) if not full else text.lower().replace("ё", "е")
        found = [a for a, s in zip(args, stems) if s in hay]
        if found:
            m = re.search(r"^primaryKeyword: *(.+)$", text, re.M)
            t = re.search(r'^title: *"?(.*?)"?\s*$', text, re.M)
            hits[pathlib.Path(path).stem] = (
                found, (m.group(1).strip() if m else ""), (t.group(1) if t else ""))

    where = "в тексте" if full else "в заголовке, ключах и тегах"
    if not hits:
        print(f"по словам {', '.join(args)} {where} — ничего. Направление свободно.")
        return 0

    print(f"по словам {', '.join(args)} {where} уже есть {len(hits)}:\n")
    for slug, (found, pk, title) in hits.items():
        print(f"  {slug}")
        print(f"      {title[:70]}")
        print(f"      ключ: {pk}   ← совпало: {', '.join(found)}")
    print(f"\nПрежде чем заказывать сбор, прочитайте тела этих статей:")
    print("  они могут закрывать направление целиком, как было с переездом.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
