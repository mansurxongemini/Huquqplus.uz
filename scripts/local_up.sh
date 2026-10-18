#!/usr/bin/env bash
# Lokal ishga tushirish: .env o'zgargan bo'lsa ham konteynerlar yangi qiymatlar bilan qayta yaratiladi.
# `podman restart` .env ni qayta o'qimaydi — shuning uchun doim shu skriptdan foydalaning.
set -e
cd "$(dirname "$0")/.."
COMPOSE="podman compose -f docker-compose.yaml -f docker-compose.local-ai.yaml"
$COMPOSE up -d mariadb redis
$COMPOSE up -d --force-recreate app celery_worker
sleep 5
$COMPOSE ps
