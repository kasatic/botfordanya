import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest

# ═══════════════════════════════════════════════════════════════
# 🔧 НАСТРОЙКИ БОТА-БЫДЛАНА
# ═══════════════════════════════════════════════════════════════

# Настройки антиспама
SPAM_LIMIT = 3              # Максимум стикеров/GIF за период
TIME_WINDOW_MINUTES = 1     # Период отслеживания (в минутах)
WARNING_THRESHOLD = 2       # С какого количества предупреждать

# Прогрессивные баны (в минутах)
BAN_DURATION = {
    1: 10,   # Первое нарушение - 10 минут
    2: 30,   # Второе нарушение - 30 минут
    3: 60,   # Третье нарушение - 1 час
    4: 180,  # Четвертое нарушение - 3 часа
}
DEFAULT_BAN = 360  # По умолчанию (5+ нарушений) - 6 часов

# 💀 ЖЁСТКИЕ СООБЩЕНИЯ ПРИ БАНЕ (С МАТОМ!)
BAN_MESSAGES = {
    1: "🤡 ЭЙ ЧМОНЯ! Хватит спамить! Первый бан - 10 минут посиди подумай!",
    2: "😤 ОПЯТЬ ТЫ, ДЕГЕНЕРАТ?! 30 минут без стикеров, научись себя вести!",
    3: "🔥 ДА ТЫ ЧЁ ЕБОБО?! ЧАС В МЬЮТ, МОЖЕТ МОЗГИ ВПРАВЯТСЯ!",
    4: "💀 МУДИЛА, ТЫ НЕИСПРАВИМ! 3 ЧАСА ПОМОЛЧИ, ЗАЕБАЛ УЖЕ!",
}
DEFAULT_MESSAGE = "⛔ ВСЁ, ПИЗДЕЦ! ДОЛГИЙ БАН ДЛЯ УПОРОТОГО!"

# 💬 ПРЕДУПРЕЖДЕНИЯ (ЖЁСТКИЕ)
WARNING_MESSAGES = {
    2: "⚠️ ЭЙ, {name}! УЖЕ {count} СТИКЕРА! ЕЩЁ ОДИН - ПОЛЕТИШЬ В БАН НА {ban_time} МИН!",
}

# Настройки базы данных
DB_NAME = 'stickers.db'
TOKEN_FILE = 'token.txt'
ADMIN_FILE = 'admin.txt'

# ═══════════════════════════════════════════════════════════════

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# 👑 СИСТЕМА АДМИНОВ БОТА (С ПОДДЕРЖКОЙ USERNAME)
# ═══════════════════════════════════════════════════════════════

def get_user_id_by_username(username: str):
    """Ищет user_id по username в кэше"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id FROM usernames WHERE username=? COLLATE NOCASE", (username,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Get user_id by username error: {e}")
        return None

def read_bot_admins():
    """Читает список админов бота из файла admin.txt
    
    Поддерживает как username, так и числовые ID:
    @username  # Будет искать в кэше
    123456789  # Числовой ID
    """
    try:
        with open(ADMIN_FILE, 'r', encoding='utf-8') as f:
            admins = []
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Пропускаем пустые строки и комментарии
                if not line or line.startswith('#'):
                    continue
                
                # Извлекаем ID или username (до комментария, если есть)
                try:
                    identifier = line.split('#')[0].strip()
                    
                    # Если это @username
                    if identifier.startswith('@'):
                        username = identifier[1:]  # Убираем @
                        user_id = get_user_id_by_username(username)
                        
                        if user_id:
                            admins.append(user_id)
                            logger.info(f"  ✅ Админ @{username} → ID {user_id}")
                        else:
                            logger.warning(f"⚠️ @{username} (строка {line_num}) не найден в кэше!")
                            logger.warning(f"   💡 Попросите этого пользователя написать боту /start")
                    else:
                        # Это числовой ID
                        user_id = int(identifier)
                        admins.append(user_id)
                        logger.info(f"  ✅ Админ ID {user_id}")
                        
                except ValueError:
                    logger.warning(f"⚠️ Неверный формат в {ADMIN_FILE} строка {line_num}: {line}")
            
            logger.info(f"✅ Загружено {len(admins)} админ(ов) бота из {ADMIN_FILE}")
            return admins
            
    except FileNotFoundError:
        logger.warning(f"⚠️ {ADMIN_FILE} не найден, создаю пример...")
        try:
            with open(ADMIN_FILE, 'w', encoding='utf-8') as f:
                f.write("# Список админов бота\n")
                f.write("# Можно использовать username или числовой ID\n\n")
                f.write("# Вариант 1: Username (пользователь должен написать боту /start)\n")
                f.write("# @username  # Комментарий\n\n")
                f.write("# Вариант 2: Числовой ID (всегда работает)\n")
                f.write("# 123456789  # Комментарий\n\n")
                f.write("# Узнать свой ID: напишите боту /whoami\n\n")
            logger.info(f"✅ Создан файл-пример {ADMIN_FILE}")
            logger.info(f"📝 Добавьте туда админов!")
        except Exception as e:
            logger.error(f"❌ Ошибка создания {ADMIN_FILE}: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Ошибка чтения {ADMIN_FILE}: {e}")
        return []

# Загружаем админов при старте
BOT_ADMINS = read_bot_admins()

def is_bot_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь админом бота"""
    is_admin = user_id in BOT_ADMINS
    if is_admin:
        logger.info(f"👑 User {user_id} is BOT ADMIN")
    return is_admin

def reload_bot_admins():
    """Перезагружает список админов из файла"""
    global BOT_ADMINS
    BOT_ADMINS = read_bot_admins()
    return BOT_ADMINS

def read_token():
    """Читает токен бота из файла token.txt"""
    try:
        with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
            token = f.read().strip()
            if not token:
                raise ValueError("Файл token.txt пустой!")
            logger.info("✅ Токен успешно загружен из файла")
            return token
    except FileNotFoundError:
        logger.error(f"❌ Файл {TOKEN_FILE} не найден!")
        logger.error(f"Создайте файл {TOKEN_FILE} и поместите в него токен от @BotFather")
        exit(1)
    except Exception as e:
        logger.error(f"❌ Ошибка чтения токена: {e}")
        exit(1)

