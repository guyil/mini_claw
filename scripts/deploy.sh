#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/mini_claw"
REPO_URL="https://github.com/guyil/mini_claw.git"
BRANCH="main"
COMPOSE_FILE="docker-compose.prod.yml"

echo "=== Mini Claw Deploy ==="

if [ ! -d "$APP_DIR" ]; then
  echo "[1/4] Cloning repo..."
  git clone -b "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  echo "[1/4] Pulling latest code..."
  cd "$APP_DIR"
  git fetch origin "$BRANCH"
  git reset --hard "origin/$BRANCH"
fi

cd "$APP_DIR"

if [ ! -f .env ]; then
  echo "[!] .env not found — copying from .env.example"
  cp .env.example .env
  echo "[!] Please edit $APP_DIR/.env with production values, then re-run."
  exit 1
fi

echo "[2/4] Building Docker images..."
docker compose -f "$COMPOSE_FILE" build --no-cache

echo "[3/4] Starting services..."
docker compose -f "$COMPOSE_FILE" up -d

echo "[4/4] Waiting for health check..."
sleep 5
for i in {1..12}; do
  if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
    echo "Backend healthy!"
    break
  fi
  echo "  Waiting... ($i)"
  sleep 5
done

echo ""
echo "=== Deploy complete ==="
echo "  Backend:  http://$(hostname -I | awk '{print $1}'):8001"
echo "  Frontend: http://$(hostname -I | awk '{print $1}'):3002"
docker compose -f "$COMPOSE_FILE" ps
