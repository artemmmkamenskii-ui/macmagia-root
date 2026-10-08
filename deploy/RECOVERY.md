# macmagia.ru — recovery runbook

Если `https://macmagia.ru/` (и/или `/ai`, `/artterapy`, `/mac`, `/cards`, `/coach`, `/praktik`, `lk.macmagia.ru`) не открывается.

## Топология (с 2026-10-08)

- **VPS:** Beget Cloud, «Flawless Vasiliy», Санкт-Петербург. **2 vCPU / 4 GB RAM / 40 GB NVMe**, Ubuntu 24.04, swap 2 GB. Панель: cp.beget.com → Облако → Виртуальные серверы.
- **Публичный IP:** **`159.194.240.232`**.
- **DNS:** зона на Cloudflare (NS `cory.ns.cloudflare.com`, `nia.ns.cloudflare.com`). A-записи `macmagia.ru`, `www`, `lk` → `159.194.240.232`, **все в режиме DNS only (серое облако)**. Проксирование (оранжевое облако) включать нельзя — см. инцидент 2026-08-17.
- **SSH:** `ssh -i ~/.ssh/macmagia_admin ubuntu@159.194.240.232` (ключ `macmagia_deploy` тоже прописан; `root` — тем же `macmagia_admin`).
- **Файрвол:** `ufw`, открыты только 22/80/443. PostgreSQL слушает только localhost.
- **Деплой:** во всех 8 репо (`macmagia-root`, `-cards`, `-ai-landing`, `-art-therapy`, `-mac`, `-praktik`, `-coach`, `-lk`) секреты `DEPLOY_HOST=159.194.240.232`, `DEPLOY_PORT=22`, `DEPLOY_USER=ubuntu`. Переезд на другой сервер = поменять эти три секрета и перезапустить деплои.
- **Старая ВМ** `macmagia` в Yandex Cloud (`ru-central1-b`, `111.88.154.110`) — выведена из работы после сбоя зоны 2026-10-08, на её диске остались данные ЛК после 07.10 ~03:00 (см. историю инцидентов).

## Что крутится

Всё — под **PM2** от пользователя `ubuntu`, автозапуск через `pm2-ubuntu.service` (systemd):

| Путь | Порт | PM2 name | Папка |
|---|---|---|---|
| `macmagia.ru/` и `/blog/` (статика) | — | — (nginx) | `/var/www/macmagia-root` |
| `macmagia.ru/cards` | 3000 | `macmagia` | `/home/ubuntu/macmagia` |
| `macmagia.ru/praktik` | 3022 | `landing-praktik` | `/home/ubuntu/macmagia-praktik` |
| `macmagia.ru/ai` | 3100 | `macmagia-ai` | `/home/ubuntu/macmagia-ai` |
| `macmagia.ru/artterapy` | 3110 | `macmagia-art-therapy` | `/home/ubuntu/macmagia-art-therapy` |
| `macmagia.ru/mac` | 3120 | `macmagia-mac` | `/home/ubuntu/macmagia-mac` |
| `macmagia.ru/coach` | 3130 | `macmagia-coach` | `/home/ubuntu/macmagia-coach` |
| `lk.macmagia.ru` | 3200 | `macmagia-lk` | `/home/ubuntu/macmagia-lk` |
| `lk.macmagia.ru/ws` (видеозвонки) | 3142 | `macmagia-lk-ws` | `/home/ubuntu/macmagia-lk/server/ws.js` |

nginx-конфиг: `/etc/nginx/sites-available/macmagia`. TLS — Let's Encrypt через certbot (сертификат на `macmagia.ru`, `www`, `lk`), продлевается таймером `certbot.timer`.

**Данные:**
- База ЛК — PostgreSQL 16 на этом же VPS, БД `macmagia_lk`, роль `lms`. Пароль — в `~/macmagia-lk/.env` (`DATABASE_URL`).
- Видео и материалы уроков — бакет `macmagiakursi` в Yandex Object Storage. ЛК ходит туда ключом сервисного аккаунта `lms-backup-sa` (`S3_*` в `~/macmagia-lk/.env`).
- **Бэкап базы ЛК:** `/usr/local/bin/lk-backup` по cron (`/etc/cron.d/lk-backup`) каждый день в 03:00 МСК: `pg_dump` → `/var/backups/lk/` (7 последних) + копия в `s3://macmagia-lms-backups/postgres/lms-*.sql.gz`. При ошибке — сообщение в Telegram. Лог: `/var/backups/lk/backup.log`.
- ⚠️ Все копии пока только в России (VPS + Yandex). Внешний сервер бэкапов — в планах.

