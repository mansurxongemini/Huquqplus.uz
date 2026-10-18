#! /usr/bin/env sh
set -e

echo "Running database migrations with Alembic..."
alembic upgrade head
echo "Migrations completed successfully."

echo "Seeding benefits data if table is empty..."
python -m src.database.seed_benefits || true
