#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разбор выгрузок Вордстата, сохранённых в .docx.

Артём собирает частоты руками и складывает их в Word: каждая строка — фраза
и число, слитые без разделителя («медитация517666»). Отделяем хвост цифр,
остальное считаем фразой. Имя файла становится сидом — так же, как в
автоматических выгрузках, чтобы дальше работала та же группировка.

Запуск:
    python3 scripts/parse_wordstat_docx.py "ключи/2 волна" docs/seo/raw/volna-2.csv
"""
from __future__ import annotations

import csv
import glob
import os
import re
import sys
import zipfile

ROW = re.compile(r"^(.+?)(\d+)$")


def paragraphs(path: str):
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        text = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))
        if text.strip():
            yield text.strip()


def main() -> None:
    src, out = sys.argv[1], sys.argv[2]
    rows, skipped = [], 0
    for path in sorted(glob.glob(f"{src}/*.docx")):
        seed = os.path.basename(path)[:-5].strip().lower()
        n = 0
        for line in paragraphs(path):
            m = ROW.match(line)
            if not m:
                skipped += 1
                continue
            phrase = m.group(1).strip().lower()
            # «медитация 5 минут300»: хвост цифр — частота, но если фраза
            # кончается числом по смыслу («топ 10»), отделять нечего.
            if not phrase or phrase[-1].isdigit() and len(m.group(2)) < 3:
                skipped += 1
                continue
            rows.append({"phrase": phrase, "frequency": int(m.group(2)), "seed": seed})
            n += 1
        print(f"  {seed}: {n}")

    seen, uniq = set(), []
    for r in sorted(rows, key=lambda r: -r["frequency"]):
        if r["phrase"] in seen:
            continue
        seen.add(r["phrase"])
        uniq.append(r)

    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["phrase", "frequency", "seed"])
        w.writeheader()
        w.writerows(uniq)
    print(f"\nстрок {len(rows)}, уникальных фраз {len(uniq)}, не разобрано {skipped}")
    print(f"от 300 показов: {sum(1 for r in uniq if r['frequency'] >= 300)} → {out}")


if __name__ == "__main__":
    main()
