#!/bin/bash
set -euo pipefail

echo "=== Elevare Production Deploy ==="

cd /home/deploy/elevare

echo "→ Pulling latest code..."
git pull

echo "->  Fixinf permisiions..."
sudo chown -R deploy:deploy /home/deploy/.docker


echo "→ Rebuilding containers..."
docker compose -f docker-compose.prod.yml up -d --build

echo "→ Running migrations..."
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head

echo "→ Waiting for API to be ready..."
sleep 5

echo "→ Health check..."
curl -f http://127.0.0.1:8080/health || (echo "❌ Health check failed" && exit 1)

echo "✅ Deploy complete"
docker compose -f docker-compose.prod.yml ps