#!/usr/bin/env bash
set -e

SERVER_USER="bot"
SERVER_IP="176.96.243.118"
SERVER_DIR="/home/bot/huquqplusbot"
ZIP_NAME="huquqplus_update_prod_2026_10_09.zip"

echo "========================================="
echo "📦 1. Yangilanish arxivi tayyorlanmoqda ($ZIP_NAME)..."
echo "========================================="
rm -f "$ZIP_NAME"
zip -r "$ZIP_NAME" . -x "*.git*" "*__pycache__*" "*.pytest_cache*" "*venv*" "*.idea*" "*.vscode*" "*.zip" "data/*" ".env*" "tests/*" "reports/*" "scripts/*"

echo "========================================="
echo "🚀 2. Serverga yuklanmoqda ($SERVER_USER@$SERVER_IP)..."
echo "========================================="
scp "$ZIP_NAME" "$SERVER_USER@$SERVER_IP:$SERVER_DIR/"

echo "========================================="
echo "✅ Fayl muvaffaqiyatli serverga yuklandi!"
echo ""
echo "Endi serverda yangilanishni ishga tushirish uchun:"
echo "ssh $SERVER_USER@$SERVER_IP"
echo "cd $SERVER_DIR && ./deploy.sh"
echo "========================================="
