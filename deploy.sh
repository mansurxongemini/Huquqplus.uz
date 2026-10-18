#!/usr/bin/env bash
set -e

echo "========================================="
echo "🚀 HuquqPlus yangilanishi o'rnatilmoqda..."
echo "========================================="

# 1. Eski __pycache__ larni tozalash
sudo find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# 2. Arxiv mavjud bo'lsa ochish
LATEST_ZIP=$(ls -t huquqplus_update_*.zip 2>/dev/null | head -n 1 || true)
if [ -n "$LATEST_ZIP" ] && [ -f "$LATEST_ZIP" ]; then
    echo "📦 Yangi fayllar arxivdan ($LATEST_ZIP) ochilmoqda..."
    unzip -o "$LATEST_ZIP" -x "*__pycache__*" || true
elif [ -f "huquqplus_update.zip" ]; then
    echo "📦 Yangi fayllar arxivdan (huquqplus_update.zip) ochilmoqda..."
    unzip -o huquqplus_update.zip -x "*__pycache__*" || true
fi

# 3. Ma'lumotlar bazasi migratsiyasi
echo "🗄️ Baza migratsiyalari tekshirilmoqda..."
sudo docker compose -f docker-compose.prod.yaml run --rm app alembic upgrade head
sudo docker compose -f docker-compose.prod.yaml run --rm app python -m src.database.seed_benefits || true

# 4. Faqat bot va workerni yangilab qayta ishga tushirish (MariaDB va Redis ga tegilmaydi)
echo "🔄 Bot va Celery Worker qayta qurilmoqda..."
# --force-recreate: .env o'zgarganda konteyner yangi qiymatlarni o'qishi uchun (restart buni qilmaydi)
sudo docker compose -f docker-compose.prod.yaml up -d --build --force-recreate app celery_worker

echo "========================================="
echo "✅ HuquqPlus muvaffaqiyatli yangilandi!"
echo "========================================="
sudo docker compose -f docker-compose.prod.yaml ps
