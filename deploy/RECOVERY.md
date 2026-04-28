# macmagia.ru — recovery runbook

Если `https://macmagia.ru/` (и/или `/ai`, `/artterapy`, `/mac`, `/cards/`) не открывается.

## Топология

- **VM:** `compute-vm-2-2-20-ssd-1776770416334` в Yandex Cloud (зона `ru-central1-b`, сеть `default`)
- **Публичный IP:** динамический — после каждого `Stop`/`Start` может меняться. Текущий — смотреть в консоли (Compute Cloud → ВМ → "Публичный IPv4-адрес")
- **DNS:** A-запись `macmagia.ru` (и `www`) должна указывать на актуальный публичный IP
- **SSH:** `ssh -i ~/.ssh/macmagia_deploy ubuntu@<IP>`
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
