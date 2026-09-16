#! /usr/bin/env sh
set -e

echo "Running database migrations with Alembic..."
alembic upgrade head
echo "Migrations completed successfully."
