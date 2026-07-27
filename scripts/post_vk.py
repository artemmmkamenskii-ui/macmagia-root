#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Публикация статей блога в сообщество ВКонтакте.

Берёт статьи из docs/seo/articles/*.md, постит на стену сообщества анонс
с обложкой и ссылкой на сайт. По умолчанию — те, у кого publishedAt = сегодня,
то есть скрипт можно вешать на тот же ежедневный крон, что и деплой.

Токен и id сообщества читаются из .env в корне репозитория (см. .env.example).
.env лежит вне гита — токен в репозиторий не попадает.

    python3 scripts/post_vk.py --whoami          # проверить токен и узнать id
    python3 scripts/post_vk.py --dry-run         # показать, что бы запостил
    python3 scripts/post_vk.py                   # запостить сегодняшние
    python3 scripts/post_vk.py --date 2026-07-28 # за конкретный день
    python3 scripts/post_vk.py --slug apatiya    # одну статью
    python3 scripts/post_vk.py --limit 3         # не больше трёх за раз

Уже опубликованное запоминается в docs/seo/vk-posted.json, поэтому повторный
запуск ничего не задваивает.
"""
import argparse
import datetime
import json
import sys
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "docs" / "seo" / "articles"
COVERS = ROOT / "blog" / "covers"
STATE = ROOT / "docs" / "seo" / "vk-posted.json"
ENV = ROOT / ".env"

SITE_URL = "https://macmagia.ru"
API = "https://api.vk.com/method/"


def load_env():
    if not ENV.exists():
        sys.exit("Нет файла .env — скопируй .env.example в .env и впиши токен.")
    env = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    if not env.get("VK_TOKEN"):
        sys.exit("В .env пустой VK_TOKEN.")
    return env


def vk(env, method, **params):
    params.setdefault("v", env.get("VK_API_VERSION") or "5.199")
    params["access_token"] = env["VK_TOKEN"]
    r = requests.post(API + method, data=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        e = data["error"]
        sys.exit(f"VK API {method}: [{e.get('error_code')}] {e.get('error_msg')}")
    return data["response"]


def load_meta(md_path):
    txt = md_path.read_text(encoding="utf-8")
    if not txt.startswith("---"):
        return None
    end = txt.find("\n---", 3)
    if end == -1:
        return None
    fm = yaml.safe_load(txt[3:end])
    fm.setdefault("slug", md_path.stem)
    return fm


def as_date(v):
    if isinstance(v, datetime.date):
        return v
    return datetime.date.fromisoformat(str(v)[:10])


def build_message(fm):
    """Анонс: заголовок, описание, ссылка и пара хештегов."""
    url = f"{SITE_URL}/blog/{fm['slug']}.html"
    tags = [t for t in (fm.get("tags") or [])][:3]
    hashtags = " ".join("#" + str(t).replace(" ", "_").replace("-", "_") for t in tags)
    parts = [str(fm["title"]), "", str(fm["description"]), "", f"Читать целиком: {url}"]
    if hashtags:
        parts += ["", hashtags]
    return "\n".join(parts)


def upload_cover(env, group_id, slug):
    """Загрузка обложки на стену сообщества: 3 шага по документации VK."""
    cover = COVERS / f"{slug}.jpg"
    if not cover.exists():
        return None
    up = vk(env, "photos.getWallUploadServer", group_id=group_id)
    with cover.open("rb") as f:
        r = requests.post(up["upload_url"], files={"photo": (cover.name, f, "image/jpeg")},
                          timeout=60)
    r.raise_for_status()
    up_res = r.json()
    saved = vk(env, "photos.saveWallPhoto", group_id=group_id,
               server=up_res["server"], photo=up_res["photo"], hash=up_res["hash"])
    p = saved[0]
    return f"photo{p['owner_id']}_{p['id']}"


def load_state():
    if STATE.exists():
        return set(json.loads(STATE.read_text(encoding="utf-8")))
    return set()


def save_state(done):
    STATE.write_text(json.dumps(sorted(done), ensure_ascii=False, indent=2),
                     encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--whoami", action="store_true", help="проверить токен, показать сообщество")
    ap.add_argument("--dry-run", action="store_true", help="показать, но не постить")
    ap.add_argument("--date", help="публиковать статьи за эту дату (YYYY-MM-DD)")
    ap.add_argument("--slug", help="одна конкретная статья")
    ap.add_argument("--limit", type=int, default=10, help="максимум постов за запуск")
    ap.add_argument("--force", action="store_true", help="постить, даже если уже постили")
    args = ap.parse_args()

    env = load_env()

    if args.whoami:
        groups = vk(env, "groups.getById")
        items = groups.get("groups", groups) if isinstance(groups, dict) else groups
        for g in items:
            print(f"  сообщество: {g.get('name')}  id={g.get('id')}  "
                  f"(в .env → VK_GROUP_ID={g.get('id')})")
        return 0

    group_id = env.get("VK_GROUP_ID")
    if not group_id:
        sys.exit("В .env пустой VK_GROUP_ID — узнай его командой --whoami.")

    target = as_date(args.date) if args.date else datetime.date.today()
    done = load_state()

    picked = []
    for md in sorted(ARTICLES.glob("*.md")):
        fm = load_meta(md)
        if not fm:
            continue
        if args.slug:
            if fm["slug"] == args.slug:
                picked.append(fm)
            continue
        if as_date(fm["publishedAt"]) == target:
            picked.append(fm)

    if not args.force:
        picked = [f for f in picked if f["slug"] not in done]
    picked = picked[:args.limit]

    if not picked:
        print(f"Нечего постить (дата {target}, уже опубликовано {len(done)}).")
        return 0

    for fm in picked:
        msg = build_message(fm)
        if args.dry_run:
            print(f"\n--- {fm['slug']} ---\n{msg}\n[обложка: "
                  f"{'есть' if (COVERS / (fm['slug'] + '.jpg')).exists() else 'НЕТ'}]")
            continue
        attach = upload_cover(env, group_id, fm["slug"])
        res = vk(env, "wall.post", owner_id=f"-{group_id}", from_group=1,
                 message=msg, attachments=attach or "")
        done.add(fm["slug"])
        print(f"  опубликовано vk.com/wall-{group_id}_{res['post_id']}  [{fm['slug']}]")
        time.sleep(1)  # VK не любит частые запросы подряд

    if not args.dry_run:
        save_state(done)
    return 0


if __name__ == "__main__":
    sys.exit(main())
