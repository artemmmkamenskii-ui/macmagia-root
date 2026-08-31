# macmagia.ru — recovery runbook

Если `https://macmagia.ru/` (и/или `/ai`, `/artterapy`, `/mac`, `/cards/`) не открывается.

## Топология

- **VM:** `compute-vm-2-2-20-ssd-1776770416334` в Yandex Cloud (зона `ru-central1-b`, сеть `default`). Конфигурация: **2 vCPU (100% гарантировано) / 4 GB RAM / 30 GB SSD** (после апгрейда 2026-05-17 — раньше было 2/2/20). Имя ВМ в YC consoleимеет старый суффикс `-2-2-20-ssd` — это исторический artefact, не отражает текущие характеристики.
- **Публичный IP:** **`111.88.154.110`** — статический, закреплён за ВМ (см. VPC → IP-адреса, `e2l8lq2k9s6e5nojqb3s`). При `Stop`/`Start` не меняется. Если IP всё же другой — проверять в консоли (Compute Cloud → ВМ → "Публичный IPv4-адрес").
- **DNS:** зона на Cloudflare (NS `cory.ns.cloudflare.com`, `nia.ns.cloudflare.com`). A-записи `macmagia.ru`, `www`, `lk` → `111.88.154.110`, **все в режиме DNS only (серое облако)**. Проксирование (оранжевое облако) включать нельзя — см. инцидент 2026-08-17.
- **SSH:** `ssh -i ~/.ssh/macmagia_deploy ubuntu@111.88.154.110`
- **Managed-кластера:** **не используются** (всё в Next.js без БД)

## Что крутится

Все 4 субпроекта — Next.js под управлением **PM2** (`/home/ubuntu/.pm2/dump.pm2`):

| Путь | Порт | PM2 name | Папка |
|---|---|---|---|
| `macmagia.ru/cards/` (и `/`-fallback на nginx) | 3000 | `macmagia` | `/home/ubuntu/macmagia` |
| `macmagia.ru/ai` | 3100 | `macmagia-ai` | `/home/ubuntu/macmagia-ai` |
| `macmagia.ru/artterapy` | 3110 | `macmagia-art-therapy` | `/home/ubuntu/macmagia-art-therapy` |
| `macmagia.ru/mac` | 3120 | `macmagia-mac` | `/home/ubuntu/macmagia-mac` |

Статический лендинг (этот репо) деплоится в `/var/www/macmagia-root/` через GitHub Actions и отдаётся nginx'ом на `/`.

nginx-конфиг: `/etc/nginx/sites-available/macmagia`. TLS — Let's Encrypt через certbot.

## Сайт открывается только через VPN

Первым делом сравнить, что отдаёт DNS, с реальным IP сервера:

```bash
dig +short macmagia.ru A          # должно быть 111.88.154.110
curl -sI https://macmagia.ru/ | grep -i server   # должно быть nginx, НЕ cloudflare
```

Если в DNS адреса вида `104.21.*` / `172.67.*`, а в заголовках `server: cloudflare` —
записи в Cloudflare переведены в режим Proxied. Российские провайдеры такие соединения
рвут: сайт открывается с VPN и не открывается без него, при этом сервер полностью
исправен и снаружи (из Европы) отвечает 200.

Лечение: Cloudflare → домен → DNS → Records → у записей `macmagia.ru` и `www`
переключить Proxy status с **Proxied** на **DNS only** → Save. Обновляется за минуты,
перезапускать ничего не нужно.

Проверить, что сервер готов принимать трафик напрямую, можно заранее, не трогая DNS:

```bash
curl -sI --resolve macmagia.ru:443:111.88.154.110 https://macmagia.ru/
```

Сертификат на origin — wildcard (`macmagia.ru` + `*.macmagia.ru`), так что HTTPS
после отключения проксирования работает без правок.

**Важно про мониторинг:** внешняя проверка доступности такую поломку не видит —
через Cloudflare сайт отдаёт 200, и алерт не приходит. Проверять нужно с российской
точки.

## Чек-лист "сайт не открывается"

### 1. Проверить, что ВМ запущена
Yandex Cloud Console → Compute Cloud → ВМ. Статус должен быть `Running`. Если `Stopped` — `Start` и подождать ~60 сек.

### 2. Сравнить IP с DNS
- В консоли: публичный IP ВМ
- На своей машине: `dig +short macmagia.ru A`
- Если разные — обновить A-запись у регистратора домена на актуальный IP. TTL обычно 300-600 сек.

### 3. Проверить снаружи
```bash
curl -sI https://macmagia.ru/
# Если виснет на TLS — это либо DNS не догнал, либо security group режет 80/443.
```

### 4. SSH и PM2
```bash
ssh -i ~/.ssh/macmagia_deploy ubuntu@<IP>
pm2 list                        # должно быть 4 online
# если пусто или процессы errored:
pm2 resurrect                   # восстановит из dump.pm2
sudo ss -ltnp | grep -E ':3000|:3100|:3110|:3120'   # должно быть 4 LISTEN
```

PM2 настроен на autostart через `pm2-ubuntu.service` (systemd), поэтому при ребуте ВМ всё должно подняться само. Если нет — `pm2 startup systemd -u ubuntu --hp /home/ubuntu` и потом `pm2 save`.

### 5. nginx
```bash
sudo systemctl status nginx
sudo nginx -t
sudo tail -n 50 /var/log/nginx/error.log
```

### 6. Security Group
ВМ в сети `default`, привязана SG `default-sg-enpu7i6ddq2m7o3osk1q`. В ней должны быть **inbound** правила:
- TCP 22 / 0.0.0.0/0 (SSH)
- TCP 80 / 0.0.0.0/0 (HTTP)
- TCP 443 / 0.0.0.0/0 (HTTPS)

Если 80/443 пропали (например, SG пересоздалась) — добавить через VPC → Облачные сети → `default` → Группы безопасности.

## История инцидентов

- **2026-04-28** — после перевода Yandex Cloud аккаунта с триала на платный ВМ остановилась. После старта: (1) PM2 не имел systemd-юнита, апы не поднялись → `pm2 resurrect` + `pm2 startup systemd`; (2) публичный IP сменился с `103.76.55.254` на `103.76.52.35`, обновили A-запись; (3) SG не имела правил для 80/443, добавили.
- **2026-05-17** — плановый апгрейд ВМ под будущий LMS / кабинет учеников. Stop → конфигурация изменена с 2 vCPU 20% / 2 GB / 20 GB на **2 vCPU 100% / 4 GB / 30 GB**, диск расширен в Yandex Cloud (раздел внутри ОС вырос автоматически через cloud-init, ручной `growpart`/`resize2fs` не понадобился). IP `111.88.154.110` — уже был статический, не сменился. PM2 поднял все 4 процесса сам, `resurrect` не понадобился.
- **2026-08-17** — сайт перестал открываться без VPN. Домен к тому моменту жил на Cloudflare с проксированием (оранжевое облако) на `macmagia.ru` и `www`; российские провайдеры такие соединения рвут. Сервер был полностью исправен: load 0.03, все процессы PM2 живы, origin отдавал 200 при запросе с `--resolve`. Показательно, что `lk.macmagia.ru` работал — он единственный стоял в DNS only. Вылечено переводом обеих записей в DNS only, DNS разошёлся за минуты. Внешний мониторинг молчал: через Cloudflare сайт отвечал 200.
