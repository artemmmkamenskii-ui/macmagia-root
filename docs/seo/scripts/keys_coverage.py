#!/usr/bin/env python3
# Реестр покрытия ключей: дамп Wordstat -> где покрыт в статье (ядро/тело/gap)
import zipfile, re, os
from xml.etree import ElementTree as ET
NS='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
ART='docs/seo/articles'
NOISE=re.compile(r'песн|скачать|минус|аккорд|mp3|клип|ремикс|сериал|фильм|смотреть|аниме|манга|глава|сезон|серия|симс|сонник|трейлер|актёр|актер|караоке|табы|дорама|новелл|комикс| игра|мем|цитат|стих|аудиокниг|перевод|на английск|изложение|огэ|сочинение|школа без обид|конкурс|опросник|shadow|martin|bad thoughts|тест на|тесто|синоним|воплощение|яд ревност|без обид|ефимов|шкала|3 потер',re.I)
STOP=set('и в во не на что с со а то по как для из у к о же ли бы за от до без про над под при я ты он она оно мы вы они мне меня тебя себя его её их это эта этот так уже ещё или но да нет чего чему чём кто все всё чтобы если когда где куда там тут вот'.split())
def words(q): return [w for w in re.findall(r'[а-яё]+', q.lower()) if len(w)>3 and w not in STOP]
def stem(w): return w[:5]
def parse(fn):
    z=zipfile.ZipFile(f"ключи/{fn}"); root=ET.fromstring(z.read('word/document.xml')); seen={}
    for p in root.iter('{%s}p'%NS):
        t=''.join(x.text or '' for x in p.iter('{%s}t'%NS)).strip()
        m=re.match(r'^(.*?)(\d{2,})$',t)
        if m:
            ph=m.group(1).strip().lower(); fr=int(m.group(2))
            if ph and fr<500000 and not NOISE.search(ph) and len(words(ph))>=1: seen[ph]=max(seen.get(ph,0),fr)
    return sorted(seen.items(),key=lambda x:-x[1])
def zones(slug):
    txt=open(f"{ART}/{slug}.md",encoding='utf-8').read()
    fm=re.search(r'^---\n(.*?)\n---',txt,re.DOTALL); fmt=fm.group(1) if fm else ''
    title=' '.join(re.findall(r'(?:title:|primaryKeyword:|lsiKeywords:|- )(.*)',fmt))
    h2=' '.join(re.findall(r'^##+ .*',txt,re.M))
    faqq=' '.join(re.findall(r'^\*\*.*\?\*\*',txt,re.M))
    core=(title+' '+h2+' '+faqq).lower()
    body=txt.lower()
    return core, body
def classify(q,core,body):
    ws=[stem(w) for w in words(q)]
    if not ws: return 'тело'
    incore=sum(1 for w in ws if w in core); inbody=sum(1 for w in ws if w in body)
    if incore>=max(1,len(ws)*0.6): return 'ядро'
    if inbody>=max(1,len(ws)*0.6): return 'тело'
    return 'gap'
MAP=[
 ("kak-spravitsya-s-trevogoy","тревожность273344.docx"),("navyazchivye-mysli","плохие мысли.docx"),
 ("giperkontrol","потеряв контроль.docx"),("chuvstvo-viny","вина чувство.docx"),
 ("kak-spravitsya-so-stydom","стыдно.docx"),("kak-otpustit-obidu","обида.docx"),
 ("chuvstvo-odinochestva","чувство одиночества.docx"),("sindrom-otlichnicy","все должно быть идеально.docx"),
 ("roditelskoe-vygoranie","родительское выгорание.docx"),("kak-spravitsya-s-revnostyu","ревность.docx"),
 ("kak-prinyat-i-polyubit-sebya","примет себя.docx"),("sindrom-samozvanca","синдром самозванца.docx"),
 ("perfekcionizm","перфекционизм.docx"),("lichnye-granicy","границы личные.docx"),
 ("sozavisimost","созависимость.docx"),("toksichnye-roditeli","Обида на мать.docx"),
 ("vybirayu-ne-teh","токсичные отношения.docx"),("krizis-srednego-vozrasta","кризисы возраста.docx"),
 ("kak-najti-sebya","как найти себя.docx"),("apatiya","апатия.docx"),
 ("opustevshee-gnezdo","синдром опустевшего гнезда.docx"),("kak-vosstanovit-resurs","хроническая усталость.docx"),
 ("zaedanie-emocij","переедание.docx"),("prinyatie-tela","бодипозитив.docx"),
 ("zhenskie-arhetipy","женственность.docx"),("tvorcheskij-blok"," Творческий блок.docx"),
 ("strah-proyavlyatsya","что делать если стесняешься.docx"),
]
out=["# Реестр покрытия ключей (Wordstat → статья)","",
"Авто-разбор: по каждому дампу топ чистых запросов классифицирован — **ядро** (title/H2/FAQ), **тело/синонимы**, **gap → роадмап**.",
"Сгенерировано `scripts/keys_coverage.py`. Колонка gap = «наш по интенту запрос, но на странице не покрыт» → решить: вписать или вынести в отдельную статью.",""]
for slug,fn in MAP:
    if not os.path.exists(f"ключи/{fn}") or not os.path.exists(f"{ART}/{slug}.md"): 
        out.append(f"## {slug}\n_нет дампа или статьи_\n"); continue
    core,body=zones(slug)
    fmtxt=open(f"{ART}/{slug}.md",encoding='utf-8').read()
    pk=re.search(r'primaryKeyword:\s*"?([^"\n]+)',fmtxt)
    theme=set(stem(w) for w in words(pk.group(1))) if pk else set()
    allrows=parse(fn)
    rows=[(ph,fr) for ph,fr in allrows if theme & set(stem(w) for w in words(ph))][:16]
    buckets={'ядро':[],'тело':[],'gap':[]}
    for ph,fr in rows: buckets[classify(ph,core,body)].append(f"{ph} ({fr})")
    out.append(f"## {slug}")
    out.append(f"**ядро (title/H2/FAQ):** {'; '.join(buckets['ядро']) or '—'}  ")
    out.append(f"**тело/синонимы:** {'; '.join(buckets['тело']) or '—'}  ")
    gap=buckets['gap']
    out.append(f"**⚠️ gap → роадмап:** {'; '.join(gap) if gap else '— нет'}")
    out.append("")
open("docs/seo/ключи-разбор.md","w",encoding='utf-8').write("\n".join(out))
print("готово, gap-ов всего:", sum(1 for _ in re.finditer(r'gap → роадмап:\*\* (?!— нет)', "\n".join(out))))
