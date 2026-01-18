#!/bin/bash
# =============================================================================
# 🚀 Скрипт ручного деплоя (запускать на VDS)
# =============================================================================

set -e

BOT_DIR="/opt/antispam-bot"
cd $BOT_DIR

echo "📥 Pulling latest changes..."
git pull origin main

echo "📁 Preparing data directory..."
mkdir -p data
chmod 777 data
touch data/bot.db data/admins.txt
chmod 666 data/bot.db data/admins.txt

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
