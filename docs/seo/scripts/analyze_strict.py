#!/usr/bin/env python3
"""Жёсткая очистка: убираем однословные агрегаты, off-topic, дубли. Цель — рабочее ядро 3000-8000 фраз."""
import csv
import re
import sys
import os
from collections import defaultdict

SRC = '/Users/artemkamenskij/Desktop/сайты Макмагии/общий лендинг/docs/seo/raw/wordstat-all-clean.csv'
OUT_DIR = '/Users/artemkamenskij/Desktop/сайты Макмагии/общий лендинг/docs/seo/raw'

# Жёсткие пороги
MAX_FREQ = 200_000  # выше — почти всегда мусор-агрегаты
MIN_FREQ = 30       # ниже — НЧ-хвост, в первой версии ядра пропускаем
MIN_WORDS = 2       # однословные запросы исключаем

NOISE = re.compile(r"""
\b(
  mac\s?(?:book|mini|air|pro|os)|macos|apple|m1|m2|m3|ipad|iphone|ios|айфон|айпад|
  географ|на\s+карте|карта\s+(?:мира|россии|погоды|метро|маршрут|москвы|осадков|природных|часовых|сша|герман|франц|итали|испан|польш|кит|япон|канад|франт|сво)|
  широта|долгота|меридиан|координат|пролив|маршрут|кавказ|алтай|байкал|сибир|калинин|сочи|крым|ялта|анап|москв|питер|спб|новосибирск|казан|урал|сахалин|чукотк|апатит|тула|тверь|
  карта\s+уно|уно\s+карт|карточн|карты\s+таро|игральные\s+карт|казино|покер|
  apple\s+card|сбер|тинькоф|альфа|втб|мир.?пэй|кешбэк|кэшбэк|
  нспд|росреестр|кадастр|публичная|погода\s+на|пробки|яндекс\s+карты|2gis|2гис|googlemap|gis|
  ментальн|интеллект.?карт|mind\s?map|майнд|
  maç|ascii|api|html|css|json|github|linux|ubuntu|windows|интернет\s+эксплорер|
  макдональд|макдак|wildberries|ozon|wb\b|вайлдберр|озон|алиэксп|sephora|zara|h&m|
  фильм|сериал|режисс[её]р|кинотеатр|netflix|hbo|imdb|кинопоиск|порн|
  ютуб|tiktok|тикток|инстаграм|instagram|onlyfans|тнт|первый\s+канал|
  таро|руны|гадан|гадат|астролог|нумеролог|гороскоп|эзотери|предсказ|карма|биополе|чакр|астральн|архангел|тёмная\s+ночь\s+души|духовн[аые]\s+практик|расстановк\s+хеллингер|хеллингер|
  таблетк|капл[иа]|сироп|укол|таблет|витамин|инструкция\s+по\s+применен|противопоказан|дозировк|нурофен|циклоферон|корвалол|валокордин|фезам|глицин|афобазол|новопассит|персен|тенотен|финлепсин|сульпирид|неулептил|аминалон|пантогам|стрезам|ноотропил|
  рецепт|тесто|выпечк|пирог|торт|пицц|бургер|пастил|оливье|
  гантел|штанг|футбол|хоккей|баскетбол|волейбол|тренаж[её]рн|
  закон|статья\s+гк|статья\s+ук|кодекс|приказ|постановлени|росстат|налог|штраф|госуслуг|мфц|трудовое\s+право|правонаруш|административн|конституци|демократи|границы\s+стран|
  кредит|зарплат|вакансия|резюме|hh\.ru|hr|собеседовани|оклад|премия|деньги\s+на\s+карт|банкинг|банк\s+это|
  блокчейн|крипто|биткоин|майнинг|форекс|трейд|nft|
  школьн|школа\s+\d|колледж|вуз\s+москв|егэ|огэ|олимпиад|курсова|реферат|дипломн|кандидатск|методическ.?\s+рекоменд|
  ascii\s+art|html\s+цвет|цвет\s+rgb|hex\s+цвет|
  карта\s+(?:фронта|сво|украины)|война|мобилизац|ваххаб|
  казахстан|узбекистан|туркмен|таджик|кыргыз|армен|азербайдж|грузия|молдов|беларус|
  гора\s+мак|мак\s+кинли|анатолий|пифагор|шухарт|
  путин|зеленский|байден|трамп|медведев|лавров|
  скачать\s+(?:фб|fb|книг|сериал|фильм|аудиокниг|epub|fb2|pdf\s+бесплатн)|
  система\s+органов|анализ\s+(?:крови|мочи|кала)|результат[ыа]\s+анализ|
  фб\b|фейсбук|телеграм\s+канал|вк\s+стори|стори\s+вк|вк\s+группа|
  банк\s+(?:это|россии|москв|втб)|неделя\s+коучинг|конференц|корпоратив|выставка\s+форум|
  сила\s+(?:тока|воды|трения|сопротивлен)|сила\s+магнит|закон\s+ом|
  имя\s+что\s+означает|что\s+означает\s+имя|перевод\s+слов|перевод\s+на\s+англ|перевод\s+с\s+англ|
  тип\s+личности$|типы\s+личности$|темперамент$|характер\s+это$|самооценка$|тревожный$|гнев$|стыд$|вина$|депресси$|апати$|стресс$|выгорание$|агрессия$|злость$|раздражительность$|обида$|одиночество$|стресс$|любовь$|расставание$|развод$|границы$|психология$|психолог$|психоанализ$|психотерапия$|психотерапевт$|мотивация$|тренинг$|разрабо|ии\s+для\s+карточек|ии\s+для\s+картинок|нпд|мастеркласс|онлайн.?школ\s+проф|школ\s+проф|инженер|строитель|механик|
  негативно$|критики$|симптом\s+это$|психология\s+цвета|познание\s+это$|идея\s+это$|выбор\s+это$|
  раннее\s+развитие|логопед|логопедическ|раннего\s+развития|
  скучно$|надя$|ее\s+парень$|той\s+ночью$|такая\s+как\s+все$|все\s+будет\s+хорошо$|
  суета$|бессонница$|просто\s+так$|ничего\s+не\s+хочу$|
  что\s+делать\s+если\s+(?:тебе|девушка|парень)|выпил|пьян
)\b
""", re.IGNORECASE | re.VERBOSE)

