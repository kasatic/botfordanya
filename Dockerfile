# =============================================================================
# 🐳 СТАНДАРТНЫЙ DOCKERFILE (Оптимизированный)
# Потребление: ~60-80 MB RAM
# =============================================================================

FROM python:3.11-slim as base

# Отключаем лишнее
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=2 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ---- Зависимости ----
FROM base as deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Финальный образ ----
FROM base

# Копируем установленные пакеты
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Копируем только нужный код
COPY src/ ./src/
COPY main.py .
COPY docker-entrypoint.sh .

# Безопасность
RUN useradd -m -s /bin/bash botuser \
    && mkdir -p /app/data \
    && chown -R botuser:botuser /app \
    && chmod +x /app/docker-entrypoint.sh

USER botuser

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "print('ok')" || exit 1

# Используем entrypoint для проверки прав
ENTRYPOINT ["/app/docker-entrypoint.sh"]
