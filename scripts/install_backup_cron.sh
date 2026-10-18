#!/usr/bin/env bash
# backup_db.sh ni har kuni 03:30 da ishga tushiradigan cron yozuvini qo'shadi (takror qo'shmaydi).
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
LINE="30 3 * * * cd $DIR && ./scripts/backup_db.sh >> $HOME/huquqplus_backups/backup.log 2>&1"
mkdir -p "$HOME/huquqplus_backups"
EXISTING="$(crontab -l 2>/dev/null | grep -v 'scripts/backup_db.sh' || true)"
printf '%s\n%s\n' "$EXISTING" "$LINE" | sed '/^$/d' | crontab -
echo "Cron qo'shildi: $LINE"