def init_db():
    """Инициализация базы данных с автоматической миграцией"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        # Таблица для отслеживания медиа-спама (стикеры + GIF)
        c.execute('''CREATE TABLE IF NOT EXISTS media_spam
                     (user_id INTEGER, timestamp TEXT, media_type TEXT)''')

        # Таблица для отслеживания нарушений
        c.execute('''CREATE TABLE IF NOT EXISTS violations
                     (user_id INTEGER PRIMARY KEY,
                      count INTEGER DEFAULT 0,
                      last_violation TEXT,
                      banned_until TEXT)''')

        # Таблица белого списка (доверенные пользователи)
        c.execute('''CREATE TABLE IF NOT EXISTS whitelist
                     (user_id INTEGER PRIMARY KEY,
                      added_by INTEGER,
                      added_at TEXT)''')

        # Таблица для кэша username -> user_id
        c.execute('''CREATE TABLE IF NOT EXISTS usernames
                     (user_id INTEGER PRIMARY KEY,
                      username TEXT,
                      first_name TEXT,
                      last_seen TEXT)''')

        # 🔧 МИГРАЦИЯ: Проверяем наличие колонки banned_until
        c.execute("PRAGMA table_info(violations)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'banned_until' not in columns:
            logger.warning("⚠️ Обнаружена старая версия БД, выполняю миграцию...")
            try:
                # Создаём новую таблицу с правильной структурой
                c.execute('''CREATE TABLE violations_new
                             (user_id INTEGER PRIMARY KEY,
                              count INTEGER DEFAULT 0,
                              last_violation TEXT,
                              banned_until TEXT)''')
                
                # Копируем данные из старой таблицы
                c.execute('''INSERT INTO violations_new (user_id, count, last_violation)
                             SELECT user_id, count, last_violation FROM violations''')
                
                # Удаляем старую таблицу
                c.execute('DROP TABLE violations')
                
                # Переименовываем новую
                c.execute('ALTER TABLE violations_new RENAME TO violations')
                
                logger.info("✅ Миграция БД успешно выполнена!")
            except Exception as e:
                logger.error(f"❌ Ошибка миграции: {e}")
                logger.error("💡 Рекомендуется удалить файл stickers.db и перезапустить бота")

        conn.commit()
        conn.close()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")

def update_username_cache(user_id: int, username: str, first_name: str = None):
    """Обновляет локальный кэш username -> user_id"""
    if not username:
        return
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute(
            "INSERT OR REPLACE INTO usernames (user_id, username, first_name, last_seen) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name or '', now)
        )
        conn.commit()
        conn.close()
        logger.info(f"📝 Обновлен кэш: @{username} → {user_id}")
    except Exception as e:
        logger.error(f"Update username cache error: {e}")


def add_media_spam(user_id, media_type='sticker'):
    """Добавляет запись о медиа-спаме (стикер или GIF)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute("INSERT INTO media_spam (user_id, timestamp, media_type) VALUES (?, ?, ?)",
                 (user_id, now, media_type))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Add media spam error: {e}")

def get_recent_media_spam(user_id, minutes=TIME_WINDOW_MINUTES):
    """Возвращает количество медиа-сообщений (стикеры + GIF) за период"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        c.execute("SELECT COUNT(*) FROM media_spam WHERE user_id=? AND timestamp > ?", (user_id, cutoff))
        count = c.fetchone()[0]
        c.execute("DELETE FROM media_spam WHERE timestamp < ?", (cutoff,))
        conn.commit()
        conn.close()
        return count
    except Exception as e:
        logger.error(f"Get media spam error: {e}")
        return 0

def is_currently_banned(user_id):
    """Проверяет, забанен ли пользователь сейчас"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute("SELECT banned_until FROM violations WHERE user_id=?", (user_id,))
        result = c.fetchone()
        conn.close()

        if result and result[0]:
            banned_until = result[0]
            if banned_until > now:
                logger.info(f"User {user_id} is currently banned until {banned_until}")
                return True
        return False
    except Exception as e:
        logger.error(f"Check ban error: {e}")
        return False

def add_violation(user_id, ban_minutes):
    """Добавляет нарушение и возвращает количество нарушений."""
    try:
        if is_currently_banned(user_id):
            logger.info(f"User {user_id} is already banned, not adding new violation")
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("SELECT count FROM violations WHERE user_id=?", (user_id,))
            result = c.fetchone()
            conn.close()
            return result[0] if result else 0

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now = datetime.now().isoformat()
        banned_until = (datetime.now() + timedelta(minutes=ban_minutes)).isoformat()

        c.execute("SELECT count FROM violations WHERE user_id=?", (user_id,))
        result = c.fetchone()

        if result:
            new_count = result[0] + 1
            c.execute("UPDATE violations SET count=?, last_violation=?, banned_until=? WHERE user_id=?",
                     (new_count, now, banned_until, user_id))
        else:
            new_count = 1
            c.execute("INSERT INTO violations (user_id, count, last_violation, banned_until) VALUES (?, ?, ?, ?)",
                     (user_id, new_count, now, banned_until))

        conn.commit()
        conn.close()
        logger.info(f"✅ Added violation #{new_count} for user {user_id}, banned until {banned_until}")
        return new_count
    except Exception as e:
        logger.error(f"Add violation error: {e}")
        return 1

def get_violation_count(user_id):
    """Возвращает количество нарушений пользователя"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT count FROM violations WHERE user_id=?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"Get violation error: {e}")
        return 0

def remove_ban(user_id):
    """Снимает текущий бан (обнуляет banned_until)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE violations SET banned_until=NULL WHERE user_id=?", (user_id,))
        conn.commit()
        affected = c.rowcount
        conn.close()
        logger.info(f"✅ Removed ban for user {user_id}")
        return affected > 0
    except Exception as e:
        logger.error(f"Remove ban error: {e}")
        return False

def clear_violations(user_id):
    """Полностью очищает историю нарушений пользователя"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("DELETE FROM violations WHERE user_id=?", (user_id,))
        c.execute("DELETE FROM media_spam WHERE user_id=?", (user_id,))
        conn.commit()
        affected = c.rowcount
        conn.close()
        logger.info(f"✅ Cleared all violations for user {user_id}")
        return affected > 0
    except Exception as e:
        logger.error(f"Clear violations error: {e}")
        return False

def clear_all_violations():
    """Полностью очищает ВСЮ базу данных (только для админов бота)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("DELETE FROM violations")
        c.execute("DELETE FROM media_spam")
        violations_count = c.rowcount
        conn.commit()
        conn.close()
        logger.info(f"✅ Cleared ALL violations from database")
        return violations_count
    except Exception as e:
        logger.error(f"Clear all violations error: {e}")
        return 0

# ═══════════════════════════════════════════════════════════════
# 🤍 WHITELIST (ДОВЕРЕННЫЕ ПОЛЬЗОВАТЕЛИ)
# ═══════════════════════════════════════════════════════════════

def is_whitelisted(user_id):
    """Проверяет, в белом списке ли пользователь"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id FROM whitelist WHERE user_id=?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        logger.error(f"Check whitelist error: {e}")
        return False

def add_to_whitelist(user_id, admin_id):
    """Добавляет пользователя в белый список"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute("INSERT OR REPLACE INTO whitelist (user_id, added_by, added_at) VALUES (?, ?, ?)",
                 (user_id, admin_id, now))
        conn.commit()
        conn.close()
        logger.info(f"✅ Added user {user_id} to whitelist by admin {admin_id}")
        return True
    except Exception as e:
        logger.error(f"Add to whitelist error: {e}")
        return False

