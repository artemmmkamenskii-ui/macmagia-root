#!/usr/bin/env bash
# One-time server setup for macmagia.ru root landing.
# Run this ONCE on the server as a user with sudo:
#   bash setup-server.sh <deploy_user>
# Example:
#   bash setup-server.sh deploy
#
# What it does:
#   1) creates /var/www/macmagia-root/ and gives it to <deploy_user>
#      (so GitHub Actions can rsync there without sudo)
#   2) prints the nginx snippet you need to paste into your macmagia.ru server block
#
# After running this script:
#   - paste the printed nginx snippet into your existing macmagia.ru site config
#     (usually /etc/nginx/sites-available/macmagia.ru or similar),
#   - remove/comment out any existing `return 301 /cards/;` (or 308) at root level,
#   - run: sudo nginx -t && sudo systemctl reload nginx
set -euo pipefail

DEPLOY_USER="${1:-}"
if [ -z "$DEPLOY_USER" ]; then
  echo "usage: bash setup-server.sh <deploy_user>" >&2
  exit 1
fi

WEBROOT=/var/www/macmagia-root

echo "==> creating $WEBROOT owned by $DEPLOY_USER"
sudo mkdir -p "$WEBROOT"
sudo chown -R "$DEPLOY_USER":"$DEPLOY_USER" "$WEBROOT"
sudo chmod 755 "$WEBROOT"

echo "==> placing holder index.html"
if [ ! -f "$WEBROOT/index.html" ]; then
  sudo -u "$DEPLOY_USER" tee "$WEBROOT/index.html" >/dev/null <<'HTML'
<!doctype html><meta charset="utf-8"><title>МакМагия</title>
<p>macmagia-root: deploy not ran yet.</p>
HTML
fi

cat <<'NGINX'

===============================================================
Next: paste this into your nginx server block for macmagia.ru
(inside the server { ... } that handles this domain on 443/80)
===============================================================

    # --- root static landing ---
    root /var/www/macmagia-root;
    index index.html;

    location = / {
        try_files /index.html =404;
    }

    location = /index.html { }
    location = /styles.css { expires 7d; access_log off; }
    location = /script.js  { expires 7d; access_log off; }
    location = /favicon.ico { log_not_found off; access_log off; }
    location = /robots.txt  { log_not_found off; access_log off; }

    # --- existing app proxies (leave as is) ---
    # location /cards/      { proxy_pass http://127.0.0.1:3000; ... }
    # location /mac/        { proxy_pass http://127.0.0.1:3001; ... }
    # location /artterapy/  { proxy_pass http://127.0.0.1:3002; ... }
    # location /ai/         { proxy_pass http://127.0.0.1:3003; ... }

    # IMPORTANT: remove/comment out any existing root-level redirect, e.g.
    #   return 301 /cards/;
    #   return 308 /cards/;
    # otherwise macmagia.ru/ will keep redirecting instead of serving the landing.

===============================================================
Then: sudo nginx -t && sudo systemctl reload nginx
===============================================================
NGINX
