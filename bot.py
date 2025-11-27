import logging
import sqlite3
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest

# ═══════════════════════════════════════════════════════════════
# 🔧 НАСТРОЙКИ
# ═══════════════════════════════════════════════════════════════

# Лимиты
SPAM_LIMIT = 3                  # Стикеры/GIF (штук)
TIME_WINDOW_SECONDS = 30        # Время (секунд)

TEXT_SPAM_LIMIT = 3             # Текст (штук)
TEXT_TIME_WINDOW_SECONDS = 20   # Время (секунд)

IMAGE_SPAM_LIMIT = 3            # Картинки (штук)
IMAGE_TIME_WINDOW_SECONDS = 30  # Время (секунд)

VIDEO_SPAM_LIMIT = 3            # Видео (штук)
VIDEO_TIME_WINDOW_SECONDS = 30  # Время (секунд)

# 🔥 ТАБЛИЦА БАНОВ (Минуты)
BAN_DURATION = {
    1: 10,    # 1-й раз: 10 мин
    2: 60,    # 2-й раз: 1 час
    3: 300,   # 3-й раз: 5 часов
    4: 1440,   # 4-й раз: 24 часа
}
DEFAULT_BAN = 2880 # 5+ раз: 48 часов

# Файлы
DB_NAME = 'stickers.db'
DOTA_FILE = 'godota.txt'   # 🎮 Файл с никами для доты
ADMIN_FILE = 'admin.txt'   # 👮 Файл с никами админов для разбана

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# 💾 БАЗА ДАННЫХ И УТИЛИТЫ
# ═══════════════════════════════════════════════════════════════