def remove_from_whitelist(user_id):
    """Удаляет пользователя из белого списка"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("DELETE FROM whitelist WHERE user_id=?", (user_id,))
        conn.commit()
        affected = c.rowcount
        conn.close()
        logger.info(f"✅ Removed user {user_id} from whitelist")
        return affected > 0
    except Exception as e:
        logger.error(f"Remove from whitelist error: {e}")
        return False

def get_whitelist():
    """Возвращает список всех доверенных пользователей"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id, added_at FROM whitelist")
        result = c.fetchall()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Get whitelist error: {e}")
        return []

# ═══════════════════════════════════════════════════════════════
# 📊 СТАТИСТИКА
# ═══════════════════════════════════════════════════════════════

def get_top_violators(limit=10):
    """Возвращает топ нарушителей"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id, count FROM violations ORDER BY count DESC LIMIT ?", (limit,))
        result = c.fetchall()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Get top violators error: {e}")
        return []

# ═══════════════════════════════════════════════════════════════
# 👤 РАБОТА С ПОЛЬЗОВАТЕЛЯМИ
# ═══════════════════════════════════════════════════════════════

async def get_user_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None) -> str:
    """Возвращает статус пользователя в чате"""
    if user_id is None:
        user_id = update.effective_user.id

    chat_id = update.effective_chat.id

    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status
    except Exception as e:
        logger.error(f"Get user status error: {e}")
        return "member"

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None) -> bool:
    """Проверяет, является ли пользователь администратором чата (включая владельца)"""
    status = await get_user_status(update, context, user_id)
    is_admin_user = status in ['creator', 'administrator']
    if user_id is None:
        user_id = update.effective_user.id
    logger.info(f"🛡 User {user_id} admin status: {is_admin_user} (status: {status})")
    return is_admin_user

async def get_user_info_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    """
    Извлекает информацию о пользователе из:
    - Ответа на сообщение
    - @username в аргументах
    - user_id в аргументах
    """

    message = update.effective_message
    if message is None:
        return None

    # Способ 1: Ответ на сообщение
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        return {
            'user_id': target_user.id,
            'username': target_user.username,
            'first_name': target_user.first_name,
            'mention': f"[{target_user.first_name}](tg://user?id={target_user.id})"
        }

    # Способ 2: Аргументы команды
    if context.args and len(context.args) > 0:
        arg = context.args[0]

        # Если это @username
        if arg.startswith('@'):
            username = arg[1:]

            # Сначала пробуем найти в локальном кэше username -> user_id
            try:
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("SELECT user_id, first_name FROM usernames WHERE username=? COLLATE NOCASE", (username,))
                row = c.fetchone()
                conn.close()
            except Exception as e:
                logger.error(f"Username cache lookup error for @{username}: {e}")
                row = None

            if row:
                user_id, first_name = row
                first_name = first_name or username
                return {
                    'user_id': user_id,
                    'username': username,
                    'first_name': first_name,
                    'mention': f"[{first_name}](tg://user?id={user_id})"
                }

            # Кэша нет — пытаемся получить чат по username
            try:
                chat = await context.bot.get_chat(f"@{username}")
                first_name = getattr(chat, 'first_name', None) or getattr(chat, 'title', username)

                return {
                    'user_id': chat.id,
                    'username': username,
                    'first_name': first_name,
                    'mention': f"[{first_name}](tg://user?id={chat.id})"
                }
            except Exception as e:
                logger.error(f"Failed to get user by username @{username}: {e}")
                return None

        # Если это user_id
        try:
            user_id = int(arg)
            try:
                chat_member = await context.bot.get_chat_member(
                    chat_id=update.effective_chat.id,
                    user_id=user_id
                )
                return {
                    'user_id': chat_member.user.id,
                    'username': chat_member.user.username,
                    'first_name': chat_member.user.first_name,
                    'mention': f"[{chat_member.user.first_name}](tg://user?id={chat_member.user.id})"
                }
            except Exception as e:
                logger.error(f"Failed to get user by ID {user_id}: {e}")
                return None
        except ValueError:
            pass

    return None

async def restore_user_permissions(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    """Восстанавливает разрешения пользователя"""
    try:
        chat = await context.bot.get_chat(chat_id)
        base_perms = chat.permissions or ChatPermissions()

        permissions = ChatPermissions(
            can_send_messages=True if base_perms.can_send_messages is not False else False,
            can_send_audios=True if getattr(base_perms, 'can_send_audios', None) is not False else False,
            can_send_documents=True if getattr(base_perms, 'can_send_documents', None) is not False else False,
            can_send_photos=True if getattr(base_perms, 'can_send_photos', None) is not False else False,
            can_send_videos=True if getattr(base_perms, 'can_send_videos', None) is not False else False,
            can_send_video_notes=True if getattr(base_perms, 'can_send_video_notes', None) is not False else False,
            can_send_voice_notes=True if getattr(base_perms, 'can_send_voice_notes', None) is not False else False,
            can_send_polls=True if getattr(base_perms, 'can_send_polls', None) is not False else False,
            can_send_other_messages=True if getattr(base_perms, 'can_send_other_messages', None) is not False else False,
            can_add_web_page_previews=True if getattr(base_perms, 'can_add_web_page_previews', None) is not False else False,
        )

        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=permissions
        )
        logger.info(f"✅ Restored permissions for user {user_id}")
        return True
    except Exception as e:
        if "administrator of the chat" in str(e):
            logger.info(f"ℹ️ User {user_id} is admin, permissions managed by Telegram/owner, skipping restore")
            return True

        logger.error(f"❌ Failed to restore permissions: {e}")
        return False

# ═══════════════════════════════════════════════════════════════
# 🎮 КОМАНДЫ БОТА
# ═══════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - сохраняет username в кэш"""
    user = update.effective_user
    user_id = user.id
    
    # Сохраняем username в кэш
    if user.username:
        update_username_cache(user_id, user.username, user.first_name)
        
        # Перезагружаем админов, если это был новый username
        old_count = len(BOT_ADMINS)
        reload_bot_admins()
        new_count = len(BOT_ADMINS)
        
        # Если стал админом - уведомляем
        if user_id in BOT_ADMINS and old_count < new_count:
            await update.message.reply_text(
                "👑 *ДОБРО ПОЖАЛОВАТЬ, АДМИН БОТА!*\n\n"
                "Ваш username успешно распознан!\n"
                "Теперь вам доступны все команды управления.",
                parse_mode='Markdown'
            )
            return

    text = (
        "👊 *ЗДАРОВА, БРАТАН!*\n\n"
        "Я тут за порядком слежу, чтоб всякие клоуны стикерами не спамили!\n\n"
        "⚙️ *ПРАВИЛА ПРОСТЫЕ:*\n"
        f"• Больше *{SPAM_LIMIT} стикеров/гифок* за {TIME_WINDOW_MINUTES} минуту - *ПОЛЕТИШЬ В БАН*\n"
        f"• Первый косяк - {BAN_DURATION[1]} минут мьюта\n"
        f"• Второй - {BAN_DURATION[2]} минут\n"
        f"• Дальше хуже, вплоть до {DEFAULT_BAN} минут!\n\n"
        "📱 *КОМАНДЫ ДЛЯ ВСЕХ:*\n"
        "• /whoami - узнать свой ID и username\n"
        "• /stats - твоя статистика (сколько накосячил)\n"
        "• /top - зал позора (топ мудаков-спамеров)\n"
        "• /help - все команды\n"
    )

    # Показываем команды только для админов бота
    if is_bot_admin(user_id):
        text += (
            "\n👑 *ДЛЯ АДМИНОВ БОТА:*\n"
            "• /unban - разбанить чела\n"
            "• /pardon - простить все косяки\n"
            "• /check - проверить статус\n"
            "• /trust - добавить в белый список (не банится)\n"
            "• /untrust - убрать из белого списка\n"
            "• /whitelist - показать всех доверенных\n"
            "• /reset_all CONFIRM - обнулить всю базу\n"
            "• /bot_admins - список админов бота\n"
            "• /reload_admins - перезагрузить admin.txt\n"
        )

    text += "\n*ВЕДИ СЕБЯ НОРМАЛЬНО И ВСЁ БУДЕТ ОК!* 👊"

    await update.message.reply_text(text, parse_mode='Markdown')