## Поднять всё на чистом сервере

Порядок, которым сайты подняли 2026-10-08 (заняло ~1,5 часа):

1. Ubuntu 24.04, пользователь `ubuntu` с sudo и ключами `macmagia_deploy.pub` + `macmagia_admin.pub`.
2. Пакеты: Node.js 22 (NodeSource), `pm2` глобально, `nginx`, `certbot python3-certbot-nginx`, `postgresql`, `rsync`; `ufw allow 22,80,443`.
3. База ЛК: `CREATE ROLE lms LOGIN PASSWORD '…'; CREATE DATABASE macmagia_lk OWNER lms;` → залить последний дамп `postgres/lms-*.sql.gz` из бакета `macmagia-lms-backups`. Поставить `rclone` и скрипт бэкапа `lk-backup` (копия скрипта — на текущем сервере в `/usr/local/bin/`).
4. `.env`, которых нет в GitHub-секретах, — положить руками (локальные копии лежат в папках проектов):
   `macmagia-ai/.env.production`, `macmagia-art-therapy/.env.production`, `macmagia-coach/.env.production`, `macmagia-praktik/.env.local`, `macmagia-lk/.env`.
   Сайт карт и `/mac` пишут свой `.env.local` сами из GitHub-секретов. Локальный `.env.local` сайта карт — **dev**, на сервер его не класть.
5. nginx-конфиг (см. выше) → `nginx -t && systemctl reload nginx`.
6. Поменять секреты `DEPLOY_HOST/PORT/USER` в 8 репо → запустить деплои (`gh workflow run deploy.yml -R …`). Шаг Health check будет красным, пока DNS смотрит на старый IP, — это нормально.
7. ЛК деплоится с ноутбука (Actions-деплой ЛК сломан с июня, а локальный код новее GitHub): `MACMAGIA_HOST=<ip> bash scripts/deploy.sh` из `3. платформа по обучению`, затем `pm2 start server/ws.js --name macmagia-lk-ws && pm2 save`.
8. Проверить по IP: `curl -s -o /dev/null -w "%{http_code}" -H "Host: macmagia.ru" http://<ip>/ai`.
9. Cloudflare → A-записи `macmagia.ru`, `www`, `lk` → новый IP, DNS only.
10. `certbot --nginx --redirect -d macmagia.ru -d www.macmagia.ru -d lk.macmagia.ru`.

## Сайт открывается только через VPN

Первым делом сравнить, что отдаёт DNS, с реальным IP сервера:

```bash
dig +short macmagia.ru A          # должно быть 159.194.240.232
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
curl -sI --resolve macmagia.ru:443:159.194.240.232 https://macmagia.ru/
```

Сертификат на origin — wildcard (`macmagia.ru` + `*.macmagia.ru`), так что HTTPS
после отключения проксирования работает без правок.

**Важно про мониторинг:** внешняя проверка доступности такую поломку не видит —
через Cloudflare сайт отдаёт 200, и алерт не приходит. Проверять нужно с российской
точки.

## Сайт не открывается ЧЕРЕЗ VPN (зеркальный случай)

Симптом обратный предыдущему: без туннеля сайт открывается, с туннелем — виснет.
Вместе с ним встают и другие российские сервисы (Wildberries, кабинет продавца).

Как отличить от поломки сервера:

```bash
nc -z -v -w 5 159.194.240.232 443        # порт открыт — сервер жив
curl -sv --max-time 10 https://macmagia.ru/ 2>&1 | grep -E "Connected|Client hello"
```

Если TCP подключается, `Client hello` уходит, а ответа нет — рвётся маршрут
VPN-провайдера до России, сервер ни при чём. Подтверждение: мониторинг в GitHub
Actions в это же время получает 200, и SSH на 22 порт виснет так же, как 443.

Лечение на стороне пользователя, не на сервере: сменить страну VPN либо включить
в клиенте обход для российских адресов (`geoip:ru → direct`). Переезд на другой
хостинг не поможет — при сервере в России маршрут тот же.

Проверено 8 сентября 2026: смена региона VPN вернула доступ немедленно.

## Чек-лист "сайт не открывается"

### 1. Проверить, что сервер запущен
cp.beget.com → Облако → Виртуальные серверы → «Flawless Vasiliy». Статус должен быть «Запущен». Если остановлен — запустить и подождать ~60 сек. Там же проверить баланс: при нулевом балансе Beget останавливает сервер.

