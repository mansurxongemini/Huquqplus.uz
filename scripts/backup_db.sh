#!/usr/bin/env bash
# MariaDB kunlik zaxira nusxasi: shifrlangan (AES-256), oxirgi 7 kun saqlanadi.
#
#   ./scripts/backup_db.sh                      # bir martalik
#   ./scripts/install_backup_cron.sh            # har kuni 03:30 da avtomatik
#
# Tiklash:
#   openssl enc -d -aes-256-cbc -pbkdf2 -pass file:$HOME/.config/huquqplus/backup.key \
#       -in huquqplus_YYYYmmdd_HHMM.sql.gz.enc | gunzip | <compose> exec -T mariadb mariadb -u root -p"$MYSQL_ROOT_PASSWORD" "$DB_NAME"
set -euo pipefail
cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-$HOME/huquqplus_backups}"
KEEP_DAYS="${KEEP_DAYS:-7}"
KEY_FILE="${KEY_FILE:-$HOME/.config/huquqplus/backup.key}"

if command -v docker >/dev/null 2>&1 && [ -f docker-compose.prod.yaml ] && docker compose -f docker-compose.prod.yaml ps -q mariadb >/dev/null 2>&1 && [ -n "$(docker compose -f docker-compose.prod.yaml ps -q mariadb 2>/dev/null)" ]; then
    COMPOSE="docker compose -f docker-compose.prod.yaml"
else
    COMPOSE="podman compose -f docker-compose.yaml"
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

mkdir -p "$BACKUP_DIR" "$(dirname "$KEY_FILE")"
chmod 700 "$BACKUP_DIR"
if [ ! -f "$KEY_FILE" ]; then
    openssl rand -base64 48 > "$KEY_FILE"
    chmod 600 "$KEY_FILE"
    echo "Yangi shifrlash kaliti yaratildi: $KEY_FILE (uni xavfsiz joyda ham saqlang — kalitsiz nusxani tiklab bo'lmaydi)"
fi

OUT="$BACKUP_DIR/huquqplus_$(date +%Y%m%d_%H%M).sql.gz.enc"
$COMPOSE exec -T mariadb mariadb-dump -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines "$DB_NAME" \
    | gzip -9 \
    | openssl enc -aes-256-cbc -pbkdf2 -salt -pass "file:$KEY_FILE" -out "$OUT"
chmod 600 "$OUT"

find "$BACKUP_DIR" -name 'huquqplus_*.sql.gz.enc' -mtime +"$KEEP_DAYS" -delete
echo "Zaxira: $OUT ($(du -h "$OUT" | cut -f1))"
