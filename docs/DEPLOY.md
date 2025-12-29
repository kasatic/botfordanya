# 🚀 Автодеплой на VDS

## Как это работает

```
Push в master → GitHub Actions → SSH на VDS → git pull → docker-compose up
```

---

## 📋 Настройка (один раз)

### Шаг 1: Настрой VDS

Подключись к серверу:
```bash
ssh root@185.232.205.172
```

Выполни команды:
```bash
# 1. Установи Docker
curl -fsSL https://get.docker.com | sh

# 2. Установи docker-compose
apt install -y docker-compose

# 3. Установи git
apt install -y git

# 4. Клонируй репозиторий
mkdir -p /opt/antispam-bot
cd /opt/antispam-bot
git clone https://github.com/ТВОЙ_ЮЗЕРНЕЙМ/ТВОЙ_РЕПО.git .

# 5. Создай .env файл
cp .env.example .env
nano .env   # Добавь BOT_TOKEN=твой_токен

# 6. Первый запуск
docker-compose up -d

# 7. Проверь что работает
docker-compose logs -f
```

---

### Шаг 2: Добавь секреты в GitHub

1. Открой репозиторий на GitHub
2. Перейди: **Settings** → **Secrets and variables** → **Actions**
3. Нажми **New repository secret**
4. Добавь 3 секрета:

| Name | Value |
|------|-------|
| `VDS_HOST` | `185.232.205.172` |
| `VDS_USER` | `root` |
| `VDS_PASSWORD` | `твой_пароль` |

---

### Шаг 3: Готово!

Теперь при каждом пуше в `master`:
1. GitHub запустит workflow
2. Подключится к VDS по SSH
3. Выполнит `git pull` и `docker-compose up`

---

## 🔧 Полезные команды на VDS

```bash
# Статус бота
docker-compose ps

# Логи
docker-compose logs -f

# Перезапуск
docker-compose restart

# Остановка
docker-compose down

# Пересборка вручную
docker-compose up -d --build
```

---

## 🐛 Если что-то не работает

### Проверь логи GitHub Actions
Repository → Actions → Последний workflow → Смотри логи

### Проверь логи на VDS
```bash
cd /opt/antispam-bot
docker-compose logs --tail=50
```

### Проверь .env файл
```bash
cat /opt/antispam-bot/.env
```