def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS media_spam (user_id INTEGER, timestamp TEXT, media_type TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS text_spam (user_id INTEGER, timestamp TEXT, message_text TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS photo_spam (user_id INTEGER, timestamp TEXT, file_unique_id TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS video_spam (user_id INTEGER, timestamp TEXT, file_unique_id TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS violations (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0, last_violation TEXT, banned_until TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS whitelist (user_id INTEGER PRIMARY KEY)''')
        
        c.execute("PRAGMA table_info(violations)")
        if 'banned_until' not in [x[1] for x in c.fetchall()]:
            c.execute('ALTER TABLE violations ADD COLUMN banned_until TEXT')
            
        conn.commit()
        conn.close()
    except Exception as e: logger.error(f"DB Error: {e}")

def get_dota_users():
    """Читает ники из файла godota.txt"""
    try:
        with open(DOTA_FILE, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        return []

def get_admin_users():
    """Читает ники из файла admin.txt (убирает @ и переводит в нижний регистр)"""
    try:
        with open(ADMIN_FILE, 'r', encoding='utf-8') as f:
            admins = []
            for line in f.readlines():
                clean_nick = line.strip().replace('@', '').lower()
                if clean_nick:
                    admins.append(clean_nick)
            return admins
    except FileNotFoundError:
        return []

# --- ЗАПИСЬ И ПРОВЕРКА СПАМА ---

def add_spam_record(table, user_id, content):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute(f"INSERT INTO {table} VALUES (?, ?, ?)", (user_id, datetime.now().isoformat(), content))
        conn.commit(); conn.close()
    except: pass

def check_spam_count(table, user_id, window_seconds, content_filter=None):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        cutoff = (datetime.now() - timedelta(seconds=window_seconds)).isoformat()
        c.execute(f"DELETE FROM {table} WHERE user_id=? AND timestamp < ?", (user_id, cutoff))
        
        if content_filter:
            if table == 'text_spam': col = 'message_text'
            elif table in ['photo_spam', 'video_spam']: col = 'file_unique_id'
            else: col = 'media_type'
            c.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id=? AND {col}=?", (user_id, content_filter))
        else:
            c.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id=?", (user_id,))
            
        count = c.fetchone()[0]
        conn.commit(); conn.close()
        return count
    except: return 0

def get_violation_info(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT count, banned_until FROM violations WHERE user_id=?", (user_id,))
        res = c.fetchone()
        conn.close()
        return (res[0], res[1]) if res else (0, None)
    except: return (0, None)

def record_violation(user_id, ban_minutes):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now = datetime.now().isoformat()
        until = (datetime.now() + timedelta(minutes=ban_minutes)).isoformat()
        
        c.execute("SELECT count FROM violations WHERE user_id=?", (user_id,))
        res = c.fetchone()
        new_count = (res[0] + 1) if res else 1
        
        c.execute("INSERT OR REPLACE INTO violations (user_id, count, last_violation, banned_until) VALUES (?, ?, ?, ?)", 
                  (user_id, new_count, now, until))
        conn.commit(); conn.close()
        return new_count
    except: return 1

def is_whitelisted(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id FROM whitelist WHERE user_id=?", (user_id,))
        res = c.fetchone()
        conn.close()
        return res is not None
    except: return False

# ═══════════════════════════════════════════════════════════════
# 🚨 ЛОГИКА БАНА (С РАЗРЕШЕНИЕМ ТЕКСТА)
# ═══════════════════════════════════════════════════════════════

async def execute_ban_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, count, limit, reason_text):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name

    if count >= limit:
        try: await context.bot.delete_message(chat_id, update.message.message_id)
        except: pass

        viol_count, banned_until = get_violation_info(user_id)
        if banned_until and banned_until > datetime.now().isoformat():
            pass

        next_violation_level = viol_count + 1
        ban_minutes = BAN_DURATION.get(next_violation_level, DEFAULT_BAN)
        actual_level = record_violation(user_id, ban_minutes)
        until_date = int((datetime.now() + timedelta(minutes=ban_minutes)).timestamp())

        # Оставляем текст, блокируем остальное
        permissions = ChatPermissions(
            can_send_messages=True,         # ✅ ТЕКСТ ВСЕГДА РАЗРЕШЕН
            can_send_photos=False,
            can_send_videos=False,
            can_send_audios=False,
            can_send_documents=False,
            can_send_other_messages=False,
            can_send_voice_notes=False,
            can_send_video_notes=False,
            can_send_polls=False
        )
        ban_description = "📝 ТОЛЬКО ТЕКСТ (Медиа запрещены)"

        ban_successful = False
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=permissions,
                until_date=until_date
            )
            ban_successful = True
        except BadRequest:
            ban_successful = False 

        kb = [[InlineKeyboardButton("🔓 Разбанить", callback_data=f"unban_{user_id}")]]
        
        if ban_successful:
            await context.bot.send_message(
                chat_id,
                f"⛔ *ОГРАНИЧЕНИЕ!*\n\n"
                f"👤 Нарушитель: [{user_name}](tg://user?id={user_id})\n"
                f"🔢 Нарушение №: *{actual_level}*\n"
                f"⏱ Срок: *{ban_minutes} минут*\n"
                f"🔒 Режим: *{ban_description}*\n"
                f"📉 Причина: {count} {reason_text}",
                parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb)
            )
        else:
            await context.bot.send_message(
                chat_id,
                f"⚖️ *ФОРМАЛЬНОЕ НАРУШЕНИЕ (АДМИН)*\n\n"
                f"👤 {user_name} превысил лимит: {count} {reason_text}.\n"
                f"⚠️ Нарушение записано, но я не могу ограничить права админа.",
                parse_mode='Markdown'
            )

# ═══════════════════════════════════════════════════════════════
# 👋 ОБРАБОТЧИКИ
# ═══════════════════════════════════════════════════════════════

async def handle_media_spam(update: Update, context: ContextTypes.DEFAULT_TYPE, media_type='sticker'):
    user_id = update.effective_user.id
    if update.effective_chat.type != 'supergroup': return
    if is_whitelisted(user_id): return

    add_spam_record('media_spam', user_id, media_type)
    count = check_spam_count('media_spam', user_id, TIME_WINDOW_SECONDS)
    await execute_ban_logic(update, context, count, SPAM_LIMIT, media_type)

async def handle_sticker(u, c): await handle_media_spam(u, c, 'стикеров')
async def handle_animation(u, c): await handle_media_spam(u, c, 'гифок')

async def handle_text_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.effective_chat.type != 'supergroup': return
    
    text = update.message.text
    
    # 🎮 1. ПРОВЕРКА НА "ГО ДОТА"
    text_lower = text.lower()
    dota_triggers = ["го дота", "годота", "go dota", "dodota"]
    
    if any(trigger in text_lower for trigger in dota_triggers):
        dota_users = get_dota_users()
        if dota_users:
            mentions = " ".join(dota_users)
            await update.message.reply_text(f"{mentions} го дота, дяяяяяй")
    
    # 🛑 2. ПРОВЕРКА НА СПАМ (Только если не белый список)
    if not is_whitelisted(user_id):
        add_spam_record('text_spam', user_id, text)
        count = check_spam_count('text_spam', user_id, TEXT_TIME_WINDOW_SECONDS, content_filter=text)
        await execute_ban_logic(update, context, count, TEXT_SPAM_LIMIT, 'одинаковых сообщений')

async def handle_photo_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.effective_chat.type != 'supergroup': return
    if is_whitelisted(user_id): return

    unique_id = update.message.photo[-1].file_unique_id
    add_spam_record('photo_spam', user_id, unique_id)
    count = check_spam_count('photo_spam', user_id, IMAGE_TIME_WINDOW_SECONDS, content_filter=unique_id)
    await execute_ban_logic(update, context, count, IMAGE_SPAM_LIMIT, 'одинаковых картинок')

async def handle_video_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.effective_chat.type != 'supergroup': return
    if is_whitelisted(user_id): return

    unique_id = update.message.video.file_unique_id
    add_spam_record('video_spam', user_id, unique_id)
    count = check_spam_count('video_spam', user_id, VIDEO_TIME_WINDOW_SECONDS, content_filter=unique_id)
    await execute_ban_logic(update, context, count, VIDEO_SPAM_LIMIT, 'одинаковых видео')

# ═══════════════════════════════════════════════════════════════
# КОМАНДЫ
# ═══════════════════════════════════════════════════════════════

async def start(update, context):
    await update.message.reply_text("Бот активен.\n- Спам оставляет текст, но запрещает медиа.\n- Разбан: Владелец или ники из admin.txt")

async def trust_cmd(update, context):
    if update.message.reply_to_message:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO whitelist VALUES (?)", (update.message.reply_to_message.from_user.id,))
            conn.commit(); conn.close()
            await update.message.reply_text("✅ Иммунитет выдан.")
        except: pass

async def unban_btn(update, context):
    q = update.callback_query
    chat_id = update.effective_chat.id
    user = q.from_user
    
    # 1. Получаем ник того, кто нажал (без @, строчными буквами)
    clicker_username = user.username.lower() if user.username else ""

    # 2. Проверяем, является ли он ВЛАДЕЛЬЦЕМ
    is_creator = False
    try:
        member = await context.bot.get_chat_member(chat_id, user.id)
        if member.status == 'creator':
            is_creator = True
    except Exception as e:
        logger.error(f"Ошибка проверки прав: {e}")

    # 3. Проверяем, есть ли он в admin.txt
    allowed_admins = get_admin_users()
    is_txt_admin = clicker_username in allowed_admins

    # 🚫 ЕСЛИ НЕ ВЛАДЕЛЕЦ И НЕ В СПИСКЕ — ОТКАЗАТЬ
    if not is_creator and not is_txt_admin:
        await q.answer("❌ Вы не Владелец и вас нет в admin.txt!", show_alert=True)
        return

    # --- ПРОЦЕДУРА РАЗБАНА ---
    target_id = int(q.data.split("_")[1])
    
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE violations SET banned_until=NULL WHERE user_id=?", (target_id,))
        conn.commit(); conn.close()
    except: pass
    
    try:
        await context.bot.restrict_chat_member(chat_id, target_id, 
            ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_other_messages=True,
                can_send_voice_notes=True,
                can_send_video_notes=True,
                can_send_documents=True,
                can_send_polls=True
            ))
        
        role_text = "Владельцем" if is_creator else "Админом"
        await q.edit_message_text(f"✅ Разбанен {role_text} ({user.first_name})")
    except Exception as e:
        await q.edit_message_text(f"⚠️ Ошибка снятия ограничений: {e}")

def main():
    load_dotenv()
    TOKEN = os.getenv('BOT_TOKEN')
    
    if not TOKEN:
    	exit("❌ ОШИБКА: Не найден BOT_TOKEN в файле .env (или файл отсутствует)")
    
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("trust", trust_cmd))
    app.add_handler(CallbackQueryHandler(unban_btn))

    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    app.add_handler(MessageHandler(filters.ANIMATION, handle_animation))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_spam))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video_spam))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_spam))

    logger.info("🚀 БОТ ЗАПУЩЕН")
    app.run_polling()

if __name__ == '__main__':
    main()