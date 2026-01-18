#!/bin/bash
# =============================================================================
# 🚀 Скрипт первоначальной настройки VDS
# Запускать на VDS: curl -sSL <url> | bash
# =============================================================================

set -e

echo "🔧 Настройка VDS для Telegram Bot..."

# Переменные (измени под себя)
BOT_DIR="/opt/antispam-bot"
REPO_URL="https://github.com/YOUR_USERNAME/YOUR_REPO.git"

# 1. Обновление системы
echo "📦 Обновление системы..."
sudo apt update && sudo apt upgrade -y

# 2. Установка Docker
echo "🐳 Установка Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "⚠️  Перезайди в SSH для применения группы docker"
fi

# 3. Установка Docker Compose
echo "🐳 Установка Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo apt install -y docker-compose-plugin
    # Или standalone версия:
    # sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    # sudo chmod +x /usr/local/bin/docker-compose
fi

# 4. Установка Git
echo "📦 Установка Git..."
sudo apt install -y git

# 5. Клонирование репозитория
echo "📥 Клонирование репозитория..."
if [ ! -d "$BOT_DIR" ]; then
    sudo mkdir -p $BOT_DIR
    sudo chown $USER:$USER $BOT_DIR
    git clone $REPO_URL $BOT_DIR
fi

cd $BOT_DIR

# 6. Создание .env файла
echo "⚙️  Настройка окружения..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️  Отредактируй .env файл: nano $BOT_DIR/.env"
fi

# 7. Создание директории для данных
echo "📁 Подготовка директории данных..."
mkdir -p data
chmod 777 data
touch data/bot.db data/admins.txt
chmod 666 data/bot.db data/admins.txt

echo ""
echo "✅ Настройка завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Отредактируй .env:     nano $BOT_DIR/.env"
echo "2. Запусти бота:          cd $BOT_DIR && docker-compose up -d"
echo "3. Проверь логи:          docker-compose logs -f"
echo ""
echo "🔑 Для автодеплоя добавь SSH-ключ GitHub Actions:"
echo "   cat ~/.ssh/id_rsa.pub"
