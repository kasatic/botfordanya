#!/bin/bash
# =============================================================================
# Docker entrypoint - проверка прав перед запуском
# =============================================================================

set -e

# Проверяем что директория data существует и доступна для записи
if [ ! -w "/app/data" ]; then
    echo "❌ Error: /app/data is not writable"
    echo "Fix: chmod 777 /path/to/data on host"
    exit 1
fi

# Создаём файлы если их нет
touch /app/data/bot.db 2>/dev/null || true
touch /app/data/admins.txt 2>/dev/null || true

echo "✅ Data directory is ready"

# Запускаем бота
exec python -OO main.py
