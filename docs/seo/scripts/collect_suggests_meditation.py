#!/usr/bin/env python3
import urllib.request, urllib.parse, json, re, sys
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
def get(u):
    try: return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=7).read().decode("utf-8","ignore")
    except Exception: return ""
def yandex(q):
    r=get("https://suggest.yandex.ru/suggest-ya.cgi?part="+urllib.parse.quote(q)); m=re.search(r'suggest\.apply\((.*)\)\s*$', r.strip())
    try: return [s for s in (json.loads(m.group(1)) if m else [])[1] if isinstance(s,str)]
    except Exception: return []
def google(q):
    r=get("https://suggestqueries.google.com/complete/search?client=firefox&hl=ru&q="+urllib.parse.quote(q))
    try: return [s for s in json.loads(r)[1] if isinstance(s,str)]
    except Exception: return []
SEEDS=["медитация","медитация для","медитация для сна","медитация перед сном","медитация от тревоги","медитация от стресса","медитация расслабление","медитация для женщин","медитация утренняя","медитация для начинающих","медитация для успокоения","медитация на уверенность","медитация на самооценку","медитация принятие себя","медитация отпустить","управляемая медитация","медитация дыхание","медитация для восстановления сил","медитация при тревожности","медитация исцеление"]
seen=set(); l1=set()
for s in SEEDS:
    for fn in (yandex,google):
        for p in fn(s):
            p=p.strip().lower()
            if p: seen.add(p); l1.add(p)
sys.stderr.write(f"L1: {len(l1)}\n")
for p in list(l1):
    for q in yandex(p): seen.add(q.strip().lower())
sys.stderr.write(f"после L2: {len(seen)}\n")
KEEP=re.compile(r'медитац|дыхан|расслаб|релакс|визуализац|сканирование тела|аутотрениг|аутогенн')
DROP=re.compile(r'скачать бесплатно|торрент|казино|mp3 скачать|трансерфинг|симорон')
res=sorted(p for p in seen if KEEP.search(p) and not DROP.search(p))
open("docs/seo/raw/suggests-meditation.txt","w").write("\n".join(res))
sys.stderr.write(f"релевантных: {len(res)}\n")
