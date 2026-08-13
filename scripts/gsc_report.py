#!/usr/bin/env python3
"""Отчёт из Google Search Console по API.

Заменяет ручную выгрузку CSV: показывает, какие страницы получают показы,
где мы стоим на второй странице выдачи (там переписанный заголовок даёт
быстрый прирост) и что именно творится с индексацией каждого адреса.

Доступ: сервисный аккаунт Google Cloud, его адрес добавлен в Search Console
как пользователь с полными правами. Ключ лежит вне репозитория.

    python3 scripts/gsc_report.py                 # сводка за 28 дней
    python3 scripts/gsc_report.py --days 7
    python3 scripts/gsc_report.py --queries       # ещё и по запросам
    python3 scripts/gsc_report.py --inspect 50    # статус индексации 50 адресов

Библиотеки: google-auth и requests (обе уже стоят), googleapiclient не нужен —
ходим в REST напрямую.
"""

import argparse
import datetime
import os
import pathlib
import re
import sys
import time

try:
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
except ImportError:
    sys.exit("нет google-auth. Поставить: pip3 install google-auth")

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_KEY = pathlib.Path.home() / ".config" / "macmagia" / "gsc.json"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
API = "https://searchconsole.googleapis.com"
SITE_HOST = "macmagia.ru"

# Человеческие названия статусов индексации — в ответе они приходят строками
# вроде PASS / NEUTRAL, а verdict без пояснения мало что говорит.
COVERAGE_RU = {
    "Submitted and indexed": "в индексе",
    "Indexed, not submitted in sitemap": "в индексе (нет в карте сайта)",
    "Crawled - currently not indexed": "просканирована, не в индексе",
    "Discovered - currently not indexed": "обнаружена, не сканировалась",
    "Page with redirect": "редирект",
    "Duplicate without user-selected canonical": "дубль без канонической",
    "Alternate page with proper canonical tag": "есть каноническая на другую",
    "Excluded by 'noindex' tag": "закрыта noindex",
    "Not found (404)": "404",
    "URL is unknown to Google": "Google о ней не знает",
}


def session(key_path):
    if not key_path.exists():
        sys.exit(f"нет ключа: {key_path}\n"
                 f"положить json сервисного аккаунта туда или указать --key")
    creds = service_account.Credentials.from_service_account_file(
        str(key_path), scopes=SCOPES)
    return AuthorizedSession(creds)


def pick_site(s):
    """Ресурс в Search Console. Домен, подтверждённый через DNS, называется
    sc-domain:<домен>, подтверждённый файлом — обычным адресом."""
    r = s.get(f"{API}/webmasters/v3/sites")
    if r.status_code == 403:
        sys.exit("403: сервисный аккаунт не добавлен в Search Console.\n"
                 "Настройки → Пользователи и разрешения → добавить его адрес.")
    r.raise_for_status()
    sites = [e["siteUrl"] for e in r.json().get("siteEntry", [])]
    if not sites:
        sys.exit("аккаунту не выдан доступ ни к одному ресурсу")
    for want in (f"sc-domain:{SITE_HOST}", f"https://{SITE_HOST}/"):
        if want in sites:
            return want
    for site in sites:
        if SITE_HOST in site:
            return site
    sys.exit(f"{SITE_HOST} не найден. Доступные ресурсы: {', '.join(sites)}")


def query(s, site, start, end, dims, limit=25000):
    r = s.post(
        f"{API}/webmasters/v3/sites/{site.replace('/', '%2F').replace(':', '%3A')}"
        f"/searchAnalytics/query",
        json={"startDate": start, "endDate": end, "dimensions": dims,
              "rowLimit": limit, "type": "web"},
    )
    r.raise_for_status()
    return r.json().get("rows", [])


def short(url):
    return re.sub(r"^https?://[^/]+", "", url) or "/"


def bar(n, top, width=22):
    return "▇" * max(1, round(width * n / top)) if n and top else ""