records = []
total_in = 0
noise_count = 0
too_short = 0
too_freq = 0
too_low = 0

with open(SRC, encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        total_in += 1
        phrase = row['phrase'].strip().lower()
        try:
            freq = int(row['frequency'])
        except ValueError:
            continue
        if freq < MIN_FREQ:
            too_low += 1
            continue
        if freq > MAX_FREQ:
            too_freq += 1
            continue
        # Однословные — пропускаем (статью на 1 слово не написать)
        if len(phrase.split()) < MIN_WORDS:
            too_short += 1
            continue
        if NOISE.search(phrase):
            noise_count += 1
            continue
        records.append({
            'phrase': phrase,
            'frequency': freq,
            'cluster': row['cluster'],
            'seed': row['seed'],
            'category': row['category'],
        })

# Сортируем
records.sort(key=lambda x: -x['frequency'])

# Сохранение
strict_path = os.path.join(OUT_DIR, 'wordstat-all-strict.csv')
with open(strict_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['phrase', 'frequency', 'cluster', 'seed', 'category'])
    w.writeheader()
    w.writerows(records)

# Группировка по category, без "Другое"
groups = defaultdict(list)
for it in records:
    if it['category'] == 'Другое':
        continue
    groups[it['category']].append(it)

# Сохранение по группам
groups_path = os.path.join(OUT_DIR, 'wordstat-all-strict-groups.csv')
with open(groups_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['category', 'cluster', 'phrase', 'frequency'])
    for cat in sorted(groups.keys(), key=lambda c: -sum(x['frequency'] for x in groups[c])):
        for it in sorted(groups[cat], key=lambda x: -x['frequency']):
            w.writerow([cat, it['cluster'], it['phrase'], it['frequency']])

# Отчёт
print(f'INPUT_ROWS={total_in}', file=sys.stderr)
print(f'  TOO_LOW(<{MIN_FREQ})={too_low}', file=sys.stderr)
print(f'  TOO_HIGH(>{MAX_FREQ:,})={too_freq}', file=sys.stderr)
print(f'  TOO_SHORT(<{MIN_WORDS} word)={too_short}', file=sys.stderr)
print(f'  NOISE={noise_count}', file=sys.stderr)
print(f'OUTPUT_ROWS={len(records)}', file=sys.stderr)

# Свод по категориям (без "Другое")
print('\n========== ITОГ ПО КАТЕГОРИЯМ ==========', file=sys.stderr)
print(f'{"CATEGORY":<42} {"COUNT":>6} {"TOTAL_FREQ":>13}', file=sys.stderr)
print('-' * 65, file=sys.stderr)
for cat in sorted(groups.keys(), key=lambda c: -sum(x['frequency'] for x in groups[c])):
    cnt = len(groups[cat])
    tot = sum(x['frequency'] for x in groups[cat])
    print(f'{cat:<42} {cnt:>6} {tot:>13,}', file=sys.stderr)

drugoe = [r for r in records if r['category'] == 'Другое']
print(f'\n"Другое" (отброшено из топа): {len(drugoe)} фраз, {sum(x["frequency"] for x in drugoe):,}', file=sys.stderr)

# Топ-30 по каждой ключевой категории
print('\n========== ТОП-30 КАТЕГОРИЙ ==========', file=sys.stderr)
for cat in sorted(groups.keys(), key=lambda c: -sum(x['frequency'] for x in groups[c]))[:30]:
    items = sorted(groups[cat], key=lambda x: -x['frequency'])
    cnt = len(items)
    tot = sum(x['frequency'] for x in items)
    print(f'\n--- {cat} ({cnt}, total {tot:,}) ---', file=sys.stderr)
    for it in items[:10]:
        print(f'  {it["frequency"]:>6}  {it["phrase"]}', file=sys.stderr)

print(f'\n\nSTRICT: {strict_path}', file=sys.stderr)
print(f'GROUPS: {groups_path}', file=sys.stderr)