### 2. Сравнить IP с DNS
- В панели Beget: «Публичный IPv4» в карточке сервера
- На своей машине: `dig +short macmagia.ru A @1.1.1.1`
- Если разные — Cloudflare → DNS → поправить A-записи `macmagia.ru`, `www`, `lk` (DNS only).

### 3. Проверить снаружи
```bash
curl -sI https://macmagia.ru/
# Если виснет на TLS — это либо DNS не догнал, либо файрвол режет 80/443 (см. п. 6).
# С включённым VPN проверка с ноутбука ничего не доказывает — смотреть check-host.net или мониторинг в Actions.
```

### 4. SSH и PM2
```bash
ssh -i ~/.ssh/macmagia_admin ubuntu@159.194.240.232
pm2 list                        # должно быть 8 online
# если пусто или процессы errored:
pm2 resurrect                   # восстановит из dump.pm2
sudo ss -ltnp | grep -E ':3000|:3022|:3100|:3110|:3120|:3130|:3142|:3200'   # должно быть 8 LISTEN
sudo systemctl status postgresql   # база ЛК
```

PM2 настроен на autostart через `pm2-ubuntu.service` (systemd), поэтому при ребуте ВМ всё должно подняться само. Если нет — `pm2 startup systemd -u ubuntu --hp /home/ubuntu` и потом `pm2 save`.

### 5. nginx
```bash
sudo systemctl status nginx
sudo nginx -t
sudo tail -n 50 /var/log/nginx/error.log
```

### 6. Файрвол
На сервере `ufw`: должны быть разрешены 22, 80, 443.
```bash
sudo ufw status
sudo ufw allow 80/tcp && sudo ufw allow 443/tcp   # если пропали
```
Если доступа по SSH нет совсем — терминал VNC в карточке сервера в панели Beget.

## История инцидентов

- **2026-04-28** — после перевода Yandex Cloud аккаунта с триала на платный ВМ остановилась. После старта: (1) PM2 не имел systemd-юнита, апы не поднялись → `pm2 resurrect` + `pm2 startup systemd`; (2) публичный IP сменился с `103.76.55.254` на `103.76.52.35`, обновили A-запись; (3) SG не имела правил для 80/443, добавили.
- **2026-05-17** — плановый апгрейд ВМ под будущий LMS / кабинет учеников. Stop → конфигурация изменена с 2 vCPU 20% / 2 GB / 20 GB на **2 vCPU 100% / 4 GB / 30 GB**, диск расширен в Yandex Cloud (раздел внутри ОС вырос автоматически через cloud-init, ручной `growpart`/`resize2fs` не понадобился). IP `111.88.154.110` — уже был статический, не сменился. PM2 поднял все 4 процесса сам, `resurrect` не понадобился.
- **2026-08-17** — сайт перестал открываться без VPN. Домен к тому моменту жил на Cloudflare с проксированием (оранжевое облако) на `macmagia.ru` и `www`; российские провайдеры такие соединения рвут. Сервер был полностью исправен: load 0.03, все процессы PM2 живы, origin отдавал 200 при запросе с `--resolve`. Показательно, что `lk.macmagia.ru` работал — он единственный стоял в DNS only. Вылечено переводом обеих записей в DNS only, DNS разошёлся за минуты. Внешний мониторинг молчал: через Cloudflare сайт отвечал 200.
- **2026-10-08** — отказ зоны `ru-central1-b` Yandex Cloud. ВМ `macmagia` числилась `RUNNING`, но не отвечала: TCP на 22/443 принимался, дальше тишина; serial-лог, снапшот диска и создание новых ВМ в любой зоне — `Unavailable` / `Resource allocation is restricted`. Провизор в зоне `a` и Object Storage при этом работали. Снапшотов диска не было ни одного, бэкапы БД лежали только в бакете того же Яндекса. Мониторинг: последний успех 01:02 МСК, первый провал 05:00 МСК. Решение: за ~2 часа всё поднято на Beget VPS `159.194.240.232` (порядок — «Поднять всё на чистом сервере»), база ЛК — из дампа `lms-20261007-030001`. Данные ЛК между этим дампом и падением остались на диске старой ВМ — перенести, когда Яндекс вернёт диск. Попутно: деплой лендинга падал ещё с 07.10 из-за пустого `::: cta` в статье `kollegi-spletnichayut.md`.