async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает информацию о текущем пользователе"""
    user = update.effective_user
    
    # Сохраняем/обновляем в кэше
    if user.username:
        update_username_cache(user.id, user.username, user.first_name)
    
    text = "👤 *ТВОЯ ИНФОРМАЦИЯ:*\n\n"
    text += f"🆔 User ID: `{user.id}`\n"
    
    if user.username:
        text += f"📧 Username: @{user.username}\n"
    else:
        text += f"📧 Username: _не установлен_\n"
    
    text += f"👤 Имя: {user.first_name}\n"
    
    if user.last_name:
        text += f"   Фамилия: {user.last_name}\n"
    
    # Проверяем админские права
    if is_bot_admin(user.id):
        text += "\n👑 *ВЫ АДМИН БОТА!*\n"
    
    text += "\n💡 *Для admin.txt используйте:*\n"
    if user.username:
        text += f"`@{user.username}`  # Ваш username\n"
    text += f"`{user.id}`  # Ваш ID"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подробная справка по командам"""
    user_id = update.effective_user.id

    text = (
        "📚 *ИНСТРУКЦИЯ ДЛЯ ДАУНОВ*\n\n"
        "👤 *КОМАНДЫ ДЛЯ ВСЕХ:*\n\n"

        "👁 /whoami\n"
        "Показывает ваш ID и username для admin.txt\n\n"

        "📊 /stats\n"
        "Показывает твою статистику нарушений. Сколько раз накосячил и какой следующий бан.\n"
        "_Пример:_ `/stats`\n\n"

        "🏆 /top\n"
        "Топ-10 мудаков, которые чаще всех спамят. Не попадай в этот список!\n"
        "_Пример:_ `/top`\n\n"

        "❓ /help\n"
        "Эта справка, которую ты сейчас читаешь, умник.\n\n"
    )

    if is_bot_admin(user_id):
        text += (
            "👑 *КОМАНДЫ ДЛЯ АДМИНОВ БОТА:*\n\n"

            "🔓 /unban\n"
            "Снять текущий бан с пользователя. История нарушений сохраняется.\n"
            "_Примеры:_\n"
            "`/unban` (ответ на сообщение)\n"
            "`/unban @username`\n"
            "`/unban 123456789`\n\n"

            "🎉 /pardon\n"
            "Полностью простить пользователя, стереть всю историю нарушений.\n"
            "_Примеры:_\n"
            "`/pardon` (ответ на сообщение)\n"
            "`/pardon @username`\n"
            "`/pardon 123456789`\n\n"

            "🔍 /check\n"
            "Проверить статус пользователя: сколько нарушений, забанен ли.\n"
            "_Примеры:_\n"
            "`/check` (ответ на сообщение)\n"
            "`/check @username`\n"
            "`/check 123456789`\n\n"

            "🤍 /trust\n"
            "Добавить пользователя в белый список. Он сможет спамить сколько хочет.\n"
            "_Примеры:_\n"
            "`/trust` (ответ на сообщение)\n"
            "`/trust @username`\n\n"

            "⛔ /untrust\n"
            "Убрать из белого списка. Снова будет под контролем.\n"
            "_Примеры:_\n"
            "`/untrust` (ответ на сообщение)\n"
            "`/untrust @username`\n\n"

            "📋 /whitelist\n"
            "Показать всех доверенных пользователей.\n"
            "_Пример:_ `/whitelist`\n\n"

            "💣 /reset_all CONFIRM\n"
            "УДАЛЯЕТ ВСЮ БАЗУ ДАННЫХ! Все нарушения, баны, белый список - всё нахуй!\n"
            "⚠️ *ОСТОРОЖНО! ЭТО НЕОБРАТИМО!*\n"
            "_Пример:_ `/reset_all CONFIRM`\n\n"

            "👥 /bot_admins\n"
            "Показать список всех админов бота (из admin.txt).\n"
            "_Пример:_ `/bot_admins`\n\n"

            "🔄 /reload_admins\n"
            "Перезагрузить список админов из файла admin.txt без перезапуска бота.\n"
            "_Пример:_ `/reload_admins`\n\n"
        )

    text += "Вопросы есть? Нет? Вот и заебись! 👊"

    await update.message.reply_text(text, parse_mode='Markdown')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику нарушений пользователя"""
    user_id = update.effective_user.id
    violations = get_violation_count(user_id)

    # Проверка белого списка
    if is_whitelisted(user_id):
        await update.message.reply_text(
            "😎 *ТЫ В БЕЛОМ СПИСКЕ, БРАТИШКА!*\n\n"
            "Можешь спамить сколько хочешь, тебя не тронут! 🤍",
            parse_mode='Markdown'
        )
        return

    if violations == 0:
        await update.message.reply_text(
            "✅ *КРАСАВЧИК!*\n\n"
            "У тебя нет нарушений. Так держать, братан! 👊",
            parse_mode='Markdown'
        )
    else:
        next_ban = BAN_DURATION.get(violations + 1, DEFAULT_BAN)

        # Прогресс-бар
        max_violations = 10
        progress = min(violations, max_violations)
        bar_filled = "█" * progress
        bar_empty = "░" * (max_violations - progress)
        progress_bar = f"[{bar_filled}{bar_empty}] {progress}/{max_violations}"

        if is_currently_banned(user_id):
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("SELECT banned_until FROM violations WHERE user_id=?", (user_id,))
            banned_until = c.fetchone()[0]
            conn.close()

            ban_end = datetime.fromisoformat(banned_until)
            remaining = ban_end - datetime.now()
            remaining_minutes = int(remaining.total_seconds() / 60)

            text = (
                "📊 *ТВОЯ СТАТИСТИКА, НАРУШИТЕЛЬ:*\n\n"
                f"⚠️ Косяков: *{violations}*\n"
                f"📈 Прогресс: `{progress_bar}`\n"
                f"🔒 *СЕЙЧАС В БАНЕ!* Осталось: *{remaining_minutes} мин*\n"
                f"⏭ Следующий бан: *{next_ban} мин*\n\n"
                f"Сиди тихо, жди разбана! 🤐"
            )
        else:
            text = (
                "📊 *ТВОЯ СТАТИСТИКА:*\n\n"
                f"⚠️ Нарушений: *{violations}*\n"
                f"📈 Прогресс: `{progress_bar}`\n"
                f"⏭ Следующий бан: *{next_ban} мин*\n\n"
                f"Поменьше спамь, а то хуже будет! 👊"
            )
        await update.message.reply_text(text, parse_mode='Markdown')

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает топ нарушителей"""
    top_violators = get_top_violators(10)

    if not top_violators:
        await update.message.reply_text(
            "🏆 *ЗАЛ ПОЗОРА ПУСТ!*\n\n"
            "Все ведут себя хорошо. Красавцы! 👊",
            parse_mode='Markdown'
        )
        return

    text = "🏆 *ТОП-10 МУДАКОВ-СПАМЕРОВ:*\n\n"

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    for idx, (user_id, count) in enumerate(top_violators):
        try:
            # Пытаемся получить имя пользователя
            member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            user_name = member.user.first_name
            user_mention = f"[{user_name}](tg://user?id={user_id})"
        except:
            user_mention = f"User ID: `{user_id}`"

        medal = medals[idx] if idx < len(medals) else "•"
        text += f"{medal} {user_mention} — *{count}* нарушений\n"

    text += "\n*НЕ ПОПАДАЙТЕ В ЭТОТ СПИСОК, ДЕГЕНЕРАТЫ!* 💀"

    await update.message.reply_text(text, parse_mode='Markdown')

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Снимает текущий бан с пользователя (ТОЛЬКО для админов бота)"""

    message = update.effective_message
    if message is None:
        return

    # Проверка: только админы бота
    if not is_bot_admin(update.effective_user.id):
        await message.reply_text("❌ Эта команда только для админов бота из admin.txt!")
        return

    user_info = await get_user_info_from_message(update, context)

    if user_info is None:
        await message.reply_text(
            "ℹ️ Укажи кого разбанить:\n\n"
            "• Ответь на его сообщение и напиши `/unban`\n"
            "• Или: `/unban @username`\n"
            "• Или: `/unban user_id`",
            parse_mode='Markdown'
        )
        return

    target_id = user_info['user_id']
    violations = get_violation_count(target_id)
    was_banned = is_currently_banned(target_id)

    if not was_banned and violations == 0:
        await message.reply_text(
            f"ℹ️ Пользователь {user_info['mention']} чист как слеза. Не надо его разбанивать.",
            parse_mode='Markdown'
        )
        return

    # Inline кнопки для подтверждения
    keyboard = [
        [
            InlineKeyboardButton("✅ ДА, РАЗБАНИТЬ", callback_data=f"unban_{target_id}"),
            InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.reply_text(
        f"🤔 Разбанить {user_info['mention']}?\n\n"
        f"⚠️ Нарушений: *{violations}*\n"
        f"ℹ️ История сохранится",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def pardon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полностью прощает пользователя (ТОЛЬКО для админов бота)"""

    message = update.effective_message
    if message is None:
        return

    # Проверка: только админы бота
    if not is_bot_admin(update.effective_user.id):
        await message.reply_text("❌ Только админы бота могут прощать!")
        return

    user_info = await get_user_info_from_message(update, context)

    if user_info is None:
        await message.reply_text(
            "ℹ️ Укажи кого простить:\n\n"
            "• Ответь на его сообщение и напиши `/pardon`\n"
            "• Или: `/pardon @username`\n"
            "• Или: `/pardon user_id`",
            parse_mode='Markdown'
        )
        return

    target_id = user_info['user_id']
    violations = get_violation_count(target_id)

    if violations == 0:
        await update.message.reply_text(
            f"ℹ️ У {user_info['mention']} нет косяков, прощать нечего!",
            parse_mode='Markdown'
        )
        return

    # Inline кнопки
    keyboard = [
        [
            InlineKeyboardButton("✅ ДА, ПРОСТИТЬ", callback_data=f"pardon_{target_id}"),
            InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🎉 Простить {user_info['mention']} полностью?\n\n"
        f"🧹 Удалится *{violations}* нарушений\n"
        f"⚠️ *ЭТО НЕОБРАТИМО!*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет статус пользователя (ТОЛЬКО для админов бота)"""

    # Проверка: только админы бота
    if not is_bot_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда только для админов бота!")
        return

    user_info = await get_user_info_from_message(update, context)

    if user_info is None:
        await update.message.reply_text(
            "ℹ️ Укажи кого проверить:\n\n"
            "• Ответь на его сообщение и напиши `/check`\n"
            "• Или: `/check @username`\n"
            "• Или: `/check user_id`",
            parse_mode='Markdown'
        )
        return

    target_id = user_info['user_id']
    violations = get_violation_count(target_id)
    is_banned = is_currently_banned(target_id)
    recent_spam = get_recent_media_spam(target_id)
    in_whitelist = is_whitelisted(target_id)

    status_text = f"📋 *ДОСЬЕ НА ПОДОЗРЕВАЕМОГО*\n\n"
    status_text += f"👤 {user_info['mention']}\n"

    if user_info['username']:
        status_text += f"🔖 @{user_info['username']}\n"

    status_text += f"🆔 `{target_id}`\n\n"

    if in_whitelist:
        status_text += "🤍 *В БЕЛОМ СПИСКЕ* (не банится)\n\n"

    if violations == 0:
        status_text += "✅ Нарушений нет\n"
    else:
        # Прогресс-бар
        max_violations = 10
        progress = min(violations, max_violations)
        bar_filled = "█" * progress
        bar_empty = "░" * (max_violations - progress)
        progress_bar = f"[{bar_filled}{bar_empty}] {progress}/{max_violations}"

        status_text += f"⚠️ Нарушений: *{violations}*\n"
        status_text += f"📈 `{progress_bar}`\n"

    if is_banned:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT banned_until FROM violations WHERE user_id=?", (target_id,))
        banned_until = c.fetchone()[0]
        conn.close()

        ban_end = datetime.fromisoformat(banned_until)
        remaining = ban_end - datetime.now()
        remaining_minutes = int(remaining.total_seconds() / 60)

        status_text += f"🔒 *ЗАБАНЕН!* Осталось: *{remaining_minutes} мин*\n"
    else:
        status_text += "🔓 Не забанен\n"

    if recent_spam > 0:
        status_text += f"📊 Стикеров/GIF за минуту: *{recent_spam}/{SPAM_LIMIT}*\n"

    next_ban = BAN_DURATION.get(violations + 1, DEFAULT_BAN)
    status_text += f"⏭ Следующий бан: *{next_ban} мин*"

    # Inline кнопки для быстрых действий
    keyboard = []
    if is_banned:
        keyboard.append([InlineKeyboardButton("🔓 РАЗБАНИТЬ", callback_data=f"unban_{target_id}")])
    if violations > 0:
        keyboard.append([InlineKeyboardButton("🎉 ПРОСТИТЬ", callback_data=f"pardon_{target_id}")])
    if not in_whitelist:
        keyboard.append([InlineKeyboardButton("🤍 В БЕЛЫЙ СПИСОК", callback_data=f"trust_{target_id}")])
    else:
        keyboard.append([InlineKeyboardButton("⛔ УБРАТЬ ИЗ БЕЛОГО СПИСКА", callback_data=f"untrust_{target_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    await update.message.reply_text(status_text, parse_mode='Markdown', reply_markup=reply_markup)

async def trust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет пользователя в белый список (ТОЛЬКО для админов бота)"""

    # Проверка: только админы бота
    if not is_bot_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только админы бота могут доверять!")
        return

    user_info = await get_user_info_from_message(update, context)

    if user_info is None:
        await update.message.reply_text(
            "ℹ️ Укажи кому доверяешь:\n\n"
            "• Ответь на его сообщение и напиши `/trust`\n"
            "• Или: `/trust @username`",
            parse_mode='Markdown'
        )
        return

    target_id = user_info['user_id']

    if is_whitelisted(target_id):
        await update.message.reply_text(
            f"ℹ️ {user_info['mention']} уже в белом списке!",
            parse_mode='Markdown'
        )
        return

    # Inline кнопки
    keyboard = [
        [
            InlineKeyboardButton("✅ ДА, ДОВЕРЯЮ", callback_data=f"trust_{target_id}"),
            InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🤍 Добавить {user_info['mention']} в белый список?\n\n"
        f"✅ Он сможет спамить сколько хочет\n"
        f"✅ Не будет банов и предупреждений",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def untrust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Убирает пользователя из белого списка (ТОЛЬКО для админов бота)"""

    # Проверка: только админы бота
    if not is_bot_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только админы бота могут управлять белым списком!")
        return

    user_info = await get_user_info_from_message(update, context)

    if user_info is None:
        await update.message.reply_text(
            "ℹ️ Укажи кого убрать:\n\n"
            "• Ответь на его сообщение и напиши `/untrust`\n"
            "• Или: `/untrust @username`",
            parse_mode='Markdown'
        )
        return

    target_id = user_info['user_id']

    if not is_whitelisted(target_id):
        await update.message.reply_text(
            f"ℹ️ {user_info['mention']} не в белом списке!",
            parse_mode='Markdown'
        )
        return

    # Inline кнопки
    keyboard = [
        [
            InlineKeyboardButton("✅ ДА, УБРАТЬ", callback_data=f"untrust_{target_id}"),
            InlineKeyboardButton("❌ ОТМЕНА", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"⛔ Убрать {user_info['mention']} из белого списка?\n\n"
        f"❌ Снова будет под контролем бота",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def whitelist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает белый список (ТОЛЬКО для админов бота)"""

    # Проверка: только админы бота
    if not is_bot_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только админы бота могут смотреть белый список!")
        return

    whitelist = get_whitelist()

    if not whitelist:
        await update.message.reply_text(
            "📋 *БЕЛЫЙ СПИСОК ПУСТ*\n\n"
            "Никому не доверяем! 😈",
            parse_mode='Markdown'
        )
        return

    text = "🤍 *БЕЛЫЙ СПИСОК (ДОВЕРЕННЫЕ):*\n\n"

    for idx, (user_id, added_at) in enumerate(whitelist, 1):
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            user_name = member.user.first_name
            user_mention = f"[{user_name}](tg://user?id={user_id})"
        except:
            user_mention = f"User ID: `{user_id}`"

        added_date = datetime.fromisoformat(added_at).strftime("%d.%m.%Y")
        text += f"{idx}. {user_mention} (с {added_date})\n"

    text += f"\n*Всего доверенных: {len(whitelist)}*"

    await update.message.reply_text(text, parse_mode='Markdown')

async def reset_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очищает всю базу данных (ТОЛЬКО для админов бота)"""

    # Проверка: только админы бота
    if not is_bot_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только админы бота могут сбрасывать базу!")
        return

    if not context.args or context.args[0] != "CONFIRM":
        await update.message.reply_text(
            "⚠️ *ВНИМАНИЕ, БОСС!*\n\n"
            "Эта команда *УДАЛИТ ВСЮ БАЗУ ДАННЫХ:*\n"
            "• Все нарушения\n"
            "• Все баны\n"
            "• Весь белый список\n"
            "• Всю историю спама\n\n"
            "⚠️ *ЭТО ПИЗДЕЦ КАК НЕОБРАТИМО!*\n\n"
            "Для подтверждения:\n"
            "`/reset_all CONFIRM`",
            parse_mode='Markdown'
        )
        return

    # Очищаем базу
    count = clear_all_violations()

    # Очищаем whitelist
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM whitelist")
    conn.commit()
    conn.close()

    admin_name = update.effective_user.first_name
    admin_mention = f"[{admin_name}](tg://user?id={update.effective_user.id})"

    await update.message.reply_text(
        f"💥 *ЕБАААТЬ! БАЗА ДАННЫХ УНИЧТОЖЕНА!*\n\n"
        f"👑 Админ бота: {admin_mention}\n"
        f"🗑 Удалено записей: *{count}*\n"
        f"🤍 Белый список очищен\n\n"
        f"✅ *ВСЕ НАЧИНАЮТ С ЧИСТОГО ЛИСТА!*",
        parse_mode='Markdown'
    )

    logger.warning(f"👑 BOT ADMIN {update.effective_user.id} RESET ALL DATABASE!")

async def bot_admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список админов бота (ТОЛЬКО для админов бота)"""
    
    # Проверка: только админы бота
    if not is_bot_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только админы бота могут видеть этот список!")
        return
    
    if not BOT_ADMINS:
        await update.message.reply_text(
            "📋 *АДМИНЫ БОТА:*\n\n"
            f"⚠️ Не настроены! Добавьте user_id в файл `{ADMIN_FILE}`",
            parse_mode='Markdown'
        )
        return
    
    text = "👑 *АДМИНЫ БОТА (ПОЛНЫЙ ДОСТУП):*\n\n"
    
    for idx, admin_id in enumerate(BOT_ADMINS, 1):
        try:
            # Пытаемся получить информацию о пользователе
            chat = await context.bot.get_chat(admin_id)
            name = chat.first_name or chat.username or str(admin_id)
            username = f"@{chat.username}" if chat.username else "нет username"
            text += f"{idx}. [{name}](tg://user?id={admin_id})\n"
            text += f"   ID: `{admin_id}` | {username}\n\n"
        except Exception as e:
            # Если не удалось получить инфо (бот не видел юзера)
            text += f"{idx}. ID: `{admin_id}`\n"
            text += f"   _(информация недоступна)_\n\n"
    
    text += f"*Всего админов: {len(BOT_ADMINS)}*\n\n"
    text += f"📝 Файл: `{ADMIN_FILE}`"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def reload_admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перезагружает список админов бота из файла (ТОЛЬКО для текущих админов)"""
    
    # Проверка: только админы бота
    if not is_bot_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только админы бота могут перезагружать список!")
        return
    
    global BOT_ADMINS
    old_count = len(BOT_ADMINS)
    old_admins = set(BOT_ADMINS)
    
    # Перечитываем файл
    BOT_ADMINS = read_bot_admins()
    new_count = len(BOT_ADMINS)
    new_admins = set(BOT_ADMINS)
    
    # Вычисляем изменения
    added = new_admins - old_admins
    removed = old_admins - new_admins
    
    text = "🔄 *СПИСОК АДМИНОВ ПЕРЕЗАГРУЖЕН!*\n\n"
    text += f"📊 Было: *{old_count}*\n"
    text += f"📊 Стало: *{new_count}*\n\n"
    
    if added:
        text += f"➕ Добавлено: {len(added)}\n"
        for admin_id in added:
            text += f"   • `{admin_id}`\n"
        text += "\n"
    
    if removed:
        text += f"➖ Удалено: {len(removed)}\n"
        for admin_id in removed:
            text += f"   • `{admin_id}`\n"
        text += "\n"
    
    if not added and not removed:
        text += "ℹ️ Изменений нет\n\n"
    
    text += f"✅ Готово! Файл: `{ADMIN_FILE}`"
    
    await update.message.reply_text(text, parse_mode='Markdown')
    logger.info(f"👑 Bot admin {update.effective_user.id} reloaded admin list: {old_count} -> {new_count}")

# ═══════════════════════════════════════════════════════════════
# 🎯 ОБРАБОТКА CALLBACK (INLINE КНОПКИ)
# ═══════════════════════════════════════════════════════════════

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на inline-кнопки (ТОЛЬКО для админов бота)"""
    query = update.callback_query

    # Проверка: только админы бота могут жать кнопки
    if not is_bot_admin(query.from_user.id):
        try:
            await query.answer("❌ Только админы бота из admin.txt могут жать кнопки!", show_alert=True)
        except BadRequest as e:
            # Игнорируем ошибку устаревших callback
            if "query is too old" in str(e).lower():
                logger.warning(f"Игнорирую устаревший callback query от {query.from_user.id}")
            else:
                logger.error(f"Callback error: {e}")
        return

    # Админ бота: можно обрабатывать дальше
    try:
        await query.answer()
    except BadRequest as e:
        if "query is too old" in str(e).lower():
            logger.warning(f"Устаревший callback query, пропускаю")
            return
        else:
            raise

    data = query.data

    # Отмена
    if data == "cancel":
        await query.edit_message_text("❌ Отменено!")
        return

    # Разбан
    if data.startswith("unban_"):
        target_id = int(data.split("_")[1])
        remove_ban(target_id)
        success = await restore_user_permissions(context, update.effective_chat.id, target_id)

        if success:
            violations = get_violation_count(target_id)
            try:
                member = await context.bot.get_chat_member(update.effective_chat.id, target_id)
                user_mention = f"[{member.user.first_name}](tg://user?id={target_id})"
            except:
                user_mention = f"User ID: `{target_id}`"

            admin_name = query.from_user.first_name
            admin_mention = f"[{admin_name}](tg://user?id={query.from_user.id})"

            await query.edit_message_text(
                f"✅ *РАЗБАНЕН!*\n\n"
                f"👤 {user_mention}\n"
                f"🛡 Админ бота: {admin_mention}\n"
                f"⚠️ Нарушений в истории: *{violations}*",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ Ошибка разбана!")

    # Прощение
    elif data.startswith("pardon_"):
        target_id = int(data.split("_")[1])
        violations = get_violation_count(target_id)
        clear_violations(target_id)
        success = await restore_user_permissions(context, update.effective_chat.id, target_id)

        if success:
            try:
                member = await context.bot.get_chat_member(update.effective_chat.id, target_id)
                user_mention = f"[{member.user.first_name}](tg://user?id={target_id})"
            except:
                user_mention = f"User ID: `{target_id}`"

            admin_name = query.from_user.first_name
            admin_mention = f"[{admin_name}](tg://user?id={query.from_user.id})"

            await query.edit_message_text(
                f"🎉 *ПОЛНОСТЬЮ ПРОЩЁН!*\n\n"
                f"👤 {user_mention}\n"
                f"🛡 Админ бота: {admin_mention}\n"
                f"🧹 Удалено нарушений: *{violations}*\n\n"
                f"✅ История стерта!",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ Ошибка прощения!")

    # Добавить в whitelist
    elif data.startswith("trust_"):
        target_id = int(data.split("_")[1])
        add_to_whitelist(target_id, query.from_user.id)

        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, target_id)
            user_mention = f"[{member.user.first_name}](tg://user?id={target_id})"
        except:
            user_mention = f"User ID: `{target_id}`"

        admin_name = query.from_user.first_name
        admin_mention = f"[{admin_name}](tg://user?id={query.from_user.id})"

        await query.edit_message_text(
            f"🤍 *ДОБАВЛЕН В БЕЛЫЙ СПИСОК!*\n\n"
            f"👤 {user_mention}\n"
            f"🛡 Админ бота: {admin_mention}\n\n"
            f"✅ Теперь может спамить сколько хочет!",
            parse_mode='Markdown'
        )

    # Убрать из whitelist
    elif data.startswith("untrust_"):
        target_id = int(data.split("_")[1])
        remove_from_whitelist(target_id)

        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, target_id)
            user_mention = f"[{member.user.first_name}](tg://user?id={target_id})"
        except:
            user_mention = f"User ID: `{target_id}`"

        admin_name = query.from_user.first_name
        admin_mention = f"[{admin_name}](tg://user?id={query.from_user.id})"

        await query.edit_message_text(
            f"⛔ *УБРАН ИЗ БЕЛОГО СПИСКА!*\n\n"
            f"👤 {user_mention}\n"
            f"🛡 Админ бота: {admin_mention}\n\n"
            f"❌ Снова под контролем!",
            parse_mode='Markdown'
        )

# ═══════════════════════════════════════════════════════════════
# 🚨 ОБРАБОТКА СПАМА
# ═══════════════════════════════════════════════════════════════

async def handle_media_spam(update: Update, context: ContextTypes.DEFAULT_TYPE, media_type='sticker'):
    """Обработчик спама стикерами и GIF"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Обновляем кэш username, если он есть
    if update.effective_user.username:
        update_username_cache(user_id, update.effective_user.username, update.effective_user.first_name)
    message_id = update.message.message_id

    logger.info(f"{media_type.upper()} received from user {user_id} in chat {chat_id}")

    if update.effective_chat.type != 'supergroup':
        logger.warning(f"Chat {chat_id} is not a supergroup. Skipping moderation.")
        return

    # Проверка белого списка
    if is_whitelisted(user_id):
        logger.info(f"User {user_id} is whitelisted, skipping spam check")
        return

    # Админов бота не трогаем вообще
    if is_bot_admin(user_id):
        logger.info(f"User {user_id} is bot admin, skipping spam check")
        return

    # Админов чата тоже не баним
    if await is_admin(update, context, user_id):
        logger.info(f"User {user_id} is chat admin, skipping spam check")
        return

    add_media_spam(user_id, media_type)
    count = get_recent_media_spam(user_id)

    logger.info(f"Media spam count for {user_id}: {count}/{SPAM_LIMIT} ({media_type})")

    # Предупреждение перед баном
    if count == WARNING_THRESHOLD and count < SPAM_LIMIT:
        user_name = update.effective_user.first_name
        current_violations = get_violation_count(user_id)
        next_ban = BAN_DURATION.get(current_violations + 1, DEFAULT_BAN)

        warning_text = WARNING_MESSAGES.get(count, "").format(
            name=user_name,
            count=count,
            ban_time=next_ban
        )

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=warning_text,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to send warning: {e}")

    if count >= SPAM_LIMIT:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info(f"Deleted {media_type} message from {user_id}")
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")

        if is_currently_banned(user_id):
            logger.info(f"User {user_id} already banned, just deleting messages")
            return

        current_violations = get_violation_count(user_id)
        next_violation = current_violations + 1

        ban_minutes = BAN_DURATION.get(next_violation, DEFAULT_BAN)

        violation_count = add_violation(user_id, ban_minutes)

        ban_message = BAN_MESSAGES.get(violation_count, DEFAULT_MESSAGE)

        try:
            until_date = int((datetime.now() + timedelta(minutes=ban_minutes)).timestamp())

            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_polls=True,
                    can_send_other_messages=False,
                    can_add_web_page_previews=True
                ),
                until_date=until_date
            )

            user_name = update.effective_user.first_name
            user_mention = f"[{user_name}](tg://user?id={user_id})"

            final_message = (
                f"{ban_message}\n\n"
                f"👤 Нарушитель: {user_mention}\n"
                f"📊 Нарушение №{violation_count}\n"
                f"⏱ Мьют: *{ban_minutes} минут*\n"
                f"📈 Отправил {count} {media_type} за {TIME_WINDOW_MINUTES} мин"
            )

            # Inline кнопки для админов
            keyboard = [
                [
                    InlineKeyboardButton("🔓 Разбанить", callback_data=f"unban_{user_id}"),
                    InlineKeyboardButton("🎉 Простить", callback_data=f"pardon_{user_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=final_message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

            logger.info(f"✅ Restricted user {user_id} for {ban_minutes} min (violation #{violation_count})")
        except Exception as e:
            logger.error(f"Failed to restrict: {e}")
    else:
        logger.info(f"Media spam count {count} < {SPAM_LIMIT}, no action")

async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик стикеров"""
    await handle_media_spam(update, context, media_type='стикер')

async def handle_animation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик GIF-анимаций"""
    await handle_media_spam(update, context, media_type='гифку')

# ═══════════════════════════════════════════════════════════════
# 🚀 ГЛАВНАЯ ФУНКЦИЯ
# ═══════════════════════════════════════════════════════════════

def main():
    TOKEN = read_token()

    init_db()
    application = Application.builder().token(TOKEN).build()

    # Регистрируем команды, чтобы Telegram подсвечивал их после "/"
    async def set_commands(app: Application):
        """Регистрируем команды для обычных юзеров"""
        # Общие команды (видят все)
        await app.bot.set_my_commands([
            ("start", "Инфа о боте"),
            ("whoami", "Узнать свой ID и username"),
            ("help", "Справка по командам"),
            ("stats", "Твоя статистика"),
            ("top", "Топ спамеров"),
        ])

    application.post_init = set_commands

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("whoami", whoami))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("top", top))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("pardon", pardon))
    application.add_handler(CommandHandler("check", check))
    application.add_handler(CommandHandler("trust", trust))
    application.add_handler(CommandHandler("untrust", untrust))
    application.add_handler(CommandHandler("whitelist", whitelist_command))
    application.add_handler(CommandHandler("reset_all", reset_all))
    application.add_handler(CommandHandler("bot_admins", bot_admins_command))
    application.add_handler(CommandHandler("reload_admins", reload_admins_command))

    # Обработка inline-кнопок
    application.add_handler(CallbackQueryHandler(button_callback))

    # Обработка медиа
    application.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    application.add_handler(MessageHandler(filters.ANIMATION, handle_animation))

    logger.info("🚀 БОТ-БЫДЛО ЗАПУЩЕН! ЕБАШИМ!")
    logger.info(f"⚙️ Настройки: {SPAM_LIMIT} стикеров/гифок за {TIME_WINDOW_MINUTES} мин")
    logger.info(f"📊 Прогрессивные баны: {BAN_DURATION}")
    logger.info(f"👑 Загружено админов бота: {len(BOT_ADMINS)}")
    
    if len(BOT_ADMINS) == 0:
        logger.warning(f"⚠️ НЕТ АДМИНОВ! Добавьте user_id или @username в файл {ADMIN_FILE}")
        logger.warning(f"💡 Если используете @username - админ должен написать боту /start")
    
    application.run_polling()

if __name__ == '__main__':
    main()