#!/usr/bin/env python3
# Сбор поисковых подсказок (Яндекс + Google) по темам арт-терапии. 2 уровня. Без авторизации.
import urllib.request, urllib.parse, json, re, time, sys

SEEDS = [
    # прикладные «арт-терапия + ...»
    "арт-терапия для", "арт-терапия для взрослых", "арт-терапия упражнения",
    "арт-терапия эмоции", "арт-терапия стресс", "арт-терапия самооценка",
    "арт-терапия техники", "арт-терапия как", "арт-терапия дома", "арт-терапия для себя",
    # «чистые» проблемные (воронка как в коучинге)
    "как справиться со стрессом", "как выразить эмоции", "как понять что чувствуешь",
    "апатия что делать", "ничего не хочется", "как найти себя",
    "внутренняя опора", "творческий кризис", "эмоциональное выгорание",
    "как успокоиться", "не чувствую эмоций", "рисование для",
]

def yandex(q):
    try:
        u = "https://suggest.yandex.ru/suggest-ya.cgi?part=" + urllib.parse.quote(q)
        r = urllib.request.urlopen(u, timeout=6).read().decode("utf-8","ignore")
        m = re.search(r'suggest\.apply\((.*)\)\s*$', r.strip())
        data = json.loads(m.group(1)) if m else json.loads(r)
        return [s for s in data[1] if isinstance(s, str)]
    except Exception:
        return []

def google(q):
    try:
        u = "https://suggestqueries.google.com/complete/search?client=firefox&hl=ru&q=" + urllib.parse.quote(q)
        r = urllib.request.urlopen(u, timeout=6).read().decode("utf-8","ignore")
        return [s for s in json.loads(r)[1] if isinstance(s, str)]
    except Exception:
        return []

seen, l1 = set(), set()
for s in SEEDS:
    for fn in (yandex, google):
        for p in fn(s):
            p = p.strip().lower()
            if p and p not in seen:
                seen.add(p); l1.add(p)
print(f"L1 собрано: {len(l1)}", file=sys.stderr)
# L2 — только Яндекс, по каждому L1
for p in list(l1):
    for q in yandex(p):
        seen.add(q.strip().lower())
print(f"Всего после L2: {len(seen)}", file=sys.stderr)

# фильтр релевантности
KEEP = re.compile(r'арт.?тера|рисован|творчеств|эмоци|чувств|стресс|тревог|самооцен|апати|выгоран|опора|найти себя|разобраться в себе|успоко|расслаб|мандал|коллаж|насто себя')
DROP = re.compile(r'\b(скачать бесплатно|торрент|порно|казино|mp3|วี|курсовая|реферат|гдз)\b')
res = sorted(p for p in seen if KEEP.search(p) and not DROP.search(p))
with open("docs/seo/raw/suggests-artterapy.txt","w") as f:
    f.write("\n".join(res))
print(f"Релевантных сохранено: {len(res)}", file=sys.stderr)
