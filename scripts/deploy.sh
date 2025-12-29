#!/bin/bash
# =============================================================================
# 🚀 Скрипт ручного деплоя (запускать на VDS)
# =============================================================================

set -e

BOT_DIR="/opt/antispam-bot"
cd $BOT_DIR

echo "📥 Pulling latest changes..."
git pull origin main

echo "🐳 Rebuilding container..."
docker-compose down
docker-compose build --no-cache
docker-compose up -d

echo "🧹 Cleaning up..."
docker image prune -f

echo ""
echo "✅ Deploy complete!"
echo ""
docker-compose ps
echo ""
echo "📋 Logs: docker-compose logs -f"