def report_pages(s, site, days):
    today = datetime.date.today()
    # GSC отдаёт данные с задержкой в 2-3 дня, поэтому окно сдвинуто назад
    end = today - datetime.timedelta(days=3)
    start = end - datetime.timedelta(days=days - 1)
    prev_end = start - datetime.timedelta(days=1)
    prev_start = prev_end - datetime.timedelta(days=days - 1)

    rows = query(s, site, start.isoformat(), end.isoformat(), ["page"])
    prev = {r["keys"][0]: r for r in
            query(s, site, prev_start.isoformat(), prev_end.isoformat(), ["page"])}

    imp = sum(r["impressions"] for r in rows)
    clicks = sum(r["clicks"] for r in rows)
    p_imp = sum(r["impressions"] for r in prev.values())
    p_clicks = sum(r["clicks"] for r in prev.values())

    def delta(now, was):
        if not was:
            return "новое" if now else ""
        d = round((now - was) / was * 100)
        return f"{d:+d}%"

    print(f"\n  Период: {start} — {end}  ({days} дней)")
    print(f"  Показы: {imp}  ({delta(imp, p_imp)} к прошлому периоду)")
    print(f"  Клики:  {clicks}  ({delta(clicks, p_clicks)})")
    print(f"  Страниц с показами: {len(rows)}")

    if not rows:
        print("\n  Показов нет. Для нового сайта это нормально — данные "
              "появляются после того, как страницы попадут в индекс.")
        return

    rows.sort(key=lambda r: -r["impressions"])
    top = rows[0]["impressions"]
    print(f"\n  {'страница':<44} {'показы':>7} {'клики':>6} {'поз.':>5}")
    for r in rows[:25]:
        u = short(r["keys"][0])
        print(f"  {u[:44]:<44} {r['impressions']:>7.0f} {r['clicks']:>6.0f} "
              f"{r['position']:>5.1f}  {bar(r['impressions'], top)}")

    # Позиции 8-25: страница уже нравится Google, но до кликов не дотягивает.
    # Здесь переписанный заголовок и описание окупаются быстрее всего.
    close = [r for r in rows if 8 <= r["position"] <= 25 and r["impressions"] >= 5]
    if close:
        print(f"\n  Рядом с первой страницей — сюда стоит вложиться "
              f"({len(close)}):")
        for r in sorted(close, key=lambda r: r["position"])[:15]:
            print(f"    поз. {r['position']:>4.1f}  показов {r['impressions']:>5.0f}"
                  f"  {short(r['keys'][0])}")


def report_queries(s, site, days):
    end = datetime.date.today() - datetime.timedelta(days=3)
    start = end - datetime.timedelta(days=days - 1)
    rows = query(s, site, start.isoformat(), end.isoformat(), ["query"])
    if not rows:
        return
    rows.sort(key=lambda r: -r["impressions"])
    print(f"\n  Запросы, по которым нас показывают ({len(rows)}):")
    print(f"\n  {'запрос':<44} {'показы':>7} {'клики':>6} {'поз.':>5}")
    for r in rows[:30]:
        print(f"  {r['keys'][0][:44]:<44} {r['impressions']:>7.0f} "
              f"{r['clicks']:>6.0f} {r['position']:>5.1f}")


def report_index(s, site, limit):
    """Статус индексации. Квота — 2000 адресов в сутки, 600 в минуту."""
    sitemap = ROOT / "sitemap.xml"
    if not sitemap.exists():
        sys.exit("нет sitemap.xml — сначала собрать блог")
    urls = re.findall(r"<loc>(.*?)</loc>", sitemap.read_text(encoding="utf-8"))
    urls = urls[:limit]
    print(f"\n  Проверяю {len(urls)} адресов (квота 2000 в сутки)...\n")

    counts, problems = {}, []
    for i, u in enumerate(urls, 1):
        r = s.post(f"{API}/v1/urlInspection/index:inspect",
                   json={"inspectionUrl": u, "siteUrl": site, "languageCode": "ru"})
        if r.status_code == 429:
            print("  квота исчерпана, останавливаюсь")
            break
        r.raise_for_status()
        res = r.json().get("inspectionResult", {}).get("indexStatusResult", {})
        state = res.get("coverageState", "нет данных")
        counts[state] = counts.get(state, 0) + 1
        if "indexed" not in state.lower() or "not" in state.lower():
            problems.append((state, u))
        if i % 25 == 0:
            print(f"    {i}/{len(urls)}")
        time.sleep(0.12)

    print(f"\n  Итог по {sum(counts.values())} адресам:\n")
    for state, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"    {n:>4}  {COVERAGE_RU.get(state, state)}")

    if problems:
        print(f"\n  Не в индексе ({len(problems)}), первые 30:")
        for state, u in problems[:30]:
            print(f"    {COVERAGE_RU.get(state, state):<32} {short(u)}")


def main():
    ap = argparse.ArgumentParser(description="Отчёт из Google Search Console")
    ap.add_argument("--key", type=pathlib.Path,
                    default=pathlib.Path(os.environ.get("GSC_KEY", DEFAULT_KEY)))
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--queries", action="store_true", help="ещё и разбивка по запросам")
    ap.add_argument("--inspect", type=int, metavar="N",
                    help="проверить статус индексации N адресов из карты сайта")
    args = ap.parse_args()

    s = session(args.key)
    site = pick_site(s)
    print(f"\n  Ресурс: {site}")

    report_pages(s, site, args.days)
    if args.queries:
        report_queries(s, site, args.days)
    if args.inspect:
        report_index(s, site, args.inspect)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
